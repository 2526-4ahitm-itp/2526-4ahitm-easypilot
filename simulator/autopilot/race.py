"""Autonomous race in Liftoff on an official track.

  python -m autopilot.race StrawBaleRace01 [aggressiveness] [laps] [--vision] [--perturb CP77:0,1.5,0]

--vision     camera gate detection corrects the gate map in flight, overlay window right of Liftoff
--perturb    shift a map gate on purpose (test: the camera has to find the real one)

Gate poses come from the race/track XML (see track.py); the vision pipeline checks
and corrects them while flying. The racing line goes from the spawn through all
checkpoints, `laps` times, and ends behind the finish gate.
"""
import json
import math
import sys
import threading
import time

from . import window
from .control import FlightController, Gains, ThrustModel
from .geometry import body_axes, sub, unit
from .liftoff import RUNS, Session, state_row
from .planner import Limits, RacingLine
from .racer import Racer
from .sysid import load_model
from .track import load_race_with_track, race_gates

# usable acceleration at racing speed (the static 12.7 g drop a lot with airspeed)
USABLE_ACCEL = 60.0
DRAG = 0.033          # 1/m, from the disturbance estimate at 27 m/s (~25 m/s^2)


def course(gates, laps):
    """Gate order for a whole race. Liftoff lists start and finish passages separately; when both
    are the same physical gate it is passed once per lap boundary, not twice."""
    same = (gates[0].name == gates[-1].name) if gates[0].name else math.dist(gates[0].center, gates[-1].center) < 0.5
    lap = gates[:-1] if same else gates
    seq = [g for _ in range(laps) for g in lap]
    return seq + [gates[-1]] if same else seq


def launch(first_gate, spawn):
    """Start point and direction of the racing line.

    The line starts at the height of the first gate and points straight at it: a climb from the
    ground inside the line would be an S-curve over a few metres that the speed profile has to
    brake for. The position controller lifts the drone off the ground instead.
    """
    start = (spawn[0], max(spawn[1] + 0.3, first_gate.center[1]), spawn[2])
    d = sub(first_gate.center, start)
    return start, unit((d[0], 0.0, d[2]))


def build_line(gates, start, start_dir, laps, aggressiveness, max_speed=40.0):
    limits = Limits.from_thrust(USABLE_ACCEL, max_speed=max_speed, drag=DRAG)
    return RacingLine(course(gates, laps), start=start, start_dir=start_dir, laps=1, limits=limits,
                      aggressiveness=aggressiveness, finish_extra=4.0, launch_speed=9.0)


class VisionAssist(threading.Thread):
    """Detector + gate-map correction + replanning + overlay, off the 100 Hz control loop."""

    TITLE = "EasyPilot - Torerkennung"

    def __init__(self, sess, gates, laps, k, start, start_dir, racer, overlay=True):
        super().__init__(daemon=True)
        from .capture import FrameStream
        self.sess, self.laps, self.k, self.line_start, self.start_dir = sess, laps, k, start, start_dir
        self.racer, self.overlay = racer, overlay
        self.frames = FrameStream(640, fps=60)
        self.gates = gates
        self.gate_map = None
        self.running = True
        self.window_ready = threading.Event()
        self.replans = 0
        self.fps = 0.0
        self.error = ""

    def run(self):
        try:
            self._run()
        except Exception as exc:          # never take the control loop down
            self.error = repr(exc)
            self.window_ready.set()

    def _run(self):
        import cv2
        from .camera import Camera
        from .detector import GateDetector, GateMap, draw_overlay
        from .sysid import load_camera
        det = GateDetector()
        self.frames.start()
        while self.frames.latest()[1] is None:
            time.sleep(0.01)
        h, w = self.frames.latest()[1].shape[:2]
        c = load_camera()
        cam = Camera(w, h, c.hfov_deg, c.tilt_deg)
        # start/finish gate: the drone launches through it before the camera sees it properly
        self.gate_map = GateMap(self.gates, fixed={0, len(self.gates) - 1})
        if self.overlay:
            cv2.namedWindow(self.TITLE, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.TITLE, 960, 540)
            cv2.moveWindow(self.TITLE, 1945, 0)
            cv2.waitKey(1)
        self.window_ready.set()
        last_stamp, planned_version, last_plan, n, t0 = 0.0, 0, 0.0, 0, time.perf_counter()
        last_saved = 0.0
        self.overlay_dir = RUNS / f"overlay-{time.strftime('%Y%m%d-%H%M%S')}"
        self.overlay_dir.mkdir(parents=True, exist_ok=True)
        while self.running:
            stamp, img = self.frames.latest()
            if stamp == last_stamp:
                time.sleep(0.002)
                continue
            last_stamp = stamp
            s = self.sess.tel.at(stamp - 0.012)
            dets = det.detect(img)
            if s is not None and max(abs(v) for v in s.pos) > 1e-3:
                self.gate_map.update(cam, s.quat, s.pos, dets)
            now = time.perf_counter()
            if self.gate_map.version != planned_version and now - last_plan > 0.15:
                planned_version, last_plan = self.gate_map.version, now
                line = build_line(self.gate_map.all_corrected(), self.line_start, self.start_dir, self.laps, self.k)
                self.racer.swap_line(line)
                self.replans += 1
            n += 1
            if now - t0 > 1.0:
                self.fps, n, t0 = n / (now - t0), 0, now
            if self.overlay:
                info = f"Tore erkannt: {len(dets)}  |  {self.fps:4.1f} fps  |  Neuplanungen: {self.replans}"
                shown = draw_overlay(img, dets, s, cam, self.gate_map, info)
                cv2.imshow(self.TITLE, shown)
                cv2.waitKey(1)
                if dets and now - last_saved > 1.0:       # a few frames for the report
                    last_saved = now
                    cv2.imwrite(str(self.overlay_dir / f"{len(list(self.overlay_dir.glob('*.jpg'))):03d}.jpg"), shown)
        self.frames.close()
        if self.overlay:
            cv2.destroyAllWindows()

    def close(self):
        self.running = False


def main(argv):
    vision = "--vision" in argv
    perturb = {}
    if "--perturb" in argv:
        spec = argv[argv.index("--perturb") + 1]
        cp, _, off = spec.partition(":")
        perturb[cp] = tuple(float(v) for v in off.split(","))
    argv = [a for a in argv if not a.startswith("--") and ":" not in a]
    name = argv[0] if argv else "StrawBaleRace01"
    k = float(argv[1]) if len(argv) > 1 else 0.4
    laps = int(argv[2]) if len(argv) > 2 else 1
    race, track = load_race_with_track(name)
    gates = race_gates(race, track)
    true_centers = {g.name: g.center for g in gates}
    for g in gates:
        if g.name.split()[0] in perturb:
            g.center = tuple(a + b for a, b in zip(g.center, perturb[g.name.split()[0]]))
            print(f"perturbed {g.name} by {perturb[g.name.split()[0]]} m")
    rates, thrust = load_model()
    gains = Gains(tilt=16, yaw=4.0, pos=6.0, vel=5.0, drag=DRAG)
    sess = Session(f"race-{name}-{k}")
    sess.reset_drone(settle=4.5)   # race mode: wait for the 3-2-1 countdown
    s0 = sess.tel.wait()
    _, _, fwd = body_axes(s0.quat)
    start, start_dir = launch(gates[0], s0.pos)
    line = build_line(gates, start, start_dir, laps, k)
    racer = Racer(line, FlightController(rates, thrust, gains), lookahead=0.12)
    assist = None
    if vision:
        assist = VisionAssist(sess, gates, laps, k, start, start_dir, racer)
        assist.start()
        assist.window_ready.wait(30)
        window.focus_liftoff(hard=False)
    print(f"{race['name']}: {len(line.gate_sequence)} gate passages ({laps} laps), line {line.length:.0f} m, "
          f"planned {line.lap_time_estimate:.2f} s, v_max {max(line.speed):.1f} m/s")
    t0 = time.perf_counter()

    def step(s, dt):
        c = racer.step(s)
        line = racer.line
        d = racer.ctl.debug
        e = sub(s.pos, line.points[racer.idx])
        dist = racer.ctl.disturbance
        sess.log(idx=racer.idx, gate=racer.progress.gate_index, v_ref=line.speed[racer.idx],
                 xt=math.dist(s.pos, line.points[racer.idx]), e_vert=e[1], e_horiz=math.hypot(e[0], e[2]),
                 d_x=dist[0], d_y=dist[1], d_z=dist[2], tilt_err=d.get("tilt_err_deg", 0),
                 cmd_t=c.throttle, cmd_y=c.yaw, cmd_p=c.pitch, cmd_r=c.roll, **state_row(s))
        if racer.done:
            return None
        return c.as_tuple()

    ok = sess.loop(step, max_time=line.lap_time_estimate * 2.5 + 10)
    el = time.perf_counter() - t0
    if assist:
        assist.close()
    log = sess.close()
    p = racer.progress
    result = {"race": race["name"], "aggressiveness": k, "laps": laps, "ok": ok and not racer.crashed,
              "reason": "crash (drone stopped)" if racer.crashed else sess.reason,
              "gates_passed": len(p.gate_times), "gates_total": len(line.gate_sequence), "missed": p.missed,
              "time_s": round(p.gate_times[-1], 3) if p.gate_times else None,
              "planned_s": round(line.lap_time_estimate, 2), "max_cross_track_m": round(racer.max_cross_track, 2),
              "log": str(log)}
    if assist:
        gm = assist.gate_map
        result["vision"] = {"error": assist.error, "replans": assist.replans, "fps": round(assist.fps, 1),
                            "gates_corrected": {g.name.split()[0]: [round(v, 2) for v in gm.offsets[i]]
                                                for i, g in enumerate(gm.gates) if i in gm.offsets} if gm else {}}
        if gm and perturb:
            res = {}
            for i, g in enumerate(gm.gates):
                if g.name.split()[0] in perturb:
                    res[g.name] = {"map_error_before_m": round(math.dist(g.center, true_centers[g.name]), 2),
                                   "after_camera_m": round(math.dist(gm.corrected(i).center, true_centers[g.name]), 2),
                                   "detections": gm.hits.get(i, 0)}
            result["vision"]["perturbed"] = res
    print(json.dumps(result, indent=1))
    RUNS.mkdir(exist_ok=True)
    with (RUNS / "race_results.jsonl").open("a") as f:
        f.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
