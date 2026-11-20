"""Neustart-Ablauf im Freiflug: statt hartem Sprung zurück zum Start

  1. kurz auf die Absturzstelle schauen (Kamera fährt hinter/über die Stelle), Meldung groß
  2. sanft abblenden
  3. Drohne steht wieder auf der Plattform, aufblenden
  4. Countdown 3-2-1, dann „LOS!“ (der Autopilot fliegt danach weiter)

Gesamt 2,4 s (Absturz) bis 2,9 s (Bomben-Treffer, die Explosion soll man sehen).
R, Leertaste oder ein Knopf an der Fernsteuerung überspringen alles (skip()).
Die Drohne ist vom Absturz bis zum Ende des Countdowns eingefroren (Flight.frozen).
"""
import math
import random

LOOK = {"crash": 0.9, "hit": 1.4, "done": 0.35}      # s Blick auf die Stelle
FADE_OUT, FADE_IN, COUNT, GO = 0.35, 0.3, 0.9, 0.45


def _ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


class RestartSeq:
    def __init__(self):
        self.active = False
        self.t0 = 0.0
        self.done_at = None            # Ende des Countdowns (für „LOS!“)

    # ------------------------------------------------------------ Ablauf
    def begin(self, now, kind, title, sub, line, color, restart):
        """kind: 'crash' | 'hit' | 'done'. restart(): setzt Drohne/Spiel zurück (main.restart)."""
        self.active, self.t0, self.kind = True, now, kind
        self.title, self.sub, self.line, self.color = title, sub, line, color
        self.restart_cb = restart
        self.restarted = False
        self.done_at = None
        self.look = LOOK.get(kind, 0.9)
        self.t_switch = self.look + FADE_OUT
        self.t_end = self.t_switch + FADE_IN + COUNT

    def skip(self, flight):
        """R / Leertaste / Knopf: sofort fliegen."""
        if not self.active:
            return False
        if not self.restarted:
            self.restart_cb()
        flight.frozen = False
        self.active = False
        self.done_at = None
        return True

    def update(self, now, flight):
        """Pro Frame: Neustart im dunklen Moment, Drohne bis zum Ende des Countdowns festhalten."""
        if not self.active:
            return
        t = now - self.t0
        if not self.restarted:
            if flight.crashed_at is None:
                flight.frozen = True                    # Runden-Ende: Drohne steht, solange abgeblendet wird
            if t >= self.t_switch:
                self.restart_cb()
                self.restarted = True
                flight.frozen = True
        if self.restarted and t >= self.t_end:
            flight.frozen = False
            self.active = False
            self.done_at = now

    @property
    def counting(self):
        return self.active and self.restarted

    # ------------------------------------------------------------ Kamera
    def camera(self, now, flight, shake=0.0):
        """Augenpunkt und Blickziel während des Blicks auf die Absturzstelle, sonst None."""
        if not self.active or self.restarted or flight.crashed_at is None:
            return None
        t = now - self.t0
        focus = flight.crash_pos
        v = flight.crash_vel
        hv = math.hypot(v[0], v[2])
        bx, bz = (-v[0] / hv, -v[2] / hv) if hv > 1 else (0.0, -1.0)
        far = 13.0 if self.kind == "hit" else 6.5
        up = 6.0 if self.kind == "hit" else 2.8
        k = _ease(t / 0.55)
        orbit = 0.25 * t                                 # langsam um die Stelle herum
        cx, sx = math.cos(orbit), math.sin(orbit)
        bx, bz = bx * cx - bz * sx, bx * sx + bz * cx
        d = 1.2 + (far - 1.2) * k
        eye = (focus[0] + bx * d, max(0.6, focus[1] + 0.4 + (up - 0.4) * k), focus[2] + bz * d)
        if shake > 0.01:
            eye = tuple(c + random.uniform(-shake, shake) for c in eye)
        return eye, focus

    # ------------------------------------------------------------ Anzeige
    def draw(self, hud, now):
        if not self.active and (self.done_at is None or now - self.done_at > GO):
            return
        r, T = hud.r, hud.text
        W, H = r.size
        s = hud.scale()
        r.begin_2d()
        if not self.active:                              # „LOS!“ kurz nach dem Countdown
            a = 1.0 - (now - self.done_at) / GO
            T.draw("LOS!", W / 2, H * 0.42, int(150 * s * (1.0 + 0.25 * (1 - a))), tint=(0.4, 1, 0.55, a))
            return
        t = now - self.t0
        if t < self.look:
            fade = 0.0
        elif t < self.t_switch:
            fade = _ease((t - self.look) / FADE_OUT)
        else:
            fade = 1.0 - _ease((t - self.t_switch) / FADE_IN)
        # Meldung: Karte mit Grund und Zeiten, über die ganze Zeit gut lesbar
        card_a = min(1.0, t / 0.15)
        cy = H * 0.22                                   # oben: die Absturzstelle in der Bildmitte bleibt frei
        tex, tw, th = T.get(self.title, int(64 * s))
        w = max(tw, 520 * s) + 90 * s
        h = th + (110 * s if self.line else 70 * s)
        if fade > 0.0:
            hud.rect(W / 2, H / 2, W, H, (0.0, 0.0, 0.0, 0.92 * fade))
        hud.rect(W / 2, cy, w, h, (0.03, 0.04, 0.07, 0.72 * card_a))
        hud.rect(W / 2, cy - h / 2 + 3 * s, w, 6 * s, (*self.color[:3], card_a))
        y = cy - h / 2 + 14 * s + th / 2
        r.sprite(tex, W / 2, y, tw, th, tint=(*self.color[:3], card_a))
        y += th / 2 + 24 * s
        if self.sub:
            T.draw(self.sub, W / 2, y, int(28 * s), tint=(1, 1, 1, card_a), bold=False)
            y += 38 * s
        if self.line:
            T.draw(self.line, W / 2, y, int(24 * s), tint=(1, 1, 1, 0.8 * card_a), bold=False)
        # Countdown 3-2-1 nach dem Aufblenden
        tc = t - self.t_switch - FADE_IN
        if self.restarted and tc >= 0:
            step = COUNT / 3
            n = 3 - int(tc / step)
            frac = (tc % step) / step
            if n >= 1:
                size = int(190 * s * (1.25 - 0.25 * _ease(frac * 2)))
                T.draw(str(n), W / 2, H * 0.5, size, tint=(1, 1, 1, 1.0 - 0.6 * frac))
                T.draw("R / Leertaste: sofort los", W / 2, H * 0.5 + 130 * s, int(18 * s),
                       tint=(1, 1, 1, 0.55), bold=False)
        elif not self.restarted:
            T.draw("R / Leertaste: überspringen", W / 2, cy + h / 2 + 24 * s, int(18 * s),
                   tint=(1, 1, 1, 0.55 * card_a), bold=False)
