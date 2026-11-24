"""OpenGL-Darstellung (moderngl): Himmel, Wiese, Welt mit Schatten und Materialien, 2D-Sprites fürs UI.

Die Schattenkarte wird einmal beim Start gerendert (die Welt steht still), kostet pro Frame also
nur das Abtasten im Shader.
"""
import math

import moderngl
import numpy as np
import pygame

from ..geometry import qrot

SUN = np.array((0.42, 0.78, -0.46))
SUN = SUN / np.linalg.norm(SUN)
SKY_TOP = (0.26, 0.47, 0.82)
SKY_HORIZON = (0.74, 0.82, 0.91)

COMMON = """
uniform sampler2DShadow shadow; uniform vec3 sun; uniform vec3 fog_col; uniform vec3 cam;
uniform vec4 craters[24]; uniform int n_craters;
uniform float fog_k; uniform float fog_end;     // Nebel-Dichte, Sichtweite (Menü „Grafik“; Hoch = wie immer)
#ifndef SHADOW_TAPS
#define SHADOW_TAPS 9
#endif
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float shade(vec4 ls) {
    vec3 p = ls.xyz / ls.w * 0.5 + 0.5;
    if (p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0) return 1.0;
    vec2 o = 1.0 / vec2(textureSize(shadow, 0));
#if SHADOW_TAPS == 1
    return texture(shadow, vec3(p.xy, p.z - 0.0008));
#elif SHADOW_TAPS == 4
    float s = 0.0;
    for (int i = 0; i < 2; i++) for (int j = 0; j < 2; j++)
        s += texture(shadow, vec3(p.xy + (vec2(i, j) - 0.5) * o * 1.6, p.z - 0.0008));
    return s / 4.0;
#else
    float s = 0.0;
    for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++)
        s += texture(shadow, vec3(p.xy + vec2(i, j) * o * 1.3, p.z - 0.0008));
    return s / 9.0;
#endif
}
vec3 light(vec3 albedo, vec3 n, float sh, float ao) {
    float d = max(dot(n, sun), 0.0) * sh;
    vec3 amb = mix(vec3(0.36, 0.34, 0.30), vec3(0.58, 0.68, 0.85), n.y * 0.5 + 0.5);
    return albedo * (vec3(1.0, 0.95, 0.86) * d * 1.0 + amb * 0.55 * ao);
}
// Krater: 1 = Loch (verwerfen), sonst Ruß-Anteil 0..1
float crater(vec3 p, out bool hole) {
    hole = false;
    float burn = 0.0;
    for (int i = 0; i < n_craters; i++) {
        float d = distance(p, craters[i].xyz);
        float r = craters[i].w * (0.75 + 0.5 * vnoise(p.xz * 2.7 + p.y * 3.1 + float(i) * 7.0));
        if (d < r) hole = true;
        burn = max(burn, 1.0 - smoothstep(r, r * 1.55, d));
    }
    return burn;
}
vec3 fog(vec3 c, vec3 p) {
    float d = distance(p, cam);
    return mix(c, fog_col, max(1.0 - exp(-d * fog_k), smoothstep(fog_end * 0.55, fog_end, d)));
}
"""

WORLD_VS = """
uniform mat4 mvp; uniform mat4 light_mvp;
in vec3 in_pos; in vec3 in_norm; in vec3 in_col; in vec2 in_uv; in float in_mat;
#ifdef INST
in vec4 in_inst; in vec3 in_tint;          // Position + Gierwinkel, Lackfarbe (Material 8)
#endif
out vec3 v_pos; out vec3 v_n; out vec3 v_col; out vec2 v_uv; flat out int v_mat; out vec4 v_ls;
void main() {
    vec3 p = in_pos, n = in_norm, col = in_col;
    v_mat = int(in_mat + 0.5);
#ifdef INST
    float c = cos(in_inst.w), s = sin(in_inst.w);
    p = vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z) + in_inst.xyz;
    n = vec3(c * n.x + s * n.z, n.y, -s * n.x + c * n.z);
    if (v_mat == 8) col = in_tint;
#endif
    v_pos = p; v_n = n; v_col = col; v_uv = in_uv;
    v_ls = light_mvp * vec4(p + n * 0.05, 1.0);
    gl_Position = mvp * vec4(p, 1.0);
}"""

WORLD_FS = COMMON + """
uniform int next_gate; uniform int mark; uniform float time;
in vec3 v_pos; in vec3 v_n; in vec3 v_col; in vec2 v_uv; flat in int v_mat; in vec4 v_ls;
out vec4 f;
void main() {
    vec3 n = normalize(v_n);
    vec3 c = v_col;
    vec3 emit = vec3(0.0);
#ifdef INST
    if (v_mat == 6) {                                         // weicher Schatten unter Fahrzeugen/Leuten
        float a = 0.45 * (1.0 - smoothstep(0.35, 1.0, length(v_uv / v_col.xy)));
        f = vec4(0.0, 0.0, 0.0, a);
        return;
    }
    float burn = 0.0;
#else
#ifdef CRATERS
    bool hole;
    float burn = crater(v_pos, hole);
    if (hole) discard;
#else
    float burn = 0.0;
#endif
    if (dot(n, cam - v_pos) < 0.0) {                          // Innenseite (durch ein Loch gesehen)
        n = -n;
        c = vec3(0.55, 0.5, 0.44) * (0.8 + 0.2 * vnoise(v_pos.xy * 3.0));
    }
#endif
    float ao = mix(0.55, 1.0, clamp(v_pos.y / 2.5, 0.0, 1.0));
    float sh = shade(v_ls);
    if (v_mat == 1 && abs(n.y) < 0.5) {                       // Hauswand mit Fenstern
        vec2 cell = vec2(fract(v_uv.x / 2.6), fract(v_uv.y / 3.0));
        float floor_ = floor(v_uv.y / 3.0);
        if (v_uv.y > 0.6 && cell.x > 0.3 && cell.x < 0.7 && cell.y > 0.3 && cell.y < 0.8) {
            bool frame = cell.x < 0.33 || cell.x > 0.67 || cell.y < 0.34 || cell.y > 0.76 || abs(cell.x - 0.5) < 0.012;
            float r = hash(floor(v_uv / vec2(2.6, 3.0)) + floor_);
            c = frame ? vec3(0.95) : mix(vec3(0.12, 0.17, 0.25), vec3(0.45, 0.58, 0.72), r * 0.6 + 0.3 * max(n.x, 0.0));
            ao *= frame ? 1.0 : 0.9;
        }
        c *= 0.95 + 0.05 * vnoise(v_uv * 4.0);
    } else if (v_mat == 2) {                                  // Asphalt mit Mittellinie
        c *= 0.85 + 0.3 * vnoise(v_uv * 6.0) * vnoise(v_uv * 0.7);
        if (abs(v_uv.x) < 0.09 && fract(v_uv.y / 6.0) < 0.5) c = vec3(0.92);
    } else if (v_mat == 3) {                                  // Dachziegel
        c *= 0.8 + 0.2 * step(0.15, fract(v_uv.y * 3.2)) * (0.9 + 0.2 * hash(floor(v_uv * vec2(3.0, 3.2))));
    } else if (v_mat == 4) {
        c *= 0.85 + 0.3 * vnoise(v_pos.xz * 2.0 + v_pos.y);
    } else if (v_mat == 5 && n.y > 0.5) {                     // Startplatz
        float r = length(v_uv);
        if (r > 0.75 && r < 0.95) c = vec3(1.0, 0.55, 0.05);
        if (max(abs(v_uv.x), abs(v_uv.y)) > 1.15) c = fract((v_uv.x + v_uv.y) * 2.0) < 0.5 ? vec3(1.0, 0.8, 0.1) : vec3(0.1);
    } else if (v_mat == 7) {                                  // Holzbretter (senkrecht)
        float board = floor(v_uv.x / 0.32);
        c *= (0.86 + 0.18 * hash(vec2(board, 3.0))) * (0.8 + 0.2 * smoothstep(0.0, 0.06, fract(v_uv.x / 0.32)));
        c *= 0.93 + 0.12 * vnoise(vec2(v_uv.x * 3.0, v_uv.y * 0.4));
    } else if (v_mat == 11) {                                 // Acker: Furchen
        float row = fract(v_uv.y / 0.9);
        float fade = 1.0 - smoothstep(30.0, 120.0, distance(v_pos, cam));
        c *= mix(0.92, 0.75 + 0.35 * smoothstep(0.2, 0.5, row) * (1.0 - smoothstep(0.6, 0.95, row)), fade);
        c *= 0.88 + 0.24 * vnoise(v_uv * 0.15);
    } else if (v_mat == 12) {                                 // Wellblech
        float fade = 1.0 - smoothstep(8.0, 45.0, distance(v_pos, cam));
        c *= 0.92 + 0.1 * sin(v_uv.x * 41.9) * fade;
    } else if (v_mat >= 32) {                                 // Tore
        int idx = v_mat - 32;
        float stripe = step(0.5, fract((v_uv.x + v_uv.y) * 1.25));
        if (mark == 1 && idx == next_gate) {
            float pulse = 0.65 + 0.35 * sin(time * 7.0);
            c = mix(vec3(1.0, 0.15, 0.85), vec3(1.0), stripe * 0.6);
            emit = c * (0.55 + 0.45 * pulse);
        } else if (mark == 1 && idx < next_gate) {
            c = mix(vec3(0.15, 0.75, 0.3), vec3(0.9), stripe * 0.5);
            emit = c * 0.15;
        } else {
            c = mix(vec3(1.0, 0.45, 0.05), vec3(1.0), stripe * 0.75);
            emit = c * 0.2;
        }
    }
    if (v_mat == 9) emit = c * 0.8;                           // Scheinwerfer
    c *= mix(1.0, 0.1, burn);
    vec3 col = light(c, n, sh, ao) + emit;
    f = vec4(fog(col, v_pos), 1.0);
}"""

GROUND_VS = """
#version 330
uniform mat4 mvp; uniform mat4 light_mvp; in vec2 in_xz; out vec3 v_w; out vec4 v_ls;
void main() {
    v_w = vec3(in_xz.x, 0.0, in_xz.y);
    v_ls = light_mvp * vec4(v_w + vec3(0, 0.05, 0), 1.0);
    gl_Position = mvp * vec4(v_w, 1.0);
}"""
GROUND_FS = "#version 330\n" + COMMON + """
in vec3 v_w; in vec4 v_ls; out vec4 f;
void main() {
    vec2 p = v_w.xz;
    float big = vnoise(p * 0.02) * 0.6 + vnoise(p * 0.07) * 0.4;
    float fine = vnoise(p * 1.7) * 0.5 + vnoise(p * 5.3) * 0.5;
    vec3 c = mix(vec3(0.20, 0.40, 0.13), vec3(0.36, 0.52, 0.18), big);
    c = mix(c, vec3(0.45, 0.42, 0.25), smoothstep(0.72, 0.9, vnoise(p * 0.045 + 7.0)) * 0.6);   // trockene Flecken
    c *= 0.86 + 0.28 * fine;
    c *= 0.96 + 0.04 * step(0.5, fract(p.x / 6.0));                                          // Mähstreifen
    float near = 1.0 - smoothstep(18.0, 45.0, distance(v_w, cam));
    if (near > 0.0) {                                                                         // Blumen und Klee
        vec2 g = p * 2.2;
        vec2 cell = floor(g);
        float h = hash(cell + 17.0);
        float meadow = smoothstep(0.45, 0.7, vnoise(p * 0.05 + 3.0));
        if (h > 0.975 - 0.05 * meadow && length(fract(g) - 0.5 - (vec2(hash(cell), hash(cell + 5.0)) - 0.5) * 0.5) < 0.085) {
            float k = hash(cell + 31.0);
            vec3 fl = k < 0.4 ? vec3(0.97, 0.96, 0.9) : k < 0.7 ? vec3(0.98, 0.85, 0.2) : k < 0.85 ? vec3(0.7, 0.45, 0.9) : vec3(0.95, 0.35, 0.3);
            c = mix(c, fl, near);
        }
        c *= 1.0 - 0.12 * near * smoothstep(0.55, 0.8, vnoise(p * 9.0));                  // Grashalme
    }
    bool hole;
    c *= mix(1.0, 0.15, crater(v_w, hole));                    // Brandfleck
    vec3 col = light(c, vec3(0, 1, 0), shade(v_ls), 1.0);
    f = vec4(fog(col, v_w), 1.0);
}"""
SHADOW_VS = """
#version 330
uniform mat4 light_mvp; in vec3 in_pos; out vec3 v_pos;
void main() { v_pos = in_pos; gl_Position = light_mvp * vec4(in_pos, 1.0); }"""
SHADOW_FS = """
#version 330
uniform vec4 craters[24]; uniform int n_craters;
in vec3 v_pos;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
void main() {
    for (int i = 0; i < n_craters; i++) {
        vec3 p = v_pos;
        float r = craters[i].w * (0.75 + 0.5 * vnoise(p.xz * 2.7 + p.y * 3.1 + float(i) * 7.0));
        if (distance(p, craters[i].xyz) < r) discard;
    }
}"""
SKY_VS = """
#version 330
uniform float sky_z;
in vec2 in_ndc; out vec2 v_ndc;
void main() { v_ndc = in_ndc; gl_Position = vec4(in_ndc, sky_z, 1.0); }"""
SKY_FS = """
#version 330
uniform vec3 R; uniform vec3 U; uniform vec3 F; uniform vec2 tanh; uniform vec3 sun;
uniform vec3 top; uniform vec3 hor; in vec2 v_ndc; out vec4 f;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
    vec2 i = floor(p), g = fract(p); g = g * g * (3.0 - 2.0 * g);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), g.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), g.x), g.y);
}
void main() {
    vec3 d = normalize(F + R * v_ndc.x * tanh.x + U * v_ndc.y * tanh.y);
    float h = clamp(d.y, 0.0, 1.0);
    vec3 c = mix(hor, top, pow(h, 0.55));
    float s = max(dot(d, sun), 0.0);
    c += vec3(1.0, 0.9, 0.7) * (pow(s, 600.0) * 2.0 + pow(s, 12.0) * 0.18);
    if (d.y > 0.01) {
        vec2 q = d.xz / (d.y + 0.08) * 1.6;
        float n = vnoise(q) * 0.5 + vnoise(q * 2.1 + 3.0) * 0.3 + vnoise(q * 4.3) * 0.2;
        float cl = smoothstep(0.55, 0.85, n) * smoothstep(0.0, 0.25, d.y);
        c = mix(c, vec3(1.0), cl * 0.75);
    }
    f = vec4(c, 1.0);
}"""
LINE_VS = """
#version 330
uniform mat4 mvp; in vec3 in_pos;
void main() { gl_Position = mvp * vec4(in_pos, 1.0); }"""
LINE_FS = """
#version 330
uniform vec4 color; out vec4 f;
void main() { f = color; }"""
SPRITE_VS = """
#version 330
uniform vec2 screen; uniform vec4 rect; uniform float angle;
in vec2 in_uv; out vec2 v_uv;
void main() {
    v_uv = in_uv;
    vec2 p = (in_uv - 0.5) * rect.zw;
    float c = cos(angle), s = sin(angle);
    p = vec2(c * p.x - s * p.y, s * p.x + c * p.y) + rect.xy;
    gl_Position = vec4(p.x / screen.x * 2.0 - 1.0, 1.0 - p.y / screen.y * 2.0, 0.0, 1.0);
}"""
SPRITE_FS = """
#version 330
uniform sampler2D tex; uniform vec4 tint; in vec2 v_uv; out vec4 f;
void main() { f = texture(tex, v_uv) * tint; }"""


def perspective(hfov_deg, aspect, near=0.05, far=1500.0):
    tx = math.tan(math.radians(hfov_deg) / 2)
    ty = tx / aspect
    m = np.zeros((4, 4))
    m[0, 0], m[1, 1] = 1 / tx, 1 / ty
    m[2, 2], m[2, 3] = -(far + near) / (far - near), -2 * far * near / (far - near)
    m[3, 2] = -1.0
    return m, (tx, ty)


def camera_axes(quat, tilt_deg):
    """Rechts, oben, vorne der FPV-Kamera in Weltkoordinaten (Kamera um tilt nach oben gekippt)."""
    r = np.array(qrot(quat, (1.0, 0.0, 0.0)))
    u = np.array(qrot(quat, (0.0, 1.0, 0.0)))
    f = np.array(qrot(quat, (0.0, 0.0, 1.0)))
    t = math.radians(tilt_deg)
    return r, math.cos(t) * u - math.sin(t) * f, math.cos(t) * f + math.sin(t) * u


def view_matrix(pos, r, u, f):
    p = np.asarray(pos)
    return np.array([[*r, -r @ p], [*u, -u @ p], [*-f, f @ p], [0, 0, 0, 1.0]])


def gl(m):
    return np.ascontiguousarray(m.T, dtype="f4").tobytes()


# Grafik-Stufen (Menü „Grafik“, look.py): Schatten-Abtastung, Sichtweite/Nebel, Zellen-Culling, LOD.
# Ohne set_quality() zeichnet der Renderer wie immer (so bleibt das Kamerabild der Autopiloten gleich).
LEGACY = {"taps": 9, "fog_k": 0.0038, "far": 1500.0, "fog_end": 1e7, "cull": False, "lod_blob": 1e9, "lod_small": 1e9}
CELL = 90.0             # m, Kantenlänge der Zellen fürs Frustum-Culling (wenige Draw-Calls)
SMALL_EDGE = 0.35       # m: Dreiecke mit kürzerer längster Kante fallen in der Ferne weg (Fensterrahmen, Zäune …)


def _blob_starts(tri, mat):
    """Anfänge der Laub-Kugeln aus World.blob (80 Dreiecke: 20 Ikosaeder-Flächen, je 4 Teile).
    Teil 3 jeder Fläche besteht aus den Kantenmitten der Teile 0-2; die LOD-Fläche sind die Ecken."""
    n = len(tri)
    if n < 80:
        return []
    a, b, c = tri[:-3], tri[1:-2], tri[2:-1]
    d = tri[3:]
    ok = (np.all(d[:, 0] == a[:, 1], axis=1) & np.all(d[:, 1] == b[:, 2], axis=1) & np.all(d[:, 2] == c[:, 0], axis=1)
          & np.all(a[:, 1] == b[:, 0], axis=1) & np.all(a[:, 2] == c[:, 0], axis=1) & np.all(b[:, 2] == c[:, 1], axis=1))
    ok = np.concatenate((ok, np.zeros(3, dtype=bool))) & (mat == 4)
    starts, i = [], 0
    cand = np.nonzero(ok)[0]
    okl = ok.tolist()
    for i0 in cand.tolist():
        if i0 < i or i0 + 80 > n:
            continue
        if all(okl[i0 + 4 * k] for k in range(20)):
            starts.append(i0)
            i = i0 + 80
    return starts


class _VaoRef:
    """VAO, das der Renderer austauschen kann (neue Shader-Variante); render() wie ein VAO."""
    def __init__(self, vao):
        self._v = [vao]

    def __getitem__(self, i):
        return self._v[i]

    def __setitem__(self, i, v):
        self._v[i] = v

    def render(self, *a, **k):
        return self._v[0].render(*a, **k)

    def release(self):
        self._v[0].release()


def lens_forward(nx, ny, k, aspect):
    """Quellpunkt (NDC der geraden Szene) -> Bildpunkt nach der Fischaugen-Verzerrung (Umkehrung von
    r_quelle = r (1 + k r²) / (1 + k r_ecke²), Newton)."""
    qx, qy = nx, ny / aspect
    rs = math.hypot(qx, qy)
    if rs < 1e-9:
        return nx, ny
    rc2 = 1.0 + 1.0 / aspect ** 2
    target = rs * (1 + k * rc2)
    r = rs
    for _ in range(6):
        f = r + k * r ** 3 - target
        r -= f / (1 + 3 * k * r * r)
    s = r / rs
    return nx * s, ny * s


class Renderer:
    def __init__(self, ctx, world, size, hfov, tilt, target=None):
        self.ctx, self.hfov, self.tilt = ctx, hfov, tilt
        self.target = target or ctx.screen          # Bildschirm oder Offscreen-Puffer (Kamera-Autopilot)
        self.world = world
        self.q = dict(LEGACY)                        # Grafik-Stufe (set_quality)
        self.lens = 0.0                              # Fischaugen-Stärke k (look.py); 0 = gerade Linse
        self.vsize = None                            # Szenen-Auflösung, wenn sie vom Bildschirm abweicht (look.py)
        self.cells = None                            # Zellen fürs Culling/LOD (set_quality mit cull)
        self._progs = {}
        self.obj = self._obj_prog(False)
        self.inst = ctx.program(vertex_shader="#version 330\n#define INST\n" + WORLD_VS,
                                fragment_shader="#version 330\n#define INST\n" + WORLD_FS)
        self.craters = []
        self.ground = ctx.program(vertex_shader=GROUND_VS, fragment_shader=GROUND_FS)
        self.sky = ctx.program(vertex_shader=SKY_VS, fragment_shader=SKY_FS)
        self.sprite_prog = ctx.program(vertex_shader=SPRITE_VS, fragment_shader=SPRITE_FS)
        self.line_prog = ctx.program(vertex_shader=LINE_VS, fragment_shader=LINE_FS)
        self.line_vao = None
        shadow_prog = ctx.program(vertex_shader=SHADOW_VS, fragment_shader=SHADOW_FS)
        vbo = self.vbo = ctx.buffer(world.vertices.tobytes())
        shadow_vao = ctx.vertex_array(shadow_prog, [(vbo, "3f 36x", "in_pos")])
        g = 3000.0
        quad = np.array([-g, -g, g, -g, g, g, -g, -g, g, g, -g, g], dtype="f4")
        self.ground_vao = ctx.vertex_array(self.ground, [(ctx.buffer(quad.tobytes()), "2f", "in_xz")])
        tri = np.array([-1, -1, 3, -1, -1, 3], dtype="f4")
        self.sky_vao = ctx.vertex_array(self.sky, [(ctx.buffer(tri.tobytes()), "2f", "in_ndc")])
        uv = np.array([0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1], dtype="f4")
        self.sprite_vao = ctx.vertex_array(self.sprite_prog, [(ctx.buffer(uv.tobytes()), "2f", "in_uv")])

        # Schattenkarte: einmal beim Start, neu nur wenn ein Ziel zerstört wurde
        self.light_mvp = self._light_matrix(world.vertices[:, :3])
        self.shadow_tex = ctx.depth_texture((4096, 4096))
        self.shadow_tex.compare_func = "<="
        self.shadow_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.shadow_fbo = ctx.framebuffer(depth_attachment=self.shadow_tex)
        self.shadow_prog, self.shadow_vao = shadow_prog, shadow_vao
        shadow_prog["light_mvp"].write(gl(self.light_mvp))
        self.hidden = []                 # (erster Vertex, Anzahl) zerstörter Ziele
        self.render_shadow()

        for prog in (self.ground, self.inst) + tuple(p for p, _, _ in self._progs.values()):
            self._static(prog)
        self.sky["top"].value, self.sky["hor"].value = SKY_TOP, SKY_HORIZON
        self.sky["sky_z"].value = 0.99999
        self.sky["sun"].value = tuple(SUN)
        self.sprite_prog["tex"].value = 0
        self.inst["mark"].value = 0
        self.set_craters([])
        self.resize(size)

    def set_world(self, world):
        """Andere Strecke (world.World(track=...)): neue Geometrie, gleiche Shader und Texturen."""
        ctx = self.ctx
        self._release_cells()
        for key, (prog, vao, ivao) in self._progs.items():
            vao.release()
        for obj in (self.shadow_vao, self.vbo):
            obj.release()
        self.world = world
        vbo = self.vbo = ctx.buffer(world.vertices.tobytes())
        self.shadow_vao = ctx.vertex_array(self.shadow_prog, [(vbo, "3f 36x", "in_pos")])
        self.light_mvp = self._light_matrix(world.vertices[:, :3])
        self._progs = {k: (p, self._vao(p), None) for k, (p, _, _) in self._progs.items()}
        for prog in (self.shadow_prog, self.ground, self.inst) + tuple(p for p, _, _ in self._progs.values()):
            prog["light_mvp"].write(gl(self.light_mvp))
        self.hidden = []
        if self.q["cull"]:
            self._build_cells()
        self.set_craters([])                      # zeichnet auch die Schattenkarte neu

    # ------------------------------------------------------------ Grafik-Stufen, Shader-Varianten

    def _static(self, prog):
        """Gleichbleibende Uniforms (Licht, Nebel, Schattenkarte) in ein Programm schreiben."""
        for name, val in (("sun", tuple(SUN)), ("fog_col", SKY_HORIZON), ("shadow", 1),
                          ("fog_k", self.q["fog_k"]), ("fog_end", self.q["fog_end"])):
            if name in prog:
                prog[name].value = val
        if "light_mvp" in prog and hasattr(self, "light_mvp"):
            prog["light_mvp"].write(gl(self.light_mvp))

    def _vao(self, prog):
        return self.ctx.vertex_array(prog, [(self.vbo, "3f 3f 3f 2f 1f", "in_pos", "in_norm", "in_col", "in_uv", "in_mat")])

    def _obj_prog(self, craters):
        """Welt-Shader: mit Kratern (discard) nur, wenn es Krater gibt; ohne discard verwirft die Apple-GPU
        verdeckte Pixel vor dem Shader (gleiches Bild, weniger Arbeit)."""
        key = (bool(craters), self.q["taps"])
        if key not in self._progs:
            head = "#version 330\n" + (f"#define SHADOW_TAPS {self.q['taps']}\n")
            prog = self.ctx.program(vertex_shader="#version 330\n" + WORLD_VS,
                                    fragment_shader=head + ("#define CRATERS\n" if craters else "") + WORLD_FS)
            self._progs[key] = (prog, self._vao(prog) if hasattr(self, "vbo") else None, None)
            self._static(prog)
            if "mark" in prog:
                prog["mark"].value = 1
        prog, vao, ivao = self._progs[key]
        if vao is None and hasattr(self, "vbo"):
            vao = self._vao(prog)
            self._progs[key] = (prog, vao, ivao)
        self.obj, self.obj_vao = prog, vao
        return prog

    def _use_obj(self):
        """Passende Welt-Shader-Variante wählen (Krater ja/nein, Schatten-Taps)."""
        self._obj_prog(bool(self.craters))
        if "craters" in self.obj:
            data = np.zeros((24, 4), dtype="f4")
            if self.craters:
                data[:len(self.craters)] = self.craters
            self.obj["craters"].write(data.tobytes())
            self.obj["n_craters"].value = len(self.craters)

    def set_quality(self, q):
        """Grafik-Stufe: dict mit taps (Schatten 9/4/1), fog_k, fog_end, far (m), cull, lod_blob, lod_small (m)."""
        old = self.q
        self.q = {**LEGACY, **q}
        if old["taps"] != self.q["taps"]:
            self.ground = self._ground_prog()
            self.inst_prog_taps()
        for prog in (self.ground, self.inst) + tuple(p for p, _, _ in self._progs.values()):
            self._static(prog)
        self._use_obj()
        if self.q["cull"] and self.cells is None:
            self._build_cells()
        elif not self.q["cull"]:
            self._release_cells()
        self.resize(self.size)

    def _ground_prog(self):
        old = self.ground
        prog = self.ctx.program(vertex_shader=GROUND_VS, fragment_shader=GROUND_FS.replace(
            "#version 330\n", f"#version 330\n#define SHADOW_TAPS {self.q['taps']}\n", 1))
        self._static(prog)
        self._crater_uniforms(prog)
        g = 3000.0
        quad = np.array([-g, -g, g, -g, g, g, -g, -g, g, g, -g, g], dtype="f4")
        self.ground_vao.release()
        self.ground_vao = self.ctx.vertex_array(prog, [(self.ctx.buffer(quad.tobytes()), "2f", "in_xz")])
        old.release()
        return prog

    def inst_prog_taps(self):
        """Fahrzeug-/Personen-Shader mit den neuen Schatten-Taps; die Modelle (entity_vao) bauen ihre VAOs neu."""
        old = self.inst
        self.inst = self.ctx.program(vertex_shader="#version 330\n#define INST\n" + WORLD_VS,
                                     fragment_shader=f"#version 330\n#define INST\n#define SHADOW_TAPS {self.q['taps']}\n"
                                     + WORLD_FS)
        self._static(self.inst)
        self.inst["mark"].value = 0
        for item in getattr(self, "_entity_models", []):
            vbo, ibuf, holder = item
            holder[0].release()
            holder[0] = self.ctx.vertex_array(self.inst, [(vbo, "3f 3f 3f 2f 1f", "in_pos", "in_norm", "in_col", "in_uv",
                                                           "in_mat"), (ibuf, "4f 3f/i", "in_inst", "in_tint")])
        old.release()

    def _crater_uniforms(self, prog):
        if "craters" in prog:
            data = np.zeros((24, 4), dtype="f4")
            if self.craters:
                data[:len(self.craters)] = self.craters
            prog["craters"].write(data.tobytes())
            prog["n_craters"].value = len(self.craters)

    # ------------------------------------------------------------ Zellen (Frustum-Culling) und LOD

    def _release_cells(self):
        if self.cells is not None:
            self.cells["ibo"].release()
            self.cells["lod_vbo"].release()
            for key, (prog, vao, ivao) in self._progs.items():
                if ivao is not None:
                    ivao.release()
                    self._progs[key] = (prog, vao, None)
        self.cells = None

    def _build_cells(self):
        """Dreiecke nach 90-m-Zellen sortieren (Index-Puffer, die Vertices bleiben wie sie sind).
        Je Zelle hintereinander: [Laub fein | kleine Teile | Rest | Laub grob], so ist jede LOD-Stufe
        ein zusammenhängender Bereich: nah = fein+klein+Rest, mittel = klein+Rest+grob, fern = Rest+grob."""
        self._release_cells()
        v = self.world.vertices
        n_tri = len(v) // 3
        tri_pos = v[:n_tri * 3, :3].reshape(n_tri, 3, 3)
        mat = np.rint(v[0:n_tri * 3:3, 11]).astype(int)
        starts = _blob_starts(tri_pos, mat)
        blob = np.zeros(n_tri, dtype=bool)
        lod_tris = []
        for s0 in starts:
            blob[s0:s0 + 80] = True
            t = tri_pos[s0:s0 + 80].reshape(20, 4, 3, 3)
            corners = np.stack((t[:, 0, 0], t[:, 1, 1], t[:, 2, 2]), axis=1)      # (20, 3, 3)
            lod_tris.append((s0, corners))
        edge = np.max(np.linalg.norm(tri_pos - np.roll(tri_pos, 1, axis=1), axis=2), axis=1)
        small = (edge < SMALL_EDGE) & ~blob & (mat < 32)                           # Tore nie weglassen
        # grobe Laub-Vertices anhängen: Farbe/Material vom ersten Teil-Dreieck, Normale der großen Fläche
        lod_v = []
        for s0, corners in lod_tris:
            src = v[s0 * 3:(s0 + 80) * 3].reshape(20, 12, 12)          # 4 Teile x 3 Vertices je Fläche
            c = corners.mean(axis=(0, 1))
            for f in range(20):
                a, b, cc = corners[f]
                nrm = np.cross(b - a, cc - a)
                nrm /= np.linalg.norm(nrm) + 1e-9
                if np.dot(nrm, a - c) < 0:
                    nrm = -nrm
                col = src[f, 9:12, 6:9].mean(axis=0)                  # Mitte-Teil
                for p in (a, b, cc):
                    lod_v.append((*p, *nrm, *col, 0.0, 0.0, 4.0))
        lod_v = np.array(lod_v, dtype="f4").reshape(-1, 12)
        n_lod = len(lod_v) // 3
        all_v = np.concatenate((v, lod_v)) if n_lod else v
        cent = tri_pos.mean(axis=1)
        lod_cent = np.zeros((n_lod, 3))
        for k, (s0, corners) in enumerate(lod_tris):          # ganze Kugel in eine Zelle (keine Lücken an Zellgrenzen)
            mid = corners.mean(axis=(0, 1))
            cent[s0:s0 + 80] = mid
            lod_cent[k * 20:(k + 1) * 20] = mid
        # Gruppe je Dreieck: 0 Laub fein, 1 klein, 2 Rest, 3 Laub grob
        grp = np.where(blob, 0, np.where(small, 1, 2))
        cx = np.floor(np.concatenate((cent[:, 0], lod_cent[:, 0])) / CELL).astype(int)
        cz = np.floor(np.concatenate((cent[:, 2], lod_cent[:, 2])) / CELL).astype(int)
        grp = np.concatenate((grp, np.full(n_lod, 3)))
        idx = np.arange(n_tri + n_lod)
        cell_id = (cx - cx.min()) * 10000 + (cz - cz.min())
        order = np.lexsort((idx, grp, cell_id))
        tri_vert = np.concatenate((np.arange(n_tri * 3).reshape(n_tri, 3),
                                   n_tri * 3 + np.arange(n_lod * 3).reshape(n_lod, 3)))
        indices = tri_vert[order].astype("u4").ravel()
        oc, og = cell_id[order], grp[order]
        allpos = np.concatenate((tri_pos, lod_v[:, :3].reshape(-1, 3, 3))) if n_lod else tri_pos
        cells = []
        bounds = np.nonzero(np.diff(oc))[0] + 1
        for a, b in zip(np.concatenate(([0], bounds)), np.concatenate((bounds, [len(oc)]))):
            g = og[a:b]
            cnt = [int(np.count_nonzero(g == k)) for k in range(4)]
            pts = allpos[order[a:b]].reshape(-1, 3)
            cells.append((int(a) * 3, cnt, pts.min(axis=0), pts.max(axis=0)))
        ctx = self.ctx
        vbo_lod = ctx.buffer(all_v.astype("f4").tobytes())
        ibo = ctx.buffer(indices.tobytes())
        self.cells = {"ibo": ibo, "lod_vbo": vbo_lod, "first": np.array([c[0] for c in cells]),
                      "cnt": np.array([c[1] for c in cells]) * 3,
                      "lo": np.array([c[2] for c in cells]), "hi": np.array([c[3] for c in cells]),
                      "tris": n_tri, "lod_tris": n_lod, "blobs": len(starts), "small": int(small.sum())}

    def _cell_vao(self):
        key = (bool(self.craters), self.q["taps"])
        prog, vao, ivao = self._progs[key]
        if ivao is None:
            ivao = self.ctx.vertex_array(prog, [(self.cells["lod_vbo"], "3f 3f 3f 2f 1f", "in_pos", "in_norm", "in_col",
                                                 "in_uv", "in_mat")], index_buffer=self.cells["ibo"], index_element_size=4)
            self._progs[key] = (prog, vao, ivao)
        return ivao

    def visible_ranges(self, pos):
        """(erster Index, Anzahl) je sichtbarer Zelle, LOD nach Abstand der Zelle zur Kamera."""
        c = self.cells
        m = self.vp
        planes = np.array([m[3] + m[0], m[3] - m[0], m[3] + m[1], m[3] - m[1], m[3] + m[2], m[3] - m[2]])
        lo, hi = c["lo"], c["hi"]
        vis = np.ones(len(lo), dtype=bool)
        for pl in planes:
            pv = np.where(pl[:3] >= 0, hi, lo)                     # Ecke am weitesten in Richtung der Ebene
            vis &= pv @ pl[:3] + pl[3] >= 0
        d = np.linalg.norm(np.maximum(np.maximum(lo - pos, pos - hi), 0.0), axis=1)
        cnt, first = c["cnt"], c["first"]
        q = self.q
        near = d < q["lod_blob"]
        mid = ~near & (d < q["lod_small"])
        out = []
        for i in np.nonzero(vis)[0].tolist():
            f, (n0, n1, n2, n3) = int(first[i]), cnt[i].tolist()
            if near[i]:
                out.append((f, n0 + n1 + n2))
            elif mid[i]:
                out.append((f + n0, n1 + n2 + n3))
            else:
                out.append((f + n0 + n1, n2 + n3))
        return out

    def segments(self):
        """Sichtbare Vertex-Bereiche (ohne zerstörte Ziele)."""
        out, pos = [], 0
        for first, count in sorted(self.hidden):
            if first > pos:
                out.append((pos, first - pos))
            pos = max(pos, first + count)
        n = len(self.world.vertices)
        if pos < n:
            out.append((pos, n - pos))
        return out

    def set_craters(self, craters):
        """Liste von (x, y, z, Radius): Löcher in Häusern, Brandflecken am Boden."""
        self.craters = list(craters)[-24:]
        self._use_obj()                            # mit Kratern: Shader-Variante mit Löchern
        for prog in (self.ground, self.shadow_prog):
            self._crater_uniforms(prog)
        self.render_shadow()

    def add_crater(self, pos, radius):
        self.set_craters(self.craters + [(*pos, radius)])

    def entity_vao(self, vertices, max_instances):
        """Instanziertes Modell (Auto, Bus, Person): ein Draw-Call für alle Exemplare."""
        vbo = self.ctx.buffer(np.asarray(vertices, dtype="f4").tobytes())
        ibuf = self.ctx.buffer(reserve=max_instances * 7 * 4, dynamic=True)
        vao = self.ctx.vertex_array(self.inst, [(vbo, "3f 3f 3f 2f 1f", "in_pos", "in_norm", "in_col", "in_uv", "in_mat"),
                                                (ibuf, "4f 3f/i", "in_inst", "in_tint")])
        holder = _VaoRef(vao)
        self.__dict__.setdefault("_entity_models", []).append((vbo, ibuf, holder))
        return holder, ibuf

    def draw_entities(self, groups):
        """groups: [(vao, ibuf, instances als float32-Array (n, 7))]."""
        ctx = self.ctx
        ctx.enable(moderngl.DEPTH_TEST | moderngl.BLEND)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.inst["mvp"].write(gl(self.vp))
        self.inst["cam"].value = tuple(self.cam_pos)
        for vao, ibuf, inst in groups:
            if len(inst):
                ibuf.write(np.ascontiguousarray(inst, dtype="f4").tobytes())
                vao.render(instances=len(inst))
        ctx.disable(moderngl.BLEND)

    def hide(self, first, count):
        self.hidden.append((first, count))
        self.render_shadow()

    def show_all(self):
        self.hidden = []
        self.render_shadow()

    def render_shadow(self):
        ctx = self.ctx
        self.shadow_fbo.use()
        self.shadow_fbo.clear(depth=1.0)
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.BLEND)
        for first, count in self.segments():
            self.shadow_vao.render(first=first, vertices=count)
        self.target.use()
        if hasattr(self, "size"):
            ctx.viewport = (0, 0, *self.size)

    def _light_matrix(self, pts):
        f = -SUN
        r = np.cross(f, (0.0, 1.0, 0.0))
        r /= np.linalg.norm(r)
        u = np.cross(r, f)
        v = np.array([[*r, 0], [*u, 0], [*-f, 0], [0, 0, 0, 1.0]])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        corners = np.array([[x, y, z, 1] for x in (lo[0], hi[0]) for y in (0.0, hi[1]) for z in (lo[2], hi[2])])
        ls = corners @ v.T
        mn, mx = ls.min(axis=0), ls.max(axis=0)
        o = np.eye(4)
        o[0, 0], o[0, 3] = 2 / (mx[0] - mn[0]), -(mx[0] + mn[0]) / (mx[0] - mn[0])
        o[1, 1], o[1, 3] = 2 / (mx[1] - mn[1]), -(mx[1] + mn[1]) / (mx[1] - mn[1])
        near, far = -mx[2] - 1, -mn[2] + 1
        o[2, 2], o[2, 3] = -2 / (far - near), -(far + near) / (far - near)
        return o @ v

    def render_hfov(self):
        """Sichtfeld, mit dem die Szene gerendert wird: mit Fischaugen-Linse etwas weiter, damit nach der
        Verzerrung (look.py: r_quelle = r (1 + k r²) / (1 + k r_ecke²)) waagrecht wieder genau hfov zu sehen ist."""
        if not self.lens:
            return self.hfov
        k, aspect = self.lens, self.size[0] / self.size[1]
        rc2 = 1.0 + 1.0 / aspect ** 2
        t = math.tan(math.radians(self.hfov) / 2) * (1 + k * rc2) / (1 + k)
        return 2 * math.degrees(math.atan(t))

    def resize(self, size):
        self.size = size
        self.proj, self.tan = perspective(self.render_hfov(), size[0] / size[1], far=self.q["far"])
        self.ctx.viewport = (0, 0, *size)
        self.sprite_prog["screen"].value = tuple(float(v) for v in size)

    def set_fov(self, hfov):
        self.hfov = hfov
        self.resize(self.size)

    def draw(self, pos, quat, next_gate, mark, t, axes=None):
        ctx = self.ctx
        self.target.use()
        ctx.viewport = (0, 0, *self.size)
        ctx.viewport = (0, 0, *(self.vsize or self.size))
        r, u, f = axes if axes is not None else camera_axes(quat, self.tilt)
        self.view = view_matrix(pos, r, u, f)
        self.cam_pos = pos
        self.vp = self.proj @ self.view
        mvp = gl(self.vp)
        ctx.clear(*SKY_HORIZON)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND)
        self.sky["R"].value, self.sky["U"].value, self.sky["F"].value = tuple(r), tuple(u), tuple(f)
        self.sky["tanh"].value = self.tan
        sky_last = self.q["cull"]                 # Grafik-Stufe: Himmel zuletzt, nur wo nichts anderes ist
        if not sky_last:
            self.sky["sky_z"].value = 0.99999
            self.sky_vao.render()
        ctx.enable(moderngl.DEPTH_TEST)
        self.shadow_tex.use(1)
        for prog in (self.ground, self.obj):
            prog["mvp"].write(mvp)
            prog["shadow"].value = 1
            prog["cam"].value = tuple(pos)
        self.ground_vao.render()
        self.obj["next_gate"].value = next_gate
        self.obj["mark"].value = int(mark)
        self.obj["time"].value = t
        if self.cells is not None and not self.hidden:          # Zellen im Sichtfeld, Ferne mit LOD
            vao = self._cell_vao()
            for first, count in self.visible_ranges(np.asarray(pos, dtype="f8")):
                if count:
                    vao.render(first=first, vertices=count)
        else:
            for first, count in self.segments():
                self.obj_vao.render(first=first, vertices=count)
        if sky_last:                              # Tiefe 1.0 (= leer), Vergleich <=: gleiches Bild, weniger Pixel
            self.sky["sky_z"].value = 1.0
            ctx.depth_func = "<="
            self.sky_vao.render()
            ctx.depth_func = "<"

    def set_line(self, points):
        """Rennlinie des Autopiloten (oder None)."""
        if self.line_vao:
            self.line_vao.release()
            self.line_vao = None
        if points:
            data = np.array(points, dtype="f4")
            self.line_vao = self.ctx.vertex_array(self.line_prog, [(self.ctx.buffer(data.tobytes()), "3f", "in_pos")])

    def draw_line(self):
        if not self.line_vao:
            return
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.line_prog["mvp"].write(gl(self.vp))
        self.line_prog["color"].value = (0.2, 0.95, 1.0, 0.85)
        self.line_vao.render(moderngl.LINE_STRIP)

    @staticmethod
    def look_axes(eye, target):
        f = np.subtract(target, eye)
        f = f / np.linalg.norm(f)
        r = np.cross((0.0, 1.0, 0.0), f)        # Unity: links-händig -> rechts = up x vorne
        r = r / (np.linalg.norm(r) + 1e-9)
        u = np.cross(f, r)
        return r, u, f

    def project(self, p):
        """Bildschirmpunkt (px) eines Weltpunkts und ob er vor der Kamera liegt."""
        c = self.vp @ np.array([*p, 1.0])
        cam = self.view @ np.array([*p, 1.0])
        if c[3] <= 1e-6:
            return None, (cam[0], cam[1])
        nx, ny = c[0] / c[3], c[1] / c[3]
        if self.lens:                                 # Fischaugen (look.py): Punkt dorthin, wo er im Bild landet
            nx, ny = lens_forward(nx, ny, self.lens, self.size[0] / self.size[1])
        x = (nx * 0.5 + 0.5) * self.size[0]
        y = (0.5 - ny * 0.5) * self.size[1]
        return (x, y), (cam[0], cam[1])

    # ------------------------------------------------------------ 2D

    def begin_2d(self):
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

    def sprite(self, tex, cx, cy, w, h, angle=0.0, tint=(1, 1, 1, 1)):
        tex.use(0)
        self.sprite_prog["rect"].value = (cx, cy, w, h)
        self.sprite_prog["angle"].value = angle
        self.sprite_prog["tint"].value = tint
        self.sprite_vao.render()

    def texture(self, surface):
        tex = self.ctx.texture(surface.get_size(), 4, pygame.image.tobytes(surface, "RGBA"))
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        return tex
