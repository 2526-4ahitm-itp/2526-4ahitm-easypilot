"""Strecken des Freiflug-Simulators: Tore als Daten, gewählt im Menü „Strecke“ / --strecke.

Die Welt (Dorf, Häuser, Durchflug-Gebäude) ist für alle Strecken dieselbe: world.World legt sie immer
mit der Dorfrunde an (dieselben Zufallszahlen, dieselben Häuser) und tauscht danach nur die Tore aus;
Bäume, Büsche, Laternen und Stromleitungen, die einer anderen Strecke im Weg stehen, fallen weg.

Ein Tor ist ein dict:
  x, z      Mitte (m); bei Flaggen die Stange
  lift      Unterkante der (untersten) Öffnung über dem Boden; base = Boden darunter (Dach)
  kind      std | small | big | flag | double | ladder | tilt
  yaw       Flugrichtung in Grad (0 = +z, 90 = +x); fehlt sie: Winkelhalbierende vom vorigen zum nächsten Tor
  roll      schräges Tor: Neigung in Grad
  level     double/ladder: welche Öffnung zählt (0 = unten); double: None = beide zählen
  side      Flagge: Stange rechts ("r") oder links ("l") der Durchflugrichtung (innen in der Kurve)

Kamera-Pilot (vision.ColorGateDetector): erkennt orange Rahmen mit Loch. std, small, big, double,
ladder und tilt haben solche Rahmen (Doppel- und Leiter-Tor: jede Öffnung ein eigenes Loch, die
Mittelholme sind orange); Flaggen haben kein Loch und sind für ihn unsichtbar.
"""
import math
import os

# Öffnung (Breite, Höhe) je Torart
SIZES = {"std": (3.0, 2.4), "small": (2.2, 1.8), "big": (5.0, 3.6), "tilt": (3.0, 2.4),
         "double": (3.0, 2.4), "ladder": (3.0, 2.4), "flag": (5.0, 7.0)}
OPENINGS = {"double": 2, "ladder": 3}
KIND_LABEL = {"std": "Standardtor", "small": "enges Tor", "big": "großes Anfängertor", "tilt": "schräges Tor",
              "double": "Doppeltor", "ladder": "Leiter-Tor", "flag": "Flagge"}

# Schwierigkeitsfarbe (Pisten-Farben): Füße, Ständer, Flaggentuch. Kein Orange/Gelb/Braun:
# Orange heißt für den Kamera-Piloten „Torrahmen“.
COLORS = {1: (0.20, 0.72, 0.30), 2: (0.18, 0.42, 0.86), 3: (0.85, 0.12, 0.14), 4: (0.55, 0.25, 0.80),
          5: (0.08, 0.08, 0.09)}
COLOR_NAMES = {1: "grün", 2: "blau", 3: "rot", 4: "violett", 5: "schwarz"}

# Durchflug-Gebäude der Welt (world.py legt sie an Hand der Dorfrunde an): Achsen für Tore darin
_C = [(0, 16, 0), (4, 36, 1.5), (0, 56, 0), (18, 84, 0), (42, 100, 0)]


def _bisector(p, c, n):
    a = (c[0] - p[0], c[1] - p[1])
    b = (n[0] - c[0], n[1] - c[1])
    la, lb = math.hypot(*a), math.hypot(*b)
    return math.degrees(math.atan2(a[0] / la + b[0] / lb, a[1] / la + b[1] / lb))


BARN_YAW = _bisector(_C[2], _C[3], _C[4])                     # Scheune (Dorfrunde Tor 4)
HALL_YAW = math.degrees(math.atan2(60 - 92, 30 - 46))         # Maschinenhalle, Richtung WSW
ROAD_YAW = math.degrees(math.atan2(-4 - 60, 0 - 26))          # Zufahrt durchs Torhaus nach WSW
HALL_C = ((92 + 60) / 2 + 1.0, (46 + 30) / 2 + 0.5)
GATEHOUSE_C = (47.0, 26 * (47.0 + 4) / 64)
ROOF = 9.8                                                    # Flachdach der Wohnblöcke
DECK = 6.62                                                   # Deck der Fußgängerbrücke (60, 130)


def G(x, z, lift=0.0, kind="std", **kw):
    return {"x": x, "z": z, "lift": lift, "kind": kind, **kw}


TRACKS = {
    "anfaenger": {
        "name": "Anfänger", "stars": 1,
        "desc": "6 große, tiefe Tore als Sechseck über die Wiese: nur sanfte 60°-Kurven, das nächste Tor ist immer schon zu sehen",
        "gates": [G(0, 24, 0, "big"), G(-20, 58.6, 0, "big"), G(-60, 58.6, 0, "big"),
                  G(-80, 24, 0, "big"), G(-60, -10.6, 0, "big"), G(-20, -10.6, 0, "big")]},
    "dorfrunde": {
        "name": "Dorfrunde", "stars": 2,
        "desc": "12 Tore durchs Dorf: Scheune, Brücke, Halle, Torhaus (die bisherige Strecke)",
        "gates": None},                                          # world.COURSE, unverändert
    "scheunen": {
        "name": "Scheunen-Slalom", "stars": 3,
        "desc": "Durch Scheune, unter der Brücke, durch Halle und Torhaus, Flaggen umfliegen",
        "gates": [G(2, 38, 0.5), G(18, 84, 0.3, yaw=BARN_YAW),
                  G(40, 106, 0, "flag", side="l"),
                  G(60, 130, 0.5, yaw=0.0),
                  G(94, 162, 0, "flag", side="r"),
                  G(110, 100, 3.0),
                  G(*HALL_C, 0.6, yaw=HALL_YAW),
                  G(*GATEHOUSE_C, 0.6, yaw=ROAD_YAW),
                  G(4, -6, 0, "flag", side="r")]},
    "turm": {
        "name": "Turm & Höhe", "stars": 4,
        "desc": "Doppel- und Leiter-Tore, hoch am Wasserturm, Tore auf Dächern und auf der Brücke",
        "gates": [G(0, 24, 0.25, "double", level=None, plan=1),
                  G(-16, 64, 0.25, "ladder", level=2),
                  G(-12, 129, 14.0),
                  G(46.0, 146.0, ROOF + 0.3, base=ROOF),
                  G(60, 130, DECK + 0.3, base=DECK, yaw=180.0),      # auf dem Brückendeck
                  G(83, 100, 0.25, "double", level=None, plan=1, yaw=180.0),
                  G(84, 64, 0.25, "ladder", level=2, yaw=180.0),
                  G(73.2, 17.0, ROOF + 0.3, base=ROOF),
                  G(18, -12, 1.5)]},
    "profi": {
        "name": "Profi", "stars": 5,
        "desc": "Enge und schräge Tore, Split-S, Sturzflug übers Dach, unter der Brücke, Haarnadel",
        "gates": [G(0, 20, 0.3, "small"),
                  G(0, 56, 1.2, "tilt", roll=40),                 # in der Säulenhalle
                  G(18, 84, 0.4, "small", yaw=BARN_YAW),
                  G(60, 130, 0.6, "small", yaw=0.0),               # unter der Brücke
                  G(60, 192, 8.0, yaw=0.0),                       # Split-S: oben hinaus ...
                  G(60, 165, 0.5, "small", yaw=180.0),            # ... unten zurück
                  G(37, 134, 8.5, yaw=180.0),                     # Sturzflug übers Hausdach
                  G(37, 89, 0.4, "small", yaw=180.0),
                  G(34, 38, 1.0, "tilt", roll=-40),
                  G(10, -6, 0, "flag", side="r")]},               # Haarnadel zurück nach Norden
}
ORDER = ["anfaenger", "dorfrunde", "scheunen", "turm", "profi"]
DEFAULT = "dorfrunde"
ALIASES = {"anfänger": "anfaenger", "anfanger": "anfaenger", "beginner": "anfaenger", "dorf": "dorfrunde",
           "scheune": "scheunen", "scheunen-slalom": "scheunen", "slalom": "scheunen", "turm&hoehe": "turm",
           "turm-hoehe": "turm", "hoehe": "turm", "höhe": "turm", "pro": "profi"}


def key(name):
    """Schlüssel einer Strecke aus Name, Schlüssel oder Nummer (1-5); unbekannt -> Dorfrunde."""
    if name is None:
        name = os.environ.get("FREEFLY_STRECKE") or DEFAULT
    n = str(name).strip().lower()
    if n.isdigit() and 1 <= int(n) <= len(ORDER):
        return ORDER[int(n) - 1]
    n = ALIASES.get(n, n)
    if n in TRACKS:
        return n
    for k, t in TRACKS.items():
        if t["name"].lower() == n:
            return k
    return DEFAULT


def info(name):
    k = key(name)
    return {"key": k, **TRACKS[k]}


def stars(n):
    return "★" * n + "☆" * (5 - n)


def label(name):
    """Für Menü-Werte und OSD (Avenir kennt kein ★): „Profi 5/5“."""
    t = info(name)
    return f"{t['name']}  {t['stars']}/5"


STAR_FONT = "Apple Symbols,Arial Unicode MS"


def draw_card(hud, name, highlight=False):
    """Strecken-Karte links neben dem Menü: Farbbalken, Name, Sterne in der Schwierigkeitsfarbe, Beschreibung."""
    t = info(name)
    r, T = hud.r, hud.text
    W, H = r.size
    s = hud.scale()
    cw, ch = 470 * s, 250 * s
    cx = max(cw / 2 + 12 * s, W / 2 - 310 * s - 24 * s - cw / 2)
    cy = H / 2
    col = COLORS[t["stars"]]
    r.begin_2d()
    hud.rect(cx, cy, cw, ch, (0.06, 0.07, 0.11, 0.9 if highlight else 0.78))
    hud.rect(cx, cy - ch / 2 + 4 * s, cw, 8 * s, (*col, 1.0) if t["stars"] < 5 else (0.85, 0.85, 0.9, 1.0))
    T.draw("STRECKE", cx, cy - ch / 2 + 34 * s, int(16 * s), tint=(1, 1, 1, 0.6), bold=False, outline=False)
    T.draw(t["name"], cx, cy - ch / 2 + 74 * s, int(36 * s), outline=False)
    star_col = (*col, 1.0) if t["stars"] < 5 else (0.95, 0.95, 1.0, 1.0)
    T.draw(stars(t["stars"]), cx, cy - ch / 2 + 122 * s, int(38 * s), tint=star_col, outline=False, family=STAR_FONT)
    words, lines, cur = t["desc"].split(), [], ""
    for w in words:                                  # Beschreibung umbrechen
        if len(cur) + len(w) > 40 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    for i, ln in enumerate(lines[:3]):
        T.draw(ln, cx, cy - ch / 2 + (168 + 26 * i) * s, int(19 * s), tint=(1, 1, 1, 0.8), bold=False, outline=False)


def summary():
    """Für Studio/remote: alle Strecken ohne Tor-Daten."""
    return [{"key": k, "name": TRACKS[k]["name"], "stars": TRACKS[k]["stars"], "desc": TRACKS[k]["desc"],
             "color": "#%02x%02x%02x" % tuple(int(255 * c) for c in COLORS[TRACKS[k]["stars"]])} for k in ORDER]
