"""Autonomous race in Liftoff on an official track.

  python -m autopilot.race StrawBaleRace01 [aggressiveness] [laps]

Gate poses come from the race/track XML (see track.py); the vision pipeline checks
and corrects them while flying. The racing line goes from the spawn through all
checkpoints, `laps` times, and ends behind the finish gate.
"""
import json
import math
import sys
import time

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
    same = math.dist(gates[0].center, gates[-1].center) < 0.5
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


def main(argv):
    name = argv[0] if argv else "StrawBaleRace01"
    k = float(argv[1]) if len(argv) > 1 else 0.4
    laps = int(argv[2]) if len(argv) > 2 else 1
    race, track = load_race_with_track(name)
    gates = race_gates(race, track)
    rates, thrust = load_model()
    gains = Gains(tilt=16, yaw=4.0, pos=6.0, vel=5.0, drag=DRAG)
    sess = Session(f"race-{name}-{k}")
    sess.reset_drone(settle=4.5)   # race mode: wait for the 3-2-1 countdown
    s0 = sess.tel.wait()
    _, _, fwd = body_axes(s0.quat)
    line = build_line(gates, *launch(gates[0], s0.pos), laps, k)
    racer = Racer(line, FlightController(rates, thrust, gains), lookahead=0.12)
    print(f"{race['name']}: {len(line.gate_sequence)} gate passages ({laps} laps), line {line.length:.0f} m, "
          f"planned {line.lap_time_estimate:.2f} s, v_max {max(line.speed):.1f} m/s")
    t0 = time.perf_counter()

    def step(s, dt):
        c = racer.step(s)
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
    log = sess.close()
    p = racer.progress
    result = {"race": race["name"], "aggressiveness": k, "laps": laps, "ok": ok and not racer.crashed,
              "reason": "crash (drone stopped)" if racer.crashed else sess.reason,
              "gates_passed": len(p.gate_times), "gates_total": len(line.gate_sequence), "missed": p.missed,
              "time_s": round(p.gate_times[-1], 3) if p.gate_times else None,
              "planned_s": round(line.lap_time_estimate, 2), "max_cross_track_m": round(racer.max_cross_track, 2),
              "log": str(log)}
    print(json.dumps(result, indent=1))
    RUNS.mkdir(exist_ok=True)
    with (RUNS / "race_results.jsonl").open("a") as f:
        f.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
