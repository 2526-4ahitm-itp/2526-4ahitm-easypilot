"""Closed-loop tests: racing line + flight controller on the Liftoff-like model.

Run from simulator/:  python -m unittest discover -s autopilot/tests -v
"""
import math
import unittest

from autopilot.control import FlightController, ThrustModel
from autopilot.geometry import axis_angle, qrot, unit
from autopilot.planner import Gate, Limits, RacingLine
from autopilot.rates import Rates
from autopilot.sim import SimDrone, SimParams

DT = 0.002


def oval_track():
    """8 gates on a 60 x 30 m oval with some height changes, clockwise seen from above."""
    gates = []
    for k in range(8):
        a = 2 * math.pi * k / 8
        c = (30 * math.sin(a), 2.5 + 1.0 * math.sin(2 * a), 15 * math.cos(a) + 15)
        tangent = unit((30 * math.cos(a), 2.0 * math.cos(2 * a) * 2 * math.pi / 8, -15 * math.sin(a)))
        gates.append(Gate(c, tangent, 2.0, 2.0, f"G{k + 1}"))
    return gates


def fly(gates, aggressiveness, laps=1, params=SimParams(), thrust=ThrustModel(), max_time=120.0):
    from autopilot.control import Gains
    from autopilot.racer import Racer
    start = (0.0, 0.5, -2.0)
    line = RacingLine(gates, start=start, start_dir=(0, 0.3, 1), laps=laps,
                      limits=Limits.from_thrust(thrust.max_accel), aggressiveness=aggressiveness)
    drone = SimDrone(pos=start, params=params)
    racer = Racer(line, FlightController(Rates(), thrust, Gains(tilt=20, pos=9, vel=6)))
    cmd = None
    t = 0.0
    max_speed = 0.0
    while t < max_time and not racer.done:
        if cmd is None or int(t / DT) % 2 == 0:  # controller at 250 Hz, physics at 500 Hz
            cmd = racer.step(drone.state())
        drone.step(*cmd.as_tuple(), DT)
        max_speed = max(max_speed, math.sqrt(sum(v * v for v in drone.vel)))
        t += DT
    return racer, line, max_speed


class RateCurveTest(unittest.TestCase):
    def test_inverse(self):
        r = Rates()
        for s in (-1.0, -0.6, -0.1, 0.0, 0.05, 0.3, 0.77, 1.0):
            self.assertAlmostEqual(r.roll.stick(r.roll.rate(s)), s, places=5)

    def test_full_stick_rate(self):
        # Betaflight: 200 * 1.55 / (1 - 0.73) at full stick
        self.assertAlmostEqual(Rates().roll.rate(1.0), 200 * 1.55 / 0.27, places=3)


class RacingTest(unittest.TestCase):
    def test_line_passes_gates(self):
        gates = oval_track()
        line = RacingLine(gates, start=(0, 0.5, -2), laps=1)
        for g in gates:
            d = min(math.dist(p, g.center) for p in line.points)
            self.assertLess(d, 0.3, g.name)

    def test_lap_at_increasing_speed(self):
        for k in (0.4, 0.7, 1.0):
            racer, line, vmax = fly(oval_track(), k)
            with self.subTest(aggressiveness=k):
                self.assertEqual(racer.progress.missed, [], f"missed gates at {k}")
                self.assertEqual(len(racer.progress.gate_times), 8)
                print(f"\n  aggressiveness {k}: lap {racer.progress.gate_times[-1]:.2f} s "
                      f"(planned {line.lap_time_estimate:.2f} s), v_max {vmax:.1f} m/s, "
                      f"max cross-track {racer.max_cross_track:.2f} m")

    def test_robust_to_model_errors(self):
        """Wrong hover throttle, stronger drag and side wind: the disturbance estimate must absorb it."""
        params = SimParams(hover_throttle=0.33, drag=0.035, wind=(3.0, 0.0, 0.0), motor_tau=0.045)
        racer, line, vmax = fly(oval_track(), 0.85, params=params)
        self.assertEqual(racer.progress.missed, [])
        self.assertEqual(len(racer.progress.gate_times), 8)


class CourseTest(unittest.TestCase):
    def test_shared_start_finish_gate_passed_once_per_lap(self):
        from autopilot.race import course
        a, b, c = (Gate((0, 1, 0), (0, 0, 1)), Gate((0, 1, 20), (0, 0, 1)), Gate((10, 1, 10), (1, 0, 0)))
        finish = Gate((0, 1, 0), (0, 0, 1))
        self.assertEqual(len(course([a, b, c, finish], 3)), 3 * 3 + 1)

    def test_separate_finish_gate(self):
        from autopilot.race import course
        a, b, finish = (Gate((0, 1, 0), (0, 0, 1)), Gate((0, 1, 20), (0, 0, 1)), Gate((0, 1, -5), (0, 0, 1)))
        self.assertEqual(len(course([a, b, finish], 3)), 9)


if __name__ == "__main__":
    unittest.main()
