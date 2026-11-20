"""Die Welt des Freiflug-Simulators: Wiese, Dorf mit Straßen und Häusern, Bäume, Tor-Strecke.

Strecken (tracks.py): das Dorf wird immer an Hand der Dorfrunde (COURSE) angelegt, damit Häuser und
Bäume für jede Strecke an derselben Stelle stehen. Für eine andere Strecke (World(track=...)) ersetzt
_use_track danach die Tore und räumt Deko (Bäume, Büsche, Laternen, Leitungen, Steine) aus deren Linie.

Alles ist Low-Poly-Geometrie in einem Vertex-Puffer (Position, Normale, Farbe, uv in Metern,
Material). Kollision: orientierte Boxen (Drehung um y), Dächer und Baumkronen als gestufte Boxen.
Koordinaten wie Unity/sim.py: x rechts, y oben, z vorne (Startrichtung).
"""
import math
from dataclasses import dataclass

import numpy as np

RADIUS = 0.12                    # m, Kollisionskugel der Drohne
GATE_W, GATE_H, GATE_T = 3.0, 2.4, 0.22

# Materialien (Shader entscheidet anhand der Nummer)
M_PLAIN, M_WALL, M_ROAD, M_ROOF, M_LEAF, M_PAD = 0, 1, 2, 3, 4, 5
M_WOOD, M_LIGHT, M_FIELD, M_METAL = 7, 9, 11, 12   # Bretter, Lampe (leuchtet), Acker, Wellblech
M_GATE = 32                      # + Tor-Index (gfx.py: v_mat >= 32)


@dataclass
class Gate:
    x: float
    z: float
    lift: float
    yaw: float = 0.0
    kind: str = "std"            # Torart (tracks.py): std small big tilt double ladder flag
    w: float = GATE_W            # Öffnung
    h: float = GATE_H
    roll: float = 0.0            # rad, schräges Tor
    n_open: int = 1              # Öffnungen übereinander (Doppeltor 2, Leiter 3)
    level: object = 0            # zählende Öffnung, None = jede
    plan: int = 0                # Öffnung, auf die die Rennlinie zielt (wenn level None)
    base: float = 0.0            # Boden unter dem Tor (Flachdach)
    pole: tuple = None           # Flagge: Stange (x, z); das Tor ist das Fenster daneben

    def open_y(self, k):
        return self.lift + self.h / 2 + k * (self.h + GATE_T)

    @property
    def center(self):
        return (self.x, self.open_y(self.plan if self.level is None else self.level), self.z)

    @property
    def plan_size(self):
        """Öffnung für die Rennlinie: schräg -> eingeschriebenes Quadrat, Flagge -> Abstand zur Stange."""
        if self.roll:
            return (min(self.w, self.h) * 0.7,) * 2
        if self.pole is not None:
            return (self.w - 1.0, self.h)
        return (self.w, self.h)

    def local(self, p):
        """(quer, hoch, Flugrichtung) relativ zur Tormitte, quer/hoch auf ein Standardtor (GATE_W x GATE_H)
        umgerechnet: game.Flight prüft |quer| < GATE_W/2 und |hoch| < GATE_H/2 für jede Torart. Bei mehreren
        zählenden Öffnungen gilt die nächstgelegene, beim schrägen Tor wird erst zurückgedreht."""
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        rx, rz = p[0] - self.x, p[2] - self.z
        q, f = c * rx - s * rz, s * rx + c * rz
        best = None
        for k in (range(self.n_open) if self.level is None else (self.level,)):
            y = p[1] - self.open_y(k)
            u = q
            if self.roll:
                cr, sr = math.cos(self.roll), math.sin(self.roll)
                u, y = cr * q + sr * y, -sr * q + cr * y
            nx, ny = u * (GATE_W / self.w), y * (GATE_H / self.h)
            m = max(abs(nx) / GATE_W, abs(ny) / GATE_H)
            if best is None or m < best[0]:
                best = (m, nx, ny)
        return best[1], best[2], f


# Rundkurs: (x, z, Höhe der Unterkante). Richtung jedes Tors = vom vorigen zum nächsten Tor.
COURSE = [(0, 16, 0), (4, 36, 1.5), (0, 56, 0), (18, 84, 0), (42, 100, 0), (60, 122, 0),
          (60, 152, 4.0), (92, 158, 0), (114, 104, 6.0), (92, 46, 0), (60, 30, 0), (8, -14, 0)]
# Straßen: (x0, z0, x1, z1, Breite)
ROADS = [(60, 10, 60, 170, 7.0), (14, 100, 112, 100, 7.0), (-4, 0, 60, 26, 5.0)]
SPAWN = (0.0, RADIUS, 0.0)
LINE_CLEAR = 3.5                 # m Luft zwischen Baumkrone und Rennlinie (Regelabweichung bei k=1,2)

WALLS = [(0.93, 0.90, 0.84), (0.95, 0.86, 0.66), (0.90, 0.72, 0.62), (0.80, 0.84, 0.86),
         (0.97, 0.96, 0.93), (0.78, 0.86, 0.74), (0.88, 0.80, 0.90)]
# Dächer, Kamine, Türen bewusst nicht orange: Orange haben nur die Tore (Farb-Detektor des Kamera-Piloten)
ROOFS = [(0.6, 0.2, 0.17), (0.35, 0.33, 0.33), (0.52, 0.2, 0.2), (0.30, 0.22, 0.22), (0.26, 0.28, 0.32)]


class World:
    def __init__(self, seed=11, track=None):
        """track: Strecke aus tracks.py (Name, Schlüssel oder Nummer); None = FREEFLY_STRECKE oder Dorfrunde.
        Das Dorf wird immer mit der Dorfrunde angelegt (gleiche Häuser, gleiche Bäume für alle Strecken);
        für eine andere Strecke tauscht _use_track danach nur die Tore und räumt Deko aus ihrer Linie."""
        from . import tracks
        self.track = tracks.key(track)
        self.track_info = tracks.info(self.track)
        self.deco_items = []     # (Anfang, Ende, x, z, Radius, Höhe): Bäume, Büsche, Laternen, Leitungen, Steine
        self.v = []              # Vertices: 12 floats
        self.targets = []        # zerstörbare Objekte (Bomben-Modus), siehe _target
        self.boxes = []          # (cx, cy, cz, hx, hy, hz, yaw)
        self.rng = np.random.default_rng(seed)            # Lage von Häusern und Bäumen
        self.deco = np.random.default_rng(seed + 1)      # Verzierungen (ändert die Lage nicht)
        self.reserved = []       # (x, z, r): hier baut das Dorf nichts (Durchflug-Gebäude, Äcker)
        self.gates = self._course()
        self.line_xz = self._race_line()
        self._roads()
        self._landmarks()
        self._flythrough()
        self._village()
        self._fields()
        self._trees()
        if self.track != "dorfrunde":
            self._use_track(self.track_info)
        self.vertices = np.array(self.v, dtype="f4")
        b = np.array(self.boxes, dtype="f8")
        self.bc, self.bh = b[:, 0:3], b[:, 3:6]
        self.bcos, self.bsin = np.cos(b[:, 6]), np.sin(b[:, 6])
        self.brad = np.linalg.norm(self.bh, axis=1)
        self.near = np.arange(len(b))
        self.alive = np.ones(len(b), dtype=bool)
        self.owner = np.full(len(b), -1)
        for i, t in enumerate(self.targets):
            self.owner[t["boxes"][0]:t["boxes"][1]] = i

    def _target(self, name, start):
        """Alles, was seit `start` (Vertices, Boxen) gebaut wurde, ist ein zerstörbares Ziel."""
        v0, b0 = start
        pts = np.array([v[:3] for v in self.v[v0:]])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        self.targets.append({"name": name, "verts": (v0, len(self.v)), "boxes": (b0, len(self.boxes)),
                             "center": tuple((lo + hi) / 2), "lo": tuple(lo), "hi": tuple(hi), "alive": True})

    def mark(self):
        return len(self.v), len(self.boxes)

    def destroy(self, i):
        t = self.targets[i]
        t["alive"] = False
        self.alive[t["boxes"][0]:t["boxes"][1]] = False

    def revive(self):
        for t in self.targets:
            t["alive"] = True
        self.alive[:] = True

    # ------------------------------------------------------------ Strecken (tracks.py)

    def _deco(self, start, x, z, r, top):
        """Was seit `start` gebaut wurde, ist Deko (Baum, Busch, Laterne, Leitung, Stein): darf für eine
        andere Strecke wegfallen. r = waagrechter Radius, top = Höhe."""
        self.deco_items.append((start, self.mark(), x, z, r, top))

    def _track_gates(self, spec):
        from .tracks import OPENINGS, SIZES
        n = len(spec)
        pts = [(d["x"], d["z"]) for d in spec]
        out = []
        for i, d in enumerate(spec):
            x, z = pts[i]
            if d.get("yaw") is not None:
                yaw = math.radians(d["yaw"])
            else:                                         # Winkelhalbierende wie bei der Dorfrunde
                px, pz = pts[i - 1] if i else (0.0, 0.0)
                nx, nz = pts[(i + 1) % n]
                a = np.array((x - px, z - pz)) / math.hypot(x - px, z - pz)
                b = np.array((nx - x, nz - z)) / math.hypot(nx - x, nz - z)
                yaw = math.atan2(*(a + b))
            kind = d.get("kind", "std")
            w, h = SIZES[kind]
            base = d.get("base", 0.0)
            pole = None
            if kind == "flag":
                side = 1.0 if d.get("side", "r") == "r" else -1.0   # Stange rechts/links der Flugrichtung
                pole = (x, z)
                off = side * (w / 2 + 0.35)                   # Fenstermitte = Stange - quer * off
                x, z = x - math.cos(yaw) * off, z + math.sin(yaw) * off
                lift = 0.0
            else:
                lift = max(d.get("lift", 0.0), base + 0.25)
            nopen = OPENINGS.get(kind, 1)
            level = d.get("level", 0) if nopen > 1 else 0
            out.append(Gate(x, z, lift, yaw, kind, w, h, math.radians(d.get("roll", 0.0)), nopen, level,
                            d.get("plan", 0), base, pole))
        return out

    @staticmethod
    def _track_line(gates, ks=(0.6, 1.0)):
        """Rennlinien (ohne Hindernisse, 2 Runden) bei k 0,6 und 1,0: daraus wird die Deko geräumt."""
        try:
            from ..planner import Gate as PGate
            from ..race import build_line, launch
            pg = [PGate(g.center, (math.sin(g.yaw), 0.0, math.cos(g.yaw)), *g.plan_size) for g in gates]
            start, d = launch(pg[0], SPAWN)
            pts = []
            for k in ks:
                pts += list(build_line(pg + [pg[0]], start, d, 2, k).points)
            return np.asarray(pts, dtype="f8")
        except Exception as e:
            print("Rennlinie für die Deko-Freihaltung nicht verfügbar:", e)
            return np.zeros((0, 3))

    @staticmethod
    def _in_way(pts, gates, x, z, r, top):
        if len(pts):
            d = np.hypot(pts[:, 0] - x, pts[:, 2] - z)
            if np.any((d < r + LINE_CLEAR) & (pts[:, 1] < top + 2.5)):
                return True
        for g in gates:
            for gx, gz in ((g.x, g.z),) + ((g.pole,) if g.pole else ()):
                if math.hypot(gx - x, gz - z) < r + max(g.w, 3.0) / 2 + 2.5:
                    return True
        return math.hypot(x, z) < r + 4.0                       # Startplatz

    def _use_track(self, t):
        """Dorfrunden-Tore raus, Tore der Strecke rein, Deko aus deren Linie räumen."""
        from .tracks import COLORS
        gates = self._track_gates(t["gates"])
        pts = self._track_line(gates)
        keep_v = np.ones(len(self.v), dtype=bool)
        keep_b = np.ones(len(self.boxes), dtype=bool)
        gv, gb = self._gate_mark
        keep_v[:gv] = False
        keep_b[:gb] = False
        self.removed_deco = 0
        for (v0, b0), (v1, b1), x, z, r, top in self.deco_items:
            if self._in_way(pts, gates, x, z, r, top):
                keep_v[v0:v1] = False
                keep_b[b0:b1] = False
                self.removed_deco += 1
        cv = np.concatenate(([0], np.cumsum(keep_v)))
        cb = np.concatenate(([0], np.cumsum(keep_b)))
        self.v = [v for v, k in zip(self.v, keep_v) if k]
        self.boxes = [b for b, k in zip(self.boxes, keep_b) if k]
        for tg in self.targets:
            tg["verts"] = (int(cv[tg["verts"][0]]), int(cv[tg["verts"][1]]))
            tg["boxes"] = (int(cb[tg["boxes"][0]]), int(cb[tg["boxes"][1]]))
        self.deco_items = []
        self.gates = gates
        self.line_xz = pts[:, [0, 2]] if len(pts) else np.zeros((0, 2))
        accent = COLORS[t["stars"]]
        self.gate_boxes = (len(self.boxes), None)          # Kollisionsboxen der Tore (Tests: Tor steckt in nichts)
        for i, g in enumerate(gates):
            self.gate_kind(g, M_GATE + i, accent)
        self.gate_boxes = (self.gate_boxes[0], len(self.boxes))

    # ------------------------------------------------------------ Aufbau

    def _course(self):
        gates = []
        n = len(COURSE)
        for i, (x, z, lift) in enumerate(COURSE):
            px, pz, _ = COURSE[i - 1] if i else (0, 0, 0)       # Tor 1 schaut zum Startplatz
            nx, nz, _ = COURSE[(i + 1) % n]
            a = np.array((x - px, z - pz)) / math.hypot(x - px, z - pz)      # Winkelhalbierende
            b = np.array((nx - x, nz - z)) / math.hypot(nx - x, nz - z)
            yaw = math.atan2(*(a + b))
            g = Gate(x, z, max(lift, 0.25), yaw)          # unterer Balken sichtbar über der Wiese
            gates.append(g)
            self.gate(g, M_GATE + i)
        self._gate_mark = self.mark()                     # Vertices/Boxen der Dorfrunden-Tore: [0, Marke)
        # Start-Plattform
        self.box((0, 0.04, 0), (1.3, 0.04, 1.3), 0, (0.25, 0.25, 0.27), M_PAD, collide=False)
        return gates

    def course_dist(self, x, z):
        """Abstand eines Punkts (x, z) zur Flugroute (Polylinie durch alle Tore + Start)."""
        pts = [(0.0, 0.0)] + [(g.x, g.z) for g in self.gates] + [(self.gates[0].x, self.gates[0].z)]
        best = 1e9
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            dx, dz = bx - ax, bz - az
            t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / max(1e-9, dx * dx + dz * dz)))
            best = min(best, math.hypot(x - ax - t * dx, z - az - t * dz))
        return best

    def _race_line(self):
        """Rennlinie (x, z) wie sie auto.Autopilot plant, hier ohne Hindernisse und für 2 Runden
        (Start -> Tor 1 und Tor 12 -> Tor 1). Sie schwingt in Kurven bis ~7 m neben der Tor-Polylinie
        (course_dist) aus. Bäume halten Abstand zu beiden (line_dist), sonst steht nach einer Änderung
        an der Welt schnell ein Baum in der Linie (20.11.: Absturz zwischen Tor 9 und 10 bei k=1,2)."""
        try:
            from ..planner import Gate as PGate
            from ..race import build_line, launch
            gates = [PGate(g.center, (math.sin(g.yaw), 0.0, math.cos(g.yaw)), GATE_W, GATE_H) for g in self.gates]
            start, d = launch(gates[0], SPAWN)
            line = build_line(gates + [gates[0]], start, d, 2, 0.6)
            return np.asarray(line.points, dtype="f8")[:, [0, 2]]
        except Exception as e:            # Planer fehlt: nur die Polylinie zählt
            print("Rennlinie für die Baum-Freihaltung nicht verfügbar:", e)
            return np.zeros((0, 2))

    def line_dist(self, x, z):
        """Waagrechter Abstand eines Punkts zur Rennlinie (sehr groß ohne Linie)."""
        if len(self.line_xz) == 0:
            return 1e9
        return float(np.min(np.hypot(self.line_xz[:, 0] - x, self.line_xz[:, 1] - z)))

    def free(self, x, z, r, course=5.0, y=1.0):
        return self.course_dist(x, z) > r + course and self.unreserved(x, z, r) \
            and not self.hit((x, y, z), r, all_boxes=True) and math.hypot(x, z) > r + 22

    def unreserved(self, x, z, r):
        return all(math.hypot(x - rx, z - rz) > r + rr for rx, rz, rr in self.reserved)

    def _roads(self):
        self.road_segs = []
        for k, (x0, z0, x1, z1, w) in enumerate(ROADS):
            L = math.hypot(x1 - x0, z1 - z0)
            yaw = math.atan2(x1 - x0, z1 - z0)
            cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
            top = 0.04 + 0.004 * k
            self.box((cx, top / 2, cz), (w / 2, top / 2, L / 2), yaw, (0.30, 0.30, 0.32), M_ROAD, collide=False)
            c, s = math.cos(yaw), math.sin(yaw)
            for side in (-1, 1):                                   # Gehsteige
                ox = side * (w / 2 + 0.9)
                self.box((cx + c * ox, 0.0175, cz - s * ox), (0.9, 0.0175, L / 2), yaw, (0.66, 0.65, 0.62),
                         M_PLAIN, collide=False)
            self.road_segs.append((x0, z0, x1, z1, w))

    def road_dist(self, x, z):
        best = 1e9
        for x0, z0, x1, z1, w in self.road_segs:
            dx, dz = x1 - x0, z1 - z0
            t = max(0.0, min(1.0, ((x - x0) * dx + (z - z0) * dz) / (dx * dx + dz * dz)))
            best = min(best, math.hypot(x - x0 - t * dx, z - z0 - t * dz) - w / 2)
        return best

    def _landmarks(self):
        # Säulenhalle über Tor 3
        g = self.gates[2]
        for x, z in ((-6, -6), (6, -6), (-6, 6), (6, 6)):
            self.cylinder((g.x + x, 0, g.z + z), 0.45, 8.0, (0.85, 0.84, 0.80), sides=10)
        self.box((g.x, 8.25, g.z), (7.0, 0.3, 7.6), 0, (0.6, 0.6, 0.62))
        # Container-Stapel und Lagerhalle am Feldrand
        cols = [(0.70, 0.22, 0.18), (0.18, 0.42, 0.62), (0.24, 0.50, 0.30), (0.78, 0.56, 0.18), (0.55, 0.55, 0.58)]
        for i, (x, z, yaw, lvl) in enumerate(((-22, 20, 20, 0), (-24.5, 21, 20, 0), (-23, 20.5, 20, 1),
                                               (-30, 46, 85, 0), (-30, 52.5, 85, 0), (24, 52, -30, 0))):
            if self.course_dist(x, z) > 6:
                self.container((x, 1.3 + 2.6 * lvl, z), math.radians(yaw), cols[i % len(cols)])
        self.house(-40, 82, math.radians(10), 20, 14, 7, 3, (0.70, 0.70, 0.72), (0.40, 0.42, 0.45), windows=False,
                   name="Lagerhalle")
        # Wasserturm
        start = self.mark()
        self.cylinder((-14, 0, 120), 0.4, 14, (0.5, 0.5, 0.52), sides=6)
        self.cylinder((-14, 14, 120), 3.5, 4.5, (0.82, 0.82, 0.86), sides=16)
        self.cone((-14, 18.5, 120), 3.8, 2.0, (0.55, 0.22, 0.16), sides=16)
        self._target("Wasserturm", start)

    def _village(self):
        rng = self.rng
        for x0, z0, x1, z1, w in ROADS[:2]:
            L = math.hypot(x1 - x0, z1 - z0)
            ux, uz = (x1 - x0) / L, (z1 - z0) / L
            for side in (-1, 1):
                t = rng.uniform(4, 8)
                while t < L - 4:
                    width = rng.uniform(7, 10.5)
                    depth = rng.uniform(7, 9.5)
                    t += width / 2
                    off = w / 2 + 1.8 + rng.uniform(2.5, 4.5) + depth / 2
                    nx, nz = uz * side, -ux * side          # Normale zur Straße
                    cx, cz = x0 + ux * t + nx * off, z0 + uz * t + nz * off
                    yaw = math.atan2(ux, uz) + math.pi / 2       # Haus-x entlang der Straße
                    floors = 1 + int(rng.random() < 0.45)
                    if self.road_dist(cx, cz) > depth / 2 + 1.5 and self.free(cx, cz, max(width, depth) / 2 + 1.5, 4.0):
                        if rng.random() < 0.12:
                            self.house(cx, cz, yaw, width, depth, 3 * 3 + 0.4, 0, WALLS[rng.integers(len(WALLS))],
                                       (0.4, 0.4, 0.42), flat=True)
                        else:
                            self.house(cx, cz, yaw, width, depth, 3.0 * floors + 0.3, rng.uniform(2.4, 3.6),
                                       WALLS[rng.integers(len(WALLS))], ROOFS[rng.integers(len(ROOFS))],
                                       door_side=(-nx, -nz), yard=off - depth / 2 - w / 2 - 1.8)
                    t += width / 2 + rng.uniform(3, 7)
        # Laternen entlang der Hauptstraße
        for z in range(18, 170, 16):
            if self.course_dist(64.8, z) > 11 and self.unreserved(64.8, z, 1.5):  # Rennlinie schwingt in Kurven weit aus
                m = self.mark()
                self.lamp(64.8, z)
                self._deco(m, 64.8, z, 1.4, 5.3)
        # Straßenbäume und Stromleitungen quer über die Straßen (macht es eng)
        for x0, z0, x1, z1, w in ROADS[:2]:
            L = math.hypot(x1 - x0, z1 - z0)
            ux, uz = (x1 - x0) / L, (z1 - z0) / L
            nx, nz = uz, -ux
            for t in np.arange(10, L - 6, 11.0):
                for side in (-1, 1):
                    off = side * (w / 2 + 2.3)
                    x, z = x0 + ux * t + nx * off, z0 + uz * t + nz * off
                    if self.course_dist(x, z) > 8 and not self.hit((x, 1.0, z), 0.6, all_boxes=True) \
                            and rng.random() < 0.65 and self.unreserved(x, z, 2.5) \
                            and self.line_dist(x, z) > 7.0 * 0.3 + LINE_CLEAR:        # Krone bis 0,3 * Höhe
                        m, h = self.mark(), rng.uniform(5.0, 7.0)
                        self.leafy(x, z, h)
                        self._deco(m, x, z, h * 0.38, h * 1.05)
            for t in np.arange(20, L - 10, 38.0):
                cx, cz = x0 + ux * t, z0 + uz * t
                if self.course_dist(cx, cz) < 7 or not self.unreserved(cx, cz, w / 2 + 3):
                    continue
                ends = []
                m = self.mark()
                for side in (-1, 1):
                    off = side * (w / 2 + 2.0)
                    ends.append((cx + nx * off, cz + nz * off))
                    self.cylinder((ends[-1][0], 0, ends[-1][1]), 0.12, 7.6, (0.35, 0.28, 0.2), sides=6)
                (ax, az), (bx, bz) = ends
                yaw = math.atan2(bx - ax, bz - az)
                span = math.hypot(bx - ax, bz - az)
                for dy in (7.0, 7.4):                                      # zwei Kabel
                    self.box(((ax + bx) / 2, dy, (az + bz) / 2), (0.03, 0.03, span / 2), yaw, (0.1, 0.1, 0.1))
                self._deco(m, cx, cz, span / 2 + 0.5, 7.7)

    def _trees(self):
        rng = self.rng
        placed = 0
        for _ in range(900):
            if placed >= 260:
                break
            r = rng.uniform(25, 230) if rng.random() < 0.7 else rng.uniform(140, 260)
            a = rng.uniform(0, 2 * math.pi)
            x, z = 50 + r * math.cos(a), 80 + r * math.sin(a)
            if self.road_dist(x, z) < 3 or not self.free(x, z, 2.5, 8.0):     # Kronen bis ~2,5 m + Rennlinie
                continue
            if self.line_dist(x, z) < 11 * 0.3 + LINE_CLEAR:                  # Krone bis 0,3 * Höhe (max 11 m)
                continue
            h = rng.uniform(5, 11)
            m = self.mark()
            if rng.random() < 0.5:
                self.pine(x, z, h)
            else:
                self.leafy(x, z, h)
            self._deco(m, x, z, h * 0.38, h * 1.1)
            placed += 1
        for _ in range(60):                                       # Büsche
            x, z = rng.uniform(-60, 150), rng.uniform(-30, 200)
            if self.road_dist(x, z) > 2 and self.free(x, z, 1.2, 3.0, y=0.5) and self.line_dist(x, z) > 1.2 + LINE_CLEAR:
                s = rng.uniform(0.6, 1.2)
                m = self.mark()
                self.blob((x, s * 0.6, z), (s, s * 0.7, s), (0.22, 0.45, 0.18), collide=True)
                self._deco(m, x, z, s * 1.2, s * 1.4)

    # ------------------------------------------------------------ Durchflug-Gebäude

    def _flythrough(self):
        """Gebäude zum Durchfliegen: innen hohl, Kollision nur an Wänden, Dach und Balken."""
        g = self.gates[3]                                          # Tor 4 steht mitten in der Scheune
        self.barn(g.x, g.z, g.yaw, W=13.0, L=13.0, H=5.6, door_w=8.0, door_h=5.0, name="Scheune")   # breite Tore:
        # der Kamera-Pilot kommt von Tor 3 schräg herein
        a, b = self.gates[9], self.gates[10]                       # offene Halle zwischen Tor 10 und 11
        self.hall((a.x + b.x) / 2 + 1.0, (a.z + b.z) / 2 + 0.5, math.atan2(b.x - a.x, b.z - a.z))
        self.footbridge(60.0, 130.0)                               # Fußgängerbrücke kurz nach Tor 6 (Tor 7 bleibt
                                                                   # dahinter sichtbar, es steht 4 m hoch)
        x0, z0, x1, z1, _ = ROADS[2]                               # Torhaus über der Zufahrt (Strecke Tor 11 -> 12)
        self.gatehouse(47.0, z0 + (z1 - z0) * (47.0 - x0) / (x1 - x0), math.atan2(-(z1 - z0), x1 - x0))
        self.barn(-38.0, 142.0, math.radians(25), W=12.0, L=18.0, H=6.0, door_w=7.0, door_h=5.2,
                  wall=(0.55, 0.42, 0.3), name="Feldscheune", loft=True)
        for x, z in ((-31, 132), (-29.5, 134), (-32, 135.5), (-47, 150)):
            self.bale(x, z)

    def barn(self, cx, cz, yaw, W=11.0, L=14.0, H=5.4, door_w=6.2, door_h=4.8, roof_h=3.6,
             wall=(0.6, 0.17, 0.13), name="Scheune", loft=True):
        """Scheune mit offenen Schiebetoren vorne und hinten (lokal z = Durchflugrichtung)."""
        start = self.mark()
        dr = self.deco
        c, s = math.cos(yaw), math.sin(yaw)

        def w(lx, ly, lz):
            return (cx + c * lx + s * lz, ly, cz - s * lx + c * lz)

        def bx(lx, ly, lz, hx, hy, hz, col, mat=M_WOOD, collide=True):
            self.box(w(lx, ly, lz), (hx, hy, hz), yaw, col, mat, collide)
        t = 0.3
        trim, beam, door_col = (0.93, 0.91, 0.86), (0.42, 0.3, 0.2), tuple(v * 0.8 for v in wall)
        bx(0, 0.02, 0, W / 2, 0.02, L / 2, (0.45, 0.39, 0.3), M_WOOD, False)               # Bretterboden
        for sx in (-1, 1):                                                                  # Seitenwände
            bx(sx * (W / 2 - t / 2), H / 2, 0, t / 2, H / 2, L / 2, wall)
            bx(sx * (W / 2 + 0.02), 0.25, 0, 0.04, 0.25, L / 2, (0.5, 0.48, 0.45), M_PLAIN, False)
            for lz in np.arange(-L / 2 + 2.5, L / 2 - 1.5, 4.0):                            # Stallfenster
                bx(sx * (W / 2 + 0.03), H * 0.62, lz, 0.03, 0.45, 0.6, (0.12, 0.13, 0.15), M_PLAIN, False)
                bx(sx * (W / 2 + 0.05), H * 0.62, lz, 0.02, 0.55, 0.07, trim, M_PLAIN, False)
                bx(sx * (W / 2 + 0.05), H * 0.62, lz, 0.02, 0.07, 0.7, trim, M_PLAIN, False)
        side_w = (W - door_w) / 2
        for sz in (-1, 1):                                                                  # Giebelwände mit Tor
            for sx in (-1, 1):
                bx(sx * (door_w / 2 + side_w / 2), H / 2, sz * (L / 2 - t / 2), side_w / 2, H / 2, t / 2, wall)
            bx(0, (door_h + H) / 2, sz * (L / 2 - t / 2), door_w / 2, (H - door_h) / 2, t / 2, wall)
            z_out = sz * (L / 2 + 0.03)
            for sx in (-1, 1):                                                              # weißer Torrahmen
                bx(sx * (door_w / 2 + 0.1), door_h / 2, z_out, 0.1, door_h / 2, 0.03, trim, M_PLAIN, False)
            bx(0, door_h + 0.1, z_out, door_w / 2 + 0.2, 0.1, 0.03, trim, M_PLAIN, False)
            bx(0, door_h + 0.45, sz * (L / 2 + 0.14), door_w, 0.06, 0.05, (0.2, 0.2, 0.22), M_METAL, False)  # Laufschiene
            for sx in (-1, 1):                                                              # aufgeschobene Torflügel
                lx = sx * (door_w / 2 + door_w / 4 + 0.15)
                zz = sz * (L / 2 + 0.15)
                bx(lx, door_h / 2 + 0.05, zz, door_w / 4, door_h / 2, 0.06, door_col)
                zo = sz * (L / 2 + 0.22)
                for ly in (0.12, door_h - 0.05):
                    bx(lx, ly, zo, door_w / 4, 0.08, 0.02, trim, M_PLAIN, False)
                for ex in (-1, 1):
                    bx(lx + ex * (door_w / 4 - 0.08), door_h / 2, zo, 0.08, door_h / 2, 0.02, trim, M_PLAIN, False)
                for d in (-1, 1):                                                           # weißes X
                    self.limb(w(lx - door_w / 4 + 0.15, 0.25 if d > 0 else door_h - 0.15, zo),
                              w(lx + door_w / 4 - 0.15, door_h - 0.15 if d > 0 else 0.25, zo), 0.06, trim, sides=4)
            if dr.random() < 0.9:                                                           # Lampe überm Tor
                bx(0, door_h + 0.75, sz * (L / 2 + 0.25), 0.18, 0.1, 0.12, (1.0, 0.9, 0.65), M_LIGHT, False)

        def w2(a, ly, b):                       # Dach: First entlang lokal z (Giebel über den Toren)
            return w(b, ly, a)
        self.roof(w2, L / 2 + 0.5, W / 2 + 0.6, H - 0.1, roof_h, (0.33, 0.3, 0.3), wall, inset=0.5, full=True)
        for i in range(3):
            y0 = H + roof_h * i / 3
            hx = (W / 2) * (1 - (i + 0.5) / 3) + 0.3
            p = w(0, y0 + roof_h / 6, 0)
            self.boxes.append((p[0], p[1], p[2], hx, roof_h / 6, L / 2 + 0.3, yaw))
        bx(0, H - 0.1 + roof_h, 0, 0.14, 0.08, L / 2 + 0.55, (0.22, 0.2, 0.2), M_PLAIN, False)     # First
        # innen: Binderbalken, Pfosten, Lampen, Heuboden, Strohballen
        for lz in np.arange(-L / 2 + 3.5, L / 2 - 1.0, 3.5):
            bx(0, H - 0.25, lz, W / 2 - t, 0.14, 0.14, beam)
            for sx in (-1, 1):
                bx(sx * (W / 2 - t - 0.14), H / 2, lz, 0.14, H / 2, 0.14, beam)
                self.limb(w(sx * (W / 2 - t - 0.1), H - 0.4, lz), w(0, H - 0.25 + roof_h * 0.6, lz), 0.08, beam, sides=4)
            self.limb(w(0, H - 0.1, lz), w(0, H - 0.75, lz), 0.015, (0.1, 0.1, 0.1), sides=3)
            bx(0, H - 0.85, lz, 0.13, 0.1, 0.13, (1.0, 0.88, 0.6), M_LIGHT, False)
        if loft:
            lx0 = max(W / 2 - t - 2.4, door_w / 2 + 0.2)          # Heuboden auf einer Seite, 3 m hoch (Pfosten
                                                                   # nicht in der Torflucht)
            bx((lx0 + W / 2 - t) / 2, 3.0, 0, (W / 2 - t - lx0) / 2, 0.08, L / 2 - t, beam)
            for lz in np.arange(-L / 2 + 1.0, L / 2 - 0.9, 3.5):
                bx(lx0 + 0.12, 1.5, lz, 0.12, 1.5, 0.12, beam)
            for lz in np.arange(-L / 2 + 1.6, L / 2 - 1.5, 1.9):
                bx(lx0 + 1.4, 3.5, lz, 0.85, 0.42, 0.85, (0.84, 0.76, 0.5), M_PLAIN)
            self.limb(w(lx0 - 0.6, 0.0, -L / 2 + 2.2), w(lx0 - 0.05, 3.05, -L / 2 + 2.2), 0.05, beam, sides=4)  # Leiter
        for lz in (-L / 2 + 1.5, L / 2 - 2.2):                     # Strohballen auf der anderen Seite
            for ly in (0.45, 1.35):
                bx(-W / 2 + t + 0.75, ly, lz + (ly > 1) * 0.3, 0.6, 0.45, 0.9, (0.84, 0.76, 0.5), M_PLAIN)
        self._target(name, start)
        self.reserved.append((cx, cz, math.hypot(W, L) / 2 + 2.5))

    def hall(self, cx, cz, yaw, W=12.0, L=16.0, H=6.0, roof_h=1.6):
        """Maschinenhalle: Stahlstützen, Wellblechdach, offen an drei Seiten (lokal z = Durchflug)."""
        start = self.mark()
        c, s = math.cos(yaw), math.sin(yaw)

        def w(lx, ly, lz):
            return (cx + c * lx + s * lz, ly, cz - s * lx + c * lz)

        def bx(lx, ly, lz, hx, hy, hz, col, mat=M_PLAIN, collide=True):
            self.box(w(lx, ly, lz), (hx, hy, hz), yaw, col, mat, collide)
        # kein helles Grau: der Tor-Detektor zählt das neben Orange als weiße Streifen (Tor 10 steht davor)
        steel, sheet, conc = (0.3, 0.38, 0.5), (0.2, 0.33, 0.55), (0.34, 0.34, 0.35)
        bx(0, 0.03, 0, W / 2 + 0.5, 0.03, L / 2 + 0.5, conc, M_PLAIN, False)              # Betonplatte
        posts = np.linspace(-L / 2, L / 2, 5)
        for lz in posts:
            for sx in (-1, 1):
                bx(sx * W / 2, H / 2, lz, 0.16, H / 2, 0.16, steel)
            bx(0, H - 0.15, lz, W / 2, 0.15, 0.1, steel)                                    # Binder
            for sx in (-1, 1):
                self.limb(w(sx * W / 2, H - 0.3, lz), w(0, H + roof_h - 0.2, lz), 0.07, steel, sides=4)
                self.limb(w(sx * W / 4, H - 0.3, lz), w(sx * W / 4, H + roof_h / 2 - 0.15, lz), 0.05, steel, sides=4)
        for sx in (-1, 1):
            bx(sx * W / 2, H - 0.15, 0, 0.12, 0.15, L / 2 + 0.2, steel)                     # Traufbalken
        bx(-W / 2 - 0.1, H / 2, 0, 0.06, H / 2, L / 2, sheet, M_METAL)                     # Rückwand (Wellblech)
        for lz in posts[:-1] + 2.0:                                                        # Windverband (X)
            for d in (-1, 1):
                self.limb(w(-W / 2 + 0.05, 0.3 if d > 0 else H - 0.4, lz - 1.9),
                          w(-W / 2 + 0.05, H - 0.4 if d > 0 else 0.3, lz + 1.9), 0.03, steel, sides=4)

        def w2(a, ly, b):
            return w(b, ly, a)
        self.roof(w2, L / 2 + 0.6, W / 2 + 0.6, H, roof_h, (0.28, 0.3, 0.33), sheet, inset=0.6, full=True)
        for i in range(3):
            y0 = H + roof_h * i / 3
            hx = (W / 2) * (1 - (i + 0.5) / 3) + 0.4
            p = w(0, y0 + roof_h / 6, 0)
            self.boxes.append((p[0], p[1], p[2], hx, roof_h / 6, L / 2 + 0.4, yaw))
        # Inhalt an der Rückwand: Traktor, Paletten, Fässer
        self.tractor(w(-W / 2 + 1.4, 0, -L / 2 + 2.2), yaw, (0.2, 0.5, 0.22))   # ganz an die Wand, weg von der Linie
        for k, lz in enumerate((2.5, 4.0, 5.5)):
            for ly in range(3 - k):
                bx(-W / 2 + 1.0, 0.12 + 0.3 * ly, lz, 0.55, 0.12, 0.6, (0.62, 0.5, 0.33), M_WOOD)
        for k in range(4):
            p = w(-W / 2 + 0.7 + 0.65 * (k % 2), 0, -L / 2 + 1.0 + 0.7 * (k // 2))
            self.cylinder(p, 0.3, 0.9, [(0.15, 0.3, 0.6), (0.7, 0.15, 0.1)][k % 2], sides=10)
        self._target("Maschinenhalle", start)
        self.reserved.append((cx, cz, math.hypot(W, L) / 2 + 2.5))

    def tractor(self, p, yaw, col):
        c, s = math.cos(yaw), math.sin(yaw)
        cx, _, cz = p

        def w(lx, ly, lz):
            return (cx + c * lx + s * lz, ly, cz - s * lx + c * lz)

        def bx(lx, ly, lz, hx, hy, hz, cl, mat=M_PLAIN, collide=False):
            self.box(w(lx, ly, lz), (hx, hy, hz), yaw, cl, mat, collide)
        bx(0, 1.0, 0.9, 0.45, 0.4, 1.0, col)                                               # Motorhaube
        bx(0, 1.0, -0.7, 0.6, 0.5, 0.7, col)                                               # Rumpf
        bx(0, 2.05, -0.75, 0.62, 0.55, 0.65, (0.15, 0.2, 0.26))                            # Kabine (Glas)
        bx(0, 2.65, -0.75, 0.7, 0.05, 0.72, col)                                           # Dach
        bx(0.25, 1.75, 1.5, 0.05, 0.4, 0.05, (0.15, 0.15, 0.15))                           # Auspuff
        bx(0, 1.05, 1.92, 0.4, 0.3, 0.03, (0.85, 0.85, 0.8), M_LIGHT)
        for sx in (-1, 1):
            self.limb(w(sx * 0.6, 0.85, -0.9), w(sx * 1.05, 0.85, -0.9), 0.85, (0.1, 0.1, 0.1), sides=14, caps=True)
            self.limb(w(sx * 0.62, 0.86, -0.9), w(sx * 1.07, 0.86, -0.9), 0.45, (0.85, 0.75, 0.15), sides=10, caps=True)
            self.limb(w(sx * 0.42, 0.5, 1.3), w(sx * 0.72, 0.5, 1.3), 0.5, (0.1, 0.1, 0.1), sides=12, caps=True)
        q = w(0, 1.4, 0.1)
        self.boxes.append((q[0], q[1], q[2], 1.05, 1.4, 1.9, yaw))

    def footbridge(self, x, z, span=21.0, deck_y=6.4):
        """Fußgängerbrücke quer über die Hauptstraße (Straße läuft entlang z), mit Treppentürmen."""
        start = self.mark()
        conc, rail, steel = (0.72, 0.71, 0.68), (0.2, 0.35, 0.6), (0.3, 0.32, 0.35)
        self.box((x, deck_y, z), (span / 2, 0.22, 1.6), 0, conc)                           # Deck
        for dz in (-1.25, 1.25):
            self.box((x, deck_y - 0.45, z + dz), (span / 2 - 1.5, 0.25, 0.18), 0, steel)  # Träger
        for sz in (-1, 1):                                                                  # Geländer
            zz = z + sz * 1.52
            self.box((x, deck_y + 1.05, zz), (span / 2, 0.04, 0.04), 0, rail)
            for xx in np.arange(x - span / 2 + 0.3, x + span / 2, 1.2):
                self.box((xx, deck_y + 0.6, zz), (0.025, 0.42, 0.025), 0, steel, collide=False)
            self.boxes.append((x, deck_y + 0.6, zz, span / 2, 0.45, 0.05, 0.0))
        for sx in (-1, 1):                                                                  # Treppentürme
            tx = x + sx * (span / 2 - 1.3)
            self.box((tx, (deck_y + 3.2) / 2, z), (1.3, (deck_y + 3.2) / 2, 1.7), 0, (0.8, 0.78, 0.72), M_PLAIN)
            self.box((tx, deck_y + 3.3, z), (1.5, 0.12, 1.9), 0, (0.35, 0.36, 0.38))
            self.box((tx - sx * 1.31, 2.0, z), (0.02, 1.2, 0.6), 0, (0.15, 0.17, 0.2), collide=False)   # Tür
            for k in range(3):
                self.box((tx - sx * 1.31, deck_y + 1.6, z - 1.0 + k), (0.02, 0.5, 0.3), 0, (0.2, 0.3, 0.42),
                         collide=False)
        for dz in (-1.0, 1.0):                                                              # Lampen unterm Deck
            self.box((x, deck_y - 0.75, z + dz * 0.6), (0.3, 0.05, 0.12), 0, (1.0, 0.92, 0.7), M_LIGHT, collide=False)
        self._target("Brücke", start)
        self.reserved.append((x, z, span / 2 + 2.5))

    def gatehouse(self, x, z, yaw, along=4.5, across=6.6, tunnel=4.2, tunnel_h=5.6, top=9.4):
        """Torhaus über einer Straße (lokal x = Straßenrichtung): Durchfahrt wie ein kurzer Tunnel."""
        start = self.mark()
        stone, plaster, roof, trim = (0.74, 0.7, 0.62), (0.93, 0.88, 0.74), (0.58, 0.2, 0.18), (0.6, 0.56, 0.5)
        c, s = math.cos(yaw), math.sin(yaw)

        def w(lx, ly, lz):
            return (x + c * lx + s * lz, ly, z - s * lx + c * lz)

        def bx(lx, ly, lz, hx, hy, hz, col, mat=M_PLAIN, collide=True):
            self.box(w(lx, ly, lz), (hx, hy, hz), yaw, col, mat, collide)
        side = (across - tunnel) / 2
        for sz in (-1, 1):
            bx(0, tunnel_h / 2, sz * (tunnel + side), along, tunnel_h / 2, side, stone)
            bx(0, 0.6, sz * (tunnel + 0.06), along + 0.05, 0.6, 0.06, (0.55, 0.52, 0.46), collide=False)
        bx(0, (tunnel_h + top) / 2, 0, along, (top - tunnel_h) / 2, across, plaster, M_WALL)
        bx(0, tunnel_h + 0.1, 0, along + 0.08, 0.12, across + 0.08, stone, collide=False)          # Gesims
        for sx in (-1, 1):                                                                       # Torbogen-Rahmen
            for sz in (-1, 1):
                bx(sx * (along + 0.05), tunnel_h / 2, sz * (tunnel + 0.22), 0.06, tunnel_h / 2, 0.22, trim, collide=False)
            bx(sx * (along + 0.05), tunnel_h - 0.2, 0, 0.06, 0.22, tunnel, trim, collide=False)
        for k in (-2, 0, 2):                                                                     # Lampen in der Durchfahrt
            bx(k, tunnel_h - 0.08, 0, 0.25, 0.05, 0.25, (1.0, 0.92, 0.7), M_LIGHT, collide=False)

        def w2(a, ly, b):                       # Satteldach, First quer zur Straße
            return w(b, ly, a)
        self.roof(w2, across + 0.4, along + 0.5, top - 0.1, 3.2, roof, plaster, inset=0.5, full=True)
        for i in range(3):
            y0 = top + 3.2 * i / 3
            p = w(0, y0 + 3.2 / 6, 0)
            self.boxes.append((p[0], p[1], p[2], along * (1 - (i + 0.5) / 3) + 0.4, 3.2 / 6, across + 0.4, yaw))
        bx(0, top + 3.6, 0, 0.8, 1.1, 0.8, plaster)                                              # Türmchen mit Uhr
        self.cone(w(0, top + 4.7, 0), 1.15, 2.4, (0.25, 0.4, 0.33), sides=8)
        for sx in (-1, 1):
            self.limb(w(sx * 0.8, top + 3.7, 0), w(sx * 0.86, top + 3.7, 0), 0.55, (0.95, 0.95, 0.9), 16, caps=True)
            bx(sx * 0.87, top + 3.85, 0, 0.01, 0.25, 0.03, (0.1, 0.1, 0.1), collide=False)
            bx(sx * 0.87, top + 3.7, 0.15, 0.01, 0.03, 0.18, (0.1, 0.1, 0.1), collide=False)
        self._target("Torhaus", start)
        self.reserved.append((x, z, across + 3.0))

    def _fields(self):
        """Äcker und Wiesen-Streifen rund ums Dorf, ein paar Steine."""
        dr = self.deco
        kinds = [(0.42, 0.36, 0.3), (0.82, 0.7, 0.32), (0.36, 0.55, 0.18), (0.9, 0.82, 0.18), (0.5, 0.42, 0.26)]
        placed, tries = 0, 0
        while placed < 9 and tries < 300:
            tries += 1
            a = dr.uniform(0, 2 * math.pi)
            r = dr.uniform(150, 240)
            cx, cz = 50 + r * math.cos(a), 80 + r * math.sin(a)
            hx, hz = dr.uniform(14, 26), dr.uniform(9, 18)
            rad = math.hypot(hx, hz)
            if self.course_dist(cx, cz) < rad + 10 or self.road_dist(cx, cz) < rad + 4 \
                    or not self.unreserved(cx, cz, rad) or self.hit((cx, 1.0, cz), rad * 0.8, all_boxes=True):
                continue
            yaw = dr.uniform(0, math.pi)
            self.box((cx, 0.012, cz), (hx, 0.012, hz), yaw, kinds[placed % len(kinds)], M_FIELD, collide=False)
            if placed % len(kinds) == 1:                                   # abgeerntet: Strohballen
                c, s = math.cos(yaw), math.sin(yaw)
                for _ in range(dr.integers(3, 7)):
                    lx, lz = dr.uniform(-hx + 2, hx - 2), dr.uniform(-hz + 2, hz - 2)
                    self.bale(cx + c * lx + s * lz, cz - s * lx + c * lz)
            self.reserved.append((cx, cz, rad))
            placed += 1
        for _ in range(40):                                                # Feldsteine
            x, z = dr.uniform(-80, 200), dr.uniform(-60, 240)
            if self.road_dist(x, z) > 3 and self.course_dist(x, z) > 4 and self.unreserved(x, z, 1.0):
                sc = dr.uniform(0.3, 0.8)
                m = self.mark()
                self.blob((x, sc * 0.3, z), (sc * 1.2, sc * 0.6, sc), (0.5, 0.5, 0.48), collide=sc > 0.5, mat=M_PLAIN)
                self._deco(m, x, z, sc * 1.4, sc * 0.8)

    # ------------------------------------------------------------ Bauteile

    def gate(self, g, mat):
        t, w, h = GATE_T, GATE_W, GATE_H
        c, s = math.cos(g.yaw), math.sin(g.yaw)

        def at(lx, ly, hx, hy, hz, m=mat, col=(1.0, 0.5, 0.1), lz=0.0, collide=True):
            self.box((g.x + c * lx + s * lz, ly, g.z - s * lx + c * lz), (hx, hy, hz), g.yaw, col, m, collide)
        at(-(w / 2 + t / 2), g.lift + h / 2, t / 2, h / 2 + t, t / 2)
        at(w / 2 + t / 2, g.lift + h / 2, t / 2, h / 2 + t, t / 2)
        at(0, g.lift + h + t / 2, w / 2 + t, t / 2, t / 2)
        at(0, g.lift - t / 2, w / 2 + t, t / 2, t / 2)
        steel, dark = (0.32, 0.33, 0.35), (0.16, 0.16, 0.18)
        for side in (-1, 1):
            x = side * (w / 2 + t / 2)
            if g.lift > 0.3:                                       # Ständer mit Fußplatte und Strebe
                at(x, (g.lift - t) / 2, 0.08, (g.lift - t) / 2, 0.08, M_PLAIN, steel)
                at(x, 0.03, 0.45, 0.03, 0.55, M_PLAIN, dark, collide=False)
                for lz in (-0.5, 0.5):
                    self.limb((g.x + c * x + s * lz, 0.06, g.z - s * x + c * lz),
                              (g.x + c * x, g.lift * 0.5, g.z - s * x), 0.035, steel)
            else:                                                  # Füße (keine Sandsäcke: die verdecken die
                at(x, 0.05, 0.15, 0.05, 0.6, M_PLAIN, dark)        # Rahmenecken, der Kamera-Pilot braucht den Ring)
                for lz in (-0.6, 0.6):
                    at(x, 0.06, 0.19, 0.06, 0.08, M_PLAIN, steel, lz=lz, collide=False)

    def gate_kind(self, g, mat, accent):
        """Tor einer Strecke (tracks.py): Rahmen orange/weiß (Shader, Material M_GATE + i), Füße und
        Ständer in der Schwierigkeitsfarbe. Mehrere Öffnungen übereinander teilen sich die Holme."""
        if g.pole is not None:
            return self._flag(g, mat, accent)
        if g.roll:
            return self._tilted(g, mat, accent)
        t, w, h = GATE_T, g.w, g.h
        c, s = math.cos(g.yaw), math.sin(g.yaw)

        def at(lx, ly, hx, hy, hz, m=mat, col=(1.0, 0.5, 0.1), lz=0.0, collide=True):
            self.box((g.x + c * lx + s * lz, ly, g.z - s * lx + c * lz), (hx, hy, hz), g.yaw, col, m, collide)
        inner = g.n_open * h + (g.n_open - 1) * t
        for side in (-1, 1):
            at(side * (w / 2 + t / 2), g.lift + inner / 2, t / 2, inner / 2 + t, t / 2)
        for k in range(g.n_open + 1):
            at(0, g.lift - t / 2 + k * (h + t), w / 2 + t, t / 2, t / 2)
        if g.n_open > 1 and g.level is not None:              # zählende Öffnung: Pfeile in Streckenfarbe
            y = g.open_y(g.level)
            for side in (-1, 1):
                at(side * (w / 2 + t + 0.1), y, 0.1, h * 0.32, 0.14, M_PLAIN, accent, collide=False)
        self._stands(g, [(side * (w / 2 + t / 2), 0.0) for side in (-1, 1)], g.lift - t, accent)

    def _stands(self, g, feet, top, accent):
        """Ständer vom Boden (oder Dach) bis `top` an den Stellen feet (quer, längs)."""
        c, s = math.cos(g.yaw), math.sin(g.yaw)
        dark = tuple(v * 0.5 for v in accent)
        for lx, lz0 in feet:
            px, pz = g.x + c * lx + s * lz0, g.z - s * lx + c * lz0
            hgt = top - g.base
            if hgt > 0.3:
                self.box((px, g.base + hgt / 2, pz), (0.08, hgt / 2, 0.08), g.yaw, accent)
                spread = 0.5 + 0.04 * hgt
                self.box((px, g.base + 0.03, pz), (0.45, 0.03, spread + 0.05), g.yaw, dark, collide=False)
                for lz in (-spread, spread):
                    self.limb((px + s * lz, g.base + 0.06, pz + c * lz), (px, g.base + min(hgt * 0.5, 4.0), pz),
                              0.035, accent)
            else:
                self.box((px, g.base + 0.05, pz), (0.15, 0.05, 0.6), g.yaw, accent)

    def obox(self, center, axes, half, col, mat):
        """Quader mit beliebiger Lage (axes: drei Einheitsvektoren), uv in Metern. Ohne Kollision."""
        C = np.asarray(center, float)
        A = [np.asarray(a, float) for a in axes]
        for i in range(3):
            j, k = (i + 1) % 3, (i + 2) % 3
            for sg in (-1, 1):
                n = A[i] * sg
                ctr = C + n * half[i]
                pts = [ctr + A[j] * su * half[j] + A[k] * sv * half[k] for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                if sg < 0:
                    pts = pts[::-1]
                uv = [(float(np.dot(p, A[j]) + np.dot(p, A[k])), float(np.dot(p, A[k]) - np.dot(p, A[j]))) for p in pts]
                self.quad(*[tuple(p) for p in pts], tuple(n), col, uv, mat)

    def _tilted(self, g, mat, accent):
        """Schräges Tor: Rahmen um die Flugachse gedreht. Kollision: kleine Würfel entlang der Holme."""
        t, w, h = GATE_T, g.w, g.h
        c, s = math.cos(g.yaw), math.sin(g.yaw)
        Q, F, Y = np.array((c, 0.0, -s)), np.array((s, 0.0, c)), np.array((0.0, 1.0, 0.0))
        cr, sr = math.cos(g.roll), math.sin(g.roll)
        U, V = cr * Q + sr * Y, -sr * Q + cr * Y
        C = np.array((g.x, g.open_y(0), g.z))
        bars = [(C + U * sd * (w / 2 + t / 2), (U, V, F), (t / 2, h / 2 + t, t / 2)) for sd in (-1, 1)] + \
               [(C + V * sd * (h / 2 + t / 2), (U, V, F), (w / 2 + t, t / 2, t / 2)) for sd in (-1, 1)]
        for ctr, axes, half in bars:
            self.obox(ctr, axes, half, (1.0, 0.5, 0.1), mat)
            long = int(np.argmax(half))
            L = half[long]
            for a in np.arange(-L + 0.1, L, 0.2):
                p = ctr + axes[long] * a
                self.boxes.append((p[0], p[1], p[2], t / 2 + 0.02, t / 2 + 0.02, t / 2 + 0.02, g.yaw))
        b = C - V * (h / 2 + t)                             # Ständer unter die Mitte des unteren Holms
        lq = float(np.dot(b - C, Q))
        self._stands(g, [(lq, 0.0)], float(b[1]), accent)

    def _flag(self, g, mat, accent):
        """Flagge zum Umfliegen: Stange mit Fahnentuch (Tor-Material: leuchtet als nächstes Tor),
        gezählt wird das Fenster neben der Stange (innen in der Kurve)."""
        px, pz = g.pole
        c, s = math.cos(g.yaw), math.sin(g.yaw)
        side = 1.0 if (c * (px - g.x) - s * (pz - g.z)) > 0 else -1.0
        top = g.h + 0.6
        self.cylinder((px, 0, pz), 0.06, top, (0.88, 0.88, 0.9), sides=8)
        ox = side * 0.5
        self.box((px + c * ox, (1.4 + top) / 2, pz - s * ox), (0.44, (top - 1.4) / 2, 0.03), g.yaw,
                 (1.0, 0.5, 0.1), mat)
        self.box((px + c * (ox + side * 0.47), (1.4 + top) / 2, pz - s * (ox + side * 0.47)),
                 (0.05, (top - 1.4) / 2, 0.035), g.yaw, accent, collide=False)
        self.box((px, 0.04, pz), (0.5, 0.04, 0.5), g.yaw, tuple(v * 0.5 for v in accent), collide=False)

    def container(self, center, yaw, col):
        start = self.mark()
        self._container(center, yaw, col)
        self._target("Container", start)

    def _container(self, center, yaw, col):
        self.box(center, (1.22, 1.3, 3.05), yaw, col, M_PLAIN)
        cx, cy, cz = center
        c, s = math.cos(yaw), math.sin(yaw)
        for k in range(-5, 6):                                     # Rippen
            lz = k * 0.55
            self.box((cx + s * lz, cy, cz + c * lz), (1.25, 1.22, 0.04), yaw,
                     tuple(v * 0.85 for v in col), M_PLAIN, collide=False)

    def house(self, cx, cz, yaw, width, depth, wall_h, roof_h, wall, roof, flat=False, windows=True,
              door_side=None, name=None, yard=None):
        start = self.mark()
        self._house(cx, cz, yaw, width, depth, wall_h, roof_h, wall, roof, flat, windows, door_side, yard)
        self._target(name or ("Wohnblock" if flat else "Haus"), start)

    def _house(self, cx, cz, yaw, width, depth, wall_h, roof_h, wall, roof, flat, windows, door_side, yard=None):
        dr = self.deco
        self.box((cx, wall_h / 2, cz), (width / 2, wall_h / 2, depth / 2), yaw, wall, M_WALL if windows else M_PLAIN)
        c, s = math.cos(yaw), math.sin(yaw)

        def w(lx, ly, lz):
            return (cx + c * lx + s * lz, ly, cz - s * lx + c * lz)

        def deco(lx, ly, lz, hx, hy, hz, col, mat=M_PLAIN, collide=False):
            self.box(w(lx, ly, lz), (hx, hy, hz), yaw, col, mat, collide)
        deco(0, 0.28, 0, width / 2 + 0.06, 0.28, depth / 2 + 0.06, (0.52, 0.5, 0.47))        # Sockel
        if flat or roof_h <= 0:
            self.box((cx, wall_h + 0.2, cz), (width / 2 + 0.2, 0.2, depth / 2 + 0.2), yaw, roof)
            for sx, sz, hx, hz in ((1, 0, 0.12, depth / 2 + 0.2), (-1, 0, 0.12, depth / 2 + 0.2),
                                   (0, 1, width / 2 + 0.2, 0.12), (0, -1, width / 2 + 0.2, 0.12)):     # Attika
                deco(sx * (width / 2 + 0.08), wall_h + 0.55, sz * (depth / 2 + 0.08), hx, 0.18, hz, (0.62, 0.62, 0.6))
            for _ in range(dr.integers(1, 4)):                     # Lüftung / Klimagerät am Dach
                lx, lz = dr.uniform(-width / 3, width / 3), dr.uniform(-depth / 3, depth / 3)
                deco(lx, wall_h + 0.75, lz, 0.5, 0.35, 0.4, (0.72, 0.73, 0.75), M_METAL, collide=True)
        else:
            self.roof(w, width / 2 + 0.35, depth / 2 + 0.5, wall_h - 0.15, roof_h, roof, wall)
            for i in range(3):                                     # Kollision: gestufte Boxen
                y0 = wall_h + roof_h * i / 3
                hz = depth / 2 * (1 - (i + 0.5) / 3) + 0.3
                self.boxes.append((cx, y0 + roof_h / 6, cz, width / 2 + 0.3, roof_h / 6, hz, yaw))
            dark = tuple(v * 0.7 for v in roof)
            deco(0, wall_h - 0.15 + roof_h, 0, width / 2 + 0.38, 0.08, 0.13, dark)          # First
            for sz in (-1, 1):                                                              # Dachrinnen
                deco(0, wall_h - 0.2, sz * (depth / 2 + 0.5), width / 2 + 0.35, 0.06, 0.06, (0.55, 0.55, 0.57), M_METAL)
            if self.rng.random() < 0.7:                            # Kamin
                lx = self.rng.uniform(-width / 3, width / 3)
                p = w(lx, 0, depth / 6)
                self.box((p[0], wall_h + roof_h * 0.75, p[2]), (0.35, roof_h * 0.45, 0.35), yaw, (0.5, 0.3, 0.3))
                self.box((p[0], wall_h + roof_h * 1.2 + 0.05, p[2]), (0.45, 0.06, 0.45), yaw, (0.35, 0.33, 0.32),
                         collide=False)
        door = None
        if door_side is not None:                                  # Tür zur Straße
            sign = 1 if (s * door_side[0] + c * door_side[1]) > 0 else -1
            dl = self.rng.uniform(-width / 4, width / 4)
            door = (sign, dl)
            dz = sign * (depth / 2 + 0.02)
            p = w(dl, 0, dz)
            self.box((p[0], 1.05, p[2]), (0.5, 1.05, 0.06), yaw, [(0.3, 0.2, 0.18), (0.2, 0.3, 0.45), (0.22, 0.35, 0.25)][self.deco.integers(3)], collide=False)
            deco(dl, 1.12, dz, 0.62, 1.14, 0.04, (0.92, 0.91, 0.88))                      # Türrahmen
            deco(dl, 2.45, sign * (depth / 2 + 0.45), 0.85, 0.05, 0.45, (0.3, 0.3, 0.32))   # Vordach
            deco(dl, 0.08, sign * (depth / 2 + 0.4), 0.75, 0.08, 0.38, (0.6, 0.6, 0.6))      # Stufe
            deco(dl + 0.3, 1.0, sign * (depth / 2 + 0.1), 0.04, 0.04, 0.04, (0.85, 0.75, 0.3))  # Klinke
        if windows:
            self._window_trim(w, yaw, width, depth, wall_h, flat, door)
        if door is not None and yard is not None and yard > 1.2 and dr.random() < 0.65:
            fz = door[0] * (depth / 2 + yard - 0.25)
            hedge = dr.random() < 0.4
            for x0, x1 in ((-width / 2 - 1.0, door[1] - 0.8), (door[1] + 0.8, width / 2 + 1.0)):
                if x1 - x0 < 0.5:
                    continue
                if hedge:
                    deco((x0 + x1) / 2, 0.5, fz, (x1 - x0) / 2, 0.5, 0.35, (0.2, 0.42, 0.17), M_LEAF, collide=True)
                else:
                    self._fence(w, yaw, x0, x1, fz)
        if not flat and windows and door is not None and wall_h > 6 and dr.random() < 0.4:  # Balkon im 1. Stock
            sign = door[0]
            bl = -door[1] * 0.6
            deco(bl, 3.05, sign * (depth / 2 + 0.65), 1.3, 0.08, 0.65, (0.75, 0.75, 0.74), collide=True)
            deco(bl, 3.6, sign * (depth / 2 + 1.27), 1.3, 0.45, 0.03, (0.25, 0.25, 0.27), M_METAL, collide=True)
            for sx in (-1, 1):
                deco(bl + sx * 1.27, 3.6, sign * (depth / 2 + 0.65), 0.03, 0.45, 0.62, (0.25, 0.25, 0.27), M_METAL)

    def _window_trim(self, w, yaw, width, depth, wall_h, flat, door):
        """Fensterbänke (und bei manchen Häusern Fensterläden) genau unter den Shader-Fenstern."""
        dr = self.deco
        floors = int((wall_h + 0.05) // 3)
        shutters = (not flat) and dr.random() < 0.55
        shut_col = [(0.18, 0.35, 0.22), (0.3, 0.32, 0.36), (0.2, 0.3, 0.5), (0.85, 0.85, 0.82)][dr.integers(4)]   # kein Orange/Braun: das hielte der Kamera-Pilot für Torrahmen
        sill = (0.88, 0.87, 0.83)
        for face in ("x", "z"):
            half_len = depth / 2 if face == "x" else width / 2
            out = width / 2 if face == "x" else depth / 2
            k = 0
            while 2.6 * k + 1.85 <= 2 * half_len:
                t = 2.6 * k + 1.3 - half_len                       # Fenstermitte entlang der Wand
                for sign in (-1, 1):
                    for f in range(floors):
                        if f == 0 and door is not None and face == "z" and sign == door[0] and abs(t - door[1]) < 1.5:
                            continue
                        y = 3 * f + 0.86

                        def put(along, ly, ha, hy, off, col):
                            if face == "x":
                                self.box(w(sign * (out + off), ly, along), (off, hy, ha), yaw, col, collide=False)
                            else:
                                self.box(w(along, ly, sign * (out + off)), (ha, hy, off), yaw, col, collide=False)
                        put(t, y, 0.64, 0.045, 0.09, sill)
                        if shutters:
                            for side in (-1, 1):
                                put(t + side * 0.8, 3 * f + 1.65, 0.26, 0.74, 0.04, shut_col)
                k += 1

    def _fence(self, w, yaw, x0, x1, lz, h=0.85, col=(0.93, 0.92, 0.88)):
        """Gartenzaun entlang lokal x (Latten sichtbar, eine Kollisionsbox)."""
        n = max(2, int((x1 - x0) / 0.35))
        for i in range(n + 1):
            lx = x0 + (x1 - x0) * i / n
            self.box(w(lx, h / 2, lz), (0.04, h / 2, 0.03), yaw, col, collide=False)
        for y in (0.3, h - 0.15):
            self.box(w((x0 + x1) / 2, y, lz - 0.05), ((x1 - x0) / 2, 0.04, 0.02), yaw, col, collide=False)
        p = w((x0 + x1) / 2, h / 2, lz)
        self.boxes.append((p[0], p[1], p[2], (x1 - x0) / 2, h / 2, 0.06, yaw))

    def roof(self, w, hx, hz, base, h, col, gable_col, inset=0.3, full=False):
        """Satteldach, First entlang lokal x. full: Giebel schließt dicht ans Dach (Hallen, von innen sichtbar)."""
        for side in (-1, 1):
            a, b = w(-hx, base, side * hz), w(hx, base, side * hz)
            cc, d = w(hx, base + h, 0), w(-hx, base + h, 0)
            n = self._normal(a, b, cc, up=True)
            slope = math.hypot(hz, h)
            self.quad(a, b, cc, d, n, col, ((0, 0), (2 * hx, 0), (2 * hx, slope), (0, slope)), M_ROOF)
        for side in (-1, 1):
            gz, gh = (hz, h) if full else (hz - 0.5, h - 0.3)
            a, b, cc = w(side * (hx - inset), base, -gz), w(side * (hx - inset), base, gz), \
                w(side * (hx - inset), base + gh, 0)
            n = self._normal(a, b, cc)
            n = n if (n[0] * (cc[0] - w(0, 0, 0)[0]) + n[2] * (cc[2] - w(0, 0, 0)[2])) > 0 else tuple(-v for v in n)
            self.tri(a, b, cc, n, gable_col, M_PLAIN)

    def lamp(self, x, z):
        self.cylinder((x, 0, z), 0.08, 5.0, (0.25, 0.26, 0.28), sides=6)
        self.box((x - 0.6, 5.0, z), (0.7, 0.06, 0.12), 0, (0.25, 0.26, 0.28))
        self.box((x - 1.2, 4.9, z), (0.2, 0.08, 0.15), 0, (0.95, 0.92, 0.75), collide=False)

    def pine(self, x, z, h):
        rng, dr = self.rng, self.deco
        self.cylinder((x, 0, z), 0.18 + h * 0.01, h * 0.35, (0.38, 0.26, 0.16), sides=6)
        green = (0.12, rng.uniform(0.30, 0.40), 0.16)
        r = h * 0.3
        tiers = 4
        for i in range(tiers):
            y0 = h * (0.2 + 0.17 * i)
            rr = r * (1 - 0.2 * i) * dr.uniform(0.92, 1.08)
            self.cone((x + dr.uniform(-0.1, 0.1), y0, z + dr.uniform(-0.1, 0.1)), rr, h * 0.36,
                      tuple(c * (0.85 + 0.1 * i) for c in green), sides=9, mat=M_LEAF)
            self.boxes.append((x, y0 + h * 0.09, z, rr * 0.6, h * 0.09, rr * 0.6, 0.0))
        self.boxes.append((x, h * 0.18, z, 0.2, h * 0.18, 0.2, 0.0))

    def leafy(self, x, z, h):
        rng, dr = self.rng, self.deco
        kind = dr.choice(["oak", "oak", "oak", "birch", "copper", "round"], p=[.25, .2, .15, .15, .1, .15])
        green = (rng.uniform(0.18, 0.3), rng.uniform(0.42, 0.55), 0.15)
        r = h * 0.3
        if kind == "birch":                                        # Birke: weißer Stamm, schmale helle Krone
            self.cylinder((x, 0, z), 0.13, h * 0.7, (0.88, 0.87, 0.82), sides=6)
            for y in dr.uniform(0.4, h * 0.6, 4):
                self.cylinder((x, y, z), 0.14, 0.09, (0.15, 0.14, 0.12), sides=6, collide=False)
            self.boxes.append((x, h * 0.3, z, 0.15, h * 0.3, 0.15, 0.0))
            light = (0.42, 0.6, 0.22)
            for i in range(3):
                self.blob((x + dr.uniform(-0.3, 0.3), h * (0.55 + 0.15 * i), z + dr.uniform(-0.3, 0.3)),
                          (r * 0.55, r * 0.75, r * 0.55), tuple(c * dr.uniform(0.92, 1.08) for c in light),
                          collide=(i == 1))
            return
        if kind == "copper":
            green = (0.42, 0.18, 0.16)                             # Blutbuche
        elif kind == "round":
            green = (0.3, 0.55, 0.2)
        trunk = (0.40, 0.28, 0.17)
        self.cylinder((x, 0, z), 0.22, h * 0.55, trunk, sides=7)
        self.boxes.append((x, h * 0.27, z, 0.22, h * 0.27, 0.22, 0.0))
        self.blob((x, h * 0.65, z), (r, r * 0.85, r), green)
        for _ in range(2):
            ox, oz = rng.uniform(-r * 0.6, r * 0.6, 2)
            self.blob((x + ox, h * 0.62 + rng.uniform(-0.5, 1.0), z + oz), (r * 0.7,) * 3,
                      tuple(c * rng.uniform(0.9, 1.1) for c in green), collide=False)
        for k in range(dr.integers(2, 4)):                         # Äste und kleine Kronenteile
            a = dr.uniform(0, 2 * math.pi)
            tip = (x + math.cos(a) * r * 0.8, h * dr.uniform(0.5, 0.62), z + math.sin(a) * r * 0.8)
            self.limb((x, h * 0.38, z), tip, 0.07, trunk)
            if kind != "round":
                self.blob((tip[0], tip[1] + 0.3, tip[2]), (r * 0.45,) * 3,
                          tuple(cc * dr.uniform(0.85, 1.12) for cc in green), collide=False)

    def bale(self, x, z, r=0.75, col=(0.84, 0.76, 0.5)):
        """Runder Strohballen (stehend)."""
        self.cylinder((x, 0, z), r, 1.2, col, sides=12)
        self.cylinder((x, 1.2, z), r * 0.75, 0.02, tuple(v * 0.8 for v in col), sides=12, collide=False)

    # ------------------------------------------------------------ Primitive

    def vert(self, p, n, col, uv, mat):
        self.v.append((p[0], p[1], p[2], n[0], n[1], n[2], col[0], col[1], col[2], uv[0], uv[1], float(mat)))

    def tri(self, a, b, c, n, col, mat, uv=((0, 0), (0, 0), (0, 0))):
        for p, t in zip((a, b, c), uv):
            self.vert(p, n, col, t, mat)

    def quad(self, a, b, c, d, n, col, uv, mat):
        for i in (0, 1, 2, 0, 2, 3):
            self.vert((a, b, c, d)[i], n, col, uv[i], mat)

    @staticmethod
    def _normal(a, b, c, up=False):
        u = np.subtract(b, a)
        v = np.subtract(c, a)
        n = np.cross(u, v)
        n = n / (np.linalg.norm(n) + 1e-12)
        if up and n[1] < 0:
            n = -n
        return tuple(n)

    def box(self, center, half, yaw, col, mat=M_PLAIN, collide=True):
        cx, cy, cz = center
        hx, hy, hz = half
        c, s = math.cos(yaw), math.sin(yaw)

        def w(lx, ly, lz):
            return (cx + c * lx + s * lz, cy + ly, cz - s * lx + c * lz)

        def rot(n):
            return (c * n[0] + s * n[2], n[1], -s * n[0] + c * n[2])
        # (Normale, u-Achse, v-Achse); Seiten: u waagrecht, v = Höhe
        for nrm, ua, va in (((1, 0, 0), (0, 0, 1), (0, 1, 0)), ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
                            ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 0, -1), (1, 0, 0), (0, 1, 0)),
                            ((0, 1, 0), (1, 0, 0), (0, 0, 1)), ((0, -1, 0), (1, 0, 0), (0, 0, 1))):
            ctr = [nrm[i] * half[i] for i in range(3)]
            hu = sum(abs(ua[i]) * half[i] for i in range(3))
            hv = sum(abs(va[i]) * half[i] for i in range(3))
            pts, uvs = [], []
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                pts.append(w(*[ctr[i] + su * ua[i] * half[i] + sv * va[i] * half[i] for i in range(3)]))
                if nrm[1] == 0:
                    uvs.append(((su + 1) * hu, cy + sv * hv))          # Wand: u ab Kante, v = Welthöhe
                else:
                    uvs.append((su * hu, sv * hv))                     # Deckel: zentriert
            if nrm[1] < 0 and cy - hy < 0.05:
                continue                                               # Unterseite am Boden sieht keiner
            self.quad(*pts, rot(nrm), col, uvs, mat)
        if collide:
            self.boxes.append((cx, cy, cz, hx, hy, hz, yaw))

    def limb(self, a, b, r, col, sides=6, mat=M_PLAIN, caps=False):
        """Prisma von a nach b (Äste, Streben, liegende Räder mit caps=True). Keine Kollision."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        d = b - a
        L = np.linalg.norm(d)
        if L < 1e-6:
            return
        n = d / L
        helper = np.array((0.0, 1.0, 0.0)) if abs(n[1]) < 0.9 else np.array((1.0, 0.0, 0.0))
        u = np.cross(n, helper)
        u /= np.linalg.norm(u)
        v = np.cross(n, u)
        ring = [r * (math.cos(2 * math.pi * i / sides) * u + math.sin(2 * math.pi * i / sides) * v)
                for i in range(sides + 1)]
        for i in range(sides):
            m = (ring[i] + ring[i + 1]) / 2
            nm = tuple(m / np.linalg.norm(m))
            self.quad(tuple(a + ring[i]), tuple(a + ring[i + 1]), tuple(b + ring[i + 1]), tuple(b + ring[i]),
                      nm, col, ((0, 0), (0, 0), (0, 0), (0, 0)), mat)
            if caps:
                self.tri(tuple(a + ring[i]), tuple(a + ring[i + 1]), tuple(a), tuple(-n), col, mat)
                self.tri(tuple(b + ring[i]), tuple(b + ring[i + 1]), tuple(b), tuple(n), col, mat)

    def cylinder(self, base, r, h, col, sides=8, mat=M_PLAIN, collide=True):
        x, y, z = base
        ring = [(x + r * math.cos(2 * math.pi * i / sides), z + r * math.sin(2 * math.pi * i / sides))
                for i in range(sides + 1)]
        for i in range(sides):
            (ax, az), (bx, bz) = ring[i], ring[i + 1]
            a_mid = 2 * math.pi * (i + 0.5) / sides
            n = (math.cos(a_mid), 0, math.sin(a_mid))
            self.quad((ax, y, az), (bx, y, bz), (bx, y + h, bz), (ax, y + h, az), n, col,
                      ((0, y), (1, y), (1, y + h), (0, y + h)), mat)
            self.tri((ax, y + h, az), (bx, y + h, bz), (x, y + h, z), (0, 1, 0), col, mat)
        if collide:
            self.boxes.append((x, y + h / 2, z, r * 0.9, h / 2, r * 0.9, 0.0))

    def cone(self, base, r, h, col, sides=8, mat=M_PLAIN):
        x, y, z = base
        top = (x, y + h, z)
        for i in range(sides):
            a0, a1 = 2 * math.pi * i / sides, 2 * math.pi * (i + 1) / sides
            a = (x + r * math.cos(a0), y, z + r * math.sin(a0))
            b = (x + r * math.cos(a1), y, z + r * math.sin(a1))
            am = (a0 + a1) / 2
            n = np.array((math.cos(am) * h, r, math.sin(am) * h))
            n = tuple(n / np.linalg.norm(n))
            shade = 0.92 + 0.16 * self.deco.random()
            self.tri(a, b, top, n, tuple(c * shade for c in col), mat)
            self.tri(a, b, (x, y, z), (0, -1, 0), tuple(c * 0.6 for c in col), mat)

    _ICO = None

    def blob(self, center, scale, col, collide=True, mat=M_LEAF):
        """Low-Poly-Kugel (Ikosaeder, einmal unterteilt, leicht verbeult)."""
        if World._ICO is None:
            t = (1 + 5 ** 0.5) / 2
            vs = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
                  (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
            fs = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
                  (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
                  (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
            vs = [np.array(v) / np.linalg.norm(v) for v in vs]
            out = []
            for a, b, c in fs:
                ab, bc, ca = [(vs[i] + vs[j]) / np.linalg.norm(vs[i] + vs[j]) for i, j in ((a, b), (b, c), (c, a))]
                out += [(vs[a], ab, ca), (ab, vs[b], bc), (ca, bc, vs[c]), (ab, bc, ca)]
            World._ICO = out
        cx, cy, cz = center
        sx, sy, sz = scale
        jit = {}
        for tri in World._ICO:
            pts = []
            for v in tri:
                key = tuple(np.round(v, 4))
                if key not in jit:
                    jit[key] = 1 + self.deco.uniform(-0.12, 0.12)
                k = jit[key]
                pts.append((cx + v[0] * sx * k, cy + v[1] * sy * k, cz + v[2] * sz * k))
            n = self._normal(*pts)
            if np.dot(n, np.subtract(pts[0], center)) < 0:
                n = tuple(-v for v in n)
            shade = 0.9 + 0.2 * self.deco.random()
            self.tri(*pts, n, tuple(c * shade for c in col), mat)
        if collide:
            self.boxes.append((cx, cy, cz, sx * 0.75, sy * 0.75, sz * 0.75, 0.0))

    # ------------------------------------------------------------ Kollision

    def focus(self, p, r=40.0):
        """Nur Boxen in der Nähe prüfen (einmal pro Frame aufrufen)."""
        d = np.hypot(self.bc[:, 0] - p[0], self.bc[:, 2] - p[2])
        self.near = np.nonzero((d < r + self.brad) & self.alive)[0]

    def hit_index(self, p, r=RADIUS):
        """Index der getroffenen Box oder -1."""
        i = self.near
        if len(i) == 0:
            return -1
        d = np.asarray(p, dtype="f8") - self.bc[i]
        cs, sn = self.bcos[i], self.bsin[i]
        lx = cs * d[:, 0] - sn * d[:, 2]
        lz = sn * d[:, 0] + cs * d[:, 2]
        q = np.maximum(np.abs(np.stack((lx, d[:, 1], lz), axis=1)) - self.bh[i], 0.0)
        h = np.nonzero(np.einsum("ij,ij->i", q, q) < r * r)[0]
        return int(i[h[0]]) if len(h) else -1

    def hit(self, p, r=RADIUS, all_boxes=False):
        if all_boxes:
            if not self.boxes:
                return False
            b = np.array(self.boxes, dtype="f8")
            bc, bh, cs, sn = b[:, 0:3], b[:, 3:6], np.cos(b[:, 6]), np.sin(b[:, 6])
        else:
            i = self.near
            if len(i) == 0:
                return False
            bc, bh, cs, sn = self.bc[i], self.bh[i], self.bcos[i], self.bsin[i]
        d = np.asarray(p, dtype="f8") - bc
        lx = cs * d[:, 0] - sn * d[:, 2]
        lz = sn * d[:, 0] + cs * d[:, 2]
        q = np.maximum(np.abs(np.stack((lx, d[:, 1], lz), axis=1)) - bh, 0.0)
        return bool(np.any(np.einsum("ij,ij->i", q, q) < r * r))
