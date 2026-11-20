"""Spielmodi des Freiflug-Sims (freefly/modes.py) ohne Fenster: Geist, Ringe, Paket, Freestyle-Tricks.

Geflogen wird mit der echten Physik (Flight, Liftoff-nah) und geskripteten Sticks bzw. vorgegebenen Bahnen.
Run from simulator/:  python -m unittest autopilot.tests.test_freefly_modes -v
"""
import math
import os
import tempfile
import time
import unittest

from autopilot.freefly import modes, tracks
from autopilot.freefly import world as W
from autopilot.freefly.game import Flight
from autopilot.geometry import axis_angle, qmul
from autopilot.sysid import load_model

WORLDS = {}
DT = 0.002


def world(key="dorfrunde"):
    if key not in WORLDS:
        WORLDS[key] = W.World(track=key)
    return WORLDS[key]


def flight(mode="race", physik="liftoff", key="dorfrunde", settings=None, pos=None):
    rates, thrust = load_model()
    Flight.physics = physik
    f = Flight(world(key), rates, thrust)
    f.mode = mode
    if pos is not None:
        f.drone.pos = pos
    f.armed = True
    s = {"mode": mode, "physik": physik, "ghost": True, "ghost_save": False, "ring_set": "leicht", "auto": False}
    s.update(settings or {})
    modes.attach(f, s, full=True)
    return f, s


def fly(f, sticks, seconds, focus=True):
    for k in range(int(round(seconds / DT))):
        if focus and k % 25 == 0:
            f.world.focus(f.drone.pos)
        f.step(sticks, DT)
        if f.crashed_at is not None:
            break


def pitch(deg):
    return axis_angle((1.0, 0.0, 0.0), math.radians(deg))


class Path:
    """Vorgegebene Bahn (Position, Lage) für die Trick-Erkennung: Drohne wird Schritt für Schritt gesetzt."""

    def __init__(self, f):
        self.f, self.t = f, 0.0

    def go(self, pos_fn, quat_fn, seconds, dt=0.002):
        d = self.f.drone
        n = int(round(seconds / dt))
        out = []
        for k in range(1, n + 1):
            s = k / n
            p0, p1 = pos_fn(max(0.0, s - 1e-3)), pos_fn(s)
            d.vel = tuple((p1[i] - p0[i]) / (1e-3 * seconds) for i in range(3))
            d.pos, d.quat = p1, quat_fn(s)
            if k % 25 == 0:
                self.f.world.focus(d.pos)
            g = self.f.game
            before = len(g.log)
            g.step(self.f, p0, dt)
            out += [e["name"] for e in g.log[before:]]
        return out


# ---------------------------------------------------------------------------------------------- Platz in der Welt

class PlacementTest(unittest.TestCase):
    def test_rings_free_on_all_tracks(self):
        for k in tracks.ORDER:
            w = world(k)
            for name, rs in modes.RING_SETS.items():
                for i, r in enumerate(rs["rings"]):
                    self.assertEqual(modes.ring_problems(w, r), [], f"{k}: Ring {name} {i} {r}")

    def test_ring_sets(self):
        self.assertEqual(modes.RING_ORDER, ["leicht", "schwer"])
        self.assertGreaterEqual(len(modes.RING_SETS["leicht"]["rings"]), 12)
        self.assertGreaterEqual(len(modes.RING_SETS["schwer"]["rings"]), 12)
        hard = modes.RING_SETS["schwer"]["rings"]
        self.assertTrue(any(r[1] > 20 for r in hard), "ein Ring hoch oben")
        z = modes.Tricks(None) and modes.ZONES
        inside = [n for r in hard for (b, n) in z if modes.in_obox(r[:3], b)]
        self.assertIn("SCHEUNE", inside)
        self.assertIn("BRÜCKE", inside)

    def test_addresses_and_stations(self):
        for k in tracks.ORDER:
            a = modes.addresses(world(k))
            kinds = {x["kind"] for x in a}
            self.assertGreaterEqual(len(a), 12, k)
            self.assertTrue({"dach", "balkon", "garten"} <= kinds, (k, kinds))
            for s in modes.STATIONS:
                self.assertTrue(modes.column_free(world(k), s["x"], 0.0, s["z"], 2.0, 6.0), (k, s["name"]))
        roof = [x for x in modes.addresses(world()) if x["kind"] == "dach"][0]
        self.assertAlmostEqual(roof["y"], 9.8, delta=0.05)


# ---------------------------------------------------------------------------------------------- Ringe

class RingsTest(unittest.TestCase):
    def test_collect_any_order_penalty_and_result(self):
        f, s = flight("ringe")
        g = f.game
        self.assertIsInstance(g, modes.Rings)
        order = list(range(len(g.rings)))[::-1]                   # rückwärts: Reihenfolge egal
        for n, i in enumerate(order):
            c, nrm, u = g.frames[i]
            a = tuple(c[k] - 1.0 * nrm[k] for k in range(3))
            b = tuple(c[k] + 1.0 * nrm[k] + 0.3 * u[k] for k in range(3))
            f.drone.pos = b
            g.step(f, a, 0.5)
            self.assertEqual(g.count, n + 1)
            if n == 2:
                f.crash("Test")                                   # Absturz: +5 s, Ringe bleiben
                modes.attach(f, s)
                self.assertEqual(g.count, 3)
                self.assertEqual(g.penalty, 5.0)
        self.assertTrue(g.finished)
        self.assertAlmostEqual(g.result["time"], 0.5 * len(g.rings) + 5.0, places=3)
        title, sub, line, rec = modes.take_result(f, s)
        self.assertTrue(rec)
        self.assertIn("ringe-leicht", s["best_modes"])
        self.assertIsNone(modes.take_result(f, s), "Ergebnis nur einmal")
        modes.attach(f, s)                                         # nach dem Ergebnis: neuer Lauf
        self.assertEqual(g.count, 0)

    def test_miss_outside(self):
        f, _ = flight("ringe")
        g = f.game
        c, nrm, u = g.frames[0]
        R = g.rings[0][4]
        a = tuple(c[k] - nrm[k] + (R + 0.3) * u[k] for k in range(3))
        f.drone.pos = tuple(c[k] + nrm[k] + (R + 0.3) * u[k] for k in range(3))
        g.step(f, a, 0.1)
        self.assertEqual(g.count, 0)

    def test_real_flight_through_ring(self):
        """Echte Physik: vor dem ersten leichten Ring schweben, dann hindurch."""
        f, _ = flight("ringe")
        g = f.game
        c, nrm, _ = g.frames[0]
        yaw = math.atan2(nrm[0], nrm[2])
        f.drone.pos = tuple(c[k] - 6 * nrm[k] for k in range(3))
        f.drone.quat = qmul(axis_angle((0, 1, 0), yaw), pitch(25))   # Nase leicht runter = vorwärts
        f.drone.vel = tuple(6 * nrm[k] for k in range(3))
        fly(f, (0.42, 0.0, 0.0, 0.0), 1.6)
        self.assertIsNone(f.crashed_at, f.crash_reason)
        self.assertEqual(g.count, 1)


# ---------------------------------------------------------------------------------------------- Paket

class PackageTest(unittest.TestCase):
    def setUp(self):
        self.f, self.s = flight("paket", settings={"paket_seed": 3})
        self.g = self.f.game

    def hover(self, x, y, z, seconds):
        """Drohne an einen Punkt setzen und dort halten (Seil, Paket laufen echt)."""
        d = self.f.drone
        for k in range(int(seconds / DT)):
            d.pos, d.vel, d.quat = (x, y, z), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
            if k % 25 == 0:
                self.f.world.focus(d.pos)
            self.g.step(self.f, d.pos, DT)

    def lower(self, a, speed):
        """Über der Adresse mit konstantem Tempo sinken, bis das Paket aufsetzt oder kaputt ist."""
        d = self.f.drone
        y = a["y"] + modes.ROPE + 2.0
        n0 = self.g.idx
        while y > a["y"] + 0.3 and self.g.idx == n0:
            y -= speed * DT
            d.pos, d.vel, d.quat = (a["x"], y, a["z"]), (0.0, -speed, 0.0), (0.0, 0.0, 0.0, 1.0)
            self.f.world.focus(d.pos)
            self.g.step(self.f, d.pos, DT)
        self.hover(a["x"], y, a["z"], 1.0)

    def pick(self):
        st = modes.STATIONS[0]
        self.hover(st["x"], 1.5, st["z"], 0.5)
        self.assertTrue(self.g.carry)

    def test_pick_carry_swing_and_soft_delivery(self):
        g = self.g
        self.assertEqual(len(g.queue), modes.DELIVERIES)
        self.assertFalse(g.carry)
        self.pick()
        self.hover(0.0, 20.0, 0.0, 2.0)                          # hängt am Seil, pendelt aus
        dy = self.f.drone.pos[1] - g.pkg[0][1]
        self.assertAlmostEqual(dy, modes.ROPE, delta=0.15)
        a = g.target
        self.lower(a, 0.6)
        self.assertEqual(g.delivered, 1, g.log)
        self.assertTrue(g.log[-1]["soft"])
        self.assertGreater(g.points, 200)
        self.assertFalse(g.carry)

    def test_hard_landing_breaks(self):
        self.pick()
        a = self.g.target
        self.lower(a, 6.0)
        self.assertEqual(self.g.broken, 1)
        self.assertEqual(self.g.delivered, 0)

    def test_crash_with_package_and_five_addresses(self):
        g = self.g
        self.pick()
        self.f.crash("Test")
        self.assertEqual(g.broken, 1)
        for _ in range(modes.DELIVERIES - 1):
            self.pick()
            self.lower(g.target, 0.6)
        self.assertTrue(g.finished)
        self.assertEqual(g.result["delivered"] + g.result["broken"], modes.DELIVERIES)

    def test_package_makes_drone_heavier(self):
        """Echte Physik: mit Paket sinkt die Drohne beim selben Gas, das ohne Paket schwebt."""
        def sink(carry):
            f, _ = flight("paket", pos=(0.0, 30.0, 0.0))
            fly(f, (0.3, 0, 0, 0), 1.0)                       # einschwingen
            hov = 0.3
            for _ in range(20):                               # Schwebegas suchen (ohne Paket)
                y0 = f.drone.pos[1]
                f.drone.vel = (0.0, 0.0, 0.0)
                fly(f, (hov, 0, 0, 0), 0.3)
                hov += 0.02 * (y0 - f.drone.pos[1])
            if carry:
                g = f.game
                p = f.drone.pos
                g.carry, g.pkg = True, [[p[0], p[1] - modes.ROPE, p[2]], [0.0, 0.0, 0.0]]
            f.drone.vel = (0.0, 0.0, 0.0)
            y0 = f.drone.pos[1]
            fly(f, (hov, 0, 0, 0), 1.0)
            return y0 - f.drone.pos[1]
        free, loaded = sink(False), sink(True)
        self.assertLess(abs(free), 0.6)
        self.assertGreater(loaded - free, 0.4)          # Paket 150 g an 650 g: rund 23 % mehr Gewicht


# ---------------------------------------------------------------------------------------------- Freestyle

class TricksTest(unittest.TestCase):
    def names(self, f, sticks_seq, start=(0.0, 40.0, 0.0)):
        f.drone.pos = start
        g = f.game
        for sticks, sec in sticks_seq:
            fly(f, sticks, sec)
        self.assertIsNone(f.crashed_at, f.crash_reason)
        return [e["name"] for e in g.log]

    def test_flips_and_roll_with_physics(self):
        f, _ = flight("freestyle")
        fwd = self.names(f, [((0.45, 0, 0, 0), 0.5), ((0.3, 0, 1.0, 0), 0.62), ((0.45, 0, 0, 0), 0.6)])
        f, _ = flight("freestyle")
        back = self.names(f, [((0.45, 0, 0, 0), 0.5), ((0.3, 0, -1.0, 0), 0.62), ((0.45, 0, 0, 0), 0.6)])
        f, _ = flight("freestyle")
        roll = self.names(f, [((0.45, 0, 0, 0), 0.5), ((0.3, 0, 0, 1.0), 0.62), ((0.45, 0, 0, 0), 0.6)])
        self.assertEqual(fwd, ["FRONTFLIP"])
        self.assertEqual(back, ["BACKFLIP"])
        self.assertEqual(roll, ["ROLLE"])

    def test_power_loop(self):
        f, _ = flight("freestyle")
        R, y0 = 8.0, 30.0

        def pos(s):
            a = 2 * math.pi * s
            return (0.0, y0 + R - R * math.cos(a), 20.0 + R * math.sin(a))
        names = Path(f).go(pos, lambda s: pitch(-360 * s), 2.2)
        self.assertIn("POWER-LOOP", names)
        self.assertNotIn("BACKFLIP", names)
        self.assertNotIn("FRONTFLIP", names)

    def test_split_s(self):
        f, _ = flight("freestyle")
        P = Path(f)
        roll180 = lambda s: axis_angle((0, 0, 1), math.pi * s)
        names = P.go(lambda s: (0.0, 40.0, 10.0 + 12 * s), lambda s: (0, 0, 0, 1), 0.8)
        names += P.go(lambda s: (0.0, 40.0, 22.0 + 6 * s), roll180, 0.4)
        R = 6.0

        def half_loop(s):                                  # von +z nach unten durch auf -z
            a = math.pi * s
            return (0.0, 40.0 - R + R * math.cos(a), 28.0 + R * math.sin(a))
        names += P.go(half_loop, lambda s: qmul(roll180(1), pitch(-180 * s)), 1.3)
        names += P.go(lambda s: (0.0, 40.0 - 2 * R, 28.0 - 12 * s), lambda s: axis_angle((0, 1, 0), math.pi), 0.8)
        self.assertIn("SPLIT-S", names)

    def test_dive(self):
        f, _ = flight("freestyle")
        P = Path(f)
        names = P.go(lambda s: (5.0, 45.0 - 40 * s, -30.0 + 2 * s), lambda s: pitch(80), 2.6)
        names += P.go(lambda s: (5.0, 5.0, -28.0 + 15 * s), lambda s: (0, 0, 0, 1), 1.0)
        self.assertIn("STURZFLUG", names)
        self.assertGreater(f.game.log[-1]["pts"], 15 * 35)

    def test_flythrough_barn_and_bridge(self):
        f, _ = flight("freestyle")
        P = Path(f)
        a = math.radians(tracks.BARN_YAW)
        n = (math.sin(a), math.cos(a))
        names = P.go(lambda s: (18.0 + n[0] * (-14 + 28 * s) + 3.0 * math.cos(a), 2.4,
                                84.0 + n[1] * (-14 + 28 * s) - 3.0 * math.sin(a)),
                     lambda s: axis_angle((0, 1, 0), a), 2.0)
        names += P.go(lambda s: (64.5, 3.0, 118.0 + 24 * s), lambda s: (0, 0, 0, 1), 2.0)
        self.assertIn("DURCHFLUG SCHEUNE", names)
        self.assertIn("DURCHFLUG BRÜCKE", names)

    def test_proximity_along_wall(self):
        f, _ = flight("freestyle")
        (cx, cy, cz, hx, hy, hz, yaw), _ = next(modes._house_boxes(f.world))
        c, s = math.cos(yaw), math.sin(yaw)
        off = hz + 0.7                                       # 0,7 m neben der Wand, 2 m hoch, 12 m/s

        def pos(t):
            lx = -hx + 2 * hx * t
            return (cx + c * lx + s * off, 2.0, cz - s * lx + c * off)
        p0, p1 = pos(0), pos(1)
        q = axis_angle((0, 1, 0), math.atan2(p1[0] - p0[0], p1[2] - p0[2]))
        names = Path(f).go(pos, lambda t: q, 2 * hx / 12.0)
        names += Path(f).go(lambda t: (p1[0] + (p1[0] - p0[0]) * t, 2.0 + 10 * t, p1[2] + (p1[2] - p0[2]) * t),
                            lambda t: q, 1.0)
        self.assertIn("PROXIMITY", names)

    def test_combo_multiplier_and_crash(self):
        f, s = flight("freestyle")
        g = f.game
        g.add("BACKFLIP", 200)
        g.add("ROLLE", 150)
        g.add("POWER-LOOP", 500)
        self.assertEqual(g.mult, 3)
        g.t = g.combo_t + modes.COMBO_GAP + 0.1
        g.step(f, f.drone.pos, 0.0)
        self.assertEqual(g.score, 850 * 3)
        g.add("BACKFLIP", 200)
        g.add("BACKFLIP", 200)
        f.crash("Test")                                      # Absturz verliert die Kombo
        self.assertEqual(g.score, 850 * 3)
        self.assertEqual(g.combo_n, 0)
        g.t = modes.FREESTYLE_TIME
        g.step(f, f.drone.pos, 0.01)
        self.assertTrue(g.finished)
        self.assertEqual(modes.take_result(f, s)[0], "2 550 PUNKTE")


# ---------------------------------------------------------------------------------------------- Geist

class GhostTest(unittest.TestCase):
    def lap(self, f, lap_time, speed=1.0):
        """Eine Runde vorspielen: Zieldurchflug, alle Tore, Zieldurchflug (Zeiten skaliert)."""
        g = f.game
        n = len(f.world.gates)
        t = f.flight_time
        f.lap_start, f.next_gate = t, 1
        g.step(f, f.drone.pos, 0.0)
        steps = int(lap_time / 0.01)
        for k in range(1, steps + 1):
            f.flight_time = t + k * 0.01
            f.drone.pos = (k * 0.01 * speed, 1.0, 0.0)
            gate = 1 + int((n - 1) * k / steps)
            if gate < n and gate != f.next_gate:
                f.next_gate = gate
            g.step(f, f.drone.pos, 0.01)
        f.next_gate = 0                                       # letztes Tor durch, jetzt wieder das Starttor
        g.step(f, f.drone.pos, 0.0)
        f.flight_time = t + lap_time
        f.last_lap, f.lap_start, f.next_gate = lap_time, t + lap_time, 1
        g.step(f, f.drone.pos, 0.0)

    def test_record_replace_and_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["FREEFLY_GHOST_DIR"] = tmp
            try:
                f, s = flight("race", settings={"ghost_save": True})
                g = f.game
                self.assertIsInstance(g, modes.GhostRace)
                self.assertIsNone(g.best)
                self.lap(f, 30.0)
                self.assertAlmostEqual(g.best["lap"], 30.0)
                self.assertEqual(len(g.best["splits"]), len(f.world.gates) - 1)
                self.assertGreater(len(g.best["samples"]), 30 * 59)
                self.assertTrue(os.path.exists(os.path.join(tmp, "dorfrunde-liftoff.json")))
                self.lap(f, 33.0)                                 # langsamer: Geist bleibt
                self.assertAlmostEqual(g.best["lap"], 30.0)
                self.assertGreater(g.delta[0], 0)                 # rot: langsamer
                self.lap(f, 28.0)                                 # schneller: neuer Geist
                self.assertAlmostEqual(g.best["lap"], 28.0)
                self.assertLess(g.delta[0], 0)
                f2, _ = flight("race")                            # neuer Flug lädt den Geist
                self.assertAlmostEqual(f2.game.best["lap"], 28.0)
                f3, _ = flight("race", physik="classic")          # je Physik ein eigener Geist
                self.assertIsNone(f3.game.best)
                pos, q = modes.ghost_pose(f2.game.best, 14.0)
                self.assertAlmostEqual(pos[0], 14.0 * 28 / 28.0, delta=0.05)
                f2.lap_start, f2.flight_time = 0.0, 14.0
                f2.drone.pos = (50.0, 1.0, 0.0)
                self.assertIsNotNone(f2.game.ghost_now(f2))
                f2.game.show = False
                self.assertIsNone(f2.game.ghost_now(f2))
            finally:
                os.environ.pop("FREEFLY_GHOST_DIR", None)

    def test_autopilot_laps_not_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["FREEFLY_GHOST_DIR"] = tmp
            try:
                f, s = flight("race", settings={"auto": True, "ghost_save": True})
                self.lap(f, 20.0)
                self.assertIsNone(f.game.best)
            finally:
                os.environ.pop("FREEFLY_GHOST_DIR", None)

    def test_bomb_mode_has_no_game(self):
        f, _ = flight("bomb")
        self.assertIsNone(f.game)


if __name__ == "__main__":
    unittest.main()
