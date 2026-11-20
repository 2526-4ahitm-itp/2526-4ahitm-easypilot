"""Bewegte Ziele im Dorf: Personen auf den Gehsteigen, Autos und Busse auf den Straßen.

Jede Figur läuft auf einer Straße (Anfang, Richtung, Länge) mit seitlichem Versatz hin und her.
Personen laufen weg, wenn die Drohne näher als PANIC_DIST kommt. Gezeichnet wird pro Modell mit
einem instanzierten Draw-Call; Position, Gierwinkel und Farbe kommen aus einem Instanz-Puffer.
"""
import math

import numpy as np

from .world import ROADS, World

PANIC_DIST = 14.0
KINDS = {             # Halbmaße (Kollision), Tempo m/s, Name
    "person": ((0.28, 0.9, 0.2), (1.1, 1.6), "Person"),
    "car": ((0.95, 0.75, 2.15), (8.0, 13.0), "Auto"),
    "bus": ((1.3, 1.65, 5.6), (6.0, 8.0), "Bus"),
}
SHIRTS = [(0.85, 0.2, 0.2), (0.2, 0.4, 0.85), (0.95, 0.8, 0.2), (0.25, 0.65, 0.3), (0.9, 0.5, 0.15),
          (0.6, 0.3, 0.7), (0.95, 0.95, 0.95), (0.15, 0.15, 0.18)]
PAINT = [(0.8, 0.1, 0.1), (0.1, 0.25, 0.7), (0.92, 0.92, 0.92), (0.15, 0.15, 0.16), (0.95, 0.75, 0.1),
         (0.2, 0.55, 0.35), (0.55, 0.57, 0.6), (0.85, 0.4, 0.1)]
M_PAINT, M_SHADOW, M_LIGHT = 8, 6, 9


def _builder():
    w = World.__new__(World)
    w.v, w.boxes, w.targets = [], [], []
    w.rng = np.random.default_rng(0)
    w.deco = np.random.default_rng(1)
    return w


def _blob(w, hx, hz):
    w.box((0, 0.012, 0), (hx, 0.01, hz), 0, (hx, hz, 0), M_SHADOW, collide=False)


def _wheel(w, x, y, z, r, width, hub=(0.7, 0.7, 0.72)):
    side = 1 if x > 0 else -1
    w.limb((x - side * width / 2, y, z), (x + side * width / 2, y, z), r, (0.07, 0.07, 0.07), sides=12, caps=True)
    w.limb((x + side * width / 2, y, z), (x + side * (width / 2 + 0.01), y, z), r * 0.55, hub, sides=8, caps=True)


def _cabin(w, y0, y1, bot, top, col, mat=0):
    """Kabine als Pyramidenstumpf: bot/top = (x-Halbbreite, z hinten, z vorne)."""
    (bx, bz0, bz1), (tx, tz0, tz1) = bot, top
    B = [(-bx, y0, bz0), (bx, y0, bz0), (bx, y0, bz1), (-bx, y0, bz1)]
    T = [(-tx, y1, tz0), (tx, y1, tz0), (tx, y1, tz1), (-tx, y1, tz1)]
    for i in range(4):
        j = (i + 1) % 4
        n = w._normal(B[i], B[j], T[j])
        mid = np.mean([B[i], B[j]], axis=0)
        if np.dot(n, (mid[0], 0, mid[2] - (bz0 + bz1) / 2)) < 0:
            n = tuple(-v for v in n)
        w.quad(B[i], B[j], T[j], T[i], n, col, ((0, 0),) * 4, mat)
    w.quad(*T, (0, 1, 0), col, ((0, 0),) * 4, mat)


def person_mesh():
    w = _builder()
    _blob(w, 0.45, 0.45)
    pants, skin, shoe = (0.2, 0.22, 0.3), (0.9, 0.72, 0.58), (0.12, 0.1, 0.09)
    for x in (-0.1, 0.1):
        w.box((x, 0.5, 0), (0.08, 0.42, 0.09), 0, pants, collide=False)
        w.box((x, 0.05, 0.03), (0.085, 0.05, 0.13), 0, shoe, collide=False)
    w.box((0, 0.93, 0), (0.2, 0.04, 0.12), 0, (0.15, 0.12, 0.1), collide=False)            # Gürtel
    w.box((0, 1.24, 0), (0.22, 0.31, 0.13), 0, (1, 1, 1), M_PAINT, collide=False)
    w.box((0, 1.5, 0.0), (0.1, 0.06, 0.135), 0, (1, 1, 1), M_PAINT, collide=False)          # Kragen
    for x in (-0.29, 0.29):
        w.box((x, 1.24, 0), (0.06, 0.28, 0.07), 0, (1, 1, 1), M_PAINT, collide=False)
        w.box((x, 0.9, 0), (0.05, 0.07, 0.06), 0, skin, collide=False)                     # Hände
    w.box((0, 1.58, 0), (0.06, 0.04, 0.06), 0, skin, collide=False)                         # Hals
    w.box((0, 1.72, 0), (0.11, 0.13, 0.12), 0, skin, collide=False)
    w.box((0, 1.86, -0.01), (0.125, 0.04, 0.135), 0, (0.25, 0.17, 0.1), collide=False)
    w.box((0, 1.74, -0.1), (0.12, 0.12, 0.03), 0, (0.25, 0.17, 0.1), collide=False)          # Haare hinten
    for x in (-0.045, 0.045):
        w.box((x, 1.75, 0.121), (0.018, 0.018, 0.005), 0, (0.08, 0.08, 0.1), collide=False)   # Augen
    w.box((0, 1.25, -0.2), (0.16, 0.2, 0.07), 0, (0.22, 0.25, 0.3), collide=False)           # Rucksack
    return np.array(w.v, dtype="f4")


def car_mesh():
    w = _builder()
    _blob(w, 1.2, 2.5)
    dark, chrome, glass = (0.1, 0.1, 0.11), (0.75, 0.76, 0.78), (0.13, 0.18, 0.25)
    w.box((0, 0.62, 0), (0.92, 0.3, 2.1), 0, (1, 1, 1), M_PAINT, collide=False)              # Karosserie
    w.box((0, 0.93, 1.35), (0.9, 0.03, 0.72), 0, (1, 1, 1), M_PAINT, collide=False)          # Motorhaube
    _cabin(w, 0.92, 1.38, (0.88, -1.55, 0.62), (0.76, -1.05, -0.05), glass)                  # Scheiben
    w.box((0, 1.385, -0.55), (0.77, 0.025, 0.52), 0, (1, 1, 1), M_PAINT, collide=False)      # Dach
    for x in (-0.89, 0.89):                                                                   # Türen, Griffe
        w.box((x, 0.72, -0.35), (0.01, 0.2, 0.004), 0, dark, collide=False)
        w.box((x * 1.005, 0.82, 0.1), (0.01, 0.02, 0.09), 0, chrome, collide=False)
        w.box((x * 1.05, 1.0, 0.55), (0.08, 0.05, 0.08), 0, (1, 1, 1), M_PAINT, collide=False)   # Spiegel
    for z in (-2.13, 2.13):                                                                   # Stoßstangen
        w.box((0, 0.42, z), (0.94, 0.1, 0.05), 0, dark, collide=False)
        w.box((0, 0.6, z * 1.003), (0.25, 0.07, 0.01), 0, (0.95, 0.95, 0.9), collide=False)  # Kennzeichen
    w.box((0, 0.72, 2.115), (0.4, 0.06, 0.01), 0, dark, collide=False)                       # Kühlergrill
    for x in (-0.86, 0.86):
        for z in (-1.35, 1.35):
            _wheel(w, x, 0.33, z, 0.33, 0.24)
    for x in (-0.65, 0.65):
        w.box((x, 0.75, 2.11), (0.17, 0.07, 0.02), 0, (1.0, 0.95, 0.7), M_LIGHT, collide=False)
        w.box((x, 0.75, -2.11), (0.17, 0.06, 0.02), 0, (0.9, 0.1, 0.1), M_LIGHT, collide=False)
    return np.array(w.v, dtype="f4")


def bus_mesh():
    w = _builder()
    _blob(w, 1.6, 6.0)
    dark, glass = (0.1, 0.1, 0.11), (0.12, 0.16, 0.22)
    w.box((0, 1.05, 0), (1.28, 0.75, 5.55), 0, (1, 1, 1), M_PAINT, collide=False)
    w.box((0, 2.3, 0), (1.26, 0.5, 5.5), 0, glass, collide=False)                           # Fensterband
    for z in np.arange(-4.6, 5.0, 1.5):                                                     # Fenstersäulen
        for x in (-1.275, 1.275):
            w.box((x, 2.3, z), (0.012, 0.5, 0.06), 0, (1, 1, 1), M_PAINT, collide=False)
    w.box((0, 2.95, 0), (1.3, 0.15, 5.6), 0, (1, 1, 1), M_PAINT, collide=False)
    w.box((0, 3.15, -1.0), (0.7, 0.08, 1.4), 0, (0.8, 0.8, 0.82), collide=False)            # Klimaanlage
    w.box((0, 1.6, 5.56), (1.2, 0.95, 0.01), 0, glass, collide=False)                       # Frontscheibe
    w.box((0, 2.75, 5.57), (0.95, 0.13, 0.01), 0, (1.0, 0.6, 0.1), M_LIGHT, collide=False)  # Zielanzeige
    w.box((0, 0.4, 5.6), (1.3, 0.12, 0.05), 0, dark, collide=False)
    w.box((0, 0.4, -5.6), (1.3, 0.12, 0.05), 0, dark, collide=False)
    for z in (3.9, 0.3):                                                                    # Türen rechts
        w.box((1.29, 1.45, z), (0.01, 1.15, 0.55), 0, glass, collide=False)
        w.box((1.295, 1.45, z), (0.005, 1.15, 0.015), 0, dark, collide=False)
    for x in (-1.45, 1.45):
        w.box((x, 2.2, 5.4), (0.04, 0.15, 0.08), 0, dark, collide=False)                     # Spiegel
    for z in (-3.6, 3.4):
        for x in (-1.2, 1.2):
            _wheel(w, x, 0.47, z, 0.47, 0.3)
    for x in (-0.85, 0.85):
        w.box((x, 0.75, 5.57), (0.2, 0.1, 0.02), 0, (1.0, 0.95, 0.7), M_LIGHT, collide=False)
        w.box((x, 0.75, -5.57), (0.15, 0.12, 0.02), 0, (0.9, 0.1, 0.1), M_LIGHT, collide=False)
    return np.array(w.v, dtype="f4")


class Entities:
    def __init__(self, world, n_people=46, n_cars=16, n_buses=3, seed=21):
        self.world = world
        rng = np.random.default_rng(seed)
        self.rng = rng
        roads = [r for r in ROADS]
        kinds, road, s, side, direction, speed, tint = [], [], [], [], [], [], []

        def add(kind, ri, off, col):
            x0, z0, x1, z1, w = roads[ri]
            L = math.hypot(x1 - x0, z1 - z0)
            kinds.append(kind)
            road.append(ri)
            s.append(rng.uniform(5, L - 5))
            d = rng.choice((-1, 1))
            direction.append(d)
            # Rechtsverkehr: Fahrspur rechts der Fahrtrichtung
            side.append(off if kind == "person" else d * off)
            speed.append(rng.uniform(*KINDS[kind][1]))
            tint.append(col)
        for _ in range(n_people):
            ri = rng.integers(2)                     # nicht an der Zufahrt zum Startplatz
            w = roads[ri][4]
            add("person", ri, rng.choice((-1, 1)) * (w / 2 + rng.uniform(0.4, 1.4)), SHIRTS[rng.integers(len(SHIRTS))])
        for _ in range(n_cars):
            ri = rng.integers(2)
            add("car", ri, roads[ri][4] / 4, PAINT[rng.integers(len(PAINT))])
        for _ in range(n_buses):
            add("bus", 0, roads[0][4] / 4, [(0.95, 0.75, 0.1), (0.85, 0.15, 0.12), (0.15, 0.45, 0.8)][_ % 3])
        self.kind = np.array(kinds)
        self.road = np.array(road)
        self.s = np.array(s, float)
        self.side = np.array(side, float)
        self.dir = np.array(direction, float)
        self.speed = np.array(speed, float)
        self.base_tint = np.array(tint, float)
        self.tint = self.base_tint.copy()
        self.alive = np.ones(len(kinds), bool)      # noch ein Ziel
        self.visible = np.ones(len(kinds), bool)    # gezeichnet (Wracks bleiben stehen)
        self.half = np.array([KINDS[k][0] for k in kinds], float)
        self.panic = np.zeros(len(kinds), bool)
        ra = np.array(roads, float)
        self._r0 = ra[self.road, 0:2]
        d = ra[self.road, 2:4] - self._r0
        self._len = np.linalg.norm(d, axis=1)
        self._u = d / self._len[:, None]
        self._n = np.stack((self._u[:, 1], -self._u[:, 0]), axis=1)
        self.pos = np.zeros((len(kinds), 3))
        self.yaw = np.zeros(len(kinds))
        self.t = 0.0
        self.hold = -1                                 # diese Figur bleibt stehen (Test)
        self._place()

    def _place(self):
        xz = self._r0 + self._u * self.s[:, None] + self._n * self.side[:, None]
        h = np.where(self.kind == "person", 0.0, 0.05)
        bob = np.where(self.kind == "person", 0.04 * np.abs(np.sin(self.t * 7 * self.speed + self.s)), 0.0)
        self.pos = np.stack((xz[:, 0], h + bob, xz[:, 1]), axis=1)
        mv = self._u * self.dir[:, None]
        self.yaw = np.arctan2(mv[:, 0], mv[:, 1])

    def update(self, dt, drone_pos=None):
        self.t += dt
        moving = self.alive.copy()
        if self.hold >= 0:
            moving[self.hold] = False
        v = self.speed.copy()
        if drone_pos is not None:                     # Personen rennen weg
            dp = np.asarray(drone_pos)
            d = np.hypot(self.pos[:, 0] - dp[0], self.pos[:, 2] - dp[2])
            near = (self.kind == "person") & self.alive & (d < PANIC_DIST)
            away = np.sign((self.pos[:, 0] - dp[0]) * self._u[:, 0] + (self.pos[:, 2] - dp[2]) * self._u[:, 1])
            away[away == 0] = 1
            self.dir = np.where(near & ~self.panic, away, self.dir)
            self.panic = near
            v = np.where(near, 4.5, v)
        self.s += np.where(moving, self.dir * v * dt, 0.0)
        low, high = self.s < 3, self.s > self._len - 3
        turn = (low & (self.dir < 0)) | (high & (self.dir > 0))
        self.dir = np.where(turn, -self.dir, self.dir)
        self.side = np.where(turn & (self.kind != "person"), -self.side, self.side)   # Spur wechseln
        self.s = np.clip(self.s, 3, self._len - 3)
        self._place()

    def hit(self, p, r, prefer=None):
        """Index der getroffenen Figur (Kugel gegen gedrehte Box) oder -1; `prefer` gewinnt bei mehreren."""
        if not len(self.pos):
            return -1
        d = np.asarray(p) - self.pos
        c, s = np.cos(self.yaw), np.sin(self.yaw)
        lx = c * d[:, 0] - s * d[:, 2]
        lz = s * d[:, 0] + c * d[:, 2]
        ly = d[:, 1] - self.half[:, 1]
        q = np.maximum(np.abs(np.stack((lx, ly, lz), axis=1)) - self.half, 0.0)
        h = np.nonzero((np.einsum("ij,ij->i", q, q) < r * r) & self.visible)[0]
        if prefer is not None and prefer in h:
            return int(prefer)
        return int(h[0]) if len(h) else -1

    def destroy(self, i):
        self.alive[i] = False
        if self.kind[i] == "person":
            self.visible[i] = False
        else:
            self.tint[i] = (0.07, 0.065, 0.06)        # ausgebranntes Wrack bleibt stehen

    def revive(self):
        self.alive[:] = True
        self.visible[:] = True
        self.tint = self.base_tint.copy()

    def name(self, i):
        return KINDS[self.kind[i]][2]

    def bounds(self, i):
        """Achsenparallele Hülle (lo, hi) und Mittelpunkt."""
        h = self.half[i]
        r = math.hypot(h[0], h[2])
        p = self.pos[i]
        lo = (p[0] - r, p[1], p[2] - r)
        hi = (p[0] + r, p[1] + 2 * h[1], p[2] + r)
        return lo, hi, (p[0], p[1] + h[1], p[2])

    def instances(self, kind):
        m = (self.kind == kind) & self.visible
        if not m.any():
            return np.zeros((0, 7), "f4")
        return np.column_stack((self.pos[m], self.yaw[m], self.tint[m])).astype("f4")
