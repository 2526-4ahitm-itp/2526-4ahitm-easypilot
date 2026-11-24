"""Strecken des Freiflug-Sims (freefly/tracks.py, world.World(track=...)): ohne Fenster, ohne Liftoff.

Run from simulator/:  python -m unittest autopilot.tests.test_freefly_tracks
"""
import math
import unittest

import numpy as np

from autopilot.freefly import tracks
from autopilot.freefly import world as W

WORLDS = {}


def world(key):
    if key not in WORLDS:
        WORLDS[key] = W.World(track=key)
    return WORLDS[key]


def passes(g, a, b):
    """Dieselbe Prüfung wie game.Flight._gate (Strecke a -> b durch das Tor)."""
    ax, ay, az = g.local(a)
    bx, by, bz = g.local(b)
    if not (az < 0.0 <= bz):
        return False
    t = -az / (bz - az)
    x, y = ax + t * (bx - ax), ay + t * (by - ay)
    return abs(x) <= W.GATE_W / 2 and abs(y) <= W.GATE_H / 2


def axes(g):
    c, s = math.cos(g.yaw), math.sin(g.yaw)
    return np.array((c, 0.0, -s)), np.array((s, 0.0, c))        # quer (rechts), Flugrichtung


class TrackDataTest(unittest.TestCase):
    def test_keys_and_names(self):
        self.assertGreaterEqual(len(tracks.ORDER), 5)
        self.assertEqual(tracks.key("Profi"), "profi")
        self.assertEqual(tracks.key("anfänger"), "anfaenger")
        self.assertEqual(tracks.key("1"), "anfaenger")
        self.assertEqual(tracks.key("gibtsnicht"), "dorfrunde")
        stars = [tracks.TRACKS[k]["stars"] for k in tracks.ORDER]
        self.assertEqual(stars, sorted(stars), "Menü sortiert nach Schwierigkeit")

    def test_no_orange_accent(self):
        """Schwierigkeitsfarben dürfen nicht orange sein (Kamera-Pilot: Orange = Torrahmen)."""
        import colorsys
        for col in tracks.COLORS.values():
            h, s, v = colorsys.rgb_to_hsv(*col)
            self.assertFalse(8 / 360 <= h <= 44 / 360 and s > 0.5 and v > 0.2, col)


class DorfrundeTest(unittest.TestCase):
    def test_unchanged(self):
        """Die Dorfrunde ist die alte Strecke: gleiche Tore wie world.COURSE (Netz und Bestzeiten passen)."""
        w = world("dorfrunde")
        self.assertEqual(len(w.gates), len(W.COURSE))
        for g, (x, z, lift) in zip(w.gates, W.COURSE):
            self.assertEqual((g.x, g.z, g.lift), (x, z, max(lift, 0.25)))
            self.assertEqual((g.kind, g.w, g.h, g.roll, g.n_open), ("std", W.GATE_W, W.GATE_H, 0.0, 1))
            self.assertEqual(g.center, (x, max(lift, 0.25) + W.GATE_H / 2, z))

    def test_default_world_is_dorfrunde(self):
        w = W.World()
        self.assertEqual(w.track, "dorfrunde")
        self.assertTrue(np.array_equal(w.vertices, world("dorfrunde").vertices))
        self.assertEqual(w.boxes, world("dorfrunde").boxes)


class TrackWorldTest(unittest.TestCase):
    def test_same_village(self):
        """Alle Strecken stehen im selben Dorf: dieselben Häuser und Durchflug-Gebäude an derselben Stelle."""
        ref = [(t["name"], tuple(np.round(t["center"], 3))) for t in world("dorfrunde").targets]
        for k in tracks.ORDER:
            got = [(t["name"], tuple(np.round(t["center"], 3))) for t in world(k).targets]
            self.assertEqual(got, ref, k)

    def test_gates_free(self):
        """Kein Tor steckt in einem Haus, Baum oder Dach (Berühren am Fuß ist erlaubt)."""
        for k in tracks.ORDER:
            if k == "dorfrunde":
                continue
            w = world(k)
            b = np.array(w.boxes)
            g0, g1 = w.gate_boxes
            bc, bh = b[:g0, :3], b[:g0, 3:6]
            cs, sn = np.cos(b[:g0, 6]), np.sin(b[:g0, 6])
            for i in range(g0, g1):
                cx, cy, cz, hx, hy, hz, yaw = b[i]
                c, s = math.cos(yaw), math.sin(yaw)
                hx, hy, hz = max(hx - 0.05, 0), max(hy - 0.05, 0), max(hz - 0.05, 0)
                for lx in np.linspace(-hx, hx, 4):
                    for ly in np.linspace(-hy, hy, 7):
                        for lz in (-hz, hz):
                            d = np.array((cx + c * lx + s * lz, cy + ly, cz - s * lx + c * lz)) - bc
                            x, z = cs * d[:, 0] - sn * d[:, 2], sn * d[:, 0] + cs * d[:, 2]
                            q = np.maximum(np.abs(np.stack((x, d[:, 1], z), 1)) - bh, 0)
                            self.assertFalse(np.any((q * q).sum(1) < 1e-6), f"{k}: Torbox {i} steckt in etwas")

    def test_gate_kinds(self):
        kinds = {g.kind for k in tracks.ORDER for g in world(k).gates}
        for kind in ("std", "small", "big", "tilt", "double", "ladder", "flag"):
            self.assertIn(kind, kinds)

    def test_passage(self):
        """Durch die Mitte jeder zählenden Öffnung zählt, daneben und andersherum nicht."""
        for k in tracks.ORDER:
            for i, g in enumerate(world(k).gates):
                q, f = axes(g)
                levels = range(g.n_open) if g.level is None else (g.level,)
                for lv in levels:
                    c = np.array((g.x, g.open_y(lv), g.z))
                    self.assertTrue(passes(g, c - f, c + f), f"{k} Tor {i + 1} Öffnung {lv}")
                    self.assertFalse(passes(g, c + f, c - f), f"{k} Tor {i + 1} rückwärts")
                c = np.array(g.center)
                side = q * (g.w / 2 + 1.0)
                self.assertFalse(passes(g, c + side - f, c + side + f), f"{k} Tor {i + 1} daneben")
                if g.pole is not None:            # außen an der Flagge vorbei zählt nicht
                    p = np.array((g.pole[0], 2.0, g.pole[1]))
                    out = p + (p - c) * np.array((1, 0, 1)) / np.linalg.norm((p - c)[[0, 2]]) * 1.0
                    self.assertFalse(passes(g, out - f, out + f), f"{k} Flagge {i + 1} außen")
                if g.roll:                        # schräges Tor: entlang der gedrehten Achse noch drin
                    u = math.cos(g.roll) * q + math.sin(g.roll) * np.array((0, 1.0, 0))
                    p = c + u * (g.w / 2 - 0.3)
                    self.assertTrue(passes(g, p - f, p + f), f"{k} schräges Tor {i + 1}")

    def test_race_line_clear(self):
        """Die Rennlinie des Autopiloten kommt auf jeder Strecke ohne Berührung um alle Hindernisse."""
        from autopilot.freefly.auto import Autopilot
        from autopilot.sysid import load_model
        rates, thrust = load_model()
        for k in tracks.ORDER:
            ap = Autopilot(world(k), rates, thrust, 0.6, laps=1)
            self.assertEqual(getattr(ap.line, "touching", 0), 0, k)
            n = len(world(k).gates)
            self.assertEqual(len(ap.line.gate_sequence), n + 1, k)


if __name__ == "__main__":
    unittest.main()
