"""FPV-Look und Grafik-Stufen des Freiflug-Sims (freefly/look.py, freefly/gfx.py): ohne Fenster.

Run from simulator/:  python -m unittest autopilot.tests.test_freefly_look
Die gfx-Teile brauchen moderngl/pygame und werden ohne sie übersprungen (CI).
"""
import math
import unittest

import numpy as np

from autopilot.freefly import look
from autopilot.freefly import world as W

try:
    from autopilot.freefly import gfx
except ImportError:                     # CI ohne moderngl/pygame
    gfx = None

_WORLD = []


def world():
    if not _WORLD:
        _WORLD.append(W.World())
    return _WORLD[0]


class Settings(unittest.TestCase):
    def test_defaults_look_like_before(self):
        s = {}
        look.ensure(s)
        self.assertEqual((s["look"], s["grafik"], s["sicht"]), ("sauber", "hoch", "auto"))
        q = look.quality(s)
        self.assertEqual((q["taps"], q["fog_k"], q["far"], q["scale"], q["msaa"]), (9, 0.0038, 1500.0, 1.0, 4))
        self.assertEqual(look.context_samples(s), 4)                  # Bildschirm wie bisher mit 4x MSAA
        s["look"] = "analog"
        self.assertEqual(look.context_samples(s), 0)

    def test_keeps_saved_values(self):
        s = {"look": "analog", "grafik": "schnell", "vib": False}
        look.ensure(s)
        self.assertEqual((s["look"], s["grafik"], s["vib"]), ("analog", "schnell", False))
        s["look"] = "kaputt"
        look.ensure(s)
        self.assertEqual(s["look"], "sauber")

    def test_change_cycles(self):
        s = {}
        look.ensure(s)
        seen = []
        for _ in range(3):
            self.assertTrue(look.change(s, "look", 1))
            seen.append(s["look"])
        self.assertEqual(seen, ["digital", "analog", "sauber"])
        self.assertFalse(look.change(s, "tilt", 1))
        look.change(s, "sicht", 1)
        self.assertEqual(look.quality(s)["far"], 250.0)

    def test_menu_values_complete(self):
        s = {}
        look.ensure(s)
        vals = look.menu_values(s)
        for it in look.MENU:
            if it["kind"] != "action":
                self.assertIn(it["key"], vals)


class Signal(unittest.TestCase):
    def test_blocked_by_houses(self):
        w = world()
        ant = np.array((W.SPAWN[0], 1.6, W.SPAWN[2]))
        self.assertEqual(look._blocked(w, ant, ant + (0.0, 30.0, 0.0)), 0)       # senkrecht nach oben: frei
        n = [look._blocked(w, ant, np.array((x, 3.0, z))) for x in range(-150, 151, 50) for z in range(-100, 301, 50)]
        self.assertGreater(max(n), 0, "irgendwo im Dorf stehen Häuser zwischen Start und Drohne")

    def test_nearest(self):
        w = world()
        i = len(w.boxes) // 2
        c = w.bc[i]
        w.focus(c)
        self.assertLess(look._nearest(w, c), 0.01)                                # in der Box: 0
        p = c + np.array((0.0, w.bh[i][1] + 5.0, 0.0))
        w.focus(p)
        self.assertLessEqual(look._nearest(w, p), 5.0 + 1e-6)


@unittest.skipIf(gfx is None, "moderngl/pygame fehlen")
class Lens(unittest.TestCase):
    def test_forward_inverts_shader_mapping(self):
        k, aspect = 0.2, 16 / 9
        rc2 = 1 + 1 / aspect ** 2
        for ox, oy in ((0.1, 0.2), (0.9, -0.5), (-1.0, 0.0), (0.7, 0.95)):
            q = np.array((ox, oy / aspect))                         # Bildpunkt -> Quelle (wie POST_FS)
            r2 = q @ q
            src = q * (1 + k * r2) / (1 + k * rc2)
            sx, sy = src[0], src[1] * aspect
            bx, by = gfx.lens_forward(sx, sy, k, aspect)
            self.assertAlmostEqual(bx, ox, places=5)
            self.assertAlmostEqual(by, oy, places=5)

    def test_corner_and_center(self):
        k, aspect = 0.26, 1.6
        rc2 = 1 + 1 / aspect ** 2
        self.assertEqual(gfx.lens_forward(0.0, 0.0, k, aspect), (0.0, 0.0))
        cx, cy = gfx.lens_forward(1.0, 1.0, k, aspect)              # Ecke bleibt Ecke
        self.assertAlmostEqual(cx, 1.0, places=5)
        self.assertAlmostEqual(cy, 1.0, places=5)
        ex, _ = gfx.lens_forward((1 + k) / (1 + k * rc2), 0.0, k, aspect)   # waagrechter Rand = Sichtfeld
        self.assertAlmostEqual(ex, 1.0, places=5)


@unittest.skipIf(gfx is None, "moderngl/pygame fehlen")
class Lod(unittest.TestCase):
    def test_blob_detection(self):
        w = world()
        v = w.vertices
        n = len(v) // 3
        tri = v[:n * 3, :3].reshape(n, 3, 3)
        mat = np.rint(v[0:n * 3:3, 11]).astype(int)
        starts = gfx._blob_starts(tri, mat)
        self.assertGreater(len(starts), 300)                         # Laubkronen und Büsche
        self.assertTrue(all(b - a >= 80 for a, b in zip(starts, starts[1:])))
        self.assertTrue(all((mat[s0:s0 + 80] == 4).all() for s0 in starts))
        self.assertGreater(len(starts) * 80 / max(1, np.count_nonzero(mat == 4)), 0.6)


if __name__ == "__main__":
    unittest.main()
