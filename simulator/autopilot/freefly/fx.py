"""Explosion für den Bomben-Modus: Feuerball, Funken, Rauch, Trümmer, Blitz und Wackeln.

Die Teilchen sind Sprites: pro Frame wird ihr Mittelpunkt mit der Kamera projiziert und die Größe
mit der Brennweite skaliert. Feuer und Funken leuchten additiv, Rauch und Trümmer normal.
"""
import math

import numpy as np
import pygame

import moderngl

G = 9.81


def _soft(size, inner, outer, noise=0.0, seed=0):
    """Weicher runder Fleck: inner (RGBA) in der Mitte, outer am Rand, außen durchsichtig."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size]
    r = np.hypot(x - size / 2 + 0.5, y - size / 2 + 0.5) / (size / 2)
    if noise:
        ang = np.arctan2(y - size / 2, x - size / 2)
        wob = sum(rng.uniform(0.3, 1) * np.sin(k * ang + rng.uniform(0, 6.3)) for k in (3, 5, 7)) / 3
        r = r * (1 + noise * wob)
    t = np.clip(r, 0, 1)[..., None]
    col = np.array(inner, float) * (1 - t) + np.array(outer, float) * t
    alpha = np.clip(1 - r, 0, 1) ** 1.5
    img = np.dstack([col[..., :3], (col[..., 3:] * alpha[..., None])[..., 0]])
    surf = pygame.image.frombytes(np.ascontiguousarray((img * 255).astype(np.uint8)).tobytes(), (size, size), "RGBA")
    return surf


def _chunk(size, seed):
    rng = np.random.default_rng(seed)
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    pts = [(size / 2 + math.cos(a) * size * rng.uniform(0.25, 0.48), size / 2 + math.sin(a) * size * rng.uniform(0.25, 0.48))
           for a in np.sort(rng.uniform(0, 2 * math.pi, 6))]
    pygame.draw.polygon(s, (255, 255, 255, 255), pts)
    return s


class FxTextures:
    def __init__(self, r):
        self.fire = r.texture(_soft(128, (1.0, 0.95, 0.7, 1.0), (1.0, 0.35, 0.05, 0.9), noise=0.25, seed=1))
        self.smoke = r.texture(_soft(128, (0.35, 0.33, 0.32, 0.85), (0.5, 0.5, 0.5, 0.5), noise=0.35, seed=2))
        self.spark = r.texture(_soft(32, (1.0, 1.0, 0.85, 1.0), (1.0, 0.6, 0.1, 1.0)))
        self.chunk = r.texture(_chunk(48, 3))


class Explosion:
    def __init__(self, pos, size=1.0, seed=None):
        rng = np.random.default_rng(seed)
        self.pos = np.array(pos, float)
        self.age = 0.0
        self.size = size
        p = []

        def rand_dir(up=0.0):
            v = rng.normal(size=3)
            v /= np.linalg.norm(v)
            v[1] = abs(v[1]) * (1 - up) + up if up else v[1]
            return v / np.linalg.norm(v)
        k = size ** 0.5                                     # Anzahl wächst langsamer als die Größe
        n = int(34 * k)
        for _ in range(n):                                  # Feuerball
            p.append(["fire", self.pos + rand_dir() * rng.uniform(0, 1.0) * size, rand_dir(0.3) * rng.uniform(2, 9) * size,
                      0.0, rng.uniform(0.5, 1.2), rng.uniform(1.5, 3.0) * size, rng.uniform(4, 8) * size, rng.uniform(0, 6.3), rng.uniform(-2, 2)])
        for _ in range(int(22 * k)):                        # Rauch (kommt etwas später)
            p.append(["smoke", self.pos + rand_dir() * rng.uniform(0, 1.5) * size, rand_dir(0.6) * rng.uniform(1, 3.5) * size,
                      -rng.uniform(0.15, 0.5), rng.uniform(2.5, 5.0), rng.uniform(1.5, 2.5) * size, rng.uniform(4, 7) * size, rng.uniform(0, 6.3), rng.uniform(-0.5, 0.5)])
        for _ in range(int(30 * k)):                        # Funken
            p.append(["spark", self.pos.copy(), rand_dir(0.2) * rng.uniform(12, 30) * size,
                      0.0, rng.uniform(0.4, 1.0), 0.25 * size, 0.1 * size, 0.0, 0.0])
        for _ in range(int(26 * k)):                        # Trümmer (Ziegel, Putz, Holz)
            col = (0.55, 0.22, 0.14) if rng.random() < 0.4 else (0.75, 0.72, 0.66) if rng.random() < 0.6 else (0.3, 0.22, 0.15)
            p.append(["chunk", self.pos + rand_dir() * rng.uniform(0, 1.0), rand_dir(0.4) * rng.uniform(5, 16) * k,
                      0.0, rng.uniform(4.0, 8.0), rng.uniform(0.15, 0.45) * k, col, rng.uniform(0, 6.3), rng.uniform(-12, 12)])
        self.p = p

    @property
    def done(self):
        return self.age > 8.0

    def update(self, dt):
        self.age += dt
        for q in self.p:
            kind, pos, vel = q[0], q[1], q[2]
            q[3] += dt
            if q[3] < 0:
                continue
            if kind == "fire":
                vel *= math.exp(-3.0 * dt)
                vel[1] += 2.5 * dt                          # heißes Gas steigt
            elif kind == "smoke":
                vel *= math.exp(-0.8 * dt)
                vel[1] += 1.2 * dt
            elif kind == "spark":
                vel[1] -= G * dt
                vel *= math.exp(-1.0 * dt)
            else:
                vel[1] -= G * dt
                if pos[1] <= q[5] * 0.5 and vel[1] < 0:     # liegen bleiben
                    vel[:] = (vel[0] * 0.3, -vel[1] * 0.25, vel[2] * 0.3)
                    q[8] *= 0.3
            pos += vel * dt
            q[7] += q[8] * dt

    def flash(self):
        return max(0.0, 1.0 - self.age / 0.35) * 0.8

    def shake(self):
        return 0.6 * self.size * math.exp(-self.age * 4.0)


def draw(renderer, tex, explosions):
    """Alle Teilchen als Sprites (hinten zuerst), Feuer additiv."""
    if not explosions:
        return
    W, H = renderer.size
    focal = (W / 2) / renderer.tan[0]
    view = renderer.view
    items = []
    for e in explosions:
        for q in e.p:
            kind, pos, _, age, life = q[0], q[1], q[2], q[3], q[4]
            if age < 0 or age > life:
                continue
            c = view @ np.array((*pos, 1.0))
            depth = -c[2]
            if depth < 0.3:
                continue
            k = age / life
            if kind == "chunk":
                size, alpha, tint = q[5], min(1.0, (life - age) / 1.0), q[6]
            else:
                size = q[5] + (q[6] - q[5]) * (1 - (1 - k) ** 2)
                if kind == "fire":
                    alpha, tint = (1 - k) ** 1.3, (1.0, 0.85 - 0.4 * k, 0.6 - 0.5 * k)
                elif kind == "smoke":
                    alpha, tint = min(1.0, age * 3) * (1 - k) * 0.55, (0.55, 0.53, 0.5)
                else:
                    alpha, tint = 1 - k, (1.0, 0.9, 0.6)
            sx = W / 2 + c[0] / depth * focal
            sy = H / 2 - c[1] / depth * focal
            px = size * focal / depth
            if px < 0.8 or sx < -px or sx > W + px or sy < -px or sy > H + px:
                continue
            items.append((depth, kind, sx, sy, px, q[7], (*tint, alpha)))
    items.sort(key=lambda it: -it[0])
    # gebündelt: pro Textur ein Draw-Call (Reihenfolge hinten->vorne bleibt je Art erhalten)
    batch = {}
    for depth, kind, sx, sy, px, rot, tint in items:
        c, sn = math.cos(rot) * px / 2, math.sin(rot) * px / 2
        quad = []
        for (u, v) in ((0, 0), (1, 0), (1, 1), (0, 0), (1, 1), (0, 1)):
            ox, oy = (u * 2 - 1), (v * 2 - 1)
            x = sx + c * ox - sn * oy
            y = sy + sn * ox + c * oy
            quad.append((x / W * 2 - 1, 1 - y / H * 2, u, v, *tint))
        batch.setdefault(kind, []).extend(quad)
    ctx = renderer.ctx
    ctx.disable(moderngl.DEPTH_TEST)
    ctx.enable(moderngl.BLEND)
    prog = _program(ctx)
    for kind in ("smoke", "chunk", "fire", "spark"):
        verts = batch.get(kind)
        if not verts:
            continue
        if kind in ("fire", "spark"):
            ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE
        else:
            ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        getattr(tex, kind).use(0)
        data = np.array(verts, dtype="f4").tobytes()
        buf = ctx.buffer(data)
        vao = ctx.vertex_array(prog, [(buf, "2f 2f 4f", "in_pos", "in_uv", "in_col")])
        vao.render()
        _TRASH.append((vao, buf))         # erst nach dem flip freigeben (end_frame), sonst Segfault am Mac

    ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA


_PROG = {}
_TRASH = []          # GL-Objekte, die in diesem Frame gezeichnet wurden
_OLD = []            # ... und die aus dem vorigen Frame


def end_frame():
    """Nach pygame.display.flip(): GL-Objekte des vorletzten Frames freigeben."""
    global _TRASH, _OLD
    for vao, buf in _OLD:
        vao.release()
        buf.release()
    _OLD, _TRASH = _TRASH, []


def _program(ctx):
    if "p" not in _PROG:
        _PROG["p"] = ctx.program(vertex_shader="""
#version 330
in vec2 in_pos; in vec2 in_uv; in vec4 in_col; out vec2 v_uv; out vec4 v_col;
void main() { v_uv = in_uv; v_col = in_col; gl_Position = vec4(in_pos, 0.0, 1.0); }""", fragment_shader="""
#version 330
uniform sampler2D tex; in vec2 v_uv; in vec4 v_col; out vec4 f;
void main() { f = texture(tex, v_uv) * v_col; }""")
        _PROG["p"]["tex"].value = 0
    return _PROG["p"]
