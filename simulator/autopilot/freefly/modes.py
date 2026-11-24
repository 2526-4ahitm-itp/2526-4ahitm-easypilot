"""Spielmodi für Menschen im Freiflug (Menü „Modus“, Taste M): Geist der Bestzeit, Ringe, Paket, Freestyle.

Reine Spiel-Logik ohne Fenster und ohne OpenGL (testbar mit tests/test_freefly_modes.py); gezeichnet wird
in modes_gfx.py (3D: Ringe, Paket, Stationen, Geist-Drohne) und osd.py (Elemente spiel, pfeil, ansage, geist).

  Rennen     + Geist der Bestzeit (GhostRace): die beste Runde je Strecke und Physik wird mit 60 Hz
             aufgezeichnet (Position + Lage) und fliegt beim nächsten Mal halbdurchsichtig mit; an jedem Tor
             zeigt das OSD den Abstand („+0,8 s“ rot = langsamer, „−0,3 s“ grün = schneller).
             Gespeichert unter autopilot/models/freefly_ghosts/<strecke>-<physik>.json (gitignored).
  ringe      leuchtende Ringe im ganzen Dorf (Set leicht / schwer), Reihenfolge egal, Pfeil zum nächsten;
             Zeit läuft, Absturz = +5 s Strafe (Ringe bleiben), alle gesammelt = Ergebnis (Bestzeit je Set).
  paket      Paket an der Station aufnehmen (tief darüber schweben), hängt am Seil (pendelt, macht die Drohne
             schwerer), an der markierten Adresse (Dach, Balkon, Garten, Brücke …) sanft absetzen.
             Zu hart (> 3,5 m/s) oder Absturz mit Paket = kaputt. 5 Adressen je Lauf, Punkte zählen.
  freestyle  90 s Flugzeit, Punkte für Tricks, die aus der Flugbahn erkannt werden (Tricks): Flip, Rolle,
             Power-Loop, Split-S, Sturzflug, Durchflug (Scheune, Brücke, Halle, Torhaus …), Lücke, Proximity,
             Bodennah. Tricks kurz hintereinander = Kombo mit Multiplikator; Absturz verliert die Kombo.

Ablauf in __main__: modes.attach() nach jedem Neustart (flight.game), Flight.step ruft game.step(), Flight.crash
game.on_crash(); take_result() holt ein fertiges Ergebnis (Bestwert in settings["best_modes"]).
Ein Neustart nach Absturz setzt den Lauf fort, R (Neustart von Hand), Moduswechsel oder ein fertiger Lauf
beginnen neu (full).
"""
import json
import math
import os
import random
import time
from pathlib import Path

import numpy as np

from ..geometry import qconj, qmul, qrot

GAME_MODES = ("ringe", "paket", "freestyle")
MODE_ORDER = ["race", "bomb", "ringe", "paket", "freestyle"]
MODE_LABEL = {"race": "Rennen (Tore)", "bomb": "Bomben", "ringe": "Ringe sammeln", "paket": "Paket ausliefern",
              "freestyle": "Freestyle"}
MODE_SHORT = {"race": "Rennen", "bomb": "Bomben", "ringe": "Ringe", "paket": "Paket", "freestyle": "Freestyle"}
GHOST_DIR = Path(__file__).resolve().parent.parent / "models" / "freefly_ghosts"
GHOST_HZ = 60.0

GREEN, RED, GOLD, CYAN, WHITE = (0.35, 1.0, 0.5, 1.0), (1.0, 0.35, 0.3, 1.0), (1.0, 0.82, 0.25, 1.0), \
    (0.35, 0.9, 1.0, 1.0), (1.0, 1.0, 1.0, 1.0)


def fmt_s(t, sign=False):
    """Sekunden deutsch: 12,34 s; sign: +0,8 s / −0,3 s."""
    if sign:
        return f"{'+' if t >= 0 else '−'}{abs(t):.1f} s".replace(".", ",")
    return f"{t:.2f} s".replace(".", ",")


def fmt_pts(n):
    return f"{int(n):,}".replace(",", " ")


def mode_key(mode):
    m = str(mode or "race").strip().lower()
    return {"rings": "ringe", "ring": "ringe", "package": "paket", "pakete": "paket", "tricks": "freestyle",
            "rennen": "race", "bomben": "bomb"}.get(m, m if m in MODE_ORDER else "race")


# ---------------------------------------------------------------------------------------------- Welt-Hilfen

def box_dist(world, p, idx=None):
    """Abstand (m) vom Punkt p zur nächsten Kollisionsbox in world.near (0 = drin)."""
    i = world.near if idx is None else idx
    if len(i) == 0:
        return 1e9
    d = np.asarray(p, dtype="f8") - world.bc[i]
    cs, sn = world.bcos[i], world.bsin[i]
    lx = cs * d[:, 0] - sn * d[:, 2]
    lz = sn * d[:, 0] + cs * d[:, 2]
    q = np.maximum(np.abs(np.stack((lx, d[:, 1], lz), axis=1)) - world.bh[i], 0.0)
    return float(np.sqrt(np.min(np.einsum("ij,ij->i", q, q))))


def in_obox(p, z):
    """Punkt in orientierter Box z = (cx, cy, cz, hx, hy, hz, yaw) wie world.boxes? -> lokale Koordinaten oder None."""
    cx, cy, cz, hx, hy, hz, yaw = z
    dx, dy, dz = p[0] - cx, p[1] - cy, p[2] - cz
    c, s = math.cos(yaw), math.sin(yaw)
    lx, lz = c * dx - s * dz, s * dx + c * dz
    if abs(lx) <= hx and abs(dy) <= hy and abs(lz) <= hz:
        return lx, dy, lz
    return None


def surface_y(world, x, z, top=40.0):
    """Höchste Oberfläche (Boxen-Oberseite oder Boden 0) unter (x, top, z)."""
    best = 0.0
    for (cx, cy, cz, hx, hy, hz, yaw) in world.boxes:
        if cy + hy > top or cy + hy <= best:
            continue
        c, s = math.cos(yaw), math.sin(yaw)
        dx, dz = x - cx, z - cz
        if abs(c * dx - s * dz) <= hx and abs(s * dx + c * dz) <= hz:
            best = cy + hy
    return best


# ---------------------------------------------------------------------------------------------- Geist

def ghost_path(track, physik, folder=None):
    folder = Path(folder or os.environ.get("FREEFLY_GHOST_DIR") or GHOST_DIR)
    return folder / f"{track}-{physik}.json"


def load_ghost(track, physik, folder=None):
    try:
        g = json.loads(ghost_path(track, physik, folder).read_text(encoding="utf-8"))
        g["samples"] = np.asarray(g["samples"], dtype="f8")
        return g if len(g["samples"]) >= 2 else None
    except (OSError, ValueError, KeyError):
        return None


def save_ghost(g, track, physik, folder=None):
    p = ghost_path(track, physik, folder)
    p.parent.mkdir(parents=True, exist_ok=True)
    out = {k: v for k, v in g.items() if k != "samples"}
    out["samples"] = [[round(float(v), 4) for v in s] for s in g["samples"]]
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    tmp.replace(p)


def ghost_pose(g, t):
    """(pos, quat) des Geists t Sekunden nach seinem Rundenstart (vor dem Start: erste, danach letzte Lage)."""
    S = g["samples"]
    f = max(0.0, min(len(S) - 1.0, t * g.get("hz", GHOST_HZ)))
    i = min(int(f), len(S) - 2)
    a = f - i
    p = S[i, 0:3] * (1 - a) + S[i + 1, 0:3] * a
    q0, q1 = S[i, 3:7], S[i + 1, 3:7]
    if float(np.dot(q0, q1)) < 0:
        q1 = -q1
    q = q0 * (1 - a) + q1 * a
    q = q / (np.linalg.norm(q) or 1.0)
    return tuple(p), tuple(q)


class Announcer:
    """Große Einblendungen (OSD-Element „ansage“): Trick-Namen, Ringe, Paket, Geist-Abstand."""

    def __init__(self):
        self.items = []                  # (Text, Untertitel, Farbe, Start, Dauer)

    def say(self, text, sub=None, color=WHITE, seconds=1.4):
        now = time.perf_counter()
        self.items = [it for it in self.items if now - it[3] < it[4]][-2:] + [(text, sub, color, now, seconds)]

    def current(self, now=None):
        now = time.perf_counter() if now is None else now
        return [it for it in self.items if now - it[3] < it[4]]


class Game:
    """Gemeinsame Schnittstelle der Spielmodi (flight.game)."""
    mode = None
    key = None

    def __init__(self):
        self.ann = Announcer()
        self.result = None               # fertiger Lauf: dict (take_result holt es ab)
        self.finished = False
        self.t = 0.0                     # Spielzeit (nur Flugzeit zählt)

    def respawn(self, flight, full):
        pass

    def step(self, flight, prev, dt):
        pass

    def on_crash(self, flight):
        pass

    def goal(self, pos):
        """Weltpunkt für Pfeil und Kompass (nächster Ring, Station, Adresse) oder None."""
        return None

    def summary(self):
        return {"mode": self.mode}

    def draw_items(self, now, pos):
        """3D-Objekte für modes_gfx: Liste von (Art, Daten …)."""
        return []


# ---------------------------------------------------------------------------------------------- Rennen + Geist

class GhostRace(Game):
    """Rennen mit Geist der Bestzeit (eine Runde: Start-/Zieltor bis wieder Start-/Zieltor)."""
    mode = "race"

    def __init__(self, track, physik, show=True, save=True, folder=None):
        super().__init__()
        self.track, self.physik, self.show, self.save, self.folder = track, physik, show, save, folder
        self.key = ("race", track, physik)
        self.best = load_ghost(track, physik, folder)
        self.record = True               # Autopilot-Runden werden nicht aufgezeichnet (attach)
        self.rec = None
        self.splits = []
        self.delta = None                # (Sekunden, Tor-Nummer, Zeitpunkt) für das OSD
        self._ls = None
        self._next = 0
        self._t_next = 0.0
        self.new_ghost = False

    def respawn(self, flight, full):
        self.rec, self.splits, self._ls, self._next, self.delta = None, [], flight.lap_start, flight.next_gate, None

    def lap_time(self, flight):
        return None if flight.lap_start is None else flight.flight_time - flight.lap_start

    def step(self, flight, prev, dt):
        ls = flight.lap_start
        if flight.next_gate != self._next:
            passed, self._next = self._next, flight.next_gate
            if passed == 0 and ls is not None and self._ls is not None and flight.last_lap is not None:
                self._lap_done(flight.last_lap)
            elif passed != 0 and ls is not None:
                t = flight.flight_time - ls
                self.splits.append(t)
                b = self.best
                if b and self.show and passed - 1 < len(b.get("splits", [])):
                    self._delta(t - b["splits"][passed - 1], passed)
        if ls != self._ls:                                   # neue Runde beginnt: Aufzeichnung neu
            self._ls = ls
            self.rec, self.splits, self._t_next = [], [], 0.0
        if self.rec is not None and ls is not None:
            t = flight.flight_time - ls
            if t >= self._t_next and len(self.rec) < 600 * GHOST_HZ:
                d = flight.drone
                self.rec.append((*d.pos, *d.quat))
                self._t_next += 1.0 / GHOST_HZ

    def _delta(self, dt, gate):
        self.delta = (dt, gate, time.perf_counter())
        self.ann.say(fmt_s(dt, sign=True), f"Tor {gate + 1} gegen den Geist" if gate else "Runde gegen den Geist",
                     RED if dt > 0 else GREEN, 1.6)

    def _lap_done(self, lap):
        b = self.best
        if b and self.show:
            self._delta(lap - b["lap"], 0)
        if not self.record or not self.rec or len(self.rec) < 10:
            return
        if b is None or lap < b["lap"]:
            self.best = {"track": self.track, "physik": self.physik, "lap": round(lap, 3), "hz": GHOST_HZ,
                         "splits": [round(s, 3) for s in self.splits], "date": time.strftime("%Y-%m-%d %H:%M"),
                         "samples": np.asarray(self.rec, dtype="f8")}
            self.new_ghost = True
            if self.save:
                try:
                    save_ghost(self.best, self.track, self.physik, self.folder)
                except OSError as exc:
                    print("Geist speichern:", exc)
            if b is not None and self.show:
                self.ann.say("NEUER GEIST", f"Runde {fmt_s(lap)}  ({fmt_s(lap - b['lap'], sign=True)})", GOLD, 2.2)

    def ghost_now(self, flight):
        """(pos, quat, alpha) des Geists oder None."""
        if not self.show or self.best is None:
            return None
        lt = self.lap_time(flight)
        t = 0.0 if lt is None else lt
        if t > self.best["lap"] + 1.0:
            return None
        pos, q = ghost_pose(self.best, t)
        dist = math.dist(pos, flight.drone.pos)
        alpha = 0.45 * min(1.0, max(0.0, (dist - 0.6) / 2.0))     # ganz nah: ausblenden (FPV-Kamera)
        return (pos, q, alpha) if alpha > 0.02 else None

    def summary(self):
        b = self.best
        return {"mode": "race", "ghost": bool(b), "ghost_lap": b["lap"] if b else None, "show": self.show,
                "delta": round(self.delta[0], 2) if self.delta else None}

    def draw_items(self, now, pos):
        return []


# ---------------------------------------------------------------------------------------------- Ringe

# Ring: (x, y, z, Flugrichtung in Grad, Innenradius). Geprüft gegen alle 5 Strecken (tests/test_freefly_modes.py).
RING_SETS = {
    "leicht": {"name": "Leicht", "desc": "14 große Ringe tief über Wiese und Straßen", "rings": [
        (-12.0, 3.0, 30.0, -20, 2.2), (-22.0, 3.5, 62.0, 0, 2.2), (-14.0, 4.0, 100.0, 20, 2.2),
        (4.0, 4.0, 132.0, 60, 2.2), (28.0, 4.0, 172.0, 90, 2.2), (60.0, 4.5, 190.0, 100, 2.2),
        (100.0, 5.0, 140.0, 150, 2.2), (124.0, 4.0, 100.0, 180, 2.2), (112.0, 4.0, 60.0, 200, 2.2),
        (100.0, 3.5, 18.0, 240, 2.2), (60.0, 3.5, -10.0, 270, 2.2), (21.0, 3.0, -22.0, 300, 2.2),
        (60.0, 3.5, 62.0, 0, 2.2), (30.0, 3.5, 100.0, 90, 2.2)]},
    "schwer": {"name": "Schwer", "desc": "14 kleine Ringe: in Scheunen, unter der Brücke, hoch am Turm, über Dächern",
               "rings": []},           # wird unten aus den Durchflug-Gebäuden gesetzt (_hard_rings)
}
RING_ORDER = ["leicht", "schwer"]
RING_TUBE = 0.14                         # Rohr-Radius (Zeichnung); gesammelt wird innerhalb des Innenradius


def _hard_rings():
    from . import tracks as T

    def along(x, z, yaw, d):                                            # d Meter in Flugrichtung yaw weiter
        a = math.radians(yaw)
        return round(x + d * math.sin(a), 2), round(z + d * math.cos(a), 2)
    gh_yaw = math.degrees(math.atan2(-26.0, 64.0)) + 90.0               # Torhaus: Straße = Flugrichtung
    barn = along(18.0, 84.0, T.BARN_YAW, 4.0)                           # neben dem Scheunen-Tor (Strecken)
    hall = along(*T.HALL_C, T.HALL_YAW, 5.0)
    gate = along(47.0, T.GATEHOUSE_C[1], gh_yaw, 5.0)
    return [
        (barn[0], 2.4, barn[1], T.BARN_YAW, 1.3),                       # in der Scheune
        (-38.0, 2.5, 142.0, 25.0, 1.3),                                 # Feldscheune
        (64.5, 3.0, 130.0, 0.0, 1.3),                                   # unter der Fußgängerbrücke
        (gate[0], 2.8, gate[1], gh_yaw, 1.3),                           # gleich hinter dem Torhaus-Tunnel
        (hall[0], 2.8, hall[1], T.HALL_YAW, 1.3),                       # Maschinenhalle
        (0.0, 6.2, 56.0, 0.0, 1.0),                                     # Säulenhalle, unterm Dach
        (-14.0, 23.0, 120.0, 90.0, 1.3),                                # über dem Wasserturm
        (-14.0, 8.0, 124.6, 90.0, 1.2),                                 # unter dem Wassertank
        (47.4, 15.0, 147.6, 0.0, 1.3),                                  # hoch über dem Wohnblock
        (72.4, 12.0, 109.6, 90.0, 1.3),                                 # knapp über dem Flachdach
        (-40.0, 13.5, 82.0, 100.0, 1.3),                                # über der Lagerhalle
        (56.0, 8.4, 130.0, 90.0, 1.0),                                  # über dem Brückendeck
        (-23.0, 7.0, 20.5, 20.0, 1.2),                                  # über dem Container-Stapel
        (73.2, 12.0, 21.5, 90.0, 1.3)]                                  # über dem Wohnblock am Torhaus


RING_SETS["schwer"]["rings"] = _hard_rings()


def ring_set_key(name):
    n = str(name or "leicht").strip().lower()
    return n if n in RING_SETS else "leicht"


def ring_frame(r):
    """Mitte, Flugrichtung (Normale), quer (waagrecht) für einen Ring."""
    x, y, z, yaw, R = r
    a = math.radians(yaw)
    n = (math.sin(a), 0.0, math.cos(a))
    u = (math.cos(a), 0.0, -math.sin(a))
    return (x, y, z), n, u


def ring_problems(world, r, margin=0.18):
    """Was an einem Ring stört (leer = frei): Rohr in Hindernis, Durchflug verbaut, zu tief."""
    c, n, u = ring_frame(r)
    R = r[4]
    out = []
    if c[1] - R - RING_TUBE < 0.3:
        out.append("zu tief")
    world.focus(c, 20.0)
    for k in range(24):                                    # Rohr
        a = 2 * math.pi * k / 24
        p = tuple(c[i] + (R + RING_TUBE) * (math.cos(a) * u[i] + math.sin(a) * (0, 1, 0)[i]) for i in range(3))
        if world.hit(p, RING_TUBE + margin):
            out.append(f"Rohr bei {round(math.degrees(a))}°")
            break
    for s in (-3.0, -1.5, 0.0, 1.5, 3.0):                  # Durchflug: Scheibe und davor/dahinter
        for a in range(0, 360, 60):
            rr = 0.55 * R
            p = tuple(c[i] + s * n[i] + rr * (math.cos(math.radians(a)) * u[i] + math.sin(math.radians(a)) * (0, 1, 0)[i])
                      for i in range(3))
            if world.hit(p, 0.25):
                out.append(f"Durchflug verbaut ({s:+.1f} m)")
                break
        else:
            continue
        break
    return out


class Rings(Game):
    mode = "ringe"
    PENALTY = 5.0

    def __init__(self, set_key="leicht"):
        super().__init__()
        self.set = ring_set_key(set_key)
        self.key = ("ringe", self.set)
        self.rings = RING_SETS[self.set]["rings"]
        self.frames = [ring_frame(r) for r in self.rings]
        self.reset()

    def reset(self):
        self.got = [False] * len(self.rings)
        self.got_at = [None] * len(self.rings)
        self.t, self.penalty, self.crashes = 0.0, 0.0, 0
        self.finished, self.result = False, None

    def respawn(self, flight, full):
        if full or self.finished:
            self.reset()

    @property
    def count(self):
        return sum(self.got)

    def clock(self):
        return self.t + self.penalty

    def step(self, flight, prev, dt):
        if self.finished:
            return
        self.t += dt
        p = flight.drone.pos
        for i, ((c, n, u), r) in enumerate(zip(self.frames, self.rings)):
            if self.got[i]:
                continue
            R = r[4]
            if abs(p[0] - c[0]) > R + 4 or abs(p[2] - c[2]) > R + 4 or abs(p[1] - c[1]) > R + 4:
                continue
            sa = sum((prev[k] - c[k]) * n[k] for k in range(3))
            sb = sum((p[k] - c[k]) * n[k] for k in range(3))
            if (sa < 0) == (sb < 0) or sa == sb:
                continue
            f = sa / (sa - sb)
            q = [prev[k] + f * (p[k] - prev[k]) - c[k] for k in range(3)]
            if math.sqrt(sum(v * v for v in q)) < R:
                self.got[i], self.got_at[i] = True, time.perf_counter()
                n_got, n_all = self.count, len(self.rings)
                if n_got == n_all:
                    self.finished = True
                    self.result = {"mode": "ringe", "set": self.set, "time": round(self.clock(), 3),
                                   "penalty": self.penalty, "crashes": self.crashes, "rings": n_all}
                    self.ann.say("ALLE RINGE!", fmt_s(self.clock()), GOLD, 2.5)
                else:
                    self.ann.say(f"RING {n_got} / {n_all}", None, GOLD, 1.0)

    def on_crash(self, flight):
        if not self.finished and self.t > 0:
            self.penalty += self.PENALTY
            self.crashes += 1
            self.ann.say(f"+{self.PENALTY:.0f} s STRAFE", "Ringe bleiben gesammelt", RED, 2.0)

    def goal(self, pos):
        best, bd = None, 1e9
        for (c, _, _), g in zip(self.frames, self.got):
            if not g:
                d = math.dist(c, pos)
                if d < bd:
                    best, bd = c, d
        return best

    def summary(self):
        return {"mode": "ringe", "set": self.set, "got": self.count, "total": len(self.rings),
                "time": round(self.clock(), 2), "penalty": self.penalty, "finished": self.finished}

    def draw_items(self, now, pos):
        g = self.goal(pos)
        out = []
        for i, r in enumerate(self.rings):
            if not self.got[i]:
                out.append(("ring", r, g is not None and tuple(g) == tuple(r[:3])))
            elif self.got_at[i] and now - self.got_at[i] < 0.5:
                out.append(("ring_pop", r, now - self.got_at[i]))
        return out


# ---------------------------------------------------------------------------------------------- Paket

ROPE = 1.5              # m Seil
PKG_MASS = 0.15         # kg Paket
DRONE_MASS = 0.65       # kg (Größenordnung 5"-Drohne; Paket = rund 23 % mehr Gewicht)
SOFT, BREAK = 1.5, 3.5  # m/s Aufsetzen: bis SOFT sanft, ab BREAK kaputt
PKG_R = 0.18            # m Kollisionsradius des Pakets
DELIVERIES = 5
STATIONS = [{"name": "Paketstation Start", "x": -9.0, "z": 6.0, "y": 0.0},
            {"name": "Paketstation Dorfplatz", "x": 50.5, "z": 91.0, "y": 0.0}]


def _house_boxes(world):
    """(Box, Ziel-Name) der Grundkörper aller Häuser (erste Box jedes Ziels)."""
    for t in world.targets:
        if t["name"] in ("Haus", "Wohnblock"):
            yield world.boxes[t["boxes"][0]], t["name"]


def column_free(world, x, y, z, r, h):
    """Ist über (x, y, z) ein Zylinder r × h frei (fürs Absetzen von oben)?"""
    world.focus((x, y, z), 25.0)
    for dy in np.arange(0.25, h, 0.5):
        for a in range(0, 360, 45):
            p = (x + r * math.cos(math.radians(a)), y + dy, z + r * math.sin(math.radians(a)))
            if world.hit(p, 0.12):
                return False
        if world.hit((x, y + dy, z), 0.12):
            return False
    return True


def addresses(world):
    """Lieferadressen: Flachdächer, Balkon, Gärten hinter den Häusern, Brückendeck, Scheunenboden, Container.
    Aus der Welt berechnet (gleich für alle Strecken, die Häuser stehen überall gleich) und auf Platz geprüft."""
    out = []

    def add(name, kind, x, z, r, pts=1.0, y=None, h=4.0, cr=None):
        yy = surface_y(world, x, z, top=(y + 0.5) if y is not None else 40.0)
        if column_free(world, x, yy, z, cr or max(0.5, r * 0.7), h):
            out.append({"name": name, "kind": kind, "x": round(x, 2), "y": round(yy, 3), "z": round(z, 2), "r": r,
                        "pts": pts})
            return True
        return False

    for (cx, cy, cz, hx, hy, hz, yaw), name in _house_boxes(world):     # Flachdächer (Lüftungen umgehen)
        if name != "Wohnblock":
            continue
        c, s = math.cos(yaw), math.sin(yaw)
        for lx, lz in ((0, 0), (1.8, 1.8), (-1.8, -1.8), (1.8, -1.8), (-1.8, 1.8), (2.5, 0), (-2.5, 0)):
            if add("Dach Wohnblock", "dach", cx + c * lx + s * lz, cz - s * lx + c * lz, 1.2, 1.3):
                break
    for b in world.boxes:                                                # Balkon (Deko-Box mit Kollision)
        if abs(b[3] - 1.3) < 0.01 and abs(b[4] - 0.08) < 0.01 and abs(b[5] - 0.65) < 0.01:
            add("Balkon", "balkon", b[0], b[2], 0.7, 1.6, y=b[1] + b[4], h=2.0, cr=0.3)
    from .world import ROADS
    gardens = []
    for (cx, cy, cz, hx, hy, hz, yaw), name in _house_boxes(world):     # Garten: hinter dem Haus, weg von der Straße
        if name != "Haus":
            continue
        c, s = math.cos(yaw), math.sin(yaw)
        for lx, lz in ((0, hz + 3.2), (0, -hz - 3.2), (hx + 3.2, 0), (-hx - 3.2, 0)):
            x, z = cx + c * lx + s * lz, cz - s * lx + c * lz
            if world.road_dist(x, z) > 4.5:
                gardens.append((x, z))
                break
    for x, z in gardens:
        add("Garten", "garten", x, z, 1.5, 1.0, y=0.0, h=6.0)
    add("Brückendeck", "bruecke", 60.0, 130.0, 0.9, 1.4, y=6.7, h=3.0)
    from .tracks import BARN_YAW
    a = math.radians(BARN_YAW)                                           # neben dem Scheunen-Tor der Strecken
    add("Scheunenboden", "scheune", 18.0 - 3.5 * math.sin(a), 84.0 - 3.5 * math.cos(a), 1.3, 1.4, y=0.1, h=3.5)
    add("Container", "container", -22.6, 20.3, 0.9, 1.2, y=5.3, h=3.0)
    return out


class Package(Game):
    """Paket-Lieferdienst: Station -> Adresse, 5 Adressen je Lauf."""
    mode = "paket"
    PICK_R, PICK_H, PICK_V, PICK_T = 2.0, 3.2, 3.0, 0.3

    def __init__(self, world, seed=None):
        super().__init__()
        self.key = ("paket",)
        self.world = world
        self.addr = addresses(world)
        self.seed = seed
        self.runs = 0
        self.reset()

    def reset(self):
        self.runs += 1
        rng = random.Random(self.seed if self.seed is not None else time.time_ns())
        kinds = {}
        for a in self.addr:
            kinds.setdefault(a["kind"], []).append(a)
        order = [a for k in sorted(kinds) for a in [rng.choice(kinds[k])]]           # aus jeder Art eine …
        rng.shuffle(order)
        rest = [a for a in self.addr if a not in order]
        rng.shuffle(rest)
        self.queue = (order + rest)[:DELIVERIES]                                   # … dann auffüllen
        self.idx = 0
        self.points, self.delivered, self.broken = 0, 0, 0
        self.log = []
        self.t = 0.0
        self.t_addr = 0.0
        self.finished, self.result = False, None
        self.carry = False
        self.pkg = None                  # [pos, vel] des hängenden Pakets
        self.rest_t = 0.0
        self.contact = None              # Aufsetz-Tempo des letzten Bodenkontakts
        self.hover_t = 0.0
        self.dropped = []                # zugestellte Pakete (pos, Zeit) zum Zeichnen

    def respawn(self, flight, full):
        if full or self.finished:
            self.reset()
        else:
            self.carry, self.pkg = False, None

    @property
    def target(self):
        return self.queue[self.idx] if self.idx < len(self.queue) else None

    def station(self, pos):
        return min(STATIONS, key=lambda s: math.hypot(s["x"] - pos[0], s["z"] - pos[2]))

    def goal(self, pos):
        if self.finished:
            return None
        if not self.carry:
            s = self.station(pos)
            return (s["x"], s["y"] + 0.5, s["z"])
        a = self.target
        return (a["x"], a["y"] + 0.3, a["z"]) if a else None

    def step(self, flight, prev, dt):
        if self.finished:
            return
        self.t += dt
        d = flight.drone
        p = d.pos
        v = d.vel
        if not self.carry:                                # an der Station aufnehmen: tief und langsam darüber
            s = self.station(p)
            near = math.hypot(p[0] - s["x"], p[2] - s["z"]) < self.PICK_R and p[1] - s["y"] < self.PICK_H
            slow = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) < self.PICK_V
            self.hover_t = self.hover_t + dt if near and slow else 0.0
            if self.hover_t >= self.PICK_T:
                self.carry = True
                self.pkg = [[p[0], max(PKG_R, p[1] - 0.4), p[2]], [v[0], v[1], v[2]]]
                self.t_addr = self.t
                self.hover_t = 0.0
                a = self.target
                self.ann.say("PAKET AUFGENOMMEN", f"Lieferung {self.idx + 1}/{DELIVERIES}: {a['name']}", CYAN, 2.2)
            return
        self._swing(flight, dt)

    def _swing(self, flight, dt):
        """Paket am Seil: Feder nur auf Zug, gedämpft; die Seilkraft wirkt zurück auf die Drohne."""
        d = flight.drone
        P, V = self.pkg
        dp = [P[k] - d.pos[k] for k in range(3)]
        L = math.sqrt(sum(x * x for x in dp)) or 1e-6
        if L > 3 * ROPE:                                   # Drohne versetzt (Neustart, Test): Paket nachziehen
            P = [d.pos[0], d.pos[1] - ROPE, d.pos[2]]
            V = list(d.vel)
            dp, L = [0.0, -ROPE, 0.0], ROPE
        u = [x / L for x in dp]
        rel = sum((V[k] - d.vel[k]) * u[k] for k in range(3))
        T = 0.0
        if L > ROPE:                                       # Seil gespannt
            T = max(0.0, 900.0 * (L - ROPE) + 30.0 * rel)  # m/s² am Paket (ω ≈ 30 rad/s, ζ ≈ 0,5)
        a = [-T * u[0] - 0.4 * V[0], -9.81 - T * u[1] - 0.4 * V[1], -T * u[2] - 0.4 * V[2]]
        newV = [V[k] + a[k] * dt for k in range(3)]
        newP = [P[k] + newV[k] * dt for k in range(3)]
        k_back = PKG_MASS / DRONE_MASS                     # Gegenkraft auf die Drohne (macht sie schwerer)
        vel = d.vel
        d.vel = (vel[0] + T * u[0] * k_back * dt, vel[1] + T * u[1] * k_back * dt, vel[2] + T * u[2] * k_back * dt)
        hit_ground = newP[1] < PKG_R
        hit_box = not hit_ground and self.world.hit(tuple(newP), PKG_R)
        if hit_ground or hit_box:
            speed = math.sqrt(sum(x * x for x in newV))
            if self.contact is None:                       # erster Kontakt: Aufsetz-Tempo
                self.contact = speed
                if speed > BREAK:
                    return self._broken(flight, f"zu hart aufgesetzt ({speed:.1f} m/s)".replace(".", ","))
            if hit_ground:
                newP[1] = PKG_R
            else:
                newP = list(P)
            newV = [0.0, 0.0, 0.0]
            self.rest_t += dt
        else:                                              # frei in der Luft: Kontakt vergessen
            self.contact = None
            self.rest_t = 0.0
        self.pkg = [newP, newV]
        a = self.target
        if a and self.rest_t >= 0.5 and self.contact is not None:
            if math.hypot(newP[0] - a["x"], newP[2] - a["z"]) < a["r"] and abs(newP[1] - PKG_R - a["y"]) < 0.45:
                self._delivered(self.contact)

    def _delivered(self, speed):
        a = self.target
        took = self.t - self.t_addr
        soft = speed <= SOFT
        pts = int(round((100 + (100 if soft else 30) + max(0.0, 60.0 - took) * 3) * a["pts"]))
        self.points += pts
        self.delivered += 1
        self.log.append({"name": a["name"], "pts": pts, "soft": soft, "took": round(took, 1)})
        self.dropped.append((tuple(self.pkg[0]), time.perf_counter()))
        self.ann.say(f"ZUGESTELLT +{pts}", ("sanft gelandet" if soft else "etwas ruppig") + f" · {a['name']}",
                     GREEN, 2.2)
        self._next()

    def _broken(self, flight, why):
        a = self.target
        self.broken += 1
        self.log.append({"name": a["name"] if a else "", "pts": 0, "soft": False, "broken": True})
        self.ann.say("PAKET KAPUTT", why, RED, 2.2)
        self._next()

    def _next(self):
        self.carry, self.pkg, self.contact, self.rest_t = False, None, None, 0.0
        self.idx += 1
        if self.idx >= len(self.queue):
            self.finished = True
            self.result = {"mode": "paket", "points": self.points, "delivered": self.delivered, "broken": self.broken,
                           "time": round(self.t, 2), "log": self.log}
        else:
            self.ann.say(f"NÄCHSTE ADRESSE: {self.target['name'].upper()}", "neues Paket an der Station holen", CYAN, 2.4)

    def on_crash(self, flight):
        if self.carry:
            self._broken(flight, "Absturz mit Paket")

    def summary(self):
        a = self.target
        return {"mode": "paket", "points": self.points, "delivered": self.delivered, "broken": self.broken,
                "n": self.idx, "total": len(self.queue), "carry": self.carry, "target": a["name"] if a else None,
                "time": round(self.t, 2), "finished": self.finished}

    def draw_items(self, now, pos):
        out = [("station", s, not self.carry and not self.finished) for s in STATIONS]
        a = self.target
        if a and not self.finished:
            out.append(("address", a, self.carry))
        if self.carry and self.pkg is not None:
            out.append(("package", tuple(self.pkg[0]), tuple(pos)))
        for pos, t0 in self.dropped[-3:]:
            if now - t0 < 6.0:
                out.append(("package_left", pos, now - t0))
        return out


# ---------------------------------------------------------------------------------------------- Freestyle

FREESTYLE_TIME = 90.0
COMBO_GAP = 3.0         # s: so lange darf zwischen zwei Tricks Pause sein
MAX_MULT = 5
POINTS = {"FRONTFLIP": 200, "BACKFLIP": 200, "ROLLE": 150, "POWER-LOOP": 500, "SPLIT-S": 400, "STURZFLUG": 0,
          "DURCHFLUG": 300, "LÜCKE": 150, "PROXIMITY": 0, "BODENNAH": 0}


def _zones():
    """Durchflug-Gebäude (innen hohl) als orientierte Boxen wie world.boxes: (cx, cy, cz, hx, hy, hz, yaw), Name."""
    from . import tracks as T
    gh_yaw = math.atan2(-26.0, 64.0)
    return [((18.0, 2.7, 84.0, 6.1, 2.6, 6.2, math.radians(T.BARN_YAW)), "SCHEUNE"),
            ((-38.0, 2.9, 142.0, 5.6, 2.8, 8.7, math.radians(25.0)), "FELDSCHEUNE"),
            ((T.HALL_C[0], 2.9, T.HALL_C[1], 5.6, 2.8, 7.8, math.radians(T.HALL_YAW)), "MASCHINENHALLE"),
            ((47.0, 2.7, T.GATEHOUSE_C[1], 2.2, 2.6, 2.0, gh_yaw), "TORHAUS"),
            ((60.0, 2.9, 130.0, 7.4, 2.8, 1.5, 0.0), "BRÜCKE"),
            ((0.0, 3.9, 56.0, 5.5, 3.8, 5.5, 0.0), "SÄULENHALLE")]


ZONES = None


class Tricks:
    """Erkennt Tricks aus der Flugbahn (Lage, Tempo, Abstand zu Hindernissen). update() bei ~100 Hz.
    Gibt fertige Tricks als (Name, Punkte, Zusatz) zurück; pending() = laufende Wertungen (Proximity …)."""
    HZ = 100.0

    def __init__(self, world=None):
        global ZONES
        if ZONES is None:
            ZONES = _zones()
        self.world = world
        self.reset()

    def reset(self, quat=None):
        self.q = quat
        self.acc = [0.0, 0.0, 0.0]       # Drehung im Drohnen-System (rad): Nick, Gier, Roll
        self.calm = [0.0, 0.0, 0.0]
        self.loop = 0.0                  # Drehung der Flugrichtung in der Senkrechten (rad)
        self.loop_calm = 0.0
        self.h0 = None
        self.phi = None
        self.flip_in_loop = False
        self.inv = None                  # Split-S: (t, Höhe, Kurs) beim Umdrehen auf den Rücken
        self.up_head = None              # (t, Kurs, Höhe) zuletzt aufrecht mit Tempo
        self.dive = None                 # (Starthöhe, tiefste Höhe)
        self.zone = None                 # (Index, Eintrittspunkt)
        self.gap_t = 0.0
        self.gap_cool = 0.0
        self.prox = None                 # (Dauer, Mindestabstand, Boden?)
        self.t = 0.0
        self._acc_t = 0.0
        self._probe_t = 0.0
        self.last_pos = None

    def update(self, pos, quat, vel, dt):
        """Pro Physik-Schritt aufrufen; rechnet nur alle 1/HZ s. -> Liste fertiger Tricks."""
        self._acc_t += dt
        if self._acc_t < 1.0 / self.HZ and self.q is not None:
            return []
        h, self._acc_t = self._acc_t, 0.0
        self.t += h
        out = []
        if self.q is None:
            self.q = quat
            return out
        # ---- Drehung im Drohnen-System (aus zwei Lagen)
        dq = qmul(qconj(self.q), quat)
        self.q = quat
        w = dq[3] if dq[3] >= 0 else -dq[3]
        sgn = 1.0 if dq[3] >= 0 else -1.0
        s = math.sqrt(max(0.0, 1 - w * w))
        ang = 2 * math.atan2(s, w)
        axis = [sgn * v / s for v in dq[:3]] if s > 1e-9 else [0.0, 0.0, 0.0]
        rate = [axis[i] * ang / h for i in range(3)]         # rad/s um x (Nick), y (Gier), z (Roll)
        speed = math.sqrt(vel[0] ** 2 + vel[1] ** 2 + vel[2] ** 2)
        right, up, fwd = qrot(quat, (1, 0, 0)), qrot(quat, (0, 1, 0)), qrot(quat, (0, 0, 1))
        for i, name in ((0, "FLIP"), (2, "ROLLE")):
            self.acc[i] += rate[i] * h
            self.calm[i] = self.calm[i] + h if abs(rate[i]) < math.radians(90) else 0.0
            if self.calm[i] > 0.35:
                self.acc[i] = 0.0
            if abs(self.acc[i]) >= math.radians(330):
                sign = 1 if self.acc[i] > 0 else -1
                self.acc[i] -= sign * 2 * math.pi
                if i == 0:
                    if abs(self.loop) > math.radians(180) and speed > 5:
                        self.flip_in_loop = True             # gehört zum Power-Loop
                    else:
                        out.append(("FRONTFLIP" if sign > 0 else "BACKFLIP", POINTS["FRONTFLIP"], None))
                else:
                    out.append(("ROLLE", POINTS["ROLLE"], None))
        # ---- Power-Loop: die Flugrichtung dreht sich einmal ganz in der Senkrechten
        hs = math.hypot(vel[0], vel[2])
        if speed > 4.0:
            if self.h0 is None or (abs(self.loop) < math.radians(20) and hs > 3 and abs(vel[1]) < 0.5 * hs):
                if hs > 1:
                    self.h0 = (vel[0] / hs, vel[2] / hs)
            if self.h0 is not None:
                along = vel[0] * self.h0[0] + vel[2] * self.h0[1]
                phi = math.atan2(vel[1], along)
                if self.phi is not None:
                    dphi = (phi - self.phi + math.pi) % (2 * math.pi) - math.pi
                    self.loop += dphi
                self.phi = phi
            level = abs(vel[1]) < 0.35 * speed and self.h0 is not None and \
                vel[0] * self.h0[0] + vel[2] * self.h0[1] > 0
            self.loop_calm = self.loop_calm + h if level else 0.0
        else:
            self.phi = None
            self.loop_calm += h
        if abs(self.loop) >= math.radians(300):
            out.append(("POWER-LOOP", POINTS["POWER-LOOP"], None))
            self.loop, self.flip_in_loop, self.acc[0] = 0.0, False, 0.0
        elif self.loop_calm > 0.6:
            self.loop, self.flip_in_loop = 0.0, False
        # ---- Split-S: auf den Rücken, nach unten durchziehen, Kurs umgekehrt, Höhe verloren
        y = pos[1]
        head = math.atan2(vel[0], vel[2]) if hs > 4 else None
        if up[1] > 0.6 and head is not None:
            if self.inv is not None and self.t - self.inv[0] < 3.5:
                dh = abs((head - self.inv[2] + math.pi) % (2 * math.pi) - math.pi)
                if dh > math.radians(135) and self.inv[1] - y > 3.0:
                    out.append(("SPLIT-S", POINTS["SPLIT-S"], None))
                    self.acc = [0.0, 0.0, 0.0]
                self.inv = None
            self.up_head = (self.t, head, y)
        elif up[1] < -0.5 and self.inv is None and self.up_head is not None and self.t - self.up_head[0] < 1.5:
            self.inv = (self.t, max(y, self.up_head[2]), self.up_head[1])
        if self.inv is not None and self.t - self.inv[0] > 3.5:
            self.inv = None
        # ---- Sturzflug: Nase steil nach unten, schnell sinken, sauber abfangen
        if vel[1] < -10.0 and fwd[1] < -0.55:
            self.dive = (max(self.dive[0], y), min(self.dive[1], y)) if self.dive else (y, y)
        elif self.dive is not None:
            self.dive = (self.dive[0], min(self.dive[1], y))
            if vel[1] > -2.0:
                drop = self.dive[0] - self.dive[1]
                if drop >= 8.0:
                    low = self.dive[1] < 3.0
                    out.append(("STURZFLUG", int(15 * drop + (200 if low else 0)),
                                f"{drop:.0f} m".replace(".", ",") + (" · tief abgefangen" if low else "")))
                self.dive = None
        # ---- Durchflug durch Gebäude (rein und auf der anderen Seite wieder raus)
        zi = None
        for k, (z, _) in enumerate(ZONES):
            if in_obox(pos, z) is not None:
                zi = k
                break
        if self.zone is None and zi is not None:
            self.zone = (zi, pos)
        elif self.zone is not None and zi != self.zone[0]:
            z, name = ZONES[self.zone[0]]
            a, b = self.zone[1], self.last_pos or pos
            need = 0.6 * 2 * min(z[3], z[5])
            if math.hypot(b[0] - a[0], b[2] - a[2]) >= need:
                out.append(("DURCHFLUG", POINTS["DURCHFLUG"], name))
            self.zone = (zi, pos) if zi is not None else None
        self.last_pos = pos
        # ---- Abstände (20 Hz): Lücke, Proximity, Bodennah
        self._probe_t += h
        self.gap_cool = max(0.0, self.gap_cool - h)
        if self._probe_t >= 0.05 and self.world is not None:
            ph, self._probe_t = self._probe_t, 0.0
            out += self._probe(pos, vel, speed, hs, zi, ph)
        return out

    def _probe(self, pos, vel, speed, hs, zi, h):
        out = []
        w = self.world
        # Lücke: links und rechts der Flugrichtung Hindernisse näher als 2 m
        if speed > 6.0 and hs > 3.0 and zi is None:
            px, pz = -vel[2] / hs, vel[0] / hs
            sides = []
            for sgn in (-1, 1):
                hit = False
                for dist in (0.6, 1.2, 1.9):
                    if w.hit((pos[0] + sgn * px * dist, pos[1], pos[2] + sgn * pz * dist), 0.15):
                        hit = True
                        break
                sides.append(hit)
            if all(sides):
                self.gap_t += h
            else:
                if self.gap_t >= 0.1 and self.gap_cool <= 0:
                    out.append(("LÜCKE", POINTS["LÜCKE"], None))
                    self.gap_cool = 1.5
                self.gap_t = 0.0
        else:
            self.gap_t = 0.0
        # Proximity / Bodennah
        dist = box_dist(w, pos)
        ground = pos[1] < 0.8 and speed > 9.0
        near = (dist < 1.0 and speed > 7.0) or ground
        if near:
            d0, m0, g0 = self.prox or (0.0, 9.9, False)
            self.prox = (d0 + h, min(m0, dist), g0 or (ground and dist >= 1.0))
        elif self.prox is not None:
            dur, mind, gr = self.prox
            self.prox = None
            if dur >= 0.4:
                dur = min(dur, 4.0)
                if gr:
                    out.append(("BODENNAH", int(120 * dur), f"{dur:.1f} s".replace(".", ",")))
                else:
                    out.append(("PROXIMITY", int(180 * dur), f"{dur:.1f} s · {mind:.1f} m".replace(".", ",")))
        return out


class Freestyle(Game):
    mode = "freestyle"

    def __init__(self, world, duration=FREESTYLE_TIME):
        super().__init__()
        self.key = ("freestyle",)
        self.world = world
        self.duration = duration
        self.tricks = Tricks(world)
        self.reset()

    def reset(self):
        self.t, self.score = 0.0, 0
        self.combo, self.combo_n, self.combo_t = 0, 0, None
        self.best_combo = 0
        self.log = []
        self.finished, self.result = False, None
        self.tricks.reset()

    def respawn(self, flight, full):
        if full or self.finished:
            self.reset()
        self.tricks.reset(flight.drone.quat)

    @property
    def mult(self):
        return max(1, min(MAX_MULT, self.combo_n))

    def left(self):
        return max(0.0, self.duration - self.t)

    def bank(self):
        if self.combo_n:
            pts = self.combo * self.mult
            self.score += pts
            self.best_combo = max(self.best_combo, pts)
            if self.combo_n > 1:
                self.ann.say(f"KOMBO x{self.mult}  +{fmt_pts(pts)}", f"{self.combo_n} Tricks", GOLD, 1.8)
        self.combo, self.combo_n, self.combo_t = 0, 0, None

    def add(self, name, pts, extra=None):
        if pts <= 0:
            return
        self.combo += pts
        self.combo_n += 1
        self.combo_t = self.t
        label = name if not extra or name not in ("DURCHFLUG",) else f"{name} {extra}"
        self.log.append({"t": round(self.t, 2), "name": label, "pts": pts})
        sub = f"KOMBO x{self.mult}" if self.combo_n > 1 else (extra if extra and name != "DURCHFLUG" else None)
        if extra and name not in ("DURCHFLUG",) and self.combo_n > 1:
            sub = f"{extra} · KOMBO x{self.mult}"
        self.ann.say(f"{label} +{pts}", sub, CYAN if self.combo_n < 3 else GOLD, 1.5)

    def step(self, flight, prev, dt):
        if self.finished:
            return
        self.t += dt
        d = flight.drone
        for name, pts, extra in self.tricks.update(d.pos, d.quat, d.vel, dt):
            self.add(name, pts, extra)
        if self.combo_t is not None and self.t - self.combo_t > COMBO_GAP:
            self.bank()
        if self.t >= self.duration:
            self.bank()
            self.finished = True
            self.result = {"mode": "freestyle", "points": self.score, "best_combo": self.best_combo,
                           "tricks": len(self.log), "log": self.log[-60:]}
            self.ann.say("ZEIT UM", f"{fmt_pts(self.score)} Punkte", GOLD, 2.5)

    def on_crash(self, flight):
        if self.combo_n:
            self.ann.say("KOMBO VERLOREN", f"−{fmt_pts(self.combo * self.mult)}", RED, 1.8)
        self.combo, self.combo_n, self.combo_t = 0, 0, None
        self.tricks.prox = self.tricks.dive = None

    def summary(self):
        return {"mode": "freestyle", "points": self.score, "combo": self.combo, "mult": self.mult if self.combo_n else 0,
                "left": round(self.left(), 1), "tricks": len(self.log), "finished": self.finished}


# ---------------------------------------------------------------------------------------------- Ablauf, Bestwerte

def best_key(game):
    if game is None:
        return None
    if game.mode == "ringe":
        return f"ringe-{game.set}"
    return game.mode if game.mode in ("paket", "freestyle") else None


def better(key, a, b):
    """Ist Ergebnis a besser als b? Ringe: Zeit; Paket, Freestyle: Punkte."""
    if b is None:
        return True
    if key.startswith("ringe"):
        return a["time"] < b["time"]
    return a["points"] > b["points"]


def attach(flight, settings, full=False):
    """Nach flight.respawn(): Spiel für den Modus anlegen oder fortsetzen (flight.game)."""
    mode = mode_key(settings.get("mode"))
    g = getattr(flight, "game", None)
    world = flight.world
    if mode == "ringe":
        want = ("ringe", ring_set_key(settings.get("ring_set")))
    elif mode == "race":
        want = ("race", world.track, settings.get("physik", "classic"))
    elif mode in GAME_MODES:
        want = (mode,)
    else:
        want = None
    if want is None:
        flight.game = None
        return None
    if g is None or g.key != want or getattr(g, "world", world) is not world:
        if mode == "ringe":
            g = Rings(want[1])
        elif mode == "paket":
            g = Package(world, seed=settings.get("paket_seed"))
        elif mode == "freestyle":
            g = Freestyle(world, float(settings.get("freestyle_time", FREESTYLE_TIME)))
        else:
            g = GhostRace(world.track, want[2], show=bool(settings.get("ghost", True)),
                          save=bool(settings.get("ghost_save", True)))
        g.world = world
        full = True
    if mode == "race":
        g.show = bool(settings.get("ghost", True))
        g.record = not settings.get("auto")
    flight.game = g
    g.respawn(flight, full)
    return g


def take_result(flight, settings):
    """Fertiges Ergebnis abholen und Bestwert eintragen -> (Titel, Untertitel, Zeile, neuer Rekord?) oder None."""
    g = getattr(flight, "game", None)
    if g is None or g.result is None or getattr(g, "_taken", None) is g.result:
        return None
    r = g._taken = g.result
    key = best_key(g)
    bests = settings.setdefault("best_modes", {})
    old = bests.get(key)
    rec = (not settings.get("auto")) and better(key, r, old)
    if rec:
        bests[key] = {k: v for k, v in r.items() if k not in ("log",)} | {"date": time.strftime("%Y-%m-%d %H:%M")}
    runs = settings.setdefault("mode_runs", {})
    runs[key] = int(runs.get(key, 0)) + 1
    if g.mode == "ringe":
        title = "ALLE RINGE!"
        sub = f"{fmt_s(r['time'])}" + (f"  (davon {r['penalty']:.0f} s Strafe)" if r["penalty"] else "")
        line = f"Ringe {r['rings']}   Abstürze {r['crashes']}" + (f"   Bestzeit {fmt_s(old['time'])}" if old else "")
    elif g.mode == "paket":
        title = f"{fmt_pts(r['points'])} PUNKTE"
        sub = f"{r['delivered']} zugestellt, {r['broken']} kaputt"
        line = f"Zeit {fmt_s(r['time'])}" + (f"   Bestwert {fmt_pts(old['points'])}" if old else "")
    else:
        title = f"{fmt_pts(r['points'])} PUNKTE"
        sub = f"{r['tricks']} Tricks, beste Kombo {fmt_pts(r['best_combo'])}"
        line = f"Freestyle {FREESTYLE_TIME:.0f} s" + (f"   Bestwert {fmt_pts(old['points'])}" if old else "")
    if rec:
        sub += "  ·  NEUER REKORD!"
    return title, sub, line, rec


def best_text(settings, game):
    """Bestwert des aktuellen Modus fürs OSD."""
    key = best_key(game)
    b = (settings.get("best_modes") or {}).get(key) if key else None
    if not b:
        return None
    return fmt_s(b["time"]) if key.startswith("ringe") else fmt_pts(b["points"])


def test_setup(flight, what):
    """Für Bildschirmfotos (FREEFLY_SPIEL_TEST): Spielstand vorbereiten, Einblendungen lange stehen lassen.
    what: ringe (ein paar gesammelt), paket (Paket hängt), trick (BACKFLIP-Einblendung), geist (Abstand am Tor)."""
    g = getattr(flight, "game", None)
    if g is None:
        return
    long = 1e6
    if what == "ringe" and isinstance(g, Rings):
        for i in range(1, len(g.rings), 3):
            g.got[i] = True
        g.t = 23.4
        g.ann.say(f"RING {g.count} / {len(g.rings)}", None, GOLD, long)
    elif what == "paket" and isinstance(g, Package):
        p = flight.drone.pos
        g.carry, g.pkg, g.t, g.t_addr = True, [[p[0], p[1] - ROPE, p[2]], [0.0, 0.0, 0.0]], 31.0, 12.0
        g.points, g.delivered, g.idx = 312, 1, 1
        roofs = [a for a in g.addr if a["kind"] == "dach"]
        if roofs:                                          # Bild: Dach des Wohnblocks am Torhaus
            g.queue[1] = min(roofs, key=lambda a: math.hypot(a["x"] - 73.2, a["z"] - 19.6))
        g.ann.say("PAKET AUFGENOMMEN", f"Lieferung 2/{DELIVERIES}: {g.target['name']}", CYAN, long)
    elif what == "trick" and isinstance(g, Freestyle):
        g.t, g.score = 41.0, 2350
        g.add("POWER-LOOP", 500)
        g.add("BACKFLIP", 200)
        g.add("DURCHFLUG", 300, "SCHEUNE")
        g.ann.items = [(t, s, c, t0, long) for t, s, c, t0, _ in g.ann.items]
    elif what == "geist" and isinstance(g, GhostRace):
        g.ann.say(fmt_s(-0.8, sign=True), "Tor 3 gegen den Geist", GREEN, long)
        g.delta = (-0.8, 2, time.perf_counter())
