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
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float shade(vec4 ls) {
    vec3 p = ls.xyz / ls.w * 0.5 + 0.5;
    if (p.x < 0.0 || p.x > 1.0 || p.y < 0.0 || p.y > 1.0) return 1.0;
    vec2 o = 1.0 / vec2(textureSize(shadow, 0));
    float s = 0.0;
    for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++)
        s += texture(shadow, vec3(p.xy + vec2(i, j) * o * 1.3, p.z - 0.0008));
    return s / 9.0;
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
    return mix(c, fog_col, 1.0 - exp(-d * 0.0038));
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
    bool hole;
    float burn = crater(v_pos, hole);
    if (hole) discard;
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
in vec2 in_ndc; out vec2 v_ndc;
void main() { v_ndc = in_ndc; gl_Position = vec4(in_ndc, 0.99999, 1.0); }"""
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


class Renderer:
    def __init__(self, ctx, world, size, hfov, tilt, target=None):
        self.ctx, self.hfov, self.tilt = ctx, hfov, tilt
        self.target = target or ctx.screen          # Bildschirm oder Offscreen-Puffer (Kamera-Autopilot)
        self.world = world
        self.obj = ctx.program(vertex_shader="#version 330\n" + WORLD_VS, fragment_shader="#version 330\n" + WORLD_FS)
        self.inst = ctx.program(vertex_shader="#version 330\n#define INST\n" + WORLD_VS,
                                fragment_shader="#version 330\n#define INST\n" + WORLD_FS)
        self.craters = []
        self.ground = ctx.program(vertex_shader=GROUND_VS, fragment_shader=GROUND_FS)
        self.sky = ctx.program(vertex_shader=SKY_VS, fragment_shader=SKY_FS)
        self.sprite_prog = ctx.program(vertex_shader=SPRITE_VS, fragment_shader=SPRITE_FS)
        self.line_prog = ctx.program(vertex_shader=LINE_VS, fragment_shader=LINE_FS)
        self.line_vao = None
        shadow_prog = ctx.program(vertex_shader=SHADOW_VS, fragment_shader=SHADOW_FS)
        vbo = ctx.buffer(world.vertices.tobytes())
        self.obj_vao = ctx.vertex_array(self.obj, [(vbo, "3f 3f 3f 2f 1f", "in_pos", "in_norm", "in_col", "in_uv", "in_mat")])
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

        for prog in (self.obj, self.ground, self.inst):
            prog["light_mvp"].write(gl(self.light_mvp))
            prog["sun"].value = tuple(SUN)
            prog["fog_col"].value = SKY_HORIZON
            prog["shadow"].value = 1
        self.sky["top"].value, self.sky["hor"].value = SKY_TOP, SKY_HORIZON
        self.sky["sun"].value = tuple(SUN)
        self.sprite_prog["tex"].value = 0
        self.obj["mark"].value = 1
        self.inst["mark"].value = 0
        self.set_craters([])
        self.resize(size)

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
        data = np.zeros((24, 4), dtype="f4")
        if self.craters:
            data[:len(self.craters)] = self.craters
        for prog in (self.obj, self.ground, self.shadow_prog):
            prog["craters"].write(data.tobytes())
            prog["n_craters"].value = len(self.craters)
        self.render_shadow()

    def add_crater(self, pos, radius):
        self.set_craters(self.craters + [(*pos, radius)])

    def entity_vao(self, vertices, max_instances):
        """Instanziertes Modell (Auto, Bus, Person): ein Draw-Call für alle Exemplare."""
        vbo = self.ctx.buffer(np.asarray(vertices, dtype="f4").tobytes())
        ibuf = self.ctx.buffer(reserve=max_instances * 7 * 4, dynamic=True)
        vao = self.ctx.vertex_array(self.inst, [(vbo, "3f 3f 3f 2f 1f", "in_pos", "in_norm", "in_col", "in_uv", "in_mat"),
                                                (ibuf, "4f 3f/i", "in_inst", "in_tint")])
        return vao, ibuf

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

    def resize(self, size):
        self.size = size
        self.proj, self.tan = perspective(self.hfov, size[0] / size[1])
        self.ctx.viewport = (0, 0, *size)
        self.sprite_prog["screen"].value = tuple(float(v) for v in size)

    def set_fov(self, hfov):
        self.hfov = hfov
        self.resize(self.size)

    def draw(self, pos, quat, next_gate, mark, t, axes=None):
        ctx = self.ctx
        self.target.use()
        ctx.viewport = (0, 0, *self.size)
        r, u, f = axes if axes is not None else camera_axes(quat, self.tilt)
        self.view = view_matrix(pos, r, u, f)
        self.cam_pos = pos
        self.vp = self.proj @ self.view
        mvp = gl(self.vp)
        ctx.clear(*SKY_HORIZON)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND)
        self.sky["R"].value, self.sky["U"].value, self.sky["F"].value = tuple(r), tuple(u), tuple(f)
        self.sky["tanh"].value = self.tan
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
        for first, count in self.segments():
            self.obj_vao.render(first=first, vertices=count)

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
        x = (c[0] / c[3] * 0.5 + 0.5) * self.size[0]
        y = (0.5 - c[1] / c[3] * 0.5) * self.size[1]
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
