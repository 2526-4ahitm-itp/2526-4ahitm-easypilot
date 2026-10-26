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
from .session import lap_counted, lap_record, load, race_info
from .tdot import STAGES, LapTimer
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


def run_one(tel, timer, info, gates, level):
    st = next(s for s in STAGES if s.level == level)
    sess = Session(f"matrix-{info['race']['name'][:20]}-{level}".replace(" ", ""), tel=tel)
    time.sleep(0.5)
    before = lap_record(info["race_id"])
    if not reset(sess):
        sess.close()
        return {"error": "reset not seen"}
    s0 = tel.wait(2.0)
    timer.go(s0.t)
    t0 = time.time()
    res = fly(sess, gates, 1, st.aggressiveness, max_time=240)
    timer.running = False
    time.sleep(1.5)
    after = lap_record(info["race_id"])
    return {"liftoff_lap": lap_counted(before, after), "our_gates": timer.next, "our_time": timer.time,
            "bot_gates": res["gates_passed"], "reason": res["reason"], "max_xt": res["max_cross_track_m"],
            "planned_s": res["planned_s"], "wall_s": round(time.time() - t0, 1), "log": res["log"],
            "lap_after": after["best"][:1] if after else None}


def main(argv):
    if argv and argv[0] == "summary":
        return summary()
    opts = {"--stages": "1,2,3,4,5", "--env": "", "--races": ""}
    again = "--again" in argv
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
    for race_name in races:
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
                r = run_one(tel, timer, info, gates, level)
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


if __name__ == "__main__":
    main(sys.argv[1:])
