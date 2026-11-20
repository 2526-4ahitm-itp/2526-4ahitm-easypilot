"""Bildschirm-Anzeige (OSD wie bei FPV-Brillen), Tor-Markierung und Menü."""
import math

import numpy as np
from collections import OrderedDict

import pygame

WHITE = (255, 255, 255)
MAGENTA = (1.0, 0.25, 0.9, 1.0)


class Text:
    """Text als Textur, weiß mit dunklem Rand (lesbar vor Himmel und Wiese). LRU-Cache."""

    def __init__(self, renderer, limit=400):
        self.r = renderer
        self.cache = OrderedDict()
        self.fonts = {}
        self.limit = limit
        self.retired, self.retiring = [], []

    def font(self, size, bold, family=None):
        key = (size, bold, family)
        if key not in self.fonts:
            self.fonts[key] = pygame.font.SysFont(family or "Avenir Next,Helvetica Neue,Helvetica", size, bold=bold)
        return self.fonts[key]

    def get(self, text, size, bold=True, outline=True, family=None):
        key = (text, size, bold, outline, family)
        hit = self.cache.get(key)
        if hit:
            self.cache.move_to_end(key)
            return hit
        f = self.font(size, bold, family)
        fg = f.render(text, True, WHITE)
        pad = max(2, size // 14) if outline else 0
        surf = pygame.Surface((fg.get_width() + 2 * pad, fg.get_height() + 2 * pad), pygame.SRCALPHA)
        if outline:
            bg = f.render(text, True, (0, 0, 0))
            bg.set_alpha(150)
            for dx in (-pad, 0, pad):
                for dy in (-pad, 0, pad):
                    if dx or dy:
                        surf.blit(bg, (pad + dx, pad + dy))
        surf.blit(fg, (pad, pad))
        tex = self.r.texture(surf)
        item = (tex, surf.get_width(), surf.get_height())
        self.cache[key] = item
        if len(self.cache) > self.limit:
            # nicht sofort freigeben: die Textur kann in diesem Frame schon gezeichnet worden sein.
            # Apples OpenGL-auf-Metal stürzt sonst beim flip() ab (Segfault in gldPresentFramebufferData).
            _, (old, _, _) = self.cache.popitem(last=False)
            self.retired.append(old)
        return item

    def end_frame(self):
        """Nach pygame.display.flip(): Texturen aus dem vorletzten Frame freigeben."""
        for tex in self.retiring:
            tex.release()
        self.retiring, self.retired = self.retired, []

    def draw(self, text, x, y, size, anchor="center", tint=(1, 1, 1, 1), bold=True, outline=True, family=None):
        tex, w, h = self.get(text, size, bold, outline, family)
        cx = {"center": x, "left": x + w / 2, "right": x - w / 2}[anchor]
        self.r.sprite(tex, cx, y, w, h, tint=tint)
        return w, h


def _shape(size, draw):
    """Form doppelt so groß zeichnen und verkleinern (weiche Kanten)."""
    big = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
    draw(big, size * 2)
    return pygame.transform.smoothscale(big, (size, size))


class Shapes:
    def __init__(self, r):
        self.white = r.texture(_fill((4, 4), (255, 255, 255, 255)))

        def diamond(s, n):
            c, k = n / 2, n * 0.42
            pts = [(c, c - k), (c + k, c), (c, c + k), (c - k, c)]
            pygame.draw.polygon(s, (255, 255, 255, 255), pts, width=max(3, n // 14))
        self.diamond = r.texture(_shape(96, diamond))

        def arrow(s, n):
            pygame.draw.polygon(s, (255, 255, 255, 255), [(n / 2, n * 0.08), (n * 0.92, n * 0.85),
                                                          (n / 2, n * 0.65), (n * 0.08, n * 0.85)])
        self.arrow = r.texture(_shape(96, arrow))

        def dot(s, n):
            pygame.draw.circle(s, (255, 255, 255, 255), (n / 2, n / 2), n * 0.45)
        self.dot = r.texture(_shape(48, dot))

        def frame(s, n):
            pygame.draw.rect(s, (255, 255, 255, 255), (2, 2, n - 4, n - 4), width=max(3, n // 30), border_radius=n // 10)
        self.frame = r.texture(_shape(128, frame))

        def cross(s, n):
            w = max(3, n // 16)
            c = n / 2
            for a, b in (((c - n * 0.45, c), (c - n * 0.15, c)), ((c + n * 0.15, c), (c + n * 0.45, c)),
                         ((c, c - n * 0.45), (c, c - n * 0.2))):
                pygame.draw.line(s, (255, 255, 255, 255), a, b, w)
            pygame.draw.circle(s, (255, 255, 255, 255), (c, c), w)
        self.cross = r.texture(_shape(64, cross))


def _fill(size, col):
    s = pygame.Surface(size, pygame.SRCALPHA)
    s.fill(col)
    return s


def fmt_time(t):
    if t is None:
        return "–"
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:05.2f}" if m else f"{s:.2f} s"


class Hud:
    def __init__(self, renderer):
        self.r = renderer
        self.text = Text(renderer)
        self.shapes = Shapes(renderer)

    def scale(self):
        return self.r.size[1] / 1080

    def rect(self, cx, cy, w, h, tint):
        self.r.sprite(self.shapes.white, cx, cy, w, h, tint=tint)

    def draw(self, flight, sticks, info, settings, now):
        r, T, S = self.r, self.text, self.shapes
        W, H = r.size
        s = self.scale()
        r.begin_2d()
        d = flight.drone
        o = settings.get("osd") or {"info": True, "klassisch": True}    # Elemente (osd.py)
        if settings["hud"] and o["klassisch"]:                           # Fadenkreuz (Liftoff-Visier: osd.py)
            r.sprite(S.cross, W / 2, H / 2, 34 * s, 34 * s, tint=(1, 1, 1, 0.75))

        bomb = settings.get("mode") == "bomb"
        if bomb:
            self.draw_target(flight, now)
        # Tor-Markierung
        n = len(flight.world.gates)
        if settings["mark"] and not bomb:
            g = flight.world.gates[flight.next_gate]
            dist = math.dist(d.pos, g.center)
            scr, cam = r.project(g.center)
            on = scr is not None and 40 * s < scr[0] < W - 40 * s and 40 * s < scr[1] < H - 40 * s
            pulse = 0.75 + 0.25 * math.sin(now * 7)
            if on:
                size = max(46 * s, min(150 * s, 2600 * s / max(dist, 1)))
                r.sprite(S.diamond, scr[0], scr[1], size, size, tint=(1, 0.25, 0.9, pulse))
                T.draw(str(flight.next_gate + 1), scr[0], scr[1], int(26 * s))
                T.draw(f"{dist:.0f} m", scr[0], scr[1] + size / 2 + 16 * s, int(22 * s))
            else:
                ang = math.atan2(cam[0], cam[1])          # 0 = oben, im Uhrzeigersinn
                rx, ry = W / 2 - 90 * s, H / 2 - 90 * s
                ax, ay = W / 2 + rx * math.sin(ang), H / 2 - ry * math.cos(ang)
                r.sprite(S.arrow, ax, ay, 64 * s, 64 * s, angle=ang, tint=(1, 0.25, 0.9, pulse))
                T.draw(f"Tor {flight.next_gate + 1}  {dist:.0f} m", ax - 90 * s * math.sin(ang),
                       ay + 90 * s * math.cos(ang), int(22 * s))

        if not settings["hud"]:
            return
        if info.get("auto") is not None:
            T.draw(f"AUTOPILOT  {info['auto']}", 30 * s, (104 if o["info"] else 40) * s, int(28 * s), "left",
                   tint=(0.3, 0.95, 1, 1))
        if o["info"]:
            T.draw(f"Flugzeit {fmt_time(flight.flight_time)}", 30 * s, 34 * s, int(21 * s), "left", bold=False)
            T.draw("Esc Menü   R Neustart   P Autopilot   T Steuerung   O Lage   H Anzeige", 30 * s, 64 * s, int(17 * s),
                   "left", tint=(1, 1, 1, 0.7), bold=False)
            T.draw(f"{info['fps']:.0f} fps   {info['lat']:.1f} ms", W - 30 * s, 34 * s, int(19 * s), "right", bold=False)
            T.draw(info["pad"], W - 30 * s, 62 * s, int(16 * s), "right", tint=(1, 1, 1, 0.7), bold=False)
        if not o["klassisch"]:
            return
        # oben: Tor und Runde (Bomben-Modus: Ziel und Treffer)
        if bomb:
            t = flight.target_info()
            T.draw(f"ZIEL: {t['name'].upper()}" if t else "KEIN ZIEL", W / 2, 44 * s, int(36 * s), tint=(1, 0.35, 0.3, 1))
            T.draw(f"Treffer {flight.hits}    Daneben {flight.misses}    Zeit {now - flight.target_since:.1f} s    "
                   f"übrig {int(flight.entities.alive.sum())}", W / 2, 86 * s, int(21 * s), bold=False)
        else:
            T.draw(f"TOR {flight.next_gate + 1} / {n}", W / 2, 44 * s, int(36 * s))
        lap = None if flight.lap_start is None else flight.flight_time - flight.lap_start
        if not bomb:
            T.draw(f"Runde {fmt_time(lap)}    Letzte {fmt_time(flight.last_lap)}    Beste {fmt_time(settings.get('best_lap'))}",
                   W / 2, 86 * s, int(21 * s), bold=False)

        # unten: Tempo, Höhe, Sticks
        speed = math.sqrt(sum(v * v for v in d.vel)) * 3.6
        w, _ = T.draw(f"{speed:.0f}", 40 * s, H - 70 * s, int(60 * s), "left")
        T.draw("km/h", 50 * s + w, H - 60 * s, int(22 * s), "left", bold=False)
        T.draw("m", W - 40 * s, H - 60 * s, int(22 * s), "right", bold=False)
        T.draw(f"{d.pos[1]:.1f}", W - 75 * s, H - 70 * s, int(60 * s), "right")
        box = 92 * s
        for i, (sx, sy) in enumerate(((sticks[1], sticks[0] * 2 - 1), (sticks[3], sticks[2]))):
            cx, cy = W / 2 + (i * 2 - 1) * (box / 2 + 14 * s), H - 30 * s - box / 2
            self.rect(cx, cy, box, box, (0, 0, 0, 0.25))
            r.sprite(S.frame, cx, cy, box, box, tint=(1, 1, 1, 0.55))
            r.sprite(S.dot, cx + sx * (box / 2 - 10 * s), cy - sy * (box / 2 - 10 * s), 16 * s, 16 * s,
                     tint=(1, 0.3, 0.9, 1) if i == 0 else (0.3, 0.9, 1, 1))
        T.draw(f"Gas {sticks[0] * 100:.0f} %", W / 2, H - 50 * s - box, int(19 * s), bold=False)

    def draw_target(self, flight, now):
        """Rotes Rahmen-Visier um das Ziel (alle 8 Ecken der Hülle projiziert), sonst Pfeil am Rand."""
        t = flight.target_info()
        if t is None or not t["alive"]:
            return
        r, T, S = self.r, self.text, self.shapes
        W, H = r.size
        s = self.scale()
        lo, hi = t["lo"], t["hi"]
        pts, behind = [], 0
        for x in (lo[0], hi[0]):
            for y in (lo[1], hi[1]):
                for z in (lo[2], hi[2]):
                    scr, _ = r.project((x, y, z))
                    if scr is None:
                        behind += 1
                    else:
                        pts.append(scr)
        dist = math.dist(flight.drone.pos, t["center"])
        pulse = 0.7 + 0.3 * math.sin(now * 8)
        red = (1, 0.12, 0.1, pulse)
        if behind == 0 and pts:
            x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
            y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
            pad = 8 * s
            x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
            if x1 > 0 and x0 < W and y1 > 0 and y0 < H:
                x0, y0, x1, y1 = max(x0, 4), max(y0, 4), min(x1, W - 4), min(y1, H - 4)
                th = max(2.0, 3 * s)
                L = max(14 * s, min(x1 - x0, y1 - y0) * 0.28)
                self.rect((x0 + x1) / 2, y0, x1 - x0, th * 0.5, (1, 0.12, 0.1, 0.45))   # dünner Rahmen
                self.rect((x0 + x1) / 2, y1, x1 - x0, th * 0.5, (1, 0.12, 0.1, 0.45))
                self.rect(x0, (y0 + y1) / 2, th * 0.5, y1 - y0, (1, 0.12, 0.1, 0.45))
                self.rect(x1, (y0 + y1) / 2, th * 0.5, y1 - y0, (1, 0.12, 0.1, 0.45))
                for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
                    self.rect(cx + sx * L / 2, cy, L, th * 2, red)                       # dicke Ecken
                    self.rect(cx, cy + sy * L / 2, th * 2, L, red)
                T.draw(f"ZIEL  {dist:.0f} m", (x0 + x1) / 2, max(20 * s, y0 - 22 * s), int(24 * s), tint=(1, 0.3, 0.25, 1))
                return
        c = np.array(t["center"])
        _, cam = r.project(tuple(c))
        ang = math.atan2(cam[0], cam[1])
        rx, ry = W / 2 - 90 * s, H / 2 - 90 * s
        ax, ay = W / 2 + rx * math.sin(ang), H / 2 - ry * math.cos(ang)
        r.sprite(S.arrow, ax, ay, 70 * s, 70 * s, angle=ang, tint=red)
        T.draw(f"ZIEL {dist:.0f} m", ax - 95 * s * math.sin(ang), ay + 95 * s * math.cos(ang), int(22 * s),
               tint=(1, 0.3, 0.25, 1))

    def flash(self, alpha):
        if alpha > 0.01:
            self.r.begin_2d()
            W, H = self.r.size
            self.rect(W / 2, H / 2, W, H, (1, 0.85, 0.6, alpha))

    def message(self, text, sub=None, color=(1, 1, 1, 1)):
        W, H = self.r.size
        s = self.scale()
        self.r.begin_2d()
        tex, w, h = self.text.get(text, int(54 * s))
        self.rect(W / 2, H * 0.33, w + 60 * s, h + (46 * s if sub else 16 * s), (0, 0, 0, 0.45))
        self.r.sprite(tex, W / 2, H * 0.33 - (14 * s if sub else 0), w, h, tint=color)
        if sub:
            self.text.draw(sub, W / 2, H * 0.33 + h / 2 + 2 * s, int(22 * s), bold=False)


class Menu:
    """Menü: Pfeile/Enter oder Maus. items: dicts mit label, kind ('action'|'value'|'toggle'), key."""

    def __init__(self, hud, items):
        self.hud, self.items, self.sel = hud, items, 0
        self.rows = []

    def handle(self, ev, values):
        """-> Aktion ('resume', 'restart', 'quit', ('change', key, +1/-1)) oder None."""
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 1) % len(self.items)
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 1) % len(self.items)
            elif ev.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                it = self.items[self.sel]
                if it["kind"] != "action":
                    return ("change", it["key"], 1 if ev.key in (pygame.K_RIGHT, pygame.K_d) else -1)
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self.activate(self.sel, 1)
            elif ev.key == pygame.K_ESCAPE:
                return "resume"
            elif ev.key == pygame.K_q:
                return "quit"
        elif ev.type == pygame.MOUSEMOTION:
            i = self.row_at(ev.pos)
            if i is not None:
                self.sel = i
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            i = self.row_at(ev.pos)
            if i is not None:
                self.sel = i
                return self.activate(i, -1 if ev.pos[0] < self.hud.r.size[0] / 2 - 40 else 1)
        return None

    def activate(self, i, direction):
        it = self.items[i]
        if it["kind"] == "action":
            return it["key"]
        return ("change", it["key"], direction)

    def row_at(self, pos):
        for i, (y0, y1, x0, x1) in enumerate(self.rows):
            if y0 <= pos[1] <= y1 and x0 <= pos[0] <= x1:
                return i
        return None

    def draw(self, values, title, subtitle):
        h, r, T = self.hud, self.hud.r, self.hud.text
        W, H = r.size
        s = h.scale()
        r.begin_2d()
        h.rect(W / 2, H / 2, W, H, (0.02, 0.03, 0.06, 0.45))
        row = min(56 * s, (H - 270 * s) / len(self.items))      # viele Punkte: Zeilen enger, passt immer
        pw, ph = 620 * s, 190 * s + row * len(self.items) + 50 * s
        top = H / 2 - ph / 2
        h.rect(W / 2, H / 2, pw, ph, (0.06, 0.07, 0.11, 0.88))
        h.rect(W / 2, top + 3 * s, pw, 6 * s, MAGENTA)
        T.draw(title, W / 2, top + 62 * s, int(44 * s))
        T.draw(subtitle, W / 2, top + 112 * s, int(20 * s), tint=(1, 1, 1, 0.7), bold=False, outline=False)
        self.rows = []
        y = top + 170 * s
        for i, it in enumerate(self.items):
            cy = y + row / 2
            if i == self.sel:
                h.rect(W / 2, cy, pw - 40 * s, row - 6 * s, (1, 0.25, 0.9, 0.85))
            label = it["label"]
            if it["kind"] != "action":
                val = values[it["key"]]
                T.draw(label, W / 2 - pw / 2 + 50 * s, cy, int(25 * s), "left", outline=False, bold=i == self.sel)
                T.draw(f"‹  {val}  ›", W / 2 + pw / 2 - 50 * s, cy, int(25 * s), "right", outline=False)
            else:
                T.draw(label, W / 2, cy, int(27 * s), outline=False)
            self.rows.append((cy - row / 2, cy + row / 2, W / 2 - pw / 2, W / 2 + pw / 2))
            y += row
        T.draw("Pfeiltasten wählen / ändern    Enter oder Klick    Knopf an der Fernsteuerung = Weiter",
               W / 2, top + ph - 34 * s, int(16 * s), tint=(1, 1, 1, 0.6), bold=False, outline=False)
