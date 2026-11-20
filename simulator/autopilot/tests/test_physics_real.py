"""Physik „Realistisch“ (freefly/physics_real.py): Kennwerte einer echten 5"-Drohne, Betaflight-Regler, Akku, Kollisionen.

Run from simulator/:  python -m unittest autopilot.tests.test_physics_real -v
"""
import math
import unittest

import numpy as np

from autopilot.control import ThrustModel
from autopilot.freefly.physics_real import G, RealDrone, RealParams, collide, controller_thrust, ocv
from autopilot.geometry import axis_angle
from autopilot.rates import AxisRate, Rates

DT = 0.002
AXIS = AxisRate(0.87, 0.0, 0.71)             # Rates der vermessenen Drohne (drone.json)
RATES = Rates(AxisRate(0.87, 0.0, 0.71), AxisRate(0.87, 0.0, 0.71), AxisRate(0.87, 0.0, 0.71))


def drone(**kw):
    kw.setdefault("noise", False)
    return RealDrone(pos=(0.0, 100.0, 0.0), params=RealParams(**kw), rates=RATES)


def pinned(d, thr, vax=0.0, steps=400):
    """Drohne festhalten (Lage, Ort, Fahrt), nur Motoren/Akku laufen: statischer Schub."""
    for _ in range(steps):
        d.vel, d.pos, d.quat, d.omega = (0.0, vax, 0.0), (0.0, 100.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0)
        d.step(thr, 0.0, 0.0, 0.0, DT)
    return d.thrust


def hover_throttle(**kw):
    lo, hi = 0.05, 0.6
    for _ in range(16):
        mid = 0.5 * (lo + hi)
        d = drone(**kw)
        for _ in range(600):
            d.step(mid, 0.0, 0.0, 0.0, DT)
        lo, hi = (mid, hi) if d.vel[1] < 0.0 else (lo, mid)
    return 0.5 * (lo + hi)


class FakeWorld:
    """Eine Box (Mauer) wie world.World: bc, bh, bcos, bsin, hit_index."""

    def __init__(self, center, half, yaw=0.0):
        self.bc = np.array([center], float)
        self.bh = np.array([half], float)
        self.bcos = np.array([math.cos(yaw)])
        self.bsin = np.array([math.sin(yaw)])

    def hit_index(self, p, r=0.25):
        d = np.asarray(p, float) - self.bc[0]
        c, s = self.bcos[0], self.bsin[0]
        q = np.maximum(np.abs((c * d[0] - s * d[2], d[1], s * d[0] + c * d[2])) - self.bh[0], 0.0)
        return 0 if float(q @ q) < r * r else -1


class FakeFlight:
    def __init__(self, world):
        self.world = world


class RealPhysicsTest(unittest.TestCase):
    def test_hover_and_thrust_to_weight(self):
        h = hover_throttle()
        self.assertTrue(0.15 < h < 0.25, h)              # echte 5"/6S-Racer schweben bei ~20 % Gas
        full = pinned(drone(battery=False), 1.0)
        self.assertTrue(7.0 < full / G < 11.0, full / G)  # Schub/Gewicht 7-11 (2207 1950 KV, 5,1")

    def test_motor_time_constant(self):
        """Drehzahl-Sprung: Zeitkonstante ergibt sich aus Motor + Propeller, Literatur 30-39 ms."""
        d = drone(battery=False)
        pinned(d, 0.2)
        w0 = d.w[0]
        pinned(d, 0.6, steps=600)
        w1 = d.w[0]
        d2 = drone(battery=False)
        pinned(d2, 0.2)
        t = 0.0
        while d2.w[0] < w0 + 0.632 * (w1 - w0) and t < 0.5:
            pinned(d2, 0.6, steps=1)
            t += DT
        self.assertTrue(0.008 < t < 0.05, t)

    def test_rate_step_follows_pid(self):
        """Roll-Sprung auf halben Stick: schnell (< 50 ms auf 90 %), Überschwinger begrenzt, kein Dauerfehler."""
        h = hover_throttle()
        d = drone()
        for _ in range(200):
            d.step(h, 0.0, 0.0, 0.0, DT)
        target = AXIS.rate(0.5)
        rates, t90 = [], None
        for i in range(200):
            d.step(h, 0.0, 0.0, 0.5, DT)
            r = math.degrees(-d.omega[2])
            rates.append(r)
            if t90 is None and r >= 0.9 * target:
                t90 = (i + 1) * DT
        self.assertIsNotNone(t90)
        self.assertLess(t90, 0.05)
        self.assertLess(max(rates), 1.5 * target)
        self.assertAlmostEqual(rates[-1], target, delta=0.05 * target)

    def test_airmode_keeps_authority_at_zero_throttle(self):
        d = drone()
        for _ in range(100):
            d.step(0.0, 0.0, 0.0, 1.0, DT)
        self.assertGreater(math.degrees(-d.omega[2]), 0.5 * AXIS.rate(1.0))

    def test_inflow_costs_thrust(self):
        static = pinned(drone(battery=False), 1.0)
        climbing = pinned(drone(battery=False), 1.0, vax=15.0)
        self.assertLess(climbing, 0.9 * static)

    def test_battery_sag_and_depletion(self):
        full = drone()
        a_full = pinned(full, 1.0)
        self.assertLess(full.volts, full.volts_ocv - 2.0)          # Spannungseinbruch unter Volllast
        self.assertGreater(full.volts / 6, 2.8)
        self.assertGreater(full.amps, 80.0)
        low = drone(soc0=0.3)
        self.assertLess(pinned(low, 1.0), 0.95 * a_full)           # leerer Akku: weniger Schub
        self.assertAlmostEqual(ocv(1.0), 4.2)
        self.assertGreater(full.mah, 0.0)

    def test_top_speed_plausible(self):
        """Vollgas mit fester Neigung 80°: waagrecht 35-50 m/s (5"/6S: ~130-165 km/h)."""
        d = drone(battery=False)
        q = axis_angle((1, 0, 0), math.radians(80))
        for _ in range(int(8 / DT)):
            d.quat, d.omega = q, (0.0, 0.0, 0.0)
            d.step(1.0, 0.0, 0.0, 0.0, DT)
        speed = math.hypot(d.vel[0], d.vel[2])
        self.assertTrue(35.0 < speed < 50.0, speed)

    def test_controller_thrust_matches(self):
        m = controller_thrust(ThrustModel(0.281, 2.0, inflow=1.37, airmode=13.0))
        self.assertTrue(m.real)
        self.assertAlmostEqual(m.hover_throttle, hover_throttle(battery=False, vrs=0.0, ground_effect=False), delta=0.02)
        self.assertTrue(1.2 < m.exponent < 1.8, m.exponent)

    def test_soft_wall_bounces_hard_wall_crashes(self):
        world = FakeWorld((0.0, 5.0, 10.0), (5.0, 5.0, 0.5))      # Mauer, Vorderseite bei z = 9,5
        for speed, crash in ((3.0, False), (12.0, True)):
            d = drone()
            d.pos, d.vel = (0.0, 5.0, 9.3), (0.0, 0.0, speed)
            reason = collide(FakeFlight(world), d, 0.0, DT, 0.25, 1.0)
            self.assertEqual(bool(reason), crash, (speed, reason))
            if not crash:
                self.assertLess(d.vel[2], 0.0)                     # prallt zurück
                self.assertEqual(world.hit_index(d.pos), -1)       # steckt nicht mehr in der Mauer

    def test_ground_soft_landing_and_hard_impact(self):
        world = FakeWorld((0.0, -50.0, 0.0), (0.1, 0.1, 0.1))
        d = drone()
        d.pos, d.vel = (0.0, 0.2, 0.0), (0.0, -2.0, 0.0)
        self.assertIsNone(collide(FakeFlight(world), d, -2.0, DT, 0.25, 1.0))
        self.assertGreaterEqual(d.pos[1], 0.25)
        d.pos, d.vel = (0.0, 0.2, 0.0), (0.0, -12.0, 0.0)
        self.assertTrue(collide(FakeFlight(world), d, -12.0, DT, 0.25, 1.0))


if __name__ == "__main__":
    unittest.main()
