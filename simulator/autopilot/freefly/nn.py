"""Neuronales Netz als Pilot: sieht nur das Kamerabild der Drohne und den eigenen Flugzustand.

Eingabe (nichts davon verrät, wo die Tore sind):
  - Kamerabild 128x71 aus vision.CameraView (RGB) + Tiefenbild derselben Kamera als 4. Kanal (1/Abstand)
  - Flugzustand wie ihn eine echte Drohne misst: Geschwindigkeit im Drohnen-Kurs-System (vor, rechts, hoch),
    Schwerkraft-Richtung im Körper-System (= Roll/Nick), Drehraten, Höhe über Grund. Bewusst NICHT die
    eigene letzte Ausgabe: damit lernt ein nachgeahmtes Netz nur "weiter wie bisher" (Copycat-Problem,
    erster Versuch 20.11.: Lehrer-Verlust winzig, allein 0 Tore).
Ausgabe: Soll-Werte für den vorhandenen FlightController (control.py), keine rohen Sticks:
  Tempo vorwärts, seitwärts, hoch (m/s im Kurs-System) und Gier-Rate. Der Regler hält damit die Lage
  bei 125 Hz stabil; das Netz entscheidet nur 15-mal pro Sekunde, wohin es geht. Das lernt viel
  stabiler als Sticks direkt (die müssten jede Schräglage selbst abfangen).

Training: train_nn.py (Imitation + DAgger, danach PPO ohne Lehrer). Modelle: autopilot/models/freefly_nn/.
Im Spiel: NNPilot (unten), lädt best.pt und lädt neu, wenn ein Training ein besseres Modell speichert.
"""
import dataclasses
import json
import math
import time
from pathlib import Path

import numpy as np

from ..geometry import qinvrot, qrot

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "freefly_nn"
DECISION_HZ = 15                    # Netz-Entscheidungen pro Sekunde (Kamerabild + Netz)
CAM_WIDTH = 128
CAM_TILT = 20.0                     # Grad: Kamera weniger steil als beim Renn-FPV (Netz fliegt ~11 m/s)
# Ausgabe [-1, 1] -> physikalisch
V_FWD = (7.0, 7.0)                  # vor: 7 + 7*a  -> 0 .. 14 m/s
V_SIDE = 5.0                        # m/s
V_UP = 4.0                          # m/s
YAW_RATE = math.radians(150.0)      # rad/s
N_STATE = 10
N_PRIV = 8                          # nur fürs Training (Kritiker), nie im Flug


def camera():
    from ..sysid import load_camera
    return dataclasses.replace(load_camera(CAM_WIDTH), tilt_deg=CAM_TILT)


# ----------------------------------------------------------------------------- Ein-/Ausgabe
def heading_axes(quat):
    """Waagrechte Vorwärts- und Rechts-Richtung der Drohne (Welt)."""
    f = qrot(quat, (0.0, 0.0, 1.0))
    fx, fz = f[0], f[2]
    n = math.hypot(fx, fz)
    if n < 1e-6:                     # senkrecht: nimm die Oberseite
        u = qrot(quat, (0.0, 1.0, 0.0))
        fx, fz = -u[0], -u[2]
        n = math.hypot(fx, fz) or 1.0
    fx, fz = fx / n, fz / n
    return (fx, 0.0, fz), (fz, 0.0, -fx)


def state_features(state, prev_action=None):
    fwd, right = heading_axes(state.quat)
    v = state.vel
    g = qinvrot(state.quat, (0.0, -1.0, 0.0))
    w = state.gyro
    out = np.empty(N_STATE, np.float32)
    out[0] = (v[0] * fwd[0] + v[2] * fwd[2]) / 10.0
    out[1] = (v[0] * right[0] + v[2] * right[2]) / 10.0
    out[2] = v[1] / 5.0
    out[3:6] = g
    out[6:9] = np.clip(np.asarray(w, np.float32) / 400.0, -3, 3)
    out[9] = min(state.pos[1], 40.0) / 10.0
    return out


def image_input(bgr, depth):
    """uint8 [4, H, W]: R, G, B, Nähe (255 bei <= 1,5 m, 0 weit weg)."""
    rgb = bgr[:, :, ::-1]
    near = np.clip(1.5 / np.maximum(depth, 1e-3), 0.0, 1.0) * 255.0
    return np.concatenate([rgb.transpose(2, 0, 1), near[None].astype(np.uint8)], axis=0)


def action_to_setpoint(a):
    """[-1,1]^4 -> (vor, rechts, hoch m/s, Gier-Rate rad/s)."""
    a = np.clip(np.asarray(a, np.float64), -1.0, 1.0)
    return V_FWD[0] + V_FWD[1] * a[0], V_SIDE * a[1], V_UP * a[2], YAW_RATE * a[3]


def setpoint_to_action(vf, vr, vu, yr):
    return np.clip(np.array([(vf - V_FWD[0]) / V_FWD[1], vr / V_SIDE, vu / V_UP, yr / YAW_RATE], np.float32),
                   -1.0, 1.0)


class SetpointController:
    """Soll-Tempo im Kurs-System + Gier-Rate -> Sticks über den FlightController (125 Hz)."""
    YAW_LEAD = 0.3                  # s: Blickrichtung so weit vorausgedreht

    def __init__(self, rates, thrust):
        from ..control import FlightController, Gains
        self.ctl = FlightController(rates, thrust, Gains(tilt=12, yaw=3.5, pos=0.0, vel=3.0))
        self.set = (0.0, 0.0, 0.0, 0.0)

    def reset(self):
        self.ctl.reset()
        self.set = (0.0, 0.0, 0.0, 0.0)

    def command(self, state):
        vf, vr, vu, yr = self.set
        fwd, right = heading_axes(state.quat)
        v = (fwd[0] * vf + right[0] * vr, vu, fwd[2] * vf + right[2] * vr)
        a = yr * self.YAW_LEAD
        c, s = math.cos(a), math.sin(a)
        yaw_dir = (fwd[0] * c + right[0] * s, 0.0, fwd[2] * c + right[2] * s)
        self.ctl.observe(state)
        return self.ctl.track(state, state.pos, v, (0.0, 0.0, 0.0), yaw_dir).as_tuple()


# ----------------------------------------------------------------------------- Netz
def build_net():
    import torch
    from torch import nn

    class PolicyNet(nn.Module):
        def __init__(self, h=71, w=CAM_WIDTH):
            super().__init__()
            # 4x4-Felder als erste Schicht: 3x schneller als 5x5/Schritt 2 (die GPU teilt sich der
            # Trainer mit Spiel und Liftoff, 20.11.: 130 statt 370 ms je Lernschritt)
            self.cnn = nn.Sequential(
                nn.Conv2d(4, 32, 4, 4), nn.ReLU(),
                nn.Conv2d(32, 64, 3, 2, 1), nn.ReLU(),
                nn.Conv2d(64, 128, 3, 2, 1), nn.ReLU(),
                nn.Flatten())
            with torch.no_grad():
                n = self.cnn(torch.zeros(1, 4, h, w)).shape[1]
            self.img_fc = nn.Sequential(nn.Linear(n, 256), nn.ELU())
            self.state_fc = nn.Sequential(nn.Linear(N_STATE, 64), nn.ELU())
            self.trunk = nn.Sequential(nn.Linear(320, 256), nn.ELU(), nn.Linear(256, 256), nn.ELU())
            self.mu = nn.Linear(256, 4)
            self.log_std = nn.Parameter(torch.full((4,), -1.2))
            # Kritiker (nur Training): Merkmale des Piloten (ohne Rückwirkung) + Wissen über die Strecke
            self.critic = nn.Sequential(nn.Linear(256 + N_STATE + N_PRIV, 256), nn.ELU(),
                                        nn.Linear(256, 256), nn.ELU(), nn.Linear(256, 1))

        def features(self, img, st):
            x = img.float() / 255.0 - 0.5
            return self.trunk(torch.cat([self.img_fc(self.cnn(x)), self.state_fc(st)], 1))

        def forward(self, img, st):
            return self.mu(self.features(img, st))

        def value(self, feat, st, priv):
            return self.critic(torch.cat([feat.detach(), st, priv], 1)).squeeze(1)

    return PolicyNet()


def load_model(path=None):
    """-> (Netz auf CPU im eval-Modus, Meta-Daten) oder (None, None)."""
    import torch
    path = Path(path) if path else MODEL_DIR / "best.pt"
    if not path.exists():
        return None, None
    ck = torch.load(path, map_location="cpu", weights_only=False)
    net = build_net()
    net.load_state_dict(ck["state_dict"])
    net.eval()
    return net, ck.get("meta", {})


def training_status():
    """Für OSD/Studio: Stand des Trainings aus models/freefly_nn/status.json (oder None)."""
    try:
        return json.loads((MODEL_DIR / "status.json").read_text())
    except (OSError, ValueError):
        return None


# ----------------------------------------------------------------------------- Pilot im Spiel
class NNPilot:
    """Wie CameraAutopilot: step(state) -> Sticks je Physik-Schritt. Kamerabild + Netz mit 15 Hz."""

    def __init__(self, world, rates, thrust, ctx=None, path=None):
        import moderngl
        import torch
        from .vision import CameraView
        torch.set_num_threads(2)
        self.torch = torch
        self.cam = camera()
        self.ctx = ctx or moderngl.create_standalone_context(require=330)
        self.view = CameraView(self.ctx, world, self.cam)
        self.ctl = SetpointController(rates, thrust)
        self.path = Path(path) if path else MODEL_DIR / "best.pt"
        self.net, self.meta, self.mtime = None, {}, None
        self.reload()
        self.reset()

    def reload(self):
        """Neues best.pt (Training läuft im Hintergrund)? Dann laden. -> True wenn neu geladen."""
        try:
            m = self.path.stat().st_mtime
        except OSError:
            return False
        if m == self.mtime:
            return False
        net, meta = load_model(self.path)
        if net is None:
            return False
        with self.torch.no_grad():                   # erster Aufruf ist langsam (~100 ms): nicht im Flug
            net(self.torch.zeros(1, 4, self.cam.height, self.cam.width, dtype=self.torch.uint8),
                self.torch.zeros(1, N_STATE))
        self.net, self.meta, self.mtime = net, meta or {}, m
        return True

    @property
    def ok(self):
        return self.net is not None

    @property
    def version(self):
        return self.meta.get("version", 0)

    def label(self):
        if not self.ok:
            return "kein Modell"
        m = self.meta
        s = f"NN v{m.get('version', '?')}"
        if m.get("eval_gates") is not None:
            s += f" · {m['eval_gates']:.1f} Tore"
        return s

    def reset(self):
        self.reload()
        self.ctl.reset()
        self.prev = np.zeros(4, np.float32)
        self.next_frame = 0.0
        self.n = 0
        self.cmd = None
        self.frames = 0
        self.ms = 0.0
        self.last_img = None          # was das Netz zuletzt gesehen hat (uint8 [4,H,W]), fürs OSD
        self.done = False

    def step(self, state, craters=None):
        if self.net is None:
            self.cmd = (0.0, 0.0, 0.0, 0.0)
            return self.cmd
        if state.t >= self.next_frame:
            t0 = time.perf_counter()
            bgr, depth = self.view.grab(state.pos, state.quat, craters)
            img = image_input(bgr, depth)
            st = state_features(state, self.prev)
            with self.torch.no_grad():
                a = self.net(self.torch.from_numpy(img[None].copy()), self.torch.from_numpy(st[None]))[0].numpy()
            a = np.clip(a, -1.0, 1.0).astype(np.float32)
            self.prev = a
            self.ctl.set = action_to_setpoint(a)
            self.last_img = img
            self.next_frame = state.t + 1.0 / DECISION_HZ
            self.frames += 1
            self.ms = 0.9 * self.ms + 0.1 * (time.perf_counter() - t0) * 1000
        if self.cmd is None or self.n % 4 == 0:      # Regler 125 Hz bei 500 Hz Physik
            self.cmd = self.ctl.command(state)
        self.n += 1
        return self.cmd

    def preview(self, scale=2):
        """Eingabebild als RGB-Array (H*scale, W*2*scale, 3): links Farbe, rechts Nähe (Tiefe)."""
        if self.last_img is None:
            return None
        rgb = self.last_img[:3].transpose(1, 2, 0)
        near = np.repeat(self.last_img[3][:, :, None], 3, axis=2)
        near = (near.astype(np.float32) * np.array([1.0, 0.55, 0.15])).astype(np.uint8)   # warm = nah
        both = np.concatenate([rgb, near], axis=1)
        return np.repeat(np.repeat(both, scale, axis=0), scale, axis=1)


# ----------------------------------------------------------------------------- OSD: was das Netz sieht
class NNOverlay:
    """Kleines Fenster im OSD: Eingabebild des Netzes (Farbe + Nähe), Modellversion, Trainingsstand,
    und was das Netz gerade will (Tempo, Gieren)."""

    def __init__(self, renderer):
        self.r = renderer
        self.tex = None
        self.status, self.status_t = None, 0.0

    def draw(self, hud, pilot, now):
        import moderngl
        r, T = self.r, hud.text
        W, H = r.size
        s = hud.scale()
        img = pilot.preview(scale=1) if pilot is not None else None
        if now - self.status_t > 2.0:
            self.status, self.status_t = training_status(), now
        x0, y0 = 30 * s, 150 * s
        r.begin_2d()
        T.draw("NETZ SIEHT", x0, y0, int(19 * s), "left", tint=(0.3, 0.95, 1, 1))
        if img is not None:
            h, w = img.shape[:2]
            rgba = np.concatenate([img, np.full((h, w, 1), 255, np.uint8)], axis=2)
            if self.tex is None or self.tex.size != (w, h):
                if self.tex is not None:
                    self.tex.release()
                self.tex = r.ctx.texture((w, h), 4)
                self.tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
            self.tex.write(np.ascontiguousarray(rgba).tobytes())
            dw = 460 * s
            dh = dw * h / w
            hud.rect(x0 + dw / 2, y0 + 18 * s + dh / 2, dw + 8 * s, dh + 8 * s, (0, 0, 0, 0.45))
            r.sprite(self.tex, x0 + dw / 2, y0 + 18 * s + dh / 2, dw, dh)
            T.draw("Kamera", x0 + 6 * s, y0 + 30 * s, int(14 * s), "left", bold=False)
            T.draw("Nähe", x0 + dw / 2 + 6 * s, y0 + 30 * s, int(14 * s), "left", bold=False)
            y = y0 + 34 * s + dh
        else:
            y = y0 + 30 * s
        lines = [pilot.label() if pilot is not None else "kein Modell"]
        st = self.status
        if pilot is not None and pilot.ok:
            m = pilot.meta
            steps = m.get("steps_total", 0)
            lines.append(f"trainiert: {steps / 1e6:.2f} Mio. Schritte, {m.get('episodes', 0)} Flüge, "
                         f"{m.get('minutes', 0):.0f} min")
            vf, vr, vu, yr = pilot.ctl.set
            lines.append(f"will: {vf:4.1f} m/s vor  {vr:+.1f} seitl.  {vu:+.1f} hoch  Gier {math.degrees(yr):+4.0f}°/s")
        if st and st.get("running"):
            lines.append(f"Training läuft: v{st.get('version')} ({st.get('phase')}), bestes {st.get('best_gates', 0):.1f} Tore")
        for i, t in enumerate(lines):
            T.draw(t, x0, y + 8 * s + i * 24 * s, int(17 * s), "left", bold=i == 0,
                   tint=(1, 1, 1, 0.9) if i else (0.3, 0.95, 1, 1))
