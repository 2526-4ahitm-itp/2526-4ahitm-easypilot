"""TDOT event: lap timer through gates and leaderboard ranking.

Run from simulator/:  python -m unittest autopilot.tests.test_tdot -v
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from autopilot.planner import Gate
from autopilot.tdot import STAGES, Leaderboard, LapTimer


def gates():
    # three gates along +z, the middle one shifted to the side
    return [Gate((0.0, 1.5, 10.0), (0.0, 0.0, 1.0), 3.0, 2.4, "A"),
            Gate((4.0, 1.5, 20.0), (0.0, 0.0, 1.0), 3.0, 2.4, "B"),
            Gate((0.0, 1.5, 30.0), (0.0, 0.0, 1.0), 3.0, 2.4, "C")]


def fly(timer, points, dt=0.01, t0=100.0):
    """Feed straight segments between the given points with 10 m/s."""
    t = t0
    timer.feed(SimpleNamespace(t=t, pos=points[0]))
    for a, b in zip(points, points[1:]):
        d = sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5
        n = max(1, int(d / (10.0 * dt)))
        for i in range(1, n + 1):
            t += dt
            p = tuple(x + (y - x) * i / n for x, y in zip(a, b))
            timer.feed(SimpleNamespace(t=t, pos=p))
    return t


class LapTimerTest(unittest.TestCase):
    def test_valid_run(self):
        tm = LapTimer(gates())
        tm.go(100.0)
        fly(tm, [(0, 1.5, 0), (0, 1.5, 15), (4, 1.5, 15), (4, 1.5, 25), (0, 1.5, 25), (0, 1.5, 35)])
        self.assertTrue(tm.finished)
        self.assertEqual(len(tm.splits), 3)
        # gate A after 10 m at 10 m/s
        self.assertAlmostEqual(tm.splits[0], 1.0, delta=0.02)
        # path length to gate C: 15 + 4 + 10 + 4 + 5 = 38 m
        self.assertAlmostEqual(tm.time, 3.8, delta=0.03)

    def test_missed_gate_is_not_counted(self):
        tm = LapTimer(gates())
        tm.go(100.0)
        # straight line misses gate B (opening at x 2.5..5.5)
        fly(tm, [(0, 1.5, 0), (0, 1.5, 35)])
        self.assertFalse(tm.finished)
        self.assertEqual(tm.next, 1)
        self.assertIsNone(tm.time)

    def test_gate_from_behind_does_not_count(self):
        tm = LapTimer(gates())
        tm.go(100.0)
        fly(tm, [(0, 1.5, 15), (0, 1.5, 5)])
        self.assertEqual(tm.next, 0)

    def test_nothing_before_go(self):
        tm = LapTimer(gates())
        fly(tm, [(0, 1.5, 0), (0, 1.5, 15)])
        self.assertEqual(tm.splits, [])


class LeaderboardTest(unittest.TestCase):
    def test_ranking_and_stages(self):
        with tempfile.TemporaryDirectory() as d:
            lb = Leaderboard(Path(d) / "lb.json")
            self.assertTrue(lb.add_bot(2, 40.0, [10, 20, 40.0], []))
            self.assertFalse(lb.add_bot(2, 41.0, [], []))          # slower: reference stays
            self.assertTrue(lb.add_bot(2, 38.0, [9, 19, 38.0], []))
            a = lb.add_run("Anna", 2, 37.5, [])
            lb.add_run("anna", 2, 45.0, [])                         # same pilot, slower
            lb.add_run("Ben", 2, 39.0, [])
            lb.add_run("Cem", 1, None, [])                          # did not finish
            self.assertTrue(a["beat_bot"])
            s = lb.summary()
            self.assertEqual([r["name"] for r in s["ranking"]], ["Anna", "Ben"])
            st2 = next(x for x in s["stages"] if x["level"] == 2)
            self.assertEqual(st2["bot_time"], 38.0)
            self.assertEqual(st2["beaten_by"], ["Anna"])
            self.assertEqual(len(s["stages"]), len(STAGES))
            # persisted
            again = Leaderboard(Path(d) / "lb.json")
            self.assertEqual(len(again.data["runs"]), 4)
            again.delete(a["id"])
            self.assertEqual([r["name"] for r in again.summary()["ranking"]], ["Ben", "anna"])


if __name__ == "__main__":
    unittest.main()
