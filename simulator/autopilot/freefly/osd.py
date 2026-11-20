"""OSD wie in Liftoff (Menü „Anzeige / OSD …“): weiß, dünn, leicht durchsichtig, alles bewegt sich live.

Elemente (jedes einzeln schaltbar, gespeichert in freefly.local.json unter "osd"):
  zeit      oben Mitte: Zeit 00:00:00, darunter RUNDE / TOR (Bomben-Modus: ZIEL, Treffer)
  kompass   Kompass-Band ' N ' E ' S ' W, läuft mit der Gierrichtung seitlich mit (+ Punkt zum nächsten Tor/Ziel)
  rahmen    gestrichelte Leisten links/rechts und gepunktete Linie oben (Sichtrahmen)
  visier    Fadenkreuz-Kreis in der Bildmitte (Kamera-/Drohnen-Nase)
  fpm       Flugrichtungs-Marker: wohin die Geschwindigkeit zeigt
  leiter    Horizont- und Nickleiter (alle 10°), dreht mit Roll, wandert mit Nick, nur im Rahmen
  werte     rechts oben ALT (m) und GES (km/h)
  gas       Gas-Balken unten Mitte
  sticks    Stick-Kreuz unten Mitte (gestrichelte Achsen, Ring = aktuelle Sticks)
  rec       links unten rot „● Rec“
  liste     rechts: Mitspieler (Du, Autopilot, Bestzeit, letzte Runde)
  info      alte Infozeile: Flugzeit, Tasten, fps/Latenz, Fernsteuerung
  klassisch alte EasyPilot-Anzeige: TOR x / 12 oben, große Zahlen unten, Stick-Kästen
  horizont, lkompass, leisten, drohne3d, karte   Lageanzeige aus attitude.py (rundes Instrument, Gradkompass,
            Tempo-/Höhenleisten, 3D-Drohne, Minikarte)
  gross     „Zuschauer“: alles größer und mit kurzen Erklärungen

Presets: Liftoff, Minimal, Zuschauer, Aus. Taste H schaltet alles (settings["hud"]), Taste O die Lageanzeige.
Gezeichnet wird mit attitude.Batch (alle Striche, Punkte, Ringe in einem Zeichenaufruf) und Text-Sprites;
wechselnde Zahlen werden gedrosselt neu gesetzt (jede neue Zeichenkette kostet eine Textur).
"""
import math

import numpy as np

from .attitude import Batch, lage_data

ELEMENTS = [
    ("zeit", "Zeit und Runde"),
    ("kompass", "Kompass-Band (Liftoff)"),
    ("rahmen", "Sichtrahmen"),
    ("visier", "Fadenkreuz"),
    ("fpm", "Flugrichtung (Marker)"),
    ("leiter", "Horizont-/Nickleiter"),
    ("werte", "Höhe und Tempo (rechts oben)"),
    ("gas", "Gas-Balken"),
    ("sticks", "Stick-Kreuz"),
    ("rec", "Rec (roter Punkt)"),
    ("liste", "Mitspieler-Liste"),
    ("info", "Infozeile (Tasten, fps)"),
    ("klassisch", "Klassische Anzeige"),
    ("horizont", "Horizont-Instrument"),
    ("lkompass", "Kompass mit Grad"),
    ("leisten", "Tempo-/Höhen-Leisten"),
    ("drohne3d", "3D-Drohne"),
    ("karte", "Minikarte"),
    ("gross", "Groß + Erklärungen"),
]
LAGE = ("horizont", "lkompass", "leisten", "drohne3d", "karte")       # Taste O

_on = lambda *keys: {k: k in keys for k, _ in ELEMENTS}
PRESETS = {
    "liftoff": _on("zeit", "kompass", "rahmen", "visier", "fpm", "leiter", "werte", "gas", "sticks", "liste"),
    "minimal": _on("zeit", "visier", "fpm", "werte"),
    "zuschauer": _on("zeit", "visier", "fpm", "werte", "gas", "sticks", "horizont", "lkompass", "drohne3d", "karte",
                     "gross"),
    "aus": _on(),
}
PRESET_LABEL = {"liftoff": "Liftoff", "minimal": "Minimal", "zuschauer": "Zuschauer", "aus": "Aus"}

MENU = [{"label": "Voreinstellung", "kind": "value", "key": "osd_preset"},
        {"label": "Anzeige an (H)", "kind": "toggle", "key": "hud"}] + \
       [{"label": label, "kind": "toggle", "key": "osd:" + k} for k, label in ELEMENTS] + \
       [{"label": "Zurück", "kind": "action", "key": "back"}]


def ensure(s):
    """settings["osd"] vollständig machen; alte Schalter "lage"/"karte" (Lageanzeige) übernehmen."""
    o = s.get("osd")
    if not isinstance(o, dict):
        o = dict(PRESETS["liftoff"])
        if s.get("lage"):
            o.update({k: True for k in LAGE if k != "karte"})
            o["karte"] = bool(s.get("karte"))
    for k, _ in ELEMENTS:
        o[k] = bool(o.get(k, PRESETS["liftoff"][k]))
    s["osd"] = o
    s.pop("lage", None)
    s.pop("karte", None)
    return o


def preset_of(s):
    o = s["osd"]
    for name, p in PRESETS.items():
        if all(o[k] == p[k] for k, _ in ELEMENTS):
            return name
    return None


def apply_preset(s, name):
    s["osd"] = dict(PRESETS[name])
    s["hud"] = True


def toggle_lage(s):
    o = s["osd"]
    on = not any(o[k] for k in LAGE)
    for k in LAGE:
        o[k] = on
    return on


def menu_values(s):
    p = preset_of(s)
    v = {"osd_preset": PRESET_LABEL[p] if p else "Eigene", "hud": "an" if s["hud"] else "aus"}
    v.update({"osd:" + k: "an" if s["osd"][k] else "aus" for k, _ in ELEMENTS})
    return v


def change(s, key, direction):
    """Menü-Änderung; True, wenn es ein OSD-Schalter war."""
    if key == "osd_preset":
        order = list(PRESETS)
        p = preset_of(s)
        i = order.index(p) if p else -1 if direction > 0 else 0
        apply_preset(s, order[(i + (direction or 1)) % len(order)])
        return True
    if key.startswith("osd:"):
        k = key[4:]
        s["osd"][k] = not s["osd"][k]
        return True
    return False


def shown(s, key):
    return bool(s["hud"] and s["osd"].get(key))


def clock(t):
    """Liftoff-Uhr mm:ss:hh."""
    t = max(0.0, t or 0.0)
    m, sec = divmod(t, 60)
    return f"{int(m):02d}:{int(sec):02d}:{int(sec * 100) % 100:02d}"


FONT = "DIN Alternate,Avenir Next Condensed,Helvetica Neue"
W_A = 0.92              # Deckkraft Schrift
L_A = 0.85              # Deckkraft Linien
WHITE = (1, 1, 1, L_A)


class LiftoffOsd:
    def __init__(self, renderer):
        self.r = renderer
        self.batch = Batch(renderer.ctx)
        self._texts = {}
        self.fpm = None
        self.laps, self._lap_start = 0, None

    def _txt(self, key, now, text, hz=15):
        hit = self._texts.get(key)
        if hit is None or now - hit[0] >= 1 / hz or now < hit[0]:
            self._texts[key] = hit = (now, text)
        return hit[1]

    def _lap(self, flight):
        """Runden zählen: lap_start springt bei jedem Zieldurchflug weiter, None nach Neustart."""
        ls = flight.lap_start
        if ls is None:
            self.laps = 0
        elif self._lap_start is not None and ls != self._lap_start:
            self.laps += 1
        self._lap_start = ls
        return self.laps

    # ------------------------------------------------------------------ zeichnen

    def draw(self, hud, flight, sticks, info, settings, now, dt):
        """Alles außer der Lageanzeige (attitude.Lage); nur wenn settings["hud"]."""
        if not settings["hud"]:
            return
        o = settings["osd"]
        r, T, B = self.r, hud.text, self.batch
        W, H = r.size
        g = 1.3 if o["gross"] else 1.0
        s = hud.scale()
        S = s * g
        big = o["gross"]
        bomb = settings.get("mode") == "bomb"
        d = flight.drone
        L = lage_data(flight)
        r.begin_2d()
        B.clear()
        B.size = r.size                              # falls mehr als BATCH_N Teile: Zwischen-flush braucht die Größe
        texts = []                                   # (text, x, y, size, anchor, tint) nach dem Batch

        def txt(text, x, y, size, anchor="center", tint=(1, 1, 1, W_A), bold=True):
            texts.append((text, x, y, int(size), anchor, tint, bold))

        lap_n = self._lap(flight)
        frame_x = 307 * s                            # halbe Breite des Sichtrahmens
        f_top, f_bot = 0.252 * H, 0.745 * H

        # ---- oben Mitte: Zeit, Runde / Ziel
        y_cmp = 162 * s
        if o["zeit"]:
            if bomb:
                t = flight.target_info()
                tt = now - flight.target_since
                txt(self._txt("clock", now, clock(tt), 30), W / 2, 55 * S, 32 * S)
                name = t["name"].upper() if t else "KEIN ZIEL"
                txt(self._txt("sub", now, f"ZIEL {name}   TREFFER {flight.hits}"), W / 2, 100 * S, 21 * S,
                    tint=(1, 0.55, 0.5, W_A))
            else:
                lap = 0.0 if flight.lap_start is None else flight.flight_time - flight.lap_start
                txt(self._txt("clock", now, clock(lap), 30), W / 2, 55 * S, 32 * S)
                n = len(flight.world.gates)
                name = getattr(flight.world, "track_info", {}).get("name", "")      # Strecke (tracks.py)
                txt(f"{name.upper()}   RUNDE {lap_n + 1}   TOR {flight.next_gate + 1} / {n}".strip(), W / 2, 100 * S, 21 * S)
            if big:
                txt("Rundenzeit" if not bomb else "Zeit für dieses Ziel", W / 2, 20 * S, 15 * S,
                    tint=(1, 1, 1, 0.7), bold=False)
            y_cmp = 128 * S + 34 * s
        if o["lkompass"]:
            y_cmp = max(y_cmp, (236 if big else 190) * s)   # Gradkompass (attitude.py) liegt bei 136 bzw. 180 px

        # ---- Kompass-Band
        goal = self._goal(flight, bomb)
        if o["kompass"]:
            k = 1.15 * S                              # px pro Grad
            half = 200 * S
            yaw = L["yaw"]
            letters = ("N", "O", "S", "W") if big else ("N", "E", "S", "W")
            for i in range(16):                       # wie Liftoff: ' | ' N ' | ' E …  (alle 22,5°)
                a = i * 22.5
                x = ((a - yaw + 180) % 360 - 180) * k
                if abs(x) > half:
                    continue
                fade = max(0.0, 1.0 - (abs(x) / half) ** 3)
                if i % 4 == 0:
                    txt(letters[i // 4], W / 2 + x, y_cmp, 30 * S, tint=(1, 1, 1, W_A * fade))
                elif i % 2 == 0:
                    B.add(W / 2 + x, y_cmp, 3 * S, 19 * S, (1, 1, 1, L_A * fade))
                else:
                    B.add(W / 2 + x, y_cmp - 7 * S, 3 * S, 7 * S, (1, 1, 1, L_A * fade))
            B.add(W / 2, y_cmp + 20 * S, 2 * S, 7 * S, (1, 1, 1, 0.7))      # aktuelle Richtung
            if goal is not None:
                brg = math.degrees(math.atan2(goal[0] - d.pos[0], goal[2] - d.pos[2]))
                x = max(-half, min(half, ((brg - yaw + 180) % 360 - 180) * k))
                B.add(W / 2 + x, y_cmp + 21 * S, 9 * S, 9 * S,
                      (1, 0.2, 0.15, 0.95) if bomb else (1, 0.3, 0.9, 0.95), dot=True)
            if big:
                txt(f"Richtung {L['yaw']:.0f}°", W / 2 + half + 16 * S, y_cmp, 16 * S, "left", bold=False)

        # ---- Sichtrahmen
        if o["rahmen"]:
            n = 11
            for i in range(n):
                y = f_top + (f_bot - f_top) * i / (n - 1)
                for sx in (-1, 1):
                    B.add(W / 2 + sx * frame_x, y, 7 * s, 4.5 * s, WHITE)
            for x0, x1 in ((-195, -50), (30, 178)):
                x = x0
                while x <= x1:
                    B.add(W / 2 + x * s, f_top, 4.5 * s, 4.5 * s, WHITE)
                    x += 24.5

        # ---- Horizont-/Nickleiter
        if o["leiter"]:
            self._ladder(B, d, L, W, H, s, frame_x, f_top, f_bot)

        # ---- Fadenkreuz und Flugrichtung
        if o["visier"]:
            cx, cy, R = W / 2, H / 2, 11 * S
            B.add(cx, cy, 2 * R, 2 * R, WHITE, dot=2 + 2.2 * s / R)
            B.add(cx, cy, 4 * S, 4 * S, WHITE, dot=True)
            for sx, sy, w, h in ((-1, 0, 11, 2.2), (1, 0, 11, 2.2), (0, -1, 2.2, 9)):
                B.add(cx + sx * (R + 9 * S), cy + sy * (R + 8 * S), w * S, h * S, WHITE)
            if big:
                txt("Kamera / Nase", cx + R + 26 * S, cy + 14 * S, 15 * S, "left", bold=False)
        if o["fpm"]:
            self._fpm(B, txt, d, W, H, S, big, frame_x, dt)

        # ---- rechts oben: ALT, GES
        if o["werte"]:
            xl, xv = W - 262 * S, W - 236 * S
            rows = (("HÖHE" if big else "ALT", "m", f"{d.pos[1]:.0f}", 55),
                    ("TEMPO" if big else "GES", "km/h", f"{L['speed']:.0f}", 113))
            if hasattr(d, "volts"):                  # Physik „Realistisch“: Akkuspannung unter Last (physics_real)
                rows += (("AKKU" if big else "BAT", f"V  {d.volts / d.p.cells:.2f}/Z", f"{d.volts:.1f}", 171),)
            for i, (lab, unit, val, y) in enumerate(rows):
                y *= S
                low = i == 2 and d.volts / d.p.cells < 3.5        # unter 3,5 V je Zelle: rot (landen)
                tint = (1, 0.35, 0.3, W_A) if low else (1, 1, 1, W_A)
                txt(lab, xl, y - 6 * S, 26 * S, "right", tint=tint)
                txt(self._txt("u%d" % i, now, unit) if i == 2 else unit, xl, y + 17 * S, 15 * S, "right", bold=False,
                    tint=tint)
                txt(self._txt("v%d" % i, now, val), xv, y, 34 * S, "left", tint=tint)

        # ---- unten Mitte: Gas-Balken und Stick-Kreuz
        gy = H - (100 if big else 84) * S
        half = 68 * S
        lx, rx = W / 2 - 83 * S, W / 2 + 80 * S
        if o["gas"]:
            y = gy - half - 30 * S
            w = 300 * S
            B.add(W / 2, y, w, 9 * S, (1, 1, 1, 0.16))
            th = max(0.0, min(1.0, sticks[0]))
            B.add(W / 2 - w / 2 + w * th / 2, y, w * th, 9 * S, (1, 1, 1, 0.92))
            if big:
                txt(self._txt("gas", now, f"Gas {th * 100:.0f} %"), W / 2, y - 22 * S, 16 * S, bold=False)
        if o["sticks"]:
            self._dash(B, lx - half, rx + half, gy, horizontal=True, s=S)
            for x in (lx, rx):
                self._dash(B, gy - half, gy + half, x, horizontal=False, s=S)
            for (sx, sy), cx in (((sticks[1], sticks[0] * 2 - 1), lx), ((sticks[3], sticks[2]), rx)):
                px, py = cx + max(-1, min(1, sx)) * half, gy - max(-1, min(1, sy)) * half
                B.add(px, py, 16 * S, 16 * S, (1, 1, 1, 0.95), dot=2 + 2.4 / 8)
                B.add(px, py, 4 * S, 4 * S, (1, 1, 1, 0.95), dot=True)
            if big:
                txt("Gas / Drehen", lx, gy + half + 15 * S, 15 * S, bold=False)
                txt("Vor / Seitlich", rx, gy + half + 15 * S, 15 * S, bold=False)

        # ---- Rec, Mitspieler
        if o["rec"]:
            B.add(22 * s, H - 20 * s, 12 * s, 12 * s, (1, 0.18, 0.15, 0.95), dot=True)
            txt("Rec", 34 * s, H - 20 * s, 20 * s, "left", tint=(1, 0.25, 0.2, 0.95), bold=False)
        if o["liste"]:
            rows = [("Du", "D")]
            if info.get("auto"):
                rows.append(("Autopilot", "A"))
            if settings.get("best_lap") and not bomb:
                rows.append((f"Bestzeit  {clock(settings['best_lap'])}", "B"))
            if flight.last_lap and not bomb:
                rows.append((f"Letzte  {clock(flight.last_lap)}", "L"))
            if bomb:
                rows.append((f"Treffer {flight.hits}  Daneben {flight.misses}", "Z"))
            bx = W - 55 * s
            for i, (name, ic) in enumerate(rows):
                y = 275 * s + i * 50 * s
                b = 30 * s
                for dx, dy, w, h in ((0, -1, b, 2 * s), (0, 1, b, 2 * s), (-1, 0, 2 * s, b), (1, 0, 2 * s, b)):
                    B.add(bx + dx * b / 2, y + dy * b / 2, w, h, (1, 1, 1, 0.6))
                B.add(bx, y, b, b, (1, 1, 1, 0.12))
                txt(ic, bx, y, 17 * s, bold=True)
                txt(name, bx - 28 * s, y, 19 * s, "right")

        B.flush(r.size)
        for text, x, y, size, anchor, tint, bold in texts:
            T.draw(text, x, y, size, anchor, tint=tint, bold=bold, family=FONT)

    @staticmethod
    def _goal(flight, bomb):
        if bomb:
            t = flight.target_info()
            return t["center"] if t and t["alive"] else None
        return flight.world.gates[flight.next_gate].center

    @staticmethod
    def _dash(B, a, b, c, horizontal, s):
        L, gap = 13 * s, 7 * s
        x = a
        while x < b:
            e = min(b, x + L)
            m = (x + e) / 2
            if horizontal:
                B.add(m, c, e - x, 2 * s, (1, 1, 1, 0.8))
            else:
                B.add(c, m, 2 * s, e - x, (1, 1, 1, 0.8))
            x = e + gap

    def _ladder(self, B, d, L, W, H, s, frame_x, f_top, f_bot):
        """Linien gleicher Höhenwinkel (0° = Horizont, ±10°, ±20° …) in Flugrichtung der Nase, mit der Kamera projiziert:
        so stimmen Roll, Nick, Kamera-Uptilt und Sichtfeld automatisch."""
        els = np.radians(np.repeat(np.arange(-40, 50, 10), 2))
        az = math.radians(L["yaw"]) + np.tile((-0.02, 0.02), len(els) // 2)
        P = np.ones((4, len(els)))                    # alle Punkte in einer Matrix-Multiplikation projizieren
        P[0] = d.pos[0] + 500 * np.sin(az) * np.cos(els)
        P[1] = d.pos[1] + 500 * np.sin(els)
        P[2] = d.pos[2] + 500 * np.cos(az) * np.cos(els)
        c = self.r.vp @ P
        ok = c[3] > 1e-6
        w = np.where(ok, c[3], 1.0)
        X = (c[0] / w * 0.5 + 0.5) * W
        Y = (0.5 - c[1] / w * 0.5) * H
        for j, e in enumerate(range(-40, 50, 10)):
            i0, i1 = 2 * j, 2 * j + 1
            if not (ok[i0] and ok[i1]):
                continue
            pts = ((X[i0], Y[i0]), (X[i1], Y[i1]))
            cx, cy = (pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2
            if abs(cx - W / 2) > frame_x - 30 * s or not (f_top + 12 * s < cy < f_bot - 12 * s):
                continue
            ang = math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0])
            c, sn = math.cos(ang), math.sin(ang)
            if e == 0:
                segs, a = ((-250, -45), (45, 250)), 0.95
            else:
                segs, a = ((-110, -45), (45, 110)), 0.42 if e > 0 else 0.3
            fade = 1.0 - min(1.0, abs(cy - H / 2) / (0.5 * (f_bot - f_top)))
            for u0, u1 in segs:
                u0 *= s
                u1 *= s
                m = (u0 + u1) / 2
                B.add(cx + c * m, cy + sn * m, u1 - u0, (3.2 if e == 0 else 1.8) * s, (1, 1, 1, a * (0.4 + 0.6 * fade)),
                      angle=ang)
                if e < 0:                              # unter dem Horizont: kurzer Haken nach unten (wie in Flugzeug-HUDs)
                    tip = u1 if abs(u1) > abs(u0) else u0
                    hx, hy = cx + c * tip, cy + sn * tip
                    B.add(hx - sn * 5 * s, hy + c * 5 * s, 1.8 * s, 10 * s, (1, 1, 1, a * 0.8), angle=ang)

    def _fpm(self, B, txt, d, W, H, S, big, frame_x, dt):
        v = d.vel
        sp = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        if sp < 1.0:
            self.fpm = None
            return
        p = d.pos
        scr, cam = self.r.project((p[0] + v[0] / sp * 500, p[1] + v[1] / sp * 500, p[2] + v[2] / sp * 500))
        alpha = 0.95 * min(1.0, (sp - 1.0) / 2.0)
        if scr is None:                               # nach hinten: an den Rand in Richtung der Bewegung
            ang = math.atan2(cam[0], cam[1])
            scr = (W / 2 + math.sin(ang) * W, H / 2 - math.cos(ang) * H)
        x, y = scr
        mx, my = frame_x + 40 * S, H * 0.36
        out = abs(x - W / 2) > mx or abs(y - H / 2) > my
        if out:
            k = min(mx / max(1e-6, abs(x - W / 2)), my / max(1e-6, abs(y - H / 2)))
            x, y = W / 2 + (x - W / 2) * k, H / 2 + (y - H / 2) * k
            alpha *= 0.5
        if self.fpm is not None:                      # leicht glätten (kein Zittern bei 150+ fps)
            k = 1.0 - math.exp(-dt * 25.0)
            x, y = self.fpm[0] + (x - self.fpm[0]) * k, self.fpm[1] + (y - self.fpm[1]) * k
        self.fpm = (x, y)
        R = 10 * S
        col = (1, 1, 1, alpha)
        B.add(x, y, 2 * R, 2 * R, col, dot=2 + 0.22)
        B.add(x, y, 4.5 * S, 4.5 * S, col, dot=True)
        if big:                                       # Flügel wie beim Flugzeug-HUD, für Zuschauer deutlicher
            B.add(x - R - 9 * S, y, 14 * S, 2.4 * S, col)
            B.add(x + R + 9 * S, y, 14 * S, 2.4 * S, col)
            B.add(x, y - R - 6 * S, 2.4 * S, 9 * S, col)
            txt("Flugrichtung", x + R + 22 * S, y - 16 * S, 15 * S, "left", tint=(1, 1, 1, alpha), bold=False)
