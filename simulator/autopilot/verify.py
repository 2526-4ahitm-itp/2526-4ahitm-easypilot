"""Check a race log against the TRUE gate positions from the track file.

  python -m autopilot.verify StrawBaleRace02 3 runs/race-....csv

The racer's own count uses the (possibly camera-corrected or perturbed) map; this check
replays the flown path through the unmodified gates, like Liftoff's checkpoint logic.
"""
import csv
import math
import sys

from .geometry import add, cross, dot, mul, sub, unit
from .race import course
from .track import load_race_with_track, race_gates


def passage(gate, p0, p1):
    """None if the segment does not cross the gate plane forward, else (inside, lateral, vertical)."""
    a = dot(sub(p0, gate.center), gate.normal)
    b = dot(sub(p1, gate.center), gate.normal)
    if not (a < 0 <= b):
        return None
    hit = add(p0, mul(sub(p1, p0), a / (a - b)))
    rel = sub(hit, gate.center)
    side = unit(cross((0.0, 1.0, 0.0), gate.normal), (1.0, 0.0, 0.0))
    up = cross(gate.normal, side)
    lat, ver = dot(rel, side), dot(rel, up)
    return abs(lat) <= gate.width / 2 and abs(ver) <= gate.height / 2, lat, ver


def verify(race_name, laps, log):
    race, track = load_race_with_track(race_name)
    seq = course(race_gates(race, track), laps)
    pts = []
    with open(log) as f:
        for r in csv.DictReader(f):
            pts.append((float(r["t"]), (float(r["x"]), float(r["y"]), float(r["z"]))))
    k, report = 0, []
    for (t0, p0), (t1, p1) in zip(pts, pts[1:]):
        if k >= len(seq):
            break
        g = seq[k]
        if math.dist(p1, g.center) > 3 * max(g.width, g.height):
            continue
        res = passage(g, p0, p1)
        if res is None:
            continue
        inside, lat, ver = res
        report.append((k, g.name.split()[0], inside, round(lat, 2), round(ver, 2), round(t1 - pts[0][0], 2)))
        k += 1
    return seq, report


if __name__ == "__main__":
    seq, rep = verify(sys.argv[1], int(sys.argv[2]), sys.argv[3])
    bad = [r for r in rep if not r[2]]
    print(f"passed {sum(r[2] for r in rep)} of {len(seq)} through the true gates, plane crossings {len(rep)}")
    for r in bad:
        print("  MISSED", r[:2], "lateral", r[3], "vertical", r[4], "at", r[5], "s")
