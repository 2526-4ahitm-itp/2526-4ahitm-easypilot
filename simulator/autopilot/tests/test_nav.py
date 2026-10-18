"""Closed-loop test of the GPS waypoint flight with a simulated forward depth sensor.

The map starts EMPTY; obstacles are only known once the simulated camera sees them,
like in Liftoff. Run from simulator/:  python -m unittest autopilot.tests.test_nav -v
"""
import math
import random
import unittest

from autopilot.control import FlightController, Gains, ThrustModel
from autopilot.geometry import body_axes, unit
from autopilot.nav import GeoReference, Navigator, NavLimits, OccupancyGrid, plan_path
from autopilot.rates import Rates
from autopilot.sim import SimDrone

DT = 0.002
DRONE_RADIUS = 0.25


def ray_box(o, d, box):
    """Slab test, box = (x0, z0, x1, z1, height); returns hit distance or None."""
    x0, z0, x1, z1, h = box
    lo, hi = (x0, 0.0, z0), (x1, h, z1)
    tmin, tmax = 0.0, 1e9
    for i in range(3):
        if abs(d[i]) < 1e-9:
            if o[i] < lo[i] or o[i] > hi[i]:
                return None
        else:
            t1, t2 = (lo[i] - o[i]) / d[i], (hi[i] - o[i]) / d[i]
            tmin, tmax = max(tmin, min(t1, t2)), min(tmax, max(t1, t2))
    return tmin if tmin <= tmax else None


def sense(grid, pos, quat, boxes, rng=15.0, hfov=100, vfov=50, n_h=25, n_v=7):
    _, up, fwd = body_axes(quat)
    yaw = math.atan2(fwd[0], fwd[2])
    for i in range(n_h):
        a = yaw + math.radians(-hfov / 2 + hfov * i / (n_h - 1))
        for j in range(n_v):
            e = math.radians(-vfov / 2 + vfov * j / (n_v - 1))
            d = (math.sin(a) * math.cos(e), math.sin(e), math.cos(a) * math.cos(e))
            best = rng
            for b in boxes:
                t = ray_box(pos, d, b)
                if t is not None and t < best:
                    best = t
            if d[1] < 0:
                tg = -pos[1] / d[1]
                if tg < best:
                    grid.add_point((pos[0] + d[0] * tg, 0.0, pos[2] + d[2] * tg))
                    continue
            if best < rng:
                grid.add_point((pos[0] + d[0] * best, pos[1] + d[1] * best, pos[2] + d[2] * best))


def collides(pos, boxes):
    for x0, z0, x1, z1, h in boxes:
        if x0 - DRONE_RADIUS < pos[0] < x1 + DRONE_RADIUS and z0 - DRONE_RADIUS < pos[2] < z1 + DRONE_RADIUS \
                and pos[1] < h + DRONE_RADIUS:
            return True
    return False


def forest(seed, n=25):
    r = random.Random(seed)
    boxes = []
    while len(boxes) < n:
        x, z = r.uniform(-25, 25), r.uniform(8, 70)
        w, d = r.uniform(0.6, 4.0), r.uniform(0.6, 4.0)
        boxes.append((x, z, x + w, z + d, r.uniform(2.5, 8.0)))
    return boxes


def fly_to(goal_xz, boxes, max_time=60.0, limits=NavLimits()):
    grid = OccupancyGrid(cell=0.5)
    nav = Navigator(grid, goal_xz, limits)
    ctl = FlightController(Rates(), ThrustModel(), Gains(tilt=16, pos=6, vel=5))
    drone = SimDrone(pos=(0.0, 0.0, 0.0))
    t, cmd, hit, min_alt, max_alt, vmax = 0.0, None, False, 9, 0, 0
    k = 0
    while t < max_time:
        s = drone.state()
        if k % 25 == 0:  # depth sensor at 20 Hz
            sense(grid, s.pos, s.quat, boxes)
        if k % 2 == 0:
            ctl.observe(s)
            p, v, a, look = nav.reference(s.pos, s.vel)
            cmd = ctl.track(s, p, v, a, look)
        drone.step(*cmd.as_tuple(), DT)
        if t > 3.0:
            min_alt, max_alt = min(min_alt, drone.pos[1]), max(max_alt, drone.pos[1])
        vmax = max(vmax, math.sqrt(sum(x * x for x in drone.vel)))
        if collides(drone.pos, boxes):
            hit = True
            break
        if nav.status == "ARRIVED":
            break
        t += DT
        k += 1
    return nav, hit, t, (min_alt, max_alt), vmax


class GeoTest(unittest.TestCase):
    def test_roundtrip(self):
        ref = GeoReference(48.268611, 14.251944, (10.0, -5.0), 20.0)
        x, z = ref.to_world(48.2690, 14.2525)
        lat, lon = ref.to_gps(x, z)
        self.assertAlmostEqual(lat, 48.2690, places=7)
        self.assertAlmostEqual(lon, 14.2525, places=7)

    def test_north_is_plus_z(self):
        x, z = GeoReference().to_world(48.268611 + 0.001, 14.251944)
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(z, 111.3, delta=0.5)


class PlannerTest(unittest.TestCase):
    def test_wall_with_gap(self):
        g = OccupancyGrid(0.5)
        g.add_box(-20, 10, -1.5, 11, 5)
        g.add_box(1.5, 10, 20, 11, 5)
        path = plan_path(g, (0, 0), (0, 25), 1.5, clearance=0.8)
        self.assertIsNotNone(path)
        crossing = [p for p in path]
        self.assertTrue(any(abs(p[0]) < 1.0 for p in crossing))


class NavFlightTest(unittest.TestCase):
    def test_ten_goals_no_collision(self):
        results = []
        for seed in range(10):
            boxes = forest(seed)
            r = random.Random(100 + seed)
            goal = (r.uniform(-15, 15), r.uniform(55, 75))
            nav, hit, t, alt, vmax = fly_to(goal, boxes)
            results.append((seed, nav.status, hit, round(t, 1), round(alt[0], 2), round(alt[1], 2), round(vmax, 1)))
            with self.subTest(seed=seed):
                self.assertFalse(hit, f"collision on map {seed}")
                self.assertEqual(nav.status, "ARRIVED")
                # a goal inside an obstacle is replaced by the closest free spot
                self.assertLess(math.dist(nav.goal_xz, goal), 3.0)
                self.assertGreater(alt[0], 0.8)
                self.assertLess(alt[1], 3.0)
        print("\n  seed status hit time min_alt max_alt vmax")
        for row in results:
            print("  ", *row)


if __name__ == "__main__":
    unittest.main()
