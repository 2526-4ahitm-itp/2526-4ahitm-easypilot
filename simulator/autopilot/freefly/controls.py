"""Steuerung im Freiflug: Fernsteuerung (DJI FPV RC 3 o. a.), Tastatur oder beides.

Controls ist das eine Eingabegerät für die Spielschleife (read(), buttons(), name). Im Spiel
umschaltbar (Menü „Steuerung“ oder Taste T):
  "rc"        nur die Fernsteuerung (ist keine da: Tastatur als Notlösung)
  "keyboard"  nur die Tastatur
  "auto"      beide, wer zuletzt bewegt wurde, steuert
Eine Fernsteuerung, die erst nach dem Start angesteckt wird, findet Controls von selbst: alle 2 s
schaut ein Hintergrund-Thread nach (pygame-Joystick oder RC 3 hinter OpenJoystickDriver über IOKit),
geöffnet wird dann in der Spielschleife.

Tastatur: W/S Gas, A/D Gieren, Pfeile Nicken/Rollen. Der Ausschlag steigt sanft an (kein Sprung auf
100 %), wie weit, stellt „Tastatur-Empfindlichkeit“ ein; „Gas-Tempo“ ist, wie schnell W/S das Gas
verstellen (pro Sekunde, unabhängig von der Bildrate).
"""
import threading
import time

import pygame

CTL_MODES = ("auto", "rc", "keyboard")
CTL_LABEL = {"auto": "Automatisch", "rc": "RC 3", "keyboard": "Tastatur"}
RC_NAME = "DJI FPV RC 3"


class Keyboard:
    name = "Tastatur"
    KEYS = (pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d, pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT)
    RISE = 0.22          # s bis zum vollen (eingestellten) Ausschlag
    FALL = 0.10          # s zurück zur Mitte beim Loslassen

    def __init__(self, sens=0.6, thr_rate=0.6):
        self.sens, self.thr_rate = sens, thr_rate
        self.throttle = 0.0
        self.axes = [0.0, 0.0, 0.0]          # Gieren, Nicken, Rollen
        self.thr_held = 0.0
        self.t = None

    def active(self):
        k = pygame.key.get_pressed()
        return any(k[key] for key in self.KEYS)

    def read(self):
        now = time.perf_counter()
        dt = 0.0 if self.t is None else min(0.05, now - self.t)
        self.t = now
        k = pygame.key.get_pressed()
        thr = k[pygame.K_w] - k[pygame.K_s]
        # Gas: erst langsam, nach 0,4 s gehalten volles Tempo (feine Korrektur mit kurzem Tippen)
        self.thr_held = self.thr_held + dt if thr else 0.0
        self.throttle = min(1.0, max(0.0, self.throttle + thr * self.thr_rate * dt * min(1.0, 0.3 + self.thr_held / 0.4)))
        want = (k[pygame.K_d] - k[pygame.K_a], k[pygame.K_UP] - k[pygame.K_DOWN], k[pygame.K_RIGHT] - k[pygame.K_LEFT])
        for i, w in enumerate(want):
            target = w * self.sens
            cur = self.axes[i]
            rate = (1.0 / self.RISE if abs(target) > abs(cur) and target * cur >= 0 else 1.0 / self.FALL) * dt
            self.axes[i] = cur + max(-rate, min(rate, target - cur))
        return (self.throttle, *self.axes)

    def buttons(self):
        return ()


def open_controller():
    """Kalibrierte Fernsteuerung (pilot.Controller) oder None."""
    try:
        from ..pilot import Controller
        c = Controller()
    except Exception as e:          # kein Controller / nicht kalibriert
        print("Fernsteuerung nicht verfügbar:", e)
        return None
    joy = c.joy
    c.buttons = lambda: tuple(i for i in range(joy.get_numbuttons()) if joy.get_button(i))
    if "OpenJoystickDriver" in c.name:          # so heißt die RC 3 hinter OJD
        c.name = RC_NAME
    return c


class Controls:
    def __init__(self, mode="auto", sens=0.6, thr_rate=0.6, pad=None):
        self.kb = Keyboard(sens, thr_rate)
        self.mode = mode if mode in CTL_MODES else "auto"
        self.pad = pad
        self.use_kb = pad is None
        self.last_pad = None
        self.notice = None                      # (Text, Untertitel) für das OSD, holt main ab
        self._found = threading.Event()
        self._stop = threading.Event()
        self._next_try = 0.0
        threading.Thread(target=self._watch, daemon=True, name="pad-watch").start()

    # ---------------------------------------------------------------- Einstellungen
    def configure(self, sens, thr_rate):
        self.kb.sens, self.kb.thr_rate = sens, thr_rate

    def set_mode(self, mode):
        self.mode = mode
        if mode == "keyboard":
            self.use_kb = True
        elif mode == "rc" and self.pad is not None:
            self.use_kb = False
        self.notice = (f"Steuerung: {CTL_LABEL[mode]}", self._sub())

    def cycle(self):
        self.set_mode(CTL_MODES[(CTL_MODES.index(self.mode) + 1) % len(CTL_MODES)])

    def _sub(self):
        if self.mode == "keyboard":
            return "W/S Gas  A/D Gieren  Pfeile Nicken/Rollen"
        if self.pad is None:
            return "keine Fernsteuerung gefunden, Tastatur aktiv (Fernsteuerung einstecken)"
        return f"{self.pad.name}" + (" + Tastatur, wer zuletzt bewegt wird, steuert" if self.mode == "auto" else "")

    @property
    def name(self):
        if self.mode == "keyboard" or self.pad is None:
            return "Tastatur" + (" (keine Fernsteuerung)" if self.mode != "keyboard" else "")
        if self.mode == "rc":
            return self.pad.name
        return f"{self.pad.name} + Tastatur · jetzt {'Tastatur' if self.use_kb else 'Fernsteuerung'}"

    # ---------------------------------------------------------------- Nachstecken
    def _watch(self):
        """Hintergrund: alle 2 s nachsehen, ob eine Fernsteuerung da ist (öffnen tut die Spielschleife)."""
        while not self._stop.wait(2.0):
            if self.pad is not None or self.mode == "keyboard":
                continue
            try:
                import sys
                if sys.platform == "darwin":
                    from .. import hid_mac
                    if hid_mac.find():
                        self._found.set()
            except Exception:
                pass

    def poll(self, events=()):
        """Einmal pro Frame aus der Spielschleife: pygame-Geräte-Ereignisse und Funde des Threads."""
        for ev in events:
            if ev.type == pygame.JOYDEVICEADDED and self.pad is None:
                self._found.set()
            elif ev.type == pygame.JOYDEVICEREMOVED and self.pad is not None:
                try:
                    gone = self.pad.joy.get_instance_id() == ev.instance_id
                except (AttributeError, pygame.error):
                    gone = False                       # RC 3 über IOKit: kein pygame-Gerät
                if gone:
                    self.pad = None
                    self.use_kb = True
                    self.notice = ("Fernsteuerung getrennt", "Tastatur aktiv, zum Weiterfliegen wieder einstecken")
        now = time.perf_counter()
        if self.pad is None and self.mode != "keyboard" and self._found.is_set() and now > self._next_try:
            self._found.clear()
            self._next_try = now + 4.0
            pad = open_controller()
            if pad is not None:
                self.pad = pad
                self.last_pad = None
                self.use_kb = self.mode == "keyboard"
                self.notice = (f"{pad.name} verbunden", f"Steuerung: {CTL_LABEL[self.mode]}")

    # ---------------------------------------------------------------- Lesen
    def read(self):
        if self.mode == "keyboard" or self.pad is None:
            self.use_kb = True
            return self.kb.read()
        p = self.pad.read()
        if self.mode == "rc":
            self.use_kb = False
            self.last_pad = p
            return p
        kb = self.kb.read()                            # immer lesen, damit die Rampe weiterläuft
        if self.kb.active():
            if not self.use_kb:
                self.kb.throttle = p[0]
                kb = (p[0], *kb[1:])
            self.use_kb = True
        elif self.last_pad is not None and max(abs(a - b) for a, b in zip(p, self.last_pad)) > 0.03:
            self.use_kb = False                        # Sticks bewegt -> Fernsteuerung
        self.last_pad = p
        return kb if self.use_kb else p

    def buttons(self):
        if self.pad is None or self.mode == "keyboard":
            return ()
        try:
            return self.pad.buttons()
        except Exception:
            return ()
