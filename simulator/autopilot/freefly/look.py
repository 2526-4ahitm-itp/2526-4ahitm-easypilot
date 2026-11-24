"""FPV-Look und Grafik-Stufen: Nachbearbeitung des fertigen 3D-Bildes, bevor das OSD gezeichnet wird.

Kamera-Look (Menü „Kamera-Look“, Taste L):
  Sauber   - wie bisher, kein Effekt (Standard)
  Digital  - DJI-artig: Fischaugen-Linse, leichte Vignette, Farbsäume am Rand, Kompressions-Unschärfe bei
             schnellen Bewegungen, Bitraten-Pixelblöcke nah an Hindernissen und bei schwachem Signal
  Analog   - Fischaugen, Rauschen/Schnee, Zeilenflackern, Farbsäume (Chroma läuft nach rechts aus),
             Störungen je nach Signal: weit weg vom Start, Hindernisse zwischen Start und Drohne, ganz nah an
             Wänden; kurzer Schwarz-Flash beim Absturz
  Bildzittern (Motoren): minimales Zittern abhängig vom Gas (nur Digital/Analog).

Die Linse rendert die Szene mit etwas weiterem Sichtfeld und verzerrt sie dann tonnenförmig
(r_quelle = r (1 + k r²) / (1 + k r_ecke²)), sodass waagrecht genau das eingestellte Sichtfeld zu sehen ist;
Renderer.project() rechnet Tor-Markierungen usw. mit (gfx.lens_forward), das OSD bleibt scharf.
Kamerabild der Autopiloten / des Netzes: eigener Renderer (vision.py, train_nn.py), ohne Effekt.

Grafik (Menü „Grafik“, gfx.Renderer.set_quality):
  Hoch     - gleiche Optik wie bisher (4x MSAA); Zellen-Culling + Laub-LOD erst in der Ferne, Shader ohne discard
  Mittel   - 2x MSAA, 4 Schatten-Proben, Sichtweite 650 m, LOD früher
  Schnell  - ohne MSAA, 1 Schatten-Probe, Sichtweite 380 m, LOD früh
Der teuerste Teil am M1 ist die Kantenglättung (MSAA) des Bildschirms, nicht die Geometrie. Sie lässt sich nur
beim Anlegen des GL-Kontexts wählen: ein Grafik-Wechsel startet den Sim neu (ca. 3 s). Mit Digital/Analog wird
der Bildschirm ohne MSAA angelegt und nur der Szenen-Puffer geglättet (Digital 2x, Analog gar nicht).
"""
import math
import random

import numpy as np

from .world import SPAWN

LOOKS = {"sauber": "Sauber", "digital": "Digital (DJI-artig)", "analog": "Analog"}
GRAFIK = {"hoch": "Hoch", "mittel": "Mittel", "schnell": "Schnell"}
SICHT = {"auto": "nach Stufe", "250": "250 m", "400": "400 m", "650": "650 m", "1000": "1000 m", "max": "unbegrenzt"}
QUALITY = {
    # taps/fog_k/far/fog_end/cull/lod_*: gfx.Renderer.set_quality; msaa = Kantenglättung des Bildschirms
    # (beim Start des GL-Kontexts, context_samples; ein Wechsel startet den Sim neu), scale = Szenen-Auflösung
    # (< 1 kostet einen eigenen Puffer). Gemessen am M1: 4x MSAA kostet bei 1920x1200 am meisten.
    "hoch": dict(taps=9, fog_k=0.0038, far=1500.0, fog_end=1e7, cull=True, lod_blob=120.0, lod_small=160.0,
                 scale=1.0, msaa=4),
    "mittel": dict(taps=4, fog_k=0.0042, far=650.0, fog_end=650.0, cull=True, lod_blob=70.0, lod_small=100.0,
                   scale=1.0, msaa=2),
    "schnell": dict(taps=1, fog_k=0.0048, far=380.0, fog_end=380.0, cull=True, lod_blob=40.0, lod_small=60.0,
                    scale=1.0, msaa=0),
}
LOOK_MSAA = {"digital": 2, "analog": 0}      # mit Look: Szenen-Puffer höchstens so geglättet (Effekt verwischt ohnehin)
LENS = {"sauber": 0.0, "digital": 0.16, "analog": 0.26}       # Tonnen-Verzerrung bei 135° Sichtfeld
CA = {"sauber": 0.0, "digital": 0.0035, "analog": 0.008}      # Farbsäume am Rand
VIGNETTE = {"sauber": 0.0, "digital": 0.28, "analog": 0.42}

MENU = [{"label": "Kamera-Look (L)", "kind": "value", "key": "look"},
        {"label": "Bildzittern (Motoren)", "kind": "toggle", "key": "vib"},
        {"label": "Pixelblöcke (Digital)", "kind": "toggle", "key": "blocks"},
        {"label": "Grafik", "kind": "value", "key": "grafik"},
        {"label": "Sichtweite", "kind": "value", "key": "sicht"},
        {"label": "Zurück", "kind": "action", "key": "back"}]


def ensure(s):
    """Neue Einstellungen so vorbelegen, dass alles aussieht wie bisher (Sauber, Hoch)."""
    if s.get("look") not in LOOKS:
        s["look"] = "sauber"
    if s.get("grafik") not in GRAFIK:
        s["grafik"] = "hoch"
    if s.get("sicht") not in SICHT:
        s["sicht"] = "auto"
    s.setdefault("vib", True)
    s.setdefault("blocks", True)


def menu_values(s):
    onoff = lambda k: "an" if s.get(k) else "aus"
    return {"look": LOOKS[s["look"]], "grafik": GRAFIK[s["grafik"]], "sicht": SICHT[s["sicht"]],
            "vib": onoff("vib") if s["look"] != "sauber" else "nur Digital/Analog",
            "blocks": onoff("blocks") if s["look"] == "digital" else "nur Digital"}


def _cycle(order, cur, direction):
    order = list(order)
    i = order.index(cur) if cur in order else 0
    return order[(i + (direction or 1)) % len(order)]


def change(s, key, direction):
    """True, wenn der Schalter zu diesem Modul gehört."""
    if key == "look":
        s["look"] = _cycle(LOOKS, s.get("look"), direction)
    elif key == "grafik":
        s["grafik"] = _cycle(GRAFIK, s.get("grafik"), direction)
    elif key == "sicht":
        s["sicht"] = _cycle(SICHT, s.get("sicht"), direction)
    elif key in ("vib", "blocks"):
        s[key] = not s.get(key)
    else:
        return False
    return True


def context_samples(s):
    """MSAA-Proben für den Bildschirm beim Start: mit Look 0 (die Szene glättet ihr eigener Puffer)."""
    return 0 if s.get("look", "sauber") != "sauber" else QUALITY[s.get("grafik", "hoch")]["msaa"]


def quality(s):
    q = dict(QUALITY[s.get("grafik", "hoch")])
    sicht = s.get("sicht", "auto")
    if sicht == "max":
        q.update(far=1500.0, fog_end=1e7)
    elif sicht != "auto":
        q.update(far=float(sicht), fog_end=float(sicht))
    return q


POST_VS = """
#version 330
in vec2 in_ndc; out vec2 v_uv;
void main() { v_uv = in_ndc * 0.5 + 0.5; gl_Position = vec4(in_ndc, 0.0, 1.0); }"""

POST_FS = """
#version 330
uniform sampler2D scene; uniform vec2 texel; uniform vec2 out_px;
uniform float aspect; uniform float k; uniform float rc2;
uniform int mode;                 // 0 nur skalieren, 1 Digital, 2 Analog
uniform float time; uniform float frame;
uniform float motion; uniform float blocks; uniform float interf; uniform float black;
uniform float vig; uniform float ca; uniform vec2 shake;
in vec2 v_uv; out vec4 f;
float h1(vec2 p) {                 // Hash ohne sin (gleichmäßig auch bei großen Koordinaten)
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}
vec2 lens(vec2 uv, float extra) {
    vec2 q = (uv * 2.0 - 1.0) * vec2(1.0, 1.0 / aspect);
    float r2 = dot(q, q);
    q *= (1.0 + k * r2) / (1.0 + k * rc2) * (1.0 + extra * r2);
    return q * vec2(1.0, aspect) * 0.5 + 0.5;
}
vec3 tap(vec2 uv) { return texture(scene, clamp(uv, texel * 0.5, 1.0 - texel * 0.5)).rgb; }
void main() {
    vec2 uv = v_uv + shake;
    float line = floor(v_uv.y * out_px.y);
    if (mode == 0) { f = vec4(tap(uv), 1.0); return; }
    if (mode == 2) {                                            // Zeilen-Zittern, bei Störung ganze Bänder
        float band = step(1.0 - interf * 0.3, h1(vec2(floor(line / 7.0), frame * 1.7)));
        uv.x += (h1(vec2(line * 0.37, frame)) - 0.5) * (0.0008 + 0.004 * interf)
              + band * (h1(vec2(floor(line / 7.0), frame + 3.0)) - 0.5) * 0.035 * interf;
    }
    bool blk = false;
    if (mode == 1 && blocks > 0.0) {                            // Bitraten-Blöcke (16 px)
        vec2 cell = floor(v_uv * out_px / 16.0);
        float t10 = floor(time * 10.0);
        float group = h1(floor(cell / 5.0) * 1.7 + t10 * 0.91);           // Blöcke kommen in Gruppen
        if (h1(cell * 0.73 + t10 * 1.31) < blocks * (0.15 + 2.2 * group * group)) {
            uv = (cell + 0.5) * 16.0 / out_px + shake;
            blk = true;
        }
    }
    vec2 u0 = lens(uv, 0.0);
    vec3 c = tap(u0);
    if (ca > 0.0) {
        c.r = tap(lens(uv, ca)).r;
        c.b = tap(lens(uv, -ca)).b;
    }
    if (mode == 1) {
        if (motion > 0.02 && !blk) {                           // Kompressions-Unschärfe bei schnellen Bewegungen
            vec2 o = texel * (1.0 + 2.5 * motion);
            vec3 b = tap(u0 + o) + tap(u0 - o) + tap(u0 + vec2(o.x, -o.y)) + tap(u0 + vec2(-o.x, o.y));
            c = mix(c, b * 0.25, min(0.8, motion));
        }
        if (blk) c = floor(c * 14.0 + 0.5) / 14.0;
        c = (c - 0.5) * 1.05 + 0.5;                             // etwas knackiger (DJI)
    } else {
        // Farbsäume: Helligkeit scharf, Farbe läuft nach rechts aus (wie Composite-Video)
        vec3 c1 = tap(u0 + vec2(texel.x * 2.0, 0.0)), c2 = tap(u0 + vec2(texel.x * 4.5, 0.0));
        vec3 w = vec3(0.299, 0.587, 0.114);
        vec3 ch = (c + c1 + c2) / 3.0;
        float y = dot(c, w) * 0.7 + dot(c1, w) * 0.3;           // auch die Helligkeit ein wenig weich
        c = vec3(y) + (ch - dot(ch, w)) * (1.2 - 0.7 * interf);
        c *= 0.95 + 0.05 * sin(v_uv.y * out_px.y * 1.5708);     // Zeilen
        c *= 1.0 - 0.035 * h1(vec2(frame, 1.0)) - 0.3 * interf * h1(vec2(frame, 2.0));   // Flackern
        float roll = smoothstep(0.92, 1.0, fract(v_uv.y * 0.8 - time * 0.6));            // durchlaufender Balken
        c *= 1.0 - roll * (0.06 + 0.3 * interf);
        float n = h1(floor(v_uv * out_px * 0.5) + vec2(frame * 13.1, frame * 7.7));
        float snow = 0.07 + 0.55 * interf * interf;
        c = mix(c, vec3(n), clamp(snow * (0.5 + 0.5 * h1(vec2(line, frame))), 0.0, 1.0));
        if (h1(vec2(line * 1.3, frame * 0.9)) > 1.0 - interf * 0.025
            && abs(v_uv.x - h1(vec2(line, frame * 1.1))) < 0.25) c = vec3(0.9 * n);         // Störstreifen
        c += vec3(0.02, 0.0, 0.03) * interf;
    }
    vec2 q = (v_uv * 2.0 - 1.0) * vec2(1.0, 1.0 / aspect);
    c *= 1.0 - vig * smoothstep(0.35, 1.05, sqrt(dot(q, q) / rc2));
    c = mix(c, vec3(0.0), black);
    f = vec4(clamp(c, 0.0, 1.0), 1.0);
}"""


def _smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


class PostFx:
    """Eigener Szenen-Puffer (bei Look oder Auflösungs-Skalierung), Nachbearbeitung auf den Bildschirm."""

    def __init__(self, renderer, screen_samples=4):
        self.r = renderer
        self.screen_samples = screen_samples        # so wurde der Bildschirm-Kontext angelegt (__main__)
        ctx = self.ctx = renderer.ctx
        self.prog = ctx.program(vertex_shader=POST_VS, fragment_shader=POST_FS)
        tri = np.array([-1, -1, 3, -1, -1, 3], dtype="f4")
        self.vao = ctx.vertex_array(self.prog, [(ctx.buffer(tri.tobytes()), "2f", "in_ndc")])
        self.prog["scene"].value = 0
        self.key = None
        self.fbo = self.msaa = self.tex = None
        self.active = False
        self.cfg = None
        self.prev_f = None
        self.motion = 0.0
        self.interf = 0.0
        self.sig_t = 0.0
        self.sig_target = 0.0
        self.prox = 99.0
        self.frame = 0
        self.rng = random.Random(3)
        self.t_prev = None

    # ------------------------------------------------------------ Einstellungen

    def configure(self, s):
        """Nach dem Laden und nach jeder Menü-Änderung: Grafik-Stufe und Linse in den Renderer."""
        q = quality(s)
        cfg = (s["look"], s["grafik"], s["sicht"], self.r.hfov)
        if cfg == self.cfg:
            return
        self.cfg = cfg
        self.q = q
        self.r.set_quality({k: q[k] for k in ("taps", "fog_k", "far", "fog_end", "cull", "lod_blob", "lod_small")})
        k = LENS[s["look"]]
        if k:                                       # stärker bei weitem Sichtfeld, schwächer bei engem
            k *= min(1.6, max(0.3, math.tan(math.radians(self.r.hfov) / 2) / math.tan(math.radians(67.5))))
        self.r.lens = k
        self.r.resize(self.r.size)

    def _buffers(self, size, samples):
        key = (size, samples)
        if key == self.key:
            return
        for obj in (self.fbo, self.msaa, self.tex):
            if obj is not None:
                obj.release()
        import moderngl
        ctx = self.ctx
        self.tex = ctx.texture(size, 3)
        self.tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.tex.repeat_x = self.tex.repeat_y = False
        if samples:
            self.fbo = ctx.framebuffer(color_attachments=[self.tex])
            self.msaa = ctx.framebuffer(color_attachments=[ctx.renderbuffer(size, 3, samples=samples)],
                                        depth_attachment=ctx.depth_renderbuffer(size, samples=samples))
        else:
            self.fbo = ctx.framebuffer(color_attachments=[self.tex], depth_attachment=ctx.depth_renderbuffer(size))
            self.msaa = None
        self.key = key

    # ------------------------------------------------------------ pro Frame

    def begin(self, s):
        """Vor renderer.draw(): Szene in den eigenen Puffer umleiten, falls Look oder Grafik das brauchen."""
        self.configure(s)
        q = self.q
        look = s["look"]
        samples = q["msaa"] if look == "sauber" else min(q["msaa"], LOOK_MSAA[look])
        # direkt auf den Bildschirm, solange der genauso geglättet ist (Sauber nach Start mit derselben Stufe)
        need = look != "sauber" or q["scale"] != 1.0 or samples > self.screen_samples
        self.active = need
        if not need:
            return
        W, H = self.r.size
        size = (max(64, int(W * q["scale"])), max(64, int(H * q["scale"])))
        self._buffers(size, samples)
        self.r.target = self.msaa or self.fbo
        self.r.vsize = size

    def apply(self, flight, world, s, now, sticks):
        """Nach Welt, Fahrzeugen, Linie, Explosionen: Effekt-Pass auf den Bildschirm; danach kommt das OSD."""
        if not self.active:
            return
        import moderngl
        ctx, r = self.ctx, self.r
        if self.msaa is not None:
            ctx.copy_framebuffer(self.fbo, self.msaa)
        r.target = ctx.screen
        r.vsize = None
        ctx.screen.use()
        ctx.viewport = (0, 0, *r.size)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND)
        dt = 0.0 if self.t_prev is None else min(0.1, max(0.0, now - self.t_prev))
        self.t_prev = now
        self.frame = (self.frame + 1) % 100000
        look = s["look"]
        p = self.prog
        W, H = r.size
        aspect = W / H
        sw, sh = self.key[0]
        p["texel"].value = (1.0 / sw, 1.0 / sh)
        p["out_px"].value = (float(W), float(H))
        p["aspect"].value = aspect
        p["k"].value = r.lens
        p["rc2"].value = 1.0 + 1.0 / aspect ** 2
        p["time"].value = now % 1000.0
        p["frame"].value = float(self.frame % 977)
        p["vig"].value = VIGNETTE[look]
        p["ca"].value = CA[look]
        if look == "sauber":
            p["mode"].value = 0
            for name in ("motion", "blocks", "interf", "black"):
                p[name].value = 0.0
            p["shake"].value = (0.0, 0.0)
        else:
            self._signal(flight, world, now, dt)
            self._motion(r, dt)
            p["mode"].value = 1 if look == "digital" else 2
            p["motion"].value = self.motion if look == "digital" else 0.0
            p["interf"].value = self.interf if look == "analog" else 0.0
            blocks = 0.0
            if look == "digital" and s.get("blocks", True):
                blocks = min(0.55, 0.5 * _smooth(1.6, 0.25, self.prox) + 0.6 * max(0.0, self.interf - 0.45)
                             + 0.04 * self.motion)
            p["blocks"].value = blocks
            black, extra = self._crash(flight, now, look)
            p["black"].value = black
            if extra:
                p["interf"].value = max(p["interf"].value, extra) if look == "analog" else 0.0
                if look == "digital":
                    p["blocks"].value = max(blocks, extra * 0.7)
            sx = sy = 0.0
            if s.get("vib", True) and flight.armed and flight.crashed_at is None:
                amp = (0.25 + 1.1 * max(0.0, min(1.0, sticks[0]))) / W           # 0,25 .. 1,35 Pixel
                sx, sy = self.rng.uniform(-amp, amp), self.rng.uniform(-amp, amp) * aspect
            p["shake"].value = (sx, sy)
        self.tex.use(0)
        self.vao.render()

    def _motion(self, r, dt):
        """Schnelle Bewegung: Drehrate der Kamera (Blickrichtung) -> Kompressions-Unschärfe (Digital)."""
        f = np.array(r.view[2, :3])
        rate = 0.0
        if self.prev_f is not None and dt > 0:
            rate = math.acos(max(-1.0, min(1.0, float(np.dot(f, self.prev_f))))) / dt     # rad/s
        self.prev_f = f
        target = _smooth(2.5, 9.0, rate)
        self.motion += (target - self.motion) * min(1.0, dt * (12.0 if target > self.motion else 4.0))

    def _crash(self, flight, now, look):
        """(Schwarz-Anteil, zusätzliche Störung) kurz nach dem Absturz."""
        if flight.crashed_at is None:
            return 0.0, 0.0
        try:
            dt = now - flight.crashed_at
        except TypeError:
            return 0.0, 0.0
        if dt < 0 or dt > 0.6:
            return 0.0, 0.0
        if look == "analog":
            black = 1.0 if dt < 0.09 else max(0.0, 1.0 - (dt - 0.09) / 0.25)
            return black, max(0.0, 1.0 - dt / 0.6)
        return 0.0, max(0.0, 1.0 - dt / 0.45)          # Digital: Bild zerfällt kurz in Blöcke

    def _signal(self, flight, world, now, dt):
        """Störung 0..1 (Analog) aus Entfernung zum Start, Hindernissen zwischen Start und Drohne, Wandnähe."""
        p = np.asarray(flight.drone.pos, dtype="f8")
        if now - self.sig_t > 0.05:                       # 20 Hz reicht
            self.sig_t = now
            dist = math.hypot(p[0] - SPAWN[0], p[2] - SPAWN[2])
            target = 0.7 * _smooth(180.0, 520.0, dist)
            ant = np.array((SPAWN[0], 1.6, SPAWN[2]))
            target += min(0.4, 0.13 * _blocked(world, ant, p))           # Häuser zwischen Start und Drohne
            self.prox = _nearest(world, p)
            target += 0.35 * _smooth(2.5, 0.3, self.prox)                 # dicht an Wand/Baum: Mehrwege
            target += 0.15 * _smooth(1.0, 0.2, p[1]) * _smooth(30.0, 120.0, dist)   # flach am Boden, weit weg
            self.sig_target = min(1.0, target)
        tgt = self.sig_target
        if self.rng.random() < dt * 4.0 * tgt:            # kurze Aussetzer, häufiger bei schlechtem Signal
            tgt = min(1.0, tgt + self.rng.uniform(0.15, 0.45))
        self.interf += (tgt - self.interf) * min(1.0, dt * (14.0 if tgt > self.interf else 3.0))


def _local(world, i, pts):
    """Punkte (n, 3) ins Box-System (wie World.hit: Gier um y)."""
    d = pts[None, :, :] - world.bc[i][:, None, :]
    cs, sn = world.bcos[i][:, None], world.bsin[i][:, None]
    return np.stack((cs * d[..., 0] - sn * d[..., 2], d[..., 1], sn * d[..., 0] + cs * d[..., 2]), axis=-1)


def _nearest(world, p):
    """Abstand zur nächsten Kollisionsbox in der Nähe (world.focus wurde in diesem Frame aufgerufen)."""
    i = world.near
    if len(i) == 0:
        return 99.0
    loc = _local(world, i, p[None, :])[:, 0, :]
    q = np.maximum(np.abs(loc) - world.bh[i], 0.0)
    return float(np.sqrt(np.min(np.einsum("ij,ij->i", q, q))))


def _blocked(world, a, b):
    """Wie viele große Boxen (Häuser, Hallen) die Strecke a-b schneiden (Slab-Test im Box-System)."""
    big = getattr(world, "_big_boxes", None)
    if big is None:
        vol = world.bh[:, 0] * world.bh[:, 1] * world.bh[:, 2]
        big = world._big_boxes = np.nonzero((vol > 6.0) & (world.bh[:, 1] > 1.2))[0]
    i = big[world.alive[big]]
    if len(i) == 0:
        return 0
    loc = _local(world, i, np.stack((a, b)))
    o, d = loc[:, 0, :], loc[:, 1, :] - loc[:, 0, :]
    h = world.bh[i]
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = 1.0 / np.where(np.abs(d) < 1e-9, 1e-9, d)
        t1, t2 = (-h - o) * inv, (h - o) * inv
    tmin = np.max(np.minimum(t1, t2), axis=1)
    tmax = np.min(np.maximum(t1, t2), axis=1)
    return int(np.count_nonzero((tmax >= np.maximum(tmin, 0.0)) & (tmin <= 1.0)))


def from_env(s):
    """FREEFLY_LOOK=sauber|digital|analog, FREEFLY_GRAFIK=hoch|mittel|schnell (Messungen, Bilder)."""
    import os
    if os.environ.get("FREEFLY_LOOK") in LOOKS:
        s["look"] = os.environ["FREEFLY_LOOK"]
    if os.environ.get("FREEFLY_GRAFIK") in GRAFIK:
        s["grafik"] = os.environ["FREEFLY_GRAFIK"]
