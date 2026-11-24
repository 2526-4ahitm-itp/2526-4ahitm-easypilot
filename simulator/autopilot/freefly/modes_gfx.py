"""3D-Teile der Spielmodi (modes.py): leuchtende Ringe, Paket am Seil, Stationen, Adressen mit Lichtsäule,
halbdurchsichtige Geist-Drohne. Eigenes kleines Shader-Programm, damit gfx.py unverändert bleibt; gezeichnet
wird nach der Welt in den gerade gebundenen Puffer (renderer.vp, renderer.cam_pos), vor dem OSD.
"""
import math

import moderngl
import numpy as np

from ..geometry import qrot
from .gfx import SUN

VS = """
#version 330
uniform mat4 mvp; uniform mat4 model;
in vec3 in_pos; in vec3 in_norm;
out vec3 v_n; out vec3 v_w; out float v_h;
void main() {
    vec4 w = model * vec4(in_pos, 1.0);
    v_w = w.xyz; v_h = in_pos.y;
    v_n = mat3(model) * in_norm;
    gl_Position = mvp * w;
}"""
FS = """
#version 330
uniform vec4 color; uniform float emit; uniform vec3 sun; uniform vec3 cam; uniform int beam;
in vec3 v_n; in vec3 v_w; in float v_h;
out vec4 f;
void main() {
    vec3 n = normalize(v_n);
    if (beam == 1) {                                   // Lichtsäule: oben ausblenden, Rand weich
        float side = abs(dot(n, normalize(cam - v_w)));
        f = vec4(color.rgb, color.a * (1.0 - v_h) * side * side);
        return;
    }
    if (dot(n, cam - v_w) < 0.0) n = -n;
    float d = max(dot(n, sun), 0.0);
    vec3 lit = color.rgb * (0.42 + 0.62 * d);
    vec3 c = mix(lit, color.rgb * 1.25, emit);
    float fog = 1.0 - exp(-distance(v_w, cam) * 0.0038);
    f = vec4(mix(c, vec3(0.74, 0.82, 0.91), fog * (1.0 - emit * 0.7)), color.a);
}"""


def _torus(minor=0.09, seg=48, side=10):
    v = []
    for i in range(seg):
        for j in range(side):
            quad = []
            for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1)):
                a = 2 * math.pi * (i + di) / seg
                b = 2 * math.pi * (j + dj) / side
                cx, cy = math.cos(a), math.sin(a)          # Ring in der x-y-Ebene (Normale = z = Flugrichtung)
                n = (math.cos(b) * cx, math.cos(b) * cy, math.sin(b))
                p = ((1 + minor * math.cos(b)) * cx, (1 + minor * math.cos(b)) * cy, minor * math.sin(b))
                quad.append((p, n))
            for k in (0, 1, 2, 0, 2, 3):
                v.extend((*quad[k][0], *quad[k][1]))
    return np.array(v, dtype="f4")


def _box():
    v = []
    for ax in range(3):
        for sg in (-1, 1):
            n = [0, 0, 0]
            n[ax] = sg
            u, w = [(1, 2), (0, 2), (0, 1)][ax]
            pts = []
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = [0.0, 0.0, 0.0]
                p[ax], p[u], p[w] = sg * 0.5, a * 0.5, b * 0.5
                pts.append(p)
            for k in (0, 1, 2, 0, 2, 3):
                v.extend((*pts[k], *n))
    return np.array(v, dtype="f4")


def _cylinder(seg=24, caps=True):
    """Höhe 0..1, Radius 1."""
    v = []
    for i in range(seg):
        a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        for p, n in (((c0, 0, s0), (c0, 0, s0)), ((c1, 0, s1), (c1, 0, s1)), ((c1, 1, s1), (c1, 0, s1)),
                     ((c0, 0, s0), (c0, 0, s0)), ((c1, 1, s1), (c1, 0, s1)), ((c0, 1, s0), (c0, 0, s0))):
            v.extend((*p, *n))
        if caps:
            for p in ((0, 1, 0), (c0, 1, s0), (c1, 1, s1)):
                v.extend((*p, 0, 1, 0))
    return np.array(v, dtype="f4")


def _drone():
    """Kleine 5"-Drohne fürs Geist-Bild: Rumpf, X-Arme, vier Propeller-Scheiben (Nase = +z)."""
    parts = []
    B = _box().reshape(-1, 6)
    C = _cylinder(16).reshape(-1, 6)

    def put(mesh, scale, rot_y=0.0, off=(0, 0, 0)):
        m = mesh.copy()
        m[:, 0:3] *= scale
        c, s = math.cos(rot_y), math.sin(rot_y)
        x, z = m[:, 0].copy(), m[:, 2].copy()
        m[:, 0], m[:, 2] = c * x + s * z, -s * x + c * z
        nx, nz = m[:, 3].copy(), m[:, 5].copy()
        m[:, 3], m[:, 5] = c * nx + s * nz, -s * nx + c * nz
        m[:, 0:3] += off
        parts.append(m)
    put(B, (0.07, 0.035, 0.16))
    put(B, (0.05, 0.05, 0.05), off=(0, 0.035, 0.07))                    # Kamera
    for k in range(4):
        a = math.radians(45 + 90 * k)
        put(B, (0.02, 0.012, 0.3), rot_y=a)
        px, pz = 0.15 * math.sin(a), 0.15 * math.cos(a)
        put(C, (0.065, 0.006, 0.065), off=(px, 0.02, pz))
    return np.concatenate(parts).astype("f4").ravel()


def _gl(m):
    return np.ascontiguousarray(m.T, dtype="f4").tobytes()


def _model(pos, scale=(1, 1, 1), yaw=0.0, quat=None, axes=None):
    M = np.eye(4)
    if quat is not None:
        R = np.array([qrot(quat, (1, 0, 0)), qrot(quat, (0, 1, 0)), qrot(quat, (0, 0, 1))]).T
    elif axes is not None:
        R = np.array(axes).T
    else:
        c, s = math.cos(yaw), math.sin(yaw)
        R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])          # wie world.box: lokal z -> (sin, 0, cos)
    M[:3, :3] = R * np.asarray(scale, dtype="f8")[None, :]
    M[:3, 3] = pos
    return M


class ModeGfx:
    def __init__(self, renderer):
        self.r = renderer
        ctx = renderer.ctx
        self.prog = ctx.program(vertex_shader=VS, fragment_shader=FS)
        self.prog["sun"].value = tuple(float(v) for v in SUN)
        self.mesh = {}
        for name, data in (("torus", _torus()), ("box", _box()), ("cyl", _cylinder()), ("tube", _cylinder(24, False)),
                           ("drone", _drone())):
            vbo = ctx.buffer(data.tobytes())
            self.mesh[name] = ctx.vertex_array(self.prog, [(vbo, "3f 3f", "in_pos", "in_norm")])

    def _draw(self, mesh, M, color, emit=0.0, beam=0):
        p = self.prog
        p["model"].write(_gl(M))
        p["color"].value = tuple(color)
        p["emit"].value = emit
        p["beam"].value = beam
        self.mesh[mesh].render()

    def draw(self, flight, now):
        g = getattr(flight, "game", None)
        if g is None:
            return
        ghost = g.ghost_now(flight) if hasattr(g, "ghost_now") else None
        items = g.draw_items(now, flight.drone.pos)
        if not items and ghost is None:
            return
        r, ctx = self.r, self.r.ctx
        p = self.prog
        p["mvp"].write(_gl(r.vp))
        p["cam"].value = tuple(float(v) for v in r.cam_pos)
        ctx.enable(moderngl.DEPTH_TEST | moderngl.BLEND)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        pulse = 0.5 + 0.5 * math.sin(now * 6.0)
        glow = []                                    # durchsichtig: nach allem Festen zeichnen
        for it in items:
            kind = it[0]
            if kind == "ring":
                (x, y, z, yaw, R), nxt = it[1], it[2]
                col = (1.0, 0.25 + 0.2 * pulse, 0.9, 1.0) if nxt else (1.0, 0.78, 0.18, 1.0)
                M = _model((x, y, z), (R, R, R * 1.6), math.radians(yaw))
                self._draw("torus", M, col, emit=0.75 if nxt else 0.55)
                glow.append(("torus", _model((x, y, z), (R * 1.03, R * 1.03, R * 3.0), math.radians(yaw)),
                             (col[0], col[1], col[2], 0.18 + (0.15 * pulse if nxt else 0.0)), 1.0, 0))
            elif kind == "ring_pop":
                (x, y, z, yaw, R), age = it[1], it[2]
                k = 1.0 + age * 1.6
                glow.append(("torus", _model((x, y, z), (R * k, R * k, R), math.radians(yaw)),
                             (1.0, 0.95, 0.6, max(0.0, 0.8 * (1 - age / 0.5))), 1.0, 0))
            elif kind == "station":
                s, active = it[1], it[2]
                self._draw("cyl", _model((s["x"], s["y"] + 0.01, s["z"]), (2.0, 0.05, 2.0)), (0.15, 0.45, 0.95, 1.0),
                           emit=0.35 + (0.3 * pulse if active else 0.0))
                for dx, dz, dy, sz in ((0.9, -0.5, 0.2, 0.4), (1.1, 0.0, 0.2, 0.4), (0.95, 0.45, 0.2, 0.4),
                                       (1.0, -0.1, 0.6, 0.38)):
                    self._draw("box", _model((s["x"] + dx * 1.6, s["y"] + dy, s["z"] + dz * 1.6), (sz, sz, sz), 0.3),
                               (0.72, 0.52, 0.3, 1.0))
                if active:
                    glow.append(("tube", _model((s["x"], s["y"], s["z"]), (1.6, 40.0, 1.6)),
                                 (0.3, 0.6, 1.0, 0.35), 0.0, 1))
            elif kind == "address":
                a, carrying = it[1], it[2]
                col = (0.2, 1.0, 0.45, 1.0) if carrying else (0.6, 0.9, 0.7, 1.0)
                self._draw("cyl", _model((a["x"], a["y"] + 0.02, a["z"]), (a["r"], 0.04, a["r"])), col,
                           emit=0.5 + 0.4 * pulse)
                self._draw("tube", _model((a["x"], a["y"] + 0.02, a["z"]), (a["r"] * 0.7, 0.1, a["r"] * 0.7)),
                           (1, 1, 1, 1.0), emit=0.8)
                glow.append(("tube", _model((a["x"], a["y"], a["z"]), (a["r"] * 0.9, 45.0, a["r"] * 0.9)),
                             (0.3, 1.0, 0.5, 0.42 if carrying else 0.22), 0.0, 1))
            elif kind in ("package", "package_left"):
                pos = it[1]
                self._draw("box", _model((pos[0], pos[1], pos[2]), (0.34, 0.26, 0.34)), (0.74, 0.53, 0.3, 1.0))
                self._draw("box", _model((pos[0], pos[1], pos[2]), (0.35, 0.27, 0.06)), (0.9, 0.85, 0.6, 1.0))
                if kind == "package":                       # Seil von der Drohne zum Paket
                    top = it[2]
                    d = np.subtract(top, (pos[0], pos[1] + 0.13, pos[2]))
                    L = float(np.linalg.norm(d))
                    if L > 0.05:
                        yv = d / L
                        xv = np.cross(yv, (0.0, 0.0, 1.0)) if abs(yv[2]) < 0.9 else np.cross(yv, (1.0, 0.0, 0.0))
                        xv /= np.linalg.norm(xv)
                        zv = np.cross(xv, yv)
                        M = _model((pos[0], pos[1] + 0.13, pos[2]), (0.012, L, 0.012), axes=(xv, yv, zv))
                        self._draw("tube", M, (0.15, 0.15, 0.15, 1.0))
        if ghost is not None:
            pos, q, alpha = ghost
            glow.append(("drone", _model(pos, (2.2, 2.2, 2.2), quat=q), (0.55, 0.95, 1.0, min(0.6, alpha * 1.3)), 0.8, 0))
        if glow:
            ctx.depth_mask = False
            for mesh, M, col, emit, beam in glow:
                self._draw(mesh, M, col, emit, beam)
            ctx.depth_mask = True
        ctx.disable(moderngl.BLEND)
