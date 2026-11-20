"""Lageanzeige im OSD (Taste O, Menü „Lageanzeige“): auf einen Blick, wie die Drohne in der Luft liegt.

- künstlicher Horizont (Roll und Nick) als rundes Instrument, Himmel blau, Boden braun, Nick-Leiter alle 10°
- Kompassband oben (Gierrichtung, Marke zum nächsten Tor bzw. Bomben-Ziel)
- Tempo-Leiste links, Höhen-Leiste rechts (mit Steig-/Sinkrate)
- kleines 3D-Modell der Drohne (vorne rote Propeller, Kamera), dreht sich mit der echten Lage;
  die Kamera dahinter folgt der Gierrichtung mit etwas Verzögerung, die Scheibe darunter bleibt waagrecht, N zeigt nach Norden
- Minikarte (Taste/Menü „Minikarte“): „vorne ist oben“, Blickfeld, Tore (nächstes magenta) bzw. Bomben-Ziele

Alles mit eigenen kleinen Shadern (Horizont, Kompass, Karte je ein Viereck; Drohne in einen kleinen Offscreen-Puffer),
damit es kaum Bildrate kostet. Die Lage-Werte selbst kommen aus lage_data(); dieselben Werte schickt remote.py
als Telemetrie ans Studio (roll/pitch/yaw/alt/speed/vz), dashboard/sim.js zeichnet daraus dieselbe Anzeige.
"""
import math

import moderngl
import numpy as np
import pygame

from ..geometry import body_axes
from .gfx import gl, perspective, view_matrix
from .remote import attitude

QUAD_VS = """
#version 330
uniform vec2 screen; uniform vec4 rect;
in vec2 in_uv; out vec2 v_p;
void main() {
    v_p = vec2(in_uv.x * 2.0 - 1.0, 1.0 - in_uv.y * 2.0);         // -1..1, y nach oben
    vec2 p = (in_uv - 0.5) * rect.zw + rect.xy;
    gl_Position = vec4(p.x / screen.x * 2.0 - 1.0, 1.0 - p.y / screen.y * 2.0, 0.0, 1.0);
}"""

HORIZON_FS = """
#version 330
uniform float roll, pitch, range, px;
in vec2 v_p; out vec4 f;
void main() {
    float r = length(v_p);
    float edge = 1.0 - smoothstep(1.0 - px, 1.0, r);
    if (edge <= 0.0) discard;
    float c = cos(roll), s = sin(roll);
    vec2 q = vec2(c * v_p.x + s * v_p.y, -s * v_p.x + c * v_p.y);   // Horizont dreht gegen die Rollrichtung
    float deg = q.y * range + degrees(pitch);                      // 0 = Horizont, + = Himmel
    float aa = px * range;
    vec3 sky = mix(vec3(0.26, 0.56, 0.90), vec3(0.10, 0.28, 0.62), clamp(deg / 90.0, 0.0, 1.0));
    vec3 gnd = mix(vec3(0.62, 0.40, 0.20), vec3(0.36, 0.22, 0.10), clamp(-deg / 90.0, 0.0, 1.0));
    vec3 col = mix(gnd, sky, smoothstep(-aa, aa, deg));
    col = mix(col, vec3(1.0), 1.0 - smoothstep(aa * 0.9, aa * 2.2, abs(deg)));
    float k = floor(deg / 10.0 + 0.5);
    float m = abs(deg - k * 10.0);
    float hw = mod(k, 2.0) == 0.0 ? 0.34 : 0.18;
    if (k != 0.0 && abs(k) <= 9.0 && abs(q.x) < hw)
        col = mix(col, vec3(1.0), 0.8 * (1.0 - smoothstep(aa * 0.4, aa * 1.4, m)));
    col = mix(col, vec3(0.04, 0.05, 0.08), smoothstep(0.94 - px, 0.94, r));
    f = vec4(col, edge * 0.92);
}"""

COMPASS_FS = """
#version 330
uniform float yaw, span, px; uniform sampler2D tex;
in vec2 v_p; out vec4 f;
void main() {
    float deg = yaw + v_p.x * span * 0.5;
    vec4 lab = texture(tex, vec2(deg / 360.0, (1.0 - v_p.y) * 0.5));   // N, NO, 30 ... (einmal gezeichnet)
    float dpp = span * 0.5 * px;                                   // Grad pro Pixel
    float fade = 1.0 - smoothstep(0.75, 1.0, abs(v_p.x));
    float a5 = abs(deg - 5.0 * floor(deg / 5.0 + 0.5));
    float a15 = abs(deg - 15.0 * floor(deg / 15.0 + 0.5));
    float len = a15 < 2.5 ? 0.42 : 0.22;
    float tick = (1.0 - smoothstep(dpp * 0.6, dpp * 1.6, a5)) * step(v_p.y, -1.0 + len);
    vec4 bg = vec4(0.0, 0.0, 0.0, 0.38);
    vec4 col = mix(bg, vec4(1.0, 1.0, 1.0, 0.9), tick);
    col = vec4(mix(col.rgb, lab.rgb, lab.a), lab.a + col.a * (1.0 - lab.a));
    f = vec4(col.rgb, col.a * fade);
}"""

MAP_FS = """
#version 330
uniform sampler2D tex; uniform vec2 pos; uniform float yaw, radius, hfov, px; uniform vec3 box;
in vec2 v_p; out vec4 f;
void main() {
    float r = length(v_p);
    float edge = 1.0 - smoothstep(1.0 - px, 1.0, r);
    if (edge <= 0.0) discard;
    vec2 fw = vec2(sin(yaw), cos(yaw)), rt = vec2(cos(yaw), -sin(yaw));
    vec2 w = pos + radius * (v_p.x * rt + v_p.y * fw);
    vec2 uv = vec2((w.x - box.x) / box.z, (box.y + box.z - w.y) / box.z);
    vec3 col = (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) ? vec3(0.24, 0.38, 0.20) : texture(tex, uv).rgb;
    float ang = atan(v_p.x, v_p.y);
    if (abs(ang) < hfov * 0.5) col = mix(col, vec3(1.0, 0.95, 0.7), 0.22 * (1.0 - r));     // Blickfeld
    col = mix(col, vec3(0.04, 0.05, 0.08), smoothstep(0.95 - px, 0.95, r));
    f = vec4(col, edge * 0.88);
}"""

MODEL_VS = """
#version 330
uniform mat4 vp; uniform mat3 rot; uniform vec4 place;
in vec3 in_pos; in vec3 in_norm; in vec3 in_col; out vec3 v_col; out vec3 v_n;
void main() {
    v_col = in_col; v_n = rot * in_norm;
    vec4 c = vp * vec4(rot * in_pos, 1.0);
    c.xy = c.xy * place.zw + place.xy * c.w;              // ins Feld in der Ecke schieben (statt Viewport)
    c.z = (-1.0 + (c.z / c.w + 1.0) * 0.01) * c.w;        // Tiefe ganz vorne (Welt: erst ab 5 cm), ohne Löschen
    gl_Position = c;
}"""
MODEL_FS = """
#version 330
uniform vec3 light; uniform float alpha;
in vec3 v_col; in vec3 v_n; out vec4 f;
void main() {
    float d = max(dot(normalize(v_n), light), 0.0);
    f = vec4(v_col * (0.42 + 0.7 * d), alpha);
}"""


# ---------------------------------------------------------------- Drohnen-Modell (Körper-Koordinaten: x rechts, y oben, z vorne)

def _box(out, c, h, col, yaw=0.0):
    cs, sn = math.cos(yaw), math.sin(yaw)
    rot = lambda v: (cs * v[0] + sn * v[2], v[1], -sn * v[0] + cs * v[2])
    for axis in range(3):
        for sign in (-1, 1):
            n = [0.0, 0.0, 0.0]
            n[axis] = sign
            u, v = [(1, 2), (0, 2), (0, 1)][axis]
            corners = []
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = [0.0, 0.0, 0.0]
                p[axis] = sign * h[axis]
                p[u], p[v] = a * h[u], b * h[v]
                corners.append(rot(p))
            nr = rot(n)
            for i in (0, 1, 2, 0, 2, 3):
                p = corners[i]
                out.append((c[0] + p[0], c[1] + p[1], c[2] + p[2], *nr, *col))


def _cyl(out, c, r, hh, col, n=20):
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p0, p1 = (math.cos(a0) * r, math.sin(a0) * r), (math.cos(a1) * r, math.sin(a1) * r)
        nm = (math.cos((a0 + a1) / 2), 0.0, math.sin((a0 + a1) / 2))
        top, bot = c[1] + hh, c[1] - hh
        for p, y in ((p0, bot), (p1, bot), (p1, top), (p0, bot), (p1, top), (p0, top)):
            out.append((c[0] + p[0], y, c[2] + p[1], *nm, *col))
        for y, ny, (pa, pb) in ((top, 1.0, (p0, p1)), (bot, -1.0, (p1, p0))):
            for p in ((0.0, 0.0), pa, pb):
                out.append((c[0] + p[0], y, c[2] + p[1], 0.0, ny, 0.0, *col))


def drone_mesh():
    """-> (feste Teile, Propeller-Scheiben) als float32-Arrays (pos, normal, farbe)."""
    solid, props = [], []
    carbon, dark = (0.24, 0.24, 0.27), (0.08, 0.08, 0.09)
    _box(solid, (0, 0, 0), (0.038, 0.016, 0.08), carbon)                     # Rahmen-Mitte
    _box(solid, (0, 0.032, -0.012), (0.032, 0.017, 0.055), (1.0, 0.55, 0.1))   # Haube (orange)
    _box(solid, (0, 0.022, 0.084), (0.022, 0.022, 0.016), dark)              # Kamera vorne
    _cyl_z(solid, (0, 0.022, 0.104), 0.012, 0.006, (0.25, 0.45, 0.9))        # Linse
    _box(solid, (0, 0.05, -0.07), (0.004, 0.03, 0.004), dark)                # Antenne hinten
    arm = 0.115
    for sx in (-1, 1):
        for sz in (-1, 1):
            yaw = math.atan2(sx, sz)
            _box(solid, (sx * arm / 2, 0, sz * arm / 2), (0.011, 0.007, arm * 0.72), carbon, yaw)
            _cyl(solid, (sx * arm, 0.016, sz * arm), 0.02, 0.016, (0.62, 0.63, 0.68))
            front = sz > 0
            _disc(props, (sx * arm, 0.036, sz * arm), 0.068, (1.0, 0.16, 0.1) if front else (0.7, 0.72, 0.78))
    return np.array(solid, "f4"), np.array(props, "f4")


def _disc(out, c, r, col, n=28):
    """Propellerkreis: flache Scheibe (eine Lage, überlagert sich beim Durchscheinen nicht selbst)."""
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        for x, z in ((0.0, 0.0), (math.cos(a0) * r, math.sin(a0) * r), (math.cos(a1) * r, math.sin(a1) * r)):
            out.append((c[0] + x, c[1], c[2] + z, 0.0, 1.0, 0.0, *col))


def _cyl_z(out, c, r, hh, col, n=14):
    """Zylinder entlang z (Linse)."""
    tmp = []
    _cyl(tmp, (0, 0, 0), r, hh, col, n)
    for x, y, z, nx, ny, nz, *k in tmp:
        out.append((c[0] + x, c[1] + z, c[2] + y, nx, nz, ny, *k))


def ground_mesh():
    """Waagrechte Scheibe unter der Drohne mit Nordpfeil (+z) und Kreuz."""
    out = []
    y, R = -0.075, 0.2
    n = 40
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        for p in ((0, 0), (math.cos(a0) * R, math.sin(a0) * R), (math.cos(a1) * R, math.sin(a1) * R)):
            out.append((p[0], y, p[1], 0, 1, 0, 0.35, 0.42, 0.5))
    _box(out, (0, y + 0.001, 0), (0.003, 0.0005, R * 0.95), (0.75, 0.8, 0.85))
    _box(out, (0, y + 0.001, 0), (R * 0.95, 0.0005, 0.003), (0.75, 0.8, 0.85))
    for p in ((-0.03, R * 0.78), (0.03, R * 0.78), (0.0, R * 1.05)):           # Nordpfeil
        out.append((p[0], y + 0.002, p[1], 0, 1, 0, 1.0, 0.3, 0.25))
    return np.array(out, "f4")


def lage_data(flight):
    """Lage-Werte wie in der Studio-Telemetrie (remote.py): Grad, m, km/h, m/s."""
    d = flight.drone
    roll, pitch, yaw = attitude(d.quat)
    v = d.vel
    return {"roll": roll, "pitch": pitch, "yaw": yaw, "alt": d.pos[1], "vz": v[1],
            "speed": math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) * 3.6, "quat": tuple(d.quat)}


LIGHT = tuple(float(v) for v in np.array((0.35, 0.85, -0.4)) / np.linalg.norm((0.35, 0.85, -0.4)))
DIRS = {0: "N", 45: "NO", 90: "O", 135: "SO", 180: "S", 225: "SW", 270: "W", 315: "NW"}


BATCH_N = 128           # höchstens so viele Rechtecke/Punkte pro Zeichenaufruf
BATCH_VS = """
#version 330
uniform vec2 screen; uniform vec4 geo[%d]; uniform vec4 col[%d]; uniform vec2 ext[%d];
in vec2 in_c; out vec2 v_uv; out vec4 v_col; flat out float v_dot;
void main() {
    vec4 g = geo[gl_InstanceID];                       // Mitte x, y, halbe Breite, halbe Höhe
    vec2 e = ext[gl_InstanceID];                       // Winkel (rad, im Uhrzeigersinn), runder Punkt (1)
    v_col = col[gl_InstanceID];
    v_dot = e.y;
    v_uv = in_c;
    vec2 p = in_c * g.zw;
    float c = cos(e.x), s = sin(e.x);
    p = vec2(c * p.x - s * p.y, s * p.x + c * p.y) + g.xy;
    gl_Position = vec4(p.x / screen.x * 2.0 - 1.0, 1.0 - p.y / screen.y * 2.0, 0.0, 1.0);
}""" % (BATCH_N, BATCH_N, BATCH_N)
BATCH_FS = """
#version 330
in vec2 v_uv; in vec4 v_col; flat in float v_dot; out vec4 f;
void main() {
    float a = v_col.a;
    if (v_dot > 1.5) {                                 // Ring (osd.py): v_dot = 2 + Ringdicke relativ zum Radius
        float r = length(v_uv); float aa = fwidth(r); float t = v_dot - 2.0;
        a *= (1.0 - smoothstep(1.0 - aa, 1.0, r)) * smoothstep(1.0 - t - aa, 1.0 - t, r);
    } else if (v_dot > 0.5) { float r = length(v_uv); float aa = fwidth(r); a *= 1.0 - smoothstep(1.0 - aa, 1.0, r); }
    f = vec4(v_col.rgb, a);
}"""


class Batch:
    """Viele einfarbige Rechtecke und runde Punkte in einem Zeichenaufruf (Instanzen). Die Daten gehen als
    Uniform-Felder mit: ein Puffer-Upload pro Bild kostet unter Apples OpenGL-auf-Metal ~1 ms (Synchronisierung)."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.prog = ctx.program(vertex_shader=BATCH_VS, fragment_shader=BATCH_FS)
        quad = np.array([(-1, -1), (1, -1), (1, 1), (-1, -1), (1, 1), (-1, 1)], "f4")
        self.vao = ctx.vertex_array(self.prog, [(ctx.buffer(quad.tobytes()), "2f", "in_c")])
        self.geo = np.zeros((BATCH_N, 4), "f4")
        self.col = np.zeros((BATCH_N, 4), "f4")
        self.ext = np.zeros((BATCH_N, 2), "f4")
        self.n = 0

    def clear(self):
        self.n = 0

    def add(self, cx, cy, w, h, col, angle=0.0, dot=False):
        """Wie Renderer.sprite: Mitte, Größe in Pixeln, Winkel im Uhrzeigersinn."""
        if self.n >= BATCH_N:
            self.flush(None)
        i = self.n
        self.geo[i] = (cx, cy, w / 2, h / 2)
        self.col[i] = col
        self.ext[i] = (angle, float(dot))           # False/0 Rechteck, True/1 Punkt, 2 + Dicke = Ring
        self.n += 1

    def flush(self, size):
        if not self.n:
            return
        if size is not None:
            self.size = size
        self.prog["screen"].value = tuple(float(x) for x in self.size)
        self.prog["geo"].write(self.geo.tobytes())
        self.prog["col"].write(self.col.tobytes())
        self.prog["ext"].write(self.ext.tobytes())
        self.vao.render(instances=self.n)
        self.n = 0


class Lage:
    """Zeichnet die Lageanzeige über das Bild (nach Hud.draw)."""

    def __init__(self, renderer, world):
        self.r, self.world = renderer, world
        ctx = renderer.ctx
        quad = ctx.buffer(np.array([0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1], "f4").tobytes())
        self.progs = {}
        for name, fs in (("hor", HORIZON_FS), ("cmp", COMPASS_FS), ("map", MAP_FS)):
            p = ctx.program(vertex_shader=QUAD_VS, fragment_shader=fs)
            self.progs[name] = (p, ctx.vertex_array(p, [(quad, "2f", "in_uv")]))
        self.model = ctx.program(vertex_shader=MODEL_VS, fragment_shader=MODEL_FS)
        solid, props = drone_mesh()
        fmt = "3f 3f 3f"
        names = ("in_pos", "in_norm", "in_col")
        self.solid = ctx.vertex_array(self.model, [(ctx.buffer(solid.tobytes()), fmt, *names)])
        self.props = ctx.vertex_array(self.model, [(ctx.buffer(props.tobytes()), fmt, *names)])
        self.ground = ctx.vertex_array(self.model, [(ctx.buffer(ground_mesh().tobytes()), fmt, *names)])
        self.cam_yaw = None
        self.map_tex, self.map_box = self._map_texture()
        self.symbol = self._symbol_texture()
        self.batch = Batch(ctx)
        self._texts = {}
        self._statics = {}                         # Texturen der unveränderlichen Teile (je Bildgröße)

    # ------------------------------------------------------------ einmalige Texturen

    def _map_texture(self):
        w = self.world
        b = np.array(w.boxes, float)
        x0, x1 = b[:, 0].min() - 30, b[:, 0].max() + 30
        z0, z1 = b[:, 2].min() - 30, b[:, 2].max() + 30
        span = max(x1 - x0, z1 - z0)
        n = 1024
        k = n / span
        surf = pygame.Surface((n, n))
        surf.fill((62, 98, 52))
        P = lambda x, z: ((x - x0) * k, (z0 + span - z) * k)
        for ax, az, bx, bz, rw in w.road_segs:
            pygame.draw.line(surf, (70, 70, 74), P(ax, az), P(bx, bz), max(2, int(rw * k)))
        order = np.argsort(b[:, 1] + b[:, 4])                     # hohe Teile zuletzt
        for cx, cy, cz, hx, hy, hz, yaw in b[order]:
            if cy + hy < 0.3:
                continue
            area = 4 * hx * hz
            c, s = math.cos(yaw), math.sin(yaw)
            pts = [P(cx + c * dx + s * dz, cz - s * dx + c * dz) for dx, dz in
                   ((-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz))]
            if area < 2.5 and cy + hy > 2.5:                       # Baum, Mast
                pygame.draw.circle(surf, (34, 70, 32), P(cx, cz), max(2, 1.6 * k))
            else:
                v = int(min(215, 120 + (cy + hy) * 10))
                pygame.draw.polygon(surf, (v, v - 6, v - 14), pts)
        tex = self.r.texture(surf)
        tex.build_mipmaps()
        tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        return tex, (x0, z0, span)

    def _symbol_texture(self):
        """Festes Drohnen-Symbol und Roll-Skala für den Horizont (Grafik einmal, dann nur skaliert)."""
        n = 512
        big = pygame.Surface((n, n), pygame.SRCALPHA)
        c, R = n / 2, n / 2 * 0.94
        for a in (-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60):
            t = math.radians(a)
            l = 0.13 if a % 30 == 0 else 0.07
            p0 = (c + math.sin(t) * R, c - math.cos(t) * R)
            p1 = (c + math.sin(t) * R * (1 - l), c - math.cos(t) * R * (1 - l))
            pygame.draw.line(big, (255, 255, 255, 230), p0, p1, 6 if a % 30 == 0 else 4)
        orange = (255, 150, 30, 255)
        w = 16
        for a, b in (((c - 0.46 * n / 2, c), (c - 0.14 * n / 2, c)), ((c - 0.14 * n / 2, c), (c, c + 0.09 * n / 2)),
                     ((c, c + 0.09 * n / 2), (c + 0.14 * n / 2, c)), ((c + 0.14 * n / 2, c), (c + 0.46 * n / 2, c))):
            pygame.draw.line(big, (0, 0, 0, 170), a, b, w + 8)
        for a, b in (((c - 0.46 * n / 2, c), (c - 0.14 * n / 2, c)), ((c - 0.14 * n / 2, c), (c, c + 0.09 * n / 2)),
                     ((c, c + 0.09 * n / 2), (c + 0.14 * n / 2, c)), ((c + 0.14 * n / 2, c), (c + 0.46 * n / 2, c))):
            pygame.draw.line(big, orange, a, b, w)
        pygame.draw.circle(big, orange, (c, c), 10)
        return self.r.texture(pygame.transform.smoothscale(big, (256, 256)))

    # ------------------------------------------------------------ zeichnen

    def _quad(self, name, cx, cy, w, h, **uni):
        p, vao = self.progs[name]
        p["screen"].value = tuple(float(v) for v in self.r.size)
        p["rect"].value = (cx, cy, w, h)
        for k, v in uni.items():
            p[k].value = v
        vao.render()

    def _txt(self, key, now, text):
        """Wechselnde Zahlen nur mit 15 Hz neu setzen: jede neue Zeichenkette kostet ~0,1 ms (Schrift + Textur)."""
        hit = self._texts.get(key)
        if hit is None or now - hit[0] >= 1 / 15 or now < hit[0]:
            self._texts[key] = hit = (now, text)
        return hit[1]

    def draw(self, hud, flight, settings, now, dt, left_busy=False):
        r, T, S, B = self.r, hud.text, hud.shapes, self.batch
        W, H = r.size
        s = hud.scale()
        L = lage_data(flight)
        bomb = settings.get("mode") == "bomb"
        r.begin_2d()
        B.clear()
        R = 100 * s
        hx, hy = W / 2 - 330 * s, H - 30 * s - R                  # Horizont: unten, links der Sticks
        mx, my = W / 2 + 330 * s, H - 30 * s - R                  # 3D-Drohne: unten, rechts der Sticks
        cw, ch, cy = 560 * s, 44 * s, 136 * s                     # Kompassband oben
        so = settings.get("osd") or {}
        if so.get("gross") and so.get("zeit"):
            cy = 180 * s                                          # unter der großen Uhr (osd.py, Zuschauer)
        span = 120.0

        # 1) Shader-Flächen
        o = settings.get("osd") or {k: True for k in ("horizont", "lkompass", "leisten", "drohne3d", "karte")}
        if o["horizont"]:
            self._quad("hor", hx, hy, 2 * R, 2 * R, roll=math.radians(L["roll"]), pitch=math.radians(L["pitch"]),
                       range=60.0, px=2.0 / (2 * R))
        if o["lkompass"]:
            self._static(hud, s, cw, ch, span).use(0)
            self._quad("cmp", W / 2, cy, cw, ch, yaw=float(L["yaw"]), span=span, px=2.0 / cw)
        mm = self._minimap(hud, flight, settings, now, bomb, L) if o["karte"] else None

        # 2) Rechtecke und Punkte (ein Zeichenaufruf)
        goal = self._goal(flight, bomb)
        if goal is not None and o["lkompass"]:                     # Richtung zum nächsten Tor / Ziel
            brg = math.degrees(math.atan2(goal[0] - flight.drone.pos[0], goal[2] - flight.drone.pos[2]))
            off = ((brg - L["yaw"] + 180) % 360 - 180) / (span / 2)
            col = (1, 0.15, 0.1, 1) if bomb else (1, 0.25, 0.9, 1)
            B.add(W / 2 + max(-1.0, min(1.0, off)) * cw / 2 * 0.95, cy + ch / 2 + 2 * s, 14 * s, 14 * s, col, dot=True)
        if o["lkompass"]:
            B.add(W / 2, cy - ch / 2 - 1 * s, 2 * s, 8 * s, (1, 0.6, 0.12, 1))
        bh = 300 * s
        bx = (540 if left_busy else 46) * s
        top = 50.0 if L["alt"] < 45 else 100.0 if L["alt"] < 95 else 200.0
        bars = ((bx, L["speed"], 120.0, 20, "TEMPO", "km/h", (0.35, 0.9, 1.0, 0.9), True, None),
                (W - 46 * s, L["alt"], top, 10 if top <= 50 else 20, "HÖHE", "m", (0.5, 1.0, 0.55, 0.9), False,
                 self._txt("vz", now, f"{L['vz']:+.1f} m/s"))) if o["leisten"] else ()
        for b in bars:
            self._bar_fill(s, b[0], H * 0.5, bh, b[1], b[2], b[6])
        B.flush(r.size)

        # 3) Bilder und Schrift
        if o["horizont"]:
            r.sprite(self.symbol, hx, hy, 2 * R, 2 * R)
            a = -math.radians(L["roll"])                              # Roll-Zeiger dreht mit dem Horizont
            r.sprite(S.arrow, hx + math.sin(a) * R * 0.8, hy - math.cos(a) * R * 0.8, 22 * s, 22 * s, angle=a,
                     tint=(1, 0.6, 0.12, 1))
            T.draw(self._txt("lage", now, f"LAGE   Roll {L['roll']:+.0f}°   Nick {L['pitch']:+.0f}°"), hx,
                   hy - R - 16 * s, int(17 * s))
        if o["drohne3d"]:
            T.draw(self._txt("dir", now, f"DROHNE   Richtung {L['yaw']:.0f}° {self._dir(L['yaw'])}"), mx,
                   my - R - 16 * s, int(17 * s))
        if o["lkompass"]:
            r.sprite(S.arrow, W / 2, cy + ch / 2 + 12 * s, 20 * s, 20 * s, tint=(1, 0.6, 0.12, 1))
        for b in bars:
            self._bar_text(hud, s, now, b[0], H * 0.5, bh, *b[1:6], b[7], b[8])
        if mm is not None:
            mm()

        # 4) 3D-Drohne (eigene Tiefe im Feld)
        if o["drohne3d"]:
            self._model(flight, mx, my, 2 * R, dt, hud)

    @staticmethod
    def _dir(yaw):
        return DIRS[int(((yaw + 22.5) % 360) // 45) * 45]

    @staticmethod
    def _goal(flight, bomb):
        if bomb:
            t = flight.target_info()
            return t["center"] if t and t["alive"] else None
        return flight.world.gates[flight.next_gate].center

    def _bar_fill(self, s, x, cy, h, val, top, col):
        f = max(0.0, min(1.0, val / top))
        if f > 0:
            self.batch.add(x, cy + h / 2 - f * h / 2, 14 * s, f * h, col)

    def _bar_text(self, hud, s, now, x, cy, h, val, top, step, title, unit, left, sub):
        T, w = hud.text, 14 * s
        y0 = cy + h / 2
        side, anchor = (1, "left") if left else (-1, "right")
        tex, tw, th = self._bar_static(hud, s, h, top, step, title, unit, left)
        self.r.sprite(tex, x, cy, tw, th)                         # Rahmen, Skala, Beschriftung (einmal gezeichnet)
        f = max(0.0, min(1.0, val / top))
        txt = self._txt(title, now, f"{val:.1f}" if unit == "m" and top <= 60 else f"{val:.0f}")
        T.draw(txt, x + side * (w / 2 + 40 * s), y0 - f * h, int(20 * s), anchor)
        if sub:
            T.draw(sub, x, y0 + 36 * s, int(13 * s), tint=(1, 1, 1, 0.7), bold=False)

    # ------------------------------------------------------------ unveränderliche Teile als Textur

    def _label(self, hud, text, size, bold=True, col=(255, 255, 255), alpha=255):
        """Schrift wie ui.Text (weiß mit dunklem Rand), als pygame-Fläche."""
        f = hud.text.font(size, bold)
        fg = f.render(text, True, col)
        pad = max(2, size // 14)
        surf = pygame.Surface((fg.get_width() + 2 * pad, fg.get_height() + 2 * pad), pygame.SRCALPHA)
        bg = f.render(text, True, (0, 0, 0))
        bg.set_alpha(150)
        for dx in (-pad, 0, pad):
            for dy in (-pad, 0, pad):
                if dx or dy:
                    surf.blit(bg, (pad + dx, pad + dy))
        surf.blit(fg, (pad, pad))
        if alpha < 255:
            surf.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        return surf

    def _blit(self, surf, lab, x, y, anchor="center"):
        w, h = lab.get_size()
        x = {"center": x - w / 2, "left": x, "right": x - w}[anchor]
        surf.blit(lab, (round(x), round(y - h / 2)))

    def _bar_static(self, hud, s, h, top, step, title, unit, left):
        key = ("bar", round(s, 4), round(h), top, title, left)
        hit = self._statics.get(key)
        if hit:
            return hit
        w = 14 * s
        tw, th = int(130 * s), int(h + 100 * s)
        surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        x, cy = tw / 2, th / 2
        y0, y1 = cy + h / 2, cy - h / 2
        pygame.draw.rect(surf, (0, 0, 0, 102), pygame.Rect(round(x - w / 2 - 3 * s), round(y1 - 3 * s),
                                                            round(w + 6 * s), round(h + 6 * s)))
        side, anchor = (1, "left") if left else (-1, "right")
        for v in range(0, int(top) + 1, step):
            y = y0 - v / top * h
            pygame.draw.rect(surf, (255, 255, 255, 178), pygame.Rect(round(x + side * (w / 2 + 6 * s) - 4 * s),
                                                                     round(y - s), max(1, round(8 * s)), max(1, round(2 * s))))
            if v % (step * 2) == 0:
                self._blit(surf, self._label(hud, str(v), int(13 * s), False, alpha=190), x + side * (w / 2 + 14 * s), y, anchor)
        self._blit(surf, self._label(hud, title, int(15 * s), alpha=217), x, y1 - 22 * s)
        self._blit(surf, self._label(hud, unit, int(13 * s), False, alpha=178), x, y0 + 18 * s)
        hit = (self.r.texture(surf), tw, th)
        self._statics[key] = hit
        return hit

    def _static(self, hud, s, cw, ch, span):
        """Kompassband-Beschriftung: 360° als Streifen (wiederholt), der Shader verschiebt ihn."""
        key = ("cmp", round(s, 4), round(cw), round(ch), span)
        hit = self._statics.get(key)
        if hit:
            return hit
        tw, th = int(round(cw * 360 / span)), int(round(ch))
        surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        for deg in range(0, 360, 15):
            big = deg in DIRS
            col = (255, 216, 77) if deg == 0 else (255, 255, 255)
            lab = self._label(hud, DIRS.get(deg, str(deg)), int((19 if big else 14) * s), big, col, 242 if big else 178)
            for x in (deg / 360 * tw, deg / 360 * tw + tw, deg / 360 * tw - tw):
                self._blit(surf, lab, x, th * 0.36)
        tex = self.r.texture(surf)
        tex.repeat_x, tex.repeat_y = True, False
        self._statics[key] = tex
        return tex

    def _model(self, flight, cx, cy, size, dt, hud):
        r, ctx = self.r, self.r.ctx
        q = flight.drone.quat
        right, up, fwd = body_axes(q)
        yaw = math.atan2(fwd[0], fwd[2])
        if abs(fwd[1]) > 0.97:                                     # senkrecht: Richtung aus der Oberseite
            yaw = math.atan2(-up[0], -up[2]) if fwd[1] > 0 else math.atan2(up[0], up[2])
        if self.cam_yaw is None:
            self.cam_yaw = yaw
        d = (yaw - self.cam_yaw + math.pi) % (2 * math.pi) - math.pi
        self.cam_yaw += d * min(1.0, dt / 0.7)                    # Kamera folgt der Gierrichtung weich
        D = 0.9
        eye = np.array((-math.sin(self.cam_yaw) * D * 0.82, D * 0.5, -math.cos(self.cam_yaw) * D * 0.82))
        r_, u_, f_ = r.look_axes(eye, (0.0, -0.02, 0.0))
        proj, _ = perspective(38.0, 1.0, 0.45, 1.6)                # eng ums Modell: feine Tiefenstufen
        vp = gl(proj @ view_matrix(eye, r_, u_, f_))
        rot = np.array([right, up, fwd], dtype="f4")              # Zeilen = Körperachsen; als GLSL-mat3 (spaltenweise) = Spalten
        # direkt ins Bild: kein eigener Puffer und kein Löschen der Tiefe (beides kostet auf Apple-GPUs spürbar,
        # weil das MSAA-Bild zwischengespeichert bzw. der Durchgang geteilt wird). Stattdessen liegt das Modell in
        # einem winzigen Tiefenbereich ganz vorne (MODEL_VS) und verdeckt nur sich selbst.
        W, H = r.size
        hud.rect(cx, cy, size, size, (0.02, 0.03, 0.06, 0.6))
        r.sprite(hud.shapes.frame, cx, cy, size, size, tint=(1, 1, 1, 0.35))
        m = self.model
        m["vp"].write(vp)
        m["place"].value = (cx / W * 2 - 1, 1 - cy / H * 2, size / W, size / H)
        m["light"].value = LIGHT
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        m["rot"].write(np.eye(3, dtype="f4").tobytes())
        m["alpha"].value = 0.55
        self.ground.render()                                       # ohne Tiefentest (begin_2d), liegt unten
        ctx.enable(moderngl.DEPTH_TEST)
        m["rot"].write(rot.tobytes())
        m["alpha"].value = 1.0
        self.solid.render()
        fb = r.target
        fb.depth_mask = False
        m["alpha"].value = 0.8
        self.props.render()
        fb.depth_mask = True
        r.begin_2d()

    def _minimap(self, hud, flight, settings, now, bomb, L):
        """Karte zeichnen, Punkte in den Stapel legen; -> Funktion für Schrift und Pfeil (nach dem Stapel)."""
        r, T, S, B = self.r, hud.text, hud.shapes, self.batch
        W = r.size[0]
        s = hud.scale()
        R = 118 * s
        o = settings.get("osd") or {}
        down = 150 if o.get("werte") and not o.get("leisten") else 0      # Platz für ALT/GES (osd.py) rechts oben
        cx, cy = W - 30 * s - R, (92 + down) * s + R
        rad_m = 90.0
        yaw = math.radians(L["yaw"])
        p = flight.drone.pos
        self.map_tex.use(0)
        x0, z0, span = self.map_box
        self._quad("map", cx, cy, 2 * R, 2 * R, pos=(p[0], p[2]), yaw=yaw, radius=rad_m,
                   hfov=math.radians(min(150.0, settings.get("fov", 120))) * 0.75, px=2.0 / (2 * R), box=(x0, z0, span))
        fw, rt = (math.sin(yaw), math.cos(yaw)), (math.cos(yaw), -math.sin(yaw))

        def to_map(x, z, clamp=False):
            dx, dz = x - p[0], z - p[2]
            u, v = (dx * rt[0] + dz * rt[1]) / rad_m, (dx * fw[0] + dz * fw[1]) / rad_m
            d = math.hypot(u, v)
            if d > 0.9:
                if not clamp:
                    return None
                u, v = u / d * 0.9, v / d * 0.9
            return cx + u * R, cy - v * R

        labels = []
        if bomb:
            ent = flight.entities
            if ent is not None:
                idx = np.flatnonzero(ent.alive)
                d = ent.pos[idx][:, [0, 2]] - (p[0], p[2])
                u = (d[:, 0] * rt[0] + d[:, 1] * rt[1]) / rad_m
                v = (d[:, 0] * fw[0] + d[:, 1] * fw[1]) / rad_m
                for i, uu, vv in zip(idx, u, v):
                    if uu * uu + vv * vv < 0.81 and i != flight.target:
                        B.add(cx + uu * R, cy - vv * R, 7 * s, 7 * s, (1, 0.85, 0.4, 0.85), dot=True)
            t = flight.target_info()
            if t and t["alive"]:
                q = to_map(t["center"][0], t["center"][2], clamp=True)
                pulse = 0.7 + 0.3 * math.sin(now * 8)
                B.add(q[0], q[1], 16 * s, 16 * s, (1, 0.12, 0.1, pulse), dot=True)
                labels.append(("ZIEL", q[0], q[1] - 16 * s, int(13 * s), (1, 0.35, 0.3, 1), True))
        else:
            gates = flight.world.gates
            n = len(gates)
            for i, g in enumerate(gates):
                nxt = i == flight.next_gate
                q = to_map(g.x, g.z, clamp=nxt)
                if q is None:
                    continue
                col = (1, 0.25, 0.9, 1) if nxt else (1, 1, 1, 0.75)
                B.add(q[0], q[1], (15 if nxt else 11) * s, (4 if nxt else 3) * s, col, angle=g.yaw - yaw)
                if nxt or i == (flight.next_gate + 1) % n:            # Nummern: nächstes und übernächstes Tor
                    labels.append((str(i + 1), q[0], q[1] - 11 * s, int((15 if nxt else 11) * s),
                                   col if nxt else (1, 1, 1, 0.7), nxt))

        def text():
            for lab, x, y, size, col, bold in labels:
                T.draw(lab, x, y, size, tint=col, bold=bold)
            r.sprite(S.arrow, cx, cy, 20 * s, 20 * s, tint=(1, 0.6, 0.12, 1))         # Drohne, vorne = oben
            na = -yaw                                                                # Norden am Rand
            T.draw("N", cx + math.sin(na) * R * 0.86, cy - math.cos(na) * R * 0.86, int(15 * s), tint=(1, 0.85, 0.3, 1))
        return text
