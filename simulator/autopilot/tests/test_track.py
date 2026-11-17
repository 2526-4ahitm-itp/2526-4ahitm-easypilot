"""Gate geometry from the game files (needs tracks/gatedb.json, i.e. Liftoff installed).

Run from simulator/:  python -m autopilot.tests.test_track
"""
import math
import unittest

from autopilot import gatedb


def _have_db():
    try:
        return bool(gatedb.db())
    except Exception:
        return False


@unittest.skipUnless(_have_db(), "no gate database (python -m autopilot.gatedb extract)")
class CheckpointVolumeTest(unittest.TestCase):
    def test_volume_stays_at_the_gate(self):
        """The trigger volume is (origin, 3 edges). A loop variable once overwrote an edge with an
        absolute corner point: volumes reached hundreds of metres, the lap counter saw the finish
        gate as passed 12 m before it and the drone landed short of the line (16.11.)."""
        from autopilot.session import race_info
        from autopilot.track import race_gates
        info = race_info("AutumnFieldsRace04")
        for g in race_gates(info["race"], info["track"]):
            corners = gatedb.pp_corners(g.volume)
            span = max(math.dist(a, b) for a in corners for b in corners)
            self.assertLess(span, 40.0, g.name)
            self.assertTrue(gatedb.pp_contains(g.volume, g.center, 0.5) or getattr(g, "thin", False)
                            or math.dist(g.center, corners[0]) < span, g.name)

    def test_finish_not_passed_from_the_side(self):
        """12 m beside the finish arch is no passage."""
        from autopilot.session import race_info
        from autopilot.track import race_gates
        info = race_info("AutumnFieldsRace04")
        g = race_gates(info["race"], info["track"])[0]
        side = (g.normal[2], 0.0, -g.normal[0])
        p0 = tuple(g.center[k] - 11.0 * g.normal[k] - 12.0 * side[k] for k in range(3))
        p1 = tuple(p0[k] + 0.5 * g.normal[k] for k in range(3))
        self.assertFalse(g.passed(p0, p1))
        a = tuple(g.center[k] - 0.3 * g.normal[k] for k in range(3))
        b = tuple(g.center[k] + 0.3 * g.normal[k] for k in range(3))
        self.assertTrue(g.passed(a, b))


def _have_env():
    try:
        from autopilot.envdb import for_track
        from autopilot.session import race_info
        return len(for_track(race_info("HannoverRace02")["track"])) > 0
    except Exception:
        return False


@unittest.skipUnless(_have_db() and _have_env(), "no gate / level database")
class AvoidTest(unittest.TestCase):
    def test_line_clears_the_osb_wall(self):
        """HannoverRace02: the old via search left the line 0.1 m from a diagonal OSB board wall for
        2 m, the drone hit it at 15 m/s on the line (Liftoff, 16.11.). The band repair clears it."""
        from autopilot.envdb import for_track
        from autopilot.matrix import line_hits, spawn_point
        from autopilot.race import build_line, launch
        from autopilot.session import race_info
        from autopilot.track import race_gates
        info = race_info("HannoverRace02")
        gates = race_gates(info["race"], info["track"])
        obs = for_track(info["track"])
        start, d = launch(gates[0], spawn_point(info["track"], gates[0]))
        line = build_line(gates, start, d, 1, 0.6, colliders=obs)
        self.assertFalse([h for h in line_hits(line, obs) if h[1] == "OSB22001"])
        # every real gate is still passed exactly
        for g in (g for g in line.gates if not getattr(g, "via", False)):
            self.assertLess(min(math.dist(p, g.center) for p in line.points), 0.01, g.name)


if __name__ == "__main__":
    unittest.main()
