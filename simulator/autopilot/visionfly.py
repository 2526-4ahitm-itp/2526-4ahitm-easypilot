"""Flying by camera alone: no gate positions from the track file.

Two modes (Studio > Einstellungen > Autopilot-Modus, or the command line):

  erkunden    first a slow lap: the drone flies from gate to gate by camera and maps where
              every gate stands (position, direction, size). Then it is reset, plans the racing
              line (planner.py) through its own map and races like the normal autopilot.
  nur_kamera  no map at all: always fly to the next gate the camera sees, slowly. Every gate
              is only known from the image.

  python -m autopilot.visionfly StrawBaleRace01 nur_kamera [speed m/s]
  python -m autopilot.visionfly StrawBaleRace01 erkunden [aggressiveness]
  EASYPILOT_TEST_DETECTOR=1 ...   development only: fake detections projected from the track file,
                                  to test the flight logic without the YOLO model (see TestDetector)

The track file is used only afterwards, to score: which real gates were passed (verify.py logic)
and how far the mapped gates are from the real ones.

How a gate is located: the detector gives the four corners of the opening. PnP with a nominal
size gives the direction of the gate and its orientation; the distance from PnP scales with the
assumed size, so while the drone moves, the rays to the gate centre from different positions are
triangulated (needs no size). The triangulated distance then also gives the real width.

Known limits (said plainly):
  - a gate is only found when it is in the picture; behind a sharp turn the drone has to stop
    and turn around to search (slow, and it can pick a wrong gate: the nearest one in front)
  - from the image alone the drone cannot tell from which side a gate must be flown through;
    it flies through from the side it approaches
  - closed tracks: the start gate counts as finish only when no unpassed gate is in sight
"""
import json
import math
import os
import sys
import threading
import time
from dataclasses import dataclass, field

import numpy as np

from .geometry import add, cross, dot, mul, norm, sub, unit

NOMINAL_W, NOMINAL_H = 2.5, 2.0      # m, assumed opening for PnP before triangulation corrects the scale
MIN_HITS = 3                         # detections before a gate counts as found
SEARCH_RATE = math.radians(35)       # rad/s yaw while searching
SEARCH_LEGS = 3                      # search: fly on 15 m, turn once around, up to 3 times, then give up
SEARCH_ADVANCE = 15.0                # m straight on before turning (the next gate is often just too far)
SEARCH_SPEED = 3.0
EXIT_STRAIGHT = 3.0                  # m straight on behind every gate before turning to the next


# ---------------------------------------------------------------------------- perception
@dataclass
class Observation:
    cam_pos: tuple
    ray: tuple            # unit world direction to the opening centre
    pnp_center: tuple     # with the nominal size
    normal: tuple         # gate normal from PnP (sign: away from the camera)
    pnp_dist: float
    width_px: float


@dataclass
class TrackedGate:
    id: int
    obs: list = field(default_factory=list)
    center: tuple = (0.0, 0.0, 0.0)
    normal: tuple = (0.0, 0.0, 1.0)
    width: float = NOMINAL_W
    height: float = NOMINAL_H
    passed: bool = False
    missed: bool = False
    triangulated: bool = False
    last_seen: float = 0.0

    @property
    def hits(self):
        return len(self.obs)

    def refresh(self):
        obs = self.obs[-60:]
        n = unit(tuple(sum(o.normal[k] for o in obs) for k in range(3)), (0.0, 0.0, 1.0))
        n = unit((n[0], 0.0, n[2]), (0.0, 0.0, 1.0))      # gates stand upright
        center = tuple(float(np.median([o.pnp_center[k] for o in obs])) for k in range(3))
        tri = triangulate(obs)
        self.triangulated = tri is not None
        if tri is not None:
            # scale of the nominal size: true distance / PnP distance (median over the observations)
            scale = float(np.median([math.dist(o.cam_pos, tri) / o.pnp_dist for o in obs if o.pnp_dist > 0.5]))
            if 0.4 < scale < 2.5:
                center, self.width, self.height = tri, NOMINAL_W * scale, NOMINAL_H * scale
        self.center, self.normal = center, n


def triangulate(obs, min_baseline=1.5, min_angle_deg=2.0):
    """Least-squares point closest to all centre rays; None if the rays are too parallel."""
    if len(obs) < 6:
        return None
    ps = [o.cam_pos for o in obs]
    if max(math.dist(ps[0], p) for p in ps) < min_baseline:
        return None
    rays = [o.ray for o in obs]
    spread = max(math.degrees(math.acos(max(-1.0, min(1.0, dot(rays[0], r))))) for r in rays)
    if spread < min_angle_deg:
        return None
    A, b = np.zeros((3, 3)), np.zeros(3)
    for p, d in zip(ps, rays):
        d = np.array(d)
        m = np.eye(3) - np.outer(d, d)
        A += m
        b += m @ np.array(p)
    try:
        x = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return None
    # must lie in front of the observations
    if any(dot(sub(tuple(x), p), d) < 0.5 for p, d in zip(ps[-5:], rays[-5:])):
        return None
    return tuple(float(v) for v in x)


def observe(cam, quat, pos, det):
    """Observation from one detection (4 corners needed), or None."""
    import cv2
    good = det.kp_conf > 0.5
    if good.sum() < 4:
        return None
    w, h = NOMINAL_W / 2, NOMINAL_H / 2
    obj = np.array([[-w, -h, 0], [-w, h, 0], [w, h, 0], [w, -h, 0]], dtype=np.float64)
    K = np.array([[cam.f, 0, cam.width / 2], [0, cam.f, cam.height / 2], [0, 0, 1]], dtype=np.float64)
    ok, rvec, tvec = cv2.solvePnP(obj, det.kps.astype(np.float64), K, None, flags=cv2.SOLVEPNP_IPPE)
    if not ok:
        return None
    from .geometry import qrot
    t = tvec.ravel()
    p_cam = (t[0], -t[1], t[2])                    # OpenCV -> Unity camera axes
    if not 0.8 < p_cam[2] < 60:
        return None
    R, _ = cv2.Rodrigues(rvec)
    n_cv = R[:, 2]                                 # gate plane normal in OpenCV camera axes
    n_cam = (n_cv[0], -n_cv[1], n_cv[2])
    q = cam.cam_quat(quat)
    d = qrot(q, p_cam)
    center = tuple(pos[k] + d[k] for k in range(3))
    n = qrot(q, n_cam)
    if dot(n, d) < 0:
        n = mul(n, -1.0)
    u, v = (float(x) for x in det.kps.mean(axis=0))
    ray = cam.ray(quat, u, v)
    width_px = float(np.linalg.norm(det.kps[3] - det.kps[0]))
    return Observation(tuple(pos), ray, center, unit(n), norm(d), width_px)


class GateTracker:
    """All gates seen so far, each with its observations; matched across frames in 3-D."""

    def __init__(self, match_dist=3.0):
        self.gates = []
        self.match_dist = match_dist
        self.lock = threading.Lock()
        self.frames = 0
        self.detections = 0

    def update(self, cam, quat, pos, dets, now):
        self.frames += 1
        with self.lock:
            for det in dets:
                o = observe(cam, quat, pos, det)
                if o is None:
                    continue
                self.detections += 1
                # match: the gate whose estimate lies closest to this centre ray at a plausible depth
                best, best_d = None, None
                for g in self.gates:
                    rel = sub(g.center, o.cam_pos)
                    along = dot(rel, o.ray)
                    if along <= 0.3:
                        continue
                    off = norm(sub(rel, mul(o.ray, along)))
                    depth_ok = 0.4 < along / max(o.pnp_dist, 0.1) < 2.5
                    tol = max(self.match_dist * 0.5, 0.12 * along)
                    if depth_ok and off < tol and (best_d is None or off < best_d):
                        best, best_d = g, off
                if best is None:
                    # same gate seen anew (corners cut by the image border change the PnP depth):
                    # close in 3-D to a known gate -> that gate
                    near = [g for g in self.gates if math.dist(g.center, o.pnp_center) < 1.5]
                    best = min(near, key=lambda g: math.dist(g.center, o.pnp_center)) if near else None
                if best is None:
                    best = TrackedGate(len(self.gates), center=o.pnp_center, normal=o.normal)
                    self.gates.append(best)
                best.obs.append(o)
                best.last_seen = now
                best.refresh()
                # two tracks of one gate (the first, far PnP estimates were off): merge once they meet
                for other in self.gates:
                    if other is not best and not other.passed and other.obs and \
                            math.dist(other.center, best.center) < 1.5:
                        best.obs = best.obs + other.obs
                        other.obs = []
                        best.refresh()

    def found(self):
        with self.lock:
            return [g for g in self.gates if g.hits >= MIN_HITS]


class Perception(threading.Thread):
    """Frames -> detector -> tracker, beside the control loop. `detect(img, state)` is the detector."""

    def __init__(self, tel, detect, width=640, use_frames=True):
        super().__init__(daemon=True)
        from .sysid import load_camera
        self.tel, self.detect = tel, detect
        self.cam = load_camera(width)
        self.tracker = GateTracker()
        self.running = True
        self.error = ""
        self.fps = 0.0
        self.last = (None, [], None)
        self.frames = None
        if use_frames:
            from .capture import FrameStream
            self.frames = FrameStream(width, fps=30)

    def run(self):
        try:
            self._run()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.error = repr(exc)

    def _run(self):
        n, t0, last_stamp = 0, time.perf_counter(), 0.0
        if self.frames:
            self.frames.start()
        while self.running:
            if self.frames:
                stamp, img = self.frames.latest()
                if img is None or stamp == last_stamp:
                    time.sleep(0.003)
                    continue
                last_stamp = stamp
                s = self.tel.at(stamp - 0.012)
            else:
                img, s = None, self.tel.latest(0.2)
                time.sleep(1 / 30)
            if s is None or max(abs(v) for v in s.pos) < 1e-3:
                continue
            dets = self.detect(img, s)
            self.tracker.update(self.cam, s.quat, s.pos, dets, time.perf_counter())
            self.last = (img, dets, s)
            n += 1
            if time.perf_counter() - t0 > 1.0:
                self.fps, n, t0 = n / (time.perf_counter() - t0), 0, time.perf_counter()
        if self.frames:
            self.frames.close()

    def close(self):
        self.running = False


def yolo_detect():
    from .detector import GateDetector
    det = GateDetector()
    return lambda img, s: det.detect(img)


class TestDetector:
    """DEVELOPMENT ONLY - not a vision test. Projects the track file's gate corners into the camera
    (in field of view, 3-40 m, front side, pixel noise) so that the flight logic can be tried without
    the YOLO model. Ignores occlusion and lighting, so it is far better than a real detector."""

    def __init__(self, gates, cam, noise_px=2.0):
        from .detector import opening_corners
        self.gates, self.cam, self.noise = gates, cam, noise_px
        self.corners = [opening_corners(g) for g in gates]
        self.rng = np.random.default_rng(1)

    def __call__(self, img, s):
        from .detector import Detection
        out = []
        for g, cs in zip(self.gates, self.corners):
            d = math.dist(s.pos, g.center)
            if not 3.0 < d < 40.0:
                continue
            uv = [self.cam.project(s.quat, s.pos, c) for c in cs]
            if any(p is None or not (0 <= p[0] < self.cam.width and 0 <= p[1] < self.cam.height) for p in uv):
                continue
            k = np.array(uv) + self.rng.normal(0, self.noise, (4, 2))
            box = (k[:, 0].min(), k[:, 1].min(), k[:, 0].max(), k[:, 1].max())
            out.append(Detection(tuple(float(v) for v in box), 0.9, k, np.ones(4)))
        return out


# ---------------------------------------------------------------------------- flight
class VisionPilot:
    """Fly through the gates the camera finds, one after the other.

    `explore`: same flight, the result is also the map (gates in passage order)."""

    def __init__(self, ctl, perception, speed=4.0, height=2.0):
        self.ctl, self.per = ctl, perception
        self.speed = speed
        self.target = None
        self.passed = []                    # TrackedGates in passage order
        self.prev_pos = None
        self.search_since = None
        self.search_yaw = None
        self.hold = None
        self.height = height
        self.done = False
        self.reason = ""
        self.start_t = None
        self.events = []
        self.exit_dir = None
        self.search = None
        self.stuck = 0.0
        self.exit = None

    def _pick(self, s):
        found = self.per.tracker.found()
        fwd = self._heading(s)
        best, best_cost = None, None
        for g in found:
            if g.passed or g.missed:
                continue
            rel = sub(g.center, s.pos)
            d = norm(rel)
            if d < 1.0:
                continue
            ahead = dot(unit((rel[0], 0.0, rel[2]), fwd), fwd)
            if ahead < -0.2:                              # behind us: not the next gate
                continue
            cost = d * (1.6 - ahead)                      # nearest, preferably straight ahead
            if best_cost is None or cost < best_cost:
                best, best_cost = g, cost
        if best is None and len(self.passed) >= 3:
            # closed track: back at the start gate and nothing else left in sight -> finish there
            first = self.passed[0]
            if dot(sub(first.center, s.pos), fwd) > 0 and math.dist(first.center, s.pos) < 40:
                first.passed = False
                first.finish = True
                best = first
        return best

    @staticmethod
    def _heading(s):
        from .geometry import qrot
        f = qrot(s.quat, (0.0, 0.0, 1.0))
        return unit((f[0], 0.0, f[2]), (0.0, 0.0, 1.0))

    def step(self, s, dt):
        if self.start_t is None:
            self.start_t = s.t
            self.hold = (s.pos[0], max(s.pos[1], 1.5), s.pos[2])
        if self.exit is not None:
            ex = self.exit
            if dot(sub(s.pos, ex["T"]), ex["n"]) < ex["until"]:
                d = ex["n"]
                p_ref = add(s.pos, mul(d, 1.5))
                return self.ctl.track(s, (p_ref[0], ex["T"][1], p_ref[2]), mul(d, max(2.0, min(self.speed, s.speed))),
                                      (0.0, 0.0, 0.0), unit((d[0], 0.0, d[2]), d))
            self.exit = None
        if self.target is not None and self.target.hits == 0:      # merged into another track
            self.target = None
        if self.target is None or self.target.passed or self.target.missed:
            self.target = self._pick(s)
        if self.target is None:
            return self._search(s, dt)
        self.search_since, self.search = None, None
        g = self.target
        with self.per.tracker.lock:
            T, n, w, h = g.center, g.normal, g.width, g.height
        if dot(n, sub(T, s.pos)) < 0 and not getattr(g, "committed", False):
            n = mul(n, -1.0)                               # fly through from the side we come from
        if math.dist(s.pos, T) < 6.0:
            g.committed = True                             # no flipping close to the gate
            g.locked_normal = getattr(g, "locked_normal", None) or n
            n = g.locked_normal
        along = dot(sub(s.pos, T), n)
        lat = sub(sub(s.pos, T), mul(n, along))
        # passage check
        if self.prev_pos is not None:
            a0 = dot(sub(self.prev_pos, T), n)
            if a0 < 0 <= along:
                side = unit(cross((0.0, 1.0, 0.0), n), (1.0, 0.0, 0.0))
                inside = abs(dot(lat, side)) <= w / 2 and abs(lat[1]) <= h / 2
                g.passed, g.missed = inside, not inside
                # where it really went through, and whether the gate was seen up close just before:
                # tracks of far, drifting estimates ("phantom gates") never were (explore map, 19.11.)
                g.passage_point, g.passage_dir = s.pos, unit(s.vel, n)
                last = g.obs[-1] if g.obs else None
                # the camera loses a gate 7-16 m before it (bottom corners leave the up-tilted image)
                g.confirmed = last is not None and g.hits >= 15 and g.triangulated and last.pnp_dist < 15.0 and \
                    time.perf_counter() - g.last_seen < 4.0
                last = g.obs[-1] if g.obs else None
                self.events.append((round(s.t - self.start_t, 2), g.id, ("durch" if inside else "daneben") +
                                    (f" zuletzt {last.pnp_dist:.1f} m vor {time.perf_counter() - g.last_seen:.1f} s, "
                                     f"{g.hits} Bilder" if last else " ohne Bild")))
                if inside or not getattr(g, "finish", False):
                    if g not in self.passed:
                        self.passed.append(g)
                # a second track of the same physical gate (19.11.: passed again 1.3 s later)
                for o in self.per.tracker.found():
                    if o is not g and not o.passed and math.dist(o.center, T) < 2.5:
                        o.passed = True
                self.exit_dir = unit((n[0], 0.0, n[2]), self._heading(s))
                # first straight on out of the gate: turning inside it hit the frame (CP10, 19.11.)
                self.exit = {"T": T, "n": n, "until": EXIT_STRAIGHT}
                if getattr(g, "finish", False):
                    self.done, self.reason = True, "Start-/Zieltor wieder erreicht"
                self.prev_pos = s.pos
                self.hold = (s.pos[0], T[1], s.pos[2])
                self.height = T[1]
                self.target = None
                return self._brake(s)
        self.prev_pos = s.pos
        L = max(1.5, min(8.0, 0.4 * abs(along)))
        carrot = add(T, mul(n, min(along + L, 3.0)))
        to = sub(carrot, s.pos)
        direction = unit(to, n)
        # slower while the gate is not triangulated yet or the drone is far off the axis
        v = self.speed * (1.0 if g.triangulated else 0.6)
        if along < 0 and norm(lat) > 0.5 * abs(along) + 1.0:
            v *= 0.6
        if -8.0 < along < 0 and norm(lat) > 0.4:         # last metres: get onto the axis first (CP4 missed by 3 cm)
            v *= 0.5
        # stuck: wants to fly, does not move (caught on an obstacle the camera does not know)
        self.stuck = self.stuck + dt if s.speed < 0.3 else 0.0
        if self.stuck > 2.5:
            self.done, self.reason = True, "steckt fest (Hindernis?)"
        v_ref = mul(direction, v)
        p_ref = add(s.pos, mul(direction, min(1.5, norm(to))))
        p_ref = (p_ref[0], s.pos[1] + max(-1.0, min(1.0, carrot[1] - s.pos[1])), p_ref[2])
        v_ref = (v_ref[0], max(-1.5, min(1.5, (carrot[1] - s.pos[1]) * 1.5)), v_ref[2])
        self.hold = (s.pos[0], T[1], s.pos[2])
        return self.ctl.track(s, p_ref, v_ref, (0.0, 0.0, 0.0), unit((direction[0], 0.0, direction[2]), n))

    def _brake(self, s):
        return self.ctl.track(s, s.pos, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), self._heading(s))

    def _search(self, s, dt):
        """No gate in sight: fly on in the exit direction of the last gate (the next one is often just
        too far to be seen), then stop and turn once around; repeat a few times, then give up."""
        now = s.t
        if self.search_since is None or self.search is None:
            self.search_since = now
            f = self.exit_dir or self._heading(s)
            self.search = {"leg": 0, "phase": "advance", "from": s.pos, "dir": f,
                           "yaw": math.atan2(f[0], f[2]), "turned": 0.0}
        sr = self.search
        h = max(self.height, 1.2)
        if sr["phase"] == "advance":
            if math.dist((s.pos[0], 0, s.pos[2]), (sr["from"][0], 0, sr["from"][2])) > SEARCH_ADVANCE:
                sr["phase"], self.hold = "brake", (s.pos[0], h, s.pos[2])
            else:
                d = sr["dir"]
                p_ref = add(s.pos, mul(d, 1.5))
                p_ref = (p_ref[0], h, p_ref[2])
                return self.ctl.track(s, p_ref, mul(d, SEARCH_SPEED), (0.0, 0.0, 0.0), d)
        if sr["phase"] == "brake":
            if s.speed > 0.8:
                return self.ctl.track(s, self.hold, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), self._heading(s))
            sr["phase"] = "turn"
        # turn once around on the spot
        sr["yaw"] += SEARCH_RATE * dt
        sr["turned"] += SEARCH_RATE * dt
        if sr["turned"] > 2 * math.pi:
            sr["leg"] += 1
            if sr["leg"] >= SEARCH_LEGS:
                self.done, self.reason = True, "kein weiteres Tor gefunden"
                return self._brake(s)
            sr.update(phase="advance", **{"from": s.pos, "turned": 0.0})
        look = (math.sin(sr["yaw"]), 0.0, math.cos(sr["yaw"]))
        return self.ctl.track(s, self.hold, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), look)


def fly_by_camera(sess, speed=4.0, detect=None, explore=False, on_step=None, max_time=240.0, stop=None):
    """Vision-only flight from where the drone stands (after reset/countdown).

    Returns a dict with the passages, and with `explore` the map: list of planner Gates."""
    from .control import FlightController, Gains
    from .liftoff import state_row
    from .planner import Gate
    from .sysid import load_model
    rates, thrust = load_model()
    ctl = FlightController(rates, thrust, Gains(tilt=12, yaw=3.0, pos=2.5, vel=3.0))
    per = Perception(sess.tel, detect or yolo_detect(), use_frames=not isinstance(detect, TestDetector))
    per.start()
    t_wait = time.perf_counter() + 20
    while per.fps == 0.0 and not per.error and time.perf_counter() < t_wait:
        time.sleep(0.05)
    if per.error:
        raise RuntimeError(f"Torerkennung startet nicht: {per.error}")
    pilot = VisionPilot(ctl, per, speed=speed)
    arm = {"t": None}

    def step(s, dt):
        if stop is not None and stop():
            return None
        if arm["t"] is None:
            arm["t"] = s.t
        c = pilot.step(s, dt)
        t = pilot.target
        sess.log(target=t.id if t else -1, tx=t.center[0] if t else 0, ty=t.center[1] if t else 0,
                 tz=t.center[2] if t else 0, searching=int(pilot.search is not None),
                 passed=len(pilot.passed), cmd_t=c.throttle, **state_row(s))
        if on_step:
            on_step(s, pilot)
        if pilot.done:
            return None
        return c.as_tuple()

    ok = sess.loop(step, max_time=max_time)
    per.close()
    per.join(timeout=5)
    result = {"ok": ok, "reason": pilot.reason or sess.reason, "speed": speed,
              "passages": [{"t": t, "gate": i, "result": r} for t, i, r in pilot.events],
              "gates_seen": len(per.tracker.found()), "detections": per.tracker.detections,
              "frames": per.tracker.frames, "fps": round(per.fps, 1), "error": per.error}
    if explore:
        gmap = []
        for g in pilot.passed:
            if not getattr(g, "confirmed", False):
                continue
            pp = g.passage_point
            # the drone flew through the opening at pp: trust the estimate only if it agrees
            c = tuple(g.center) if math.dist(g.center, pp) < 2.0 else tuple(pp)
            n = g.passage_dir                              # 3-D: climbing gates are tilted
            w = g.width if g.triangulated and 1.5 < g.width < 6 else NOMINAL_W
            h = g.height if g.triangulated and 1.2 < g.height < 5 else NOMINAL_H
            gmap.append(Gate(c, n, max(1.5, w - 0.4), max(1.2, h - 0.4), f"V{g.id}"))
        if gmap and getattr(pilot.passed[-1], "finish", False) and len(gmap) > 1:
            gmap[-1].name = gmap[0].name                   # same physical gate: race.course() closes the lap
        result["map"] = gmap
    return result


def score_against_track(flown_log_rows, true_gates):
    """Evaluation only: which true gates the flown path went through (verify.py logic)."""
    from .verify import passage
    hit = []
    pts = flown_log_rows
    for i, g in enumerate(true_gates):
        for p0, p1 in zip(pts, pts[1:]):
            r = passage(g, p0, p1)
            if r and r[0]:
                hit.append(i)
                break
    return hit


def map_error(gmap, true_gates, match=3.0):
    """Evaluation only: distance of each mapped gate to the nearest true gate."""
    out = []
    for g in gmap:
        d, j = min((math.dist(g.center, t.center), j) for j, t in enumerate(true_gates))
        out.append({"gate": g.name, "true": j if d < match else None, "error_m": round(d, 2),
                    "width_m": round(g.width, 2)})
    return out


# ---------------------------------------------------------------------------- command line
def main(argv):
    from .liftoff import RUNS, Session
    from .race import course, fly
    from .track import load_race_with_track, race_gates
    name = argv[0] if argv else "StrawBaleRace01"
    mode = argv[1] if len(argv) > 1 else "nur_kamera"
    race, track = load_race_with_track(name)
    true_gates = race_gates(race, track)                   # only for scoring / the test detector
    detect = None
    if os.environ.get("EASYPILOT_TEST_DETECTOR"):
        from .sysid import load_camera
        detect = TestDetector(true_gates, load_camera(640))
        print("ACHTUNG: Test-Detektor aus der Streckendatei - testet nur die Flugsteuerung, nicht die Kamera")
    path = []
    sess = Session(f"visionfly-{name}-{mode}")
    sess.reset_drone(settle=4.5)
    if mode == "nur_kamera":
        speed = float(argv[2]) if len(argv) > 2 else 4.0
        res = fly_by_camera(sess, speed, detect, on_step=lambda s, p: path.append(s.pos))
        sess.close()
    else:
        k = float(argv[2]) if len(argv) > 2 else 0.4
        res = fly_by_camera(sess, 3.0, detect, explore=True, on_step=lambda s, p: path.append(s.pos))
        sess.close()
        gmap = res.pop("map")
        res["map_vs_track"] = map_error(gmap, true_gates)
        print(json.dumps(res, indent=1))
        if len(gmap) < 2:
            sys.exit("zu wenige Tore kartiert, kein Rennen")
        sess = Session(f"visionrace-{name}")
        sess.reset_drone(settle=4.5)
        path = []
        race_res = fly(sess, gmap, 1, k, vision=False, colliders=None,
                       on_step=lambda s, r: path.append(s.pos))
        res = {"explore": res, "race": {k2: race_res[k2] for k2 in ("ok", "reason", "time_s", "gates_passed",
                                                                     "gates_total", "planned_s")}}
    seq = course(true_gates, 1)
    res["true_gates_passed"] = f"{len(score_against_track(path, seq))}/{len(seq)}"
    print(json.dumps(res, indent=1, default=str))
    RUNS.mkdir(exist_ok=True)
    with (RUNS / "visionfly_results.jsonl").open("a") as f:
        f.write(json.dumps({"race": name, "mode": mode, "test_detector": bool(detect), **res}, default=str) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
