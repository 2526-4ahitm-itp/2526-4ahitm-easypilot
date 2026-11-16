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


if __name__ == "__main__":
    unittest.main()
