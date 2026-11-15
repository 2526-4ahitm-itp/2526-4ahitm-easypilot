"""Test matrix: every official Liftoff race x every TDOT stage, flown automatically.

  python -m autopilot.matrix                         # all races, all 5 stages
  python -m autopilot.matrix --stages 1,5 --env StrawBale,ThePit
  python -m autopilot.matrix --races StrawBaleRace02 --stages 3
  python -m autopilot.matrix summary                 # table of all results so far

Per race: Liftoff is restarted with the race as "last session" (session.py), then one lap per
stage. A run counts as passed only if Liftoff itself accepted the lap (lapTimes.xml) - our own
gate timer runs alongside, the difference between both points at wrong gate geometry.
Results: runs/matrix/results.jsonl (one line per run), skips races already passed unless --again.
"""
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

from .liftoff import RUNS, Session
from .race import course, fly
from .session import flush_laps, lap_counted, lap_record, load, race_info
from .envdb import for_track
from .gatedb import track_colliders
from .recorder import Recorder, keep_as_reference
from .tdot import DATA as TDOT_DATA, STAGES, Leaderboard, LapTimer
from .telemetry import Telemetry
from .track import TRACK_DIR, race_gates

OUT = RUNS / "matrix"
RESULTS = OUT / "results.jsonl"


def all_races():
    return sorted(p.name.split("_")[0] for p in TRACK_DIR.glob("*Race*_*.xml"))


def done_before():
    passed = set()
    if RESULTS.exists():
        for line in RESULTS.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("passed"):
                passed.add((r["race"], r["stage"]))
    return passed


def reset(sess, settle=4.5):
    for _ in range(3):
        if sess.reset_drone(settle=settle):
            return True
        time.sleep(0.5)
    return False


def run_one(tel, timer, race_name, info, gates, level, record=True):
    st = next(s for s in STAGES if s.level == level)
    sess = Session(f"matrix-{race_name}-{level}", tel=tel)
    time.sleep(0.5)
    before = lap_record(info["race_id"])
    rec = Recorder(tel, race_name, level, st.aggressiveness) if record else None
    if rec:
        rec.start()
    if not reset(sess):
        sess.close()
        if rec:
            rec.finish(keep_video=False)
        return {"error": "reset not seen"}
    s0 = tel.wait(2.0)
    timer.go(s0.t)
    if rec:
        rec.go()
    t0 = time.time()
    res = fly(sess, gates, 1, st.aggressiveness, max_time=240, colliders=for_track(info["track"]))
    timer.running = False
    time.sleep(1.0)
    after = flush_laps(info["race_id"])
    passed = lap_counted(before, after)
    out = {"liftoff_lap": passed, "our_gates": timer.next, "our_time": timer.time,
           "bot_gates": res["gates_passed"], "reason": res["reason"], "max_xt": res["max_cross_track_m"],
           "planned_s": res["planned_s"], "wall_s": round(time.time() - t0, 1), "log": res["log"],
           "lap_after": after["best"][:1] if after else None}
    mp4 = rec.finish(keep_video=passed and timer.time is not None) if rec else None
    if passed and timer.time is not None:
        board = Leaderboard(TDOT_DATA / f"{race_name}-1lap.json")
        if board.add_bot(level, timer.time, timer.splits, timer.path):
            out["new_reference"] = True
            if mp4:
                keep_as_reference(mp4, race_name, level)
    if mp4 and mp4.exists():
        mp4.unlink()
    return out


def main(argv):
    if argv and argv[0] == "summary":
        return summary()
    if argv and argv[0] == "diagnose":
        return diagnose(argv[1:])
    if argv and argv[0] == "linecheck":
        return linecheck(argv[1:])
    if argv and argv[0] == "sim":
        return simcheck(argv[1:])
    opts = {"--stages": "1,2,3,4,5", "--env": "", "--races": ""}
    again = "--again" in argv
    no_record = "--no-record" in argv
    i = 0
    while i < len(argv):
        if argv[i] in opts:
            opts[argv[i]] = argv[i + 1]
            i += 1
        i += 1
    stages = [int(v) for v in opts["--stages"].split(",")]
    races = opts["--races"].split(",") if opts["--races"] else all_races()
    envs = set(opts["--env"].split(",")) if opts["--env"] else None
    OUT.mkdir(parents=True, exist_ok=True)
    passed = set() if again else done_before()
    timer = LapTimer([])
    tel = Telemetry(on_state=timer.feed)
    tel.start()
    import shutil
    for race_name in races:
        if shutil.disk_usage(RUNS).free < 3e9:
            print("less than 3 GB free on the disk - stopping (recordings need space)", flush=True)
            break
        info = race_info(race_name)
        if envs and info["env"] not in envs:
            continue
        todo = [lv for lv in stages if (race_name, lv) not in passed]
        if not todo:
            continue
        gates = race_gates(info["race"], info["track"])
        timer.seq = course(gates, 1)
        print(f"\n=== {race_name} ({info['env']}: {info['name']}), {len(timer.seq)} gates, stages {todo}", flush=True)
        ok, _ = load(race_name, tel=tel, mode="race")
        if not ok:
            rec = {"race": race_name, "env": info["env"], "stage": None, "passed": False, "error": "level not loaded"}
            _write(rec)
            continue
        for level in todo:
            try:
                r = run_one(tel, timer, race_name, info, gates, level, record=not no_record)
            except Exception as exc:
                r = {"error": repr(exc)}
            rec = {"race": race_name, "env": info["env"], "title": info["name"], "stage": level,
                   "gates": len(timer.seq), "passed": bool(r.get("liftoff_lap")), **r,
                   "date": time.strftime("%Y-%m-%d %H:%M")}
            _write(rec)
            print(f"  stage {level}: {'PASS' if rec['passed'] else 'FAIL'}  ours {r.get('our_gates')}/{len(timer.seq)} "
                  f"t={r.get('our_time')}  {r.get('reason', r.get('error', ''))}", flush=True)
    tel.close()


def _write(rec):
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def summary():
    latest = {}
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("stage") is None:
            continue
        key = (r["race"], r["stage"])
        if key not in latest or r["passed"] or not latest[key]["passed"]:
            latest[key] = r
    by_race = defaultdict(dict)
    for (race, lv), r in latest.items():
        by_race[race][lv] = r
    n_pass = sum(r["passed"] for r in latest.values())
    print(f"{n_pass}/{len(latest)} runs passed (Liftoff counted the lap)\n")
    print(f"{'race':28s} " + " ".join(f"S{s.level:<6d}" for s in STAGES))
    for race in sorted(by_race):
        cells = []
        for s in STAGES:
            r = by_race[race].get(s.level)
            cells.append("   -   " if r is None else (f"{r['our_time']:6.1f} " if r["passed"] and r.get("our_time")
                                                       else ("  ok   " if r["passed"] else " FAIL  ")))
        print(f"{race:28s} " + " ".join(cells))


def line_hits(line, colliders, radius=0.35, step=0.5):
    """Points of a racing line that run into a solid track item: [(s, item, point)]."""
    from . import gatedb
    hits = []
    pts = line.points
    last_s = -1e9
    for i, p in enumerate(pts):
        s = line.s[i]
        if s - last_s < step:
            continue
        last_s = s
        name = colliders.blocked(p, radius)
        if name:
            hits.append((round(s, 1), name, tuple(round(v, 1) for v in p)))
    return hits


def linecheck(argv):
    """Offline: does the planned racing line of every race touch a solid item? (no Liftoff needed)"""
    from . import gatedb
    from .race import build_line, launch
    k = float(argv[0]) if argv and not argv[0].startswith("--") else 0.6
    bad = 0
    for race_name in all_races():
        info = race_info(race_name)
        gates = race_gates(info["race"], info["track"])
        spawn = gates[0].center      # approximation: the line from the start gate on
        start, d = launch(gates[0], (spawn[0] - 10 * gates[0].normal[0], spawn[1], spawn[2] - 10 * gates[0].normal[2]))
        obs = for_track(info["track"])
        line = build_line(gates, start, d, 1, k, colliders=None if "--raw" in argv else obs)
        hits = line_hits(line, obs)
        if hits:
            bad += 1
            items = sorted({h[1] for h in hits})
            print(f"{race_name:28s} {len(hits):3d} hits  vias {getattr(line, 'vias', 0)}  {', '.join(items)[:100]}")
    print(f"{bad} of {len(all_races())} races: line touches solid items")


def spawn_point(track, first_gate):
    """Drone spawn of a track (SpawnPoint item), else 10 m before the first gate on the ground."""
    for b in track["blueprints"]:
        if b.item.startswith(("SpawnPoint", "PlayerPosition")):
            return b.pos
    c, n = first_gate.center, first_gate.normal
    return (c[0] - 10 * n[0], max(0.0, c[1] - 1.5), c[2] - 10 * n[2])


def sim_race(race_name, k, colliders=True, max_time=240.0):
    """Fly a race in the simulator (sim.py) with the Liftoff drone model and the real controller."""
    from . import gatedb
    from .control import FlightController, Gains, ThrustModel
    from .race import DRAG, build_line, launch
    from .racer import Racer
    from .sim import SimDrone, SimParams
    from .sysid import load_model
    info = race_info(race_name)
    gates = race_gates(info["race"], info["track"])
    obs = for_track(info["track"])
    spawn = spawn_point(info["track"], gates[0])
    start, d = launch(gates[0], spawn)
    line = build_line(gates, start, d, 1, k, colliders=obs if colliders else None)
    rates, thrust = load_model()
    drone = SimDrone(pos=spawn, params=SimParams(hover_throttle=thrust.hover_throttle,
                                                 thrust_exponent=thrust.exponent, drag=DRAG), rates=rates)
    # the simulator knows no terrain: put its ground plane below the start and every gate
    drone.ground = min([spawn[1]] + [g.center[1] - g.height / 2 for g in gates]) - 0.5
    racer = Racer(line, FlightController(rates, thrust, Gains(tilt=16, yaw=4.0, pos=6.0, vel=5.0, drag=DRAG)),
                  lookahead=0.12)
    dt, t, cmd, touch, xt = 0.002, 0.0, None, None, 0.0
    near = []
    flat = drone.ground
    while t < max_time and not racer.done:
        if cmd is None or int(t / dt) % 4 == 0:            # controller at 125 Hz like the Liftoff loop
            cmd = racer.step(drone.state())
            g = obs.ground(drone.pos[0], drone.pos[2])        # the real terrain where it is known
            drone.ground = g if g is not None else flat
        drone.step(*cmd.as_tuple(), dt)
        t += dt
        if int(t / dt) % 10 == 0 and touch is None and racer.progress.gate_index >= 1:
            name = obs.blocked(drone.pos, 0.15)
            if name:
                touch = (round(t, 1), name, racer.progress.gate_index)
    prog = racer.progress
    return {"race": race_name, "k": k, "gates": len(prog.gate_times), "total": len(line.gate_sequence),
            "missed": len(prog.missed), "time": round(prog.gate_times[-1], 2) if prog.finished else None,
            "touch": touch, "xt": round(racer.max_cross_track, 2), "vias": getattr(line, "vias", 0)}


def simcheck(argv):
    """python -m autopilot.matrix sim [k] [races...]: all races in the simulator, no Liftoff needed."""
    k = float(argv[0]) if argv and argv[0].replace(".", "").isdigit() else 0.6
    races = [a for a in argv if not a.replace(".", "").isdigit()] or all_races()
    ok = 0
    for rn in races:
        try:
            r = sim_race(rn, k)
        except Exception as exc:
            print(f"{rn:28s} ERROR {exc!r}"[:150])
            continue
        good = r["time"] is not None and not r["missed"] and r["touch"] is None
        ok += good
        if not good or len(races) < 5:
            print(f"{rn:28s} gates {r['gates']}/{r['total']} missed {r['missed']} touch {r['touch']} "
                  f"xt {r['xt']} vias {r['vias']} t {r['time']}", flush=True)
    print(f"{ok}/{len(races)} races clean in the simulator at k={k}")


def diagnose(argv):
    """Where and why did failed runs end? Crash point, gate reached, nearest solid track item."""
    import csv
    from . import gatedb
    from .track import load_race_with_track
    latest = {}
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("stage") is not None:
            latest[(r["race"], r["stage"])] = r
    fails = [r for r in latest.values() if not r["passed"] and (not argv or r["race"] in argv)]
    for r in sorted(fails, key=lambda r: r["race"]):
        print(f"\n{r['race']} S{r['stage']} ({r.get('title')}): {r.get('reason') or r.get('error')}, "
              f"ours {r.get('our_gates')}/{r.get('gates')}, xt_max {r.get('max_xt')}")
        log = r.get("log")
        if not log or not Path(log).exists():
            continue
        rows = list(csv.DictReader(open(log, encoding="utf-8")))
        if not rows:
            continue
        pts = [(float(x["x"]), float(x["y"]), float(x["z"]), float(x["speed"]), int(x["gate"]),
                float(x["xt"])) for x in rows]
        # crash = first moment the speed collapses (>6 m/s to <40 % within 0.15 s)
        crash = len(pts) - 1
        for i in range(15, len(pts)):
            if pts[i - 15][3] > 6 and pts[i][3] < 0.4 * pts[i - 15][3]:
                crash = i - 15
                break
        p = pts[crash]
        _, track = load_race_with_track(r["race"])
        cols = gatedb.track_colliders(track)
        near = sorted(((gatedb.pp_distance(pp, p[:3]), name) for name, pp in cols
                       if abs(pp[0][0] - p[0]) < 30 and abs(pp[0][2] - p[2]) < 30), key=lambda t: t[0])[:3]
        print(f"   crash at t={crash / 100:.1f}s gate {p[4]} pos ({p[0]:.1f},{p[1]:.1f},{p[2]:.1f}) "
              f"speed {pts[max(0, crash - 15)][3]:.1f} m/s, off line {p[5]:.2f} m")
        print("   nearest items:", ", ".join(f"{n} {d:.2f} m" for d, n in near))


if __name__ == "__main__":
    main(sys.argv[1:])
