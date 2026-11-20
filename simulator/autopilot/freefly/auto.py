"""Der EasyPilot-Autopilot im Freiflug-Simulator.

Dieselbe Kette wie im Liftoff-Rennen (race.py): Rennlinie durch die Tore um die Hindernisse herum
(avoid.build_line), Racer + FlightController mit den Renn-Reglerwerten, Regler mit 125 Hz. Der
Unterschied: Welt, Tore und Kollisionen kommen aus world.py, die Physik aus sim.py.

  python -m autopilot.freefly.auto [k] [runden]    # ohne Fenster fliegen und auswerten
"""
import collections
import math
import sys
import time

import numpy as np

from ..control import FlightController
from ..envdb import ObstacleSet
from ..gatedb import as_parallelepiped
from ..planner import Gate as PGate
from ..race import build_line, launch, race_gains
from ..racer import Racer
from .world import GATE_H, GATE_W, SPAWN

CONTROL_EVERY = 4        # Physik 500 Hz / 4 = Regler 125 Hz wie die Liftoff-Schleife


def planner_gates(world):
    return [PGate(g.center, (math.sin(g.yaw), 0.0, math.cos(g.yaw)), GATE_W, GATE_H, name=f"T{i + 1}")
            for i, g in enumerate(world.gates)]


def obstacles(world):
    items = []
    for i, (cx, cy, cz, hx, hy, hz, yaw) in enumerate(world.boxes):
        c, s = math.cos(yaw), math.sin(yaw)
        corners = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    lx, lz = sx * hx, sz * hz
                    corners.append((cx + c * lx + s * lz, cy + sy * hy, cz - s * lx + c * lz))
        items.append((f"box{i}", as_parallelepiped(corners)))
    return ObstacleSet(items)


class Autopilot:
    def __init__(self, world, rates, thrust, k=0.6, laps=3, latency=0.0):
        self.rates, self.thrust, self.latency = rates, thrust, latency
        self.k, self.laps = k, laps
        gates = planner_gates(world)
        t0 = time.perf_counter()
        start, d = launch(gates[0], SPAWN)
        self.line = build_line(gates + [gates[0]], start, d, laps, k, colliders=obstacles(world))
        self.plan_time = time.perf_counter() - t0
        self.reset()

    def reset(self):
        self.racer = Racer(self.line, FlightController(self.rates, self.thrust, race_gains()), lookahead=0.12)
        self.cmd = None
        self.n = 0
        self.seen = collections.deque()

    def step(self, state):
        """Sticks (Gas, Gieren, Nicken, Rollen) für einen Physik-Schritt."""
        self.seen.append(state)
        while len(self.seen) > 1 and self.seen[1].t <= state.t - self.latency:
            self.seen.popleft()
        if self.cmd is None or self.n % CONTROL_EVERY == 0:
            self.cmd = self.racer.step(self.seen[0]).as_tuple()
        self.n += 1
        return self.cmd

    @property
    def done(self):
        return self.racer.done


def main(argv):
    if argv and argv[0] == "bomben":
        return main_bomb(argv[1:])
    if argv and argv[0] == "kamera":
        return main_camera(argv[1:])
    from ..sysid import load_model
    from .game import Flight
    from .world import World
    k = float(argv[0]) if argv else 0.6
    laps = int(argv[1]) if len(argv) > 1 else 2
    rates, thrust = load_model()
    world = World()
    ap = Autopilot(world, rates, thrust, k, laps)
    line = ap.line
    print(f"Rennlinie: {line.length:.0f} m, {len(line.gate_sequence)} Tore, Vias {getattr(line, 'vias', 0)}, "
          f"berührt Hindernisse {getattr(line, 'touching', 0)}, geplant in {ap.plan_time:.1f} s")
    flight = Flight(world, rates, thrust)
    flight.armed = True
    dt, t = 0.002, 0.0
    vmax = 0.0
    while t < 300 and not ap.done and flight.crashed_at is None:
        if int(t / dt) % 50 == 0:
            world.focus(flight.drone.pos)
        sticks = ap.step(flight.drone.state())
        flight.step(sticks, dt)
        t += dt
        vmax = max(vmax, math.sqrt(sum(v * v for v in flight.drone.vel)))
    prog = ap.racer.progress
    print(f"k={k}: Tore {len(prog.gate_times)}/{len(line.gate_sequence)}, verfehlt {prog.missed}, "
          f"Absturz: {flight.crash_reason or 'nein'} bei {tuple(round(v, 1) for v in flight.drone.pos)}, "
          f"Racer crashed={ap.racer.crashed}, Zeit {t:.1f} s, max {vmax * 3.6:.0f} km/h, "
          f"Runde(n) {flight.last_lap and round(flight.last_lap, 2)}")
    if prog.gate_times:
        print("Torzeiten:", [round(x, 1) for x in prog.gate_times])


def main_bomb(argv):
    """python -m autopilot.freefly.auto bomben [Ziele] : Auto-Bomben ohne Fenster."""
    from ..sysid import load_model
    from .entities import Entities
    from .game import Flight
    from .world import World
    n_targets = int(argv[0]) if argv else 8
    rates, thrust = load_model()
    world = World()
    ent = Entities(world)
    flight = Flight(world, rates, thrust)
    flight.mode, flight.entities = "bomb", ent
    flight.next_target()
    ap = BombAutopilot(world, rates, thrust, ent)
    dt, t, t_target = 0.002, 0.0, 0.0
    t_since = 0.0                     # wie im Spiel: 30 s pro Ziel (über alle Versuche), dann ein neues
    results = []
    flight.armed = True
    while len(results) < n_targets and t < 600:
        if int(round(t / dt)) % 10 == 0:
            ent.update(10 * dt, flight.drone.pos)
            world.focus(flight.drone.pos)
        flight.step(ap.step(flight.drone.state(), flight.target), dt)
        t += dt
        if flight.crashed_at is not None or t - t_since > 30:
            name = ent.name(flight.target) if flight.target is not None else "?"
            ok = getattr(flight, "target_hit", False) and flight.crashed_at is not None
            results.append((name, ok, round(t - t_target, 1), flight.crash_reason or "Zeit um"))
            if not ok:
                print(f"      Phase: {ap.info}, Drohne {tuple(round(v, 1) for v in flight.drone.pos)}, "
                      f"Ziel {tuple(round(float(v), 1) for v in ent.bounds(flight.target)[2])}")
            print(f"{len(results):2d}. {name:6s} {'TREFFER' if ok else 'daneben':8s} {t - t_target:5.1f} s  "
                  f"{flight.crash_reason or 'nach 30 s aufgegeben (' + ap.info + ')'}", flush=True)
            flight.events.clear()
            if flight.target is None or not ent.alive[flight.target] or t - t_since > 30:
                flight.next_target()
                t_since = t
            flight.respawn()
            flight.armed = True
            ap.reset()
            t_target = t
    hits = sum(r[1] for r in results)
    print(f"Treffer {hits}/{len(results)}, Zeit pro Treffer im Mittel "
          f"{np.mean([r[2] for r in results if r[1]]) if hits else float('nan'):.1f} s")


def main_camera(argv):
    """python -m autopilot.freefly.auto kamera [m/s] : Tore nur aus dem Kamerabild, ohne Fenster."""
    from ..sysid import load_model
    from .game import Flight
    from .world import World
    speed = float(argv[0]) if argv else 6.0
    rates, thrust = load_model()
    world = World()
    flight = Flight(world, rates, thrust)
    flight.armed = True
    ap = CameraAutopilot(world, rates, thrust, speed=speed)
    dt, t, ordered = 0.002, 0.0, 0
    last_next = flight.next_gate
    t0 = time.perf_counter()
    while t < 300 and not ap.done and flight.crashed_at is None:
        if int(round(t / dt)) % 25 == 0:
            world.focus(flight.drone.pos)
        flight.step(ap.step(flight.drone.state()), dt)
        if flight.next_gate != last_next:
            ordered += 1
            print(f"  {t:6.1f} s  Tor {last_next + 1} in Reihenfolge durchflogen", flush=True)
            last_next = flight.next_gate
        t += dt
    p = ap.pilot
    hit = world.hit_index(flight.drone.pos)
    print(f"Kamera-Autopilot {speed} m/s: {t:.1f} s Flug, Ende: {p.reason or flight.crash_reason or 'Zeit um'} "
          f"bei {tuple(round(float(v), 1) for v in flight.drone.pos)}"
          f"{' (Box ' + str(tuple(round(float(v), 1) for v in world.boxes[hit][:6])) + ')' if hit >= 0 else ''}")
    print(f"Tore in Reihenfolge (Sim zählt): {ordered}, Durchflüge laut Pilot: "
          f"{sum('durch' in e[2] for e in p.events)}, daneben {sum('daneben' in e[2] for e in p.events)}, "
          f"Tore gesehen: {len(ap.per.tracker.found())}, Kamerabilder {ap.frames}, "
          f"Bild+Erkennung {ap.vision_ms:.1f} ms, Rechenzeit {time.perf_counter() - t0:.0f} s")
    for e in p.events:
        print("   ", e)




# ============================================================================ Auto-Bomben
CRUISE = 24.0            # m: über allen Dächern, Bäumen und Leitungen (Wasserturm 20,5 m)
ATTACK_RANGE = 38.0      # m waagrecht: ab hier Anflug aufs Ziel
DIVE_SPEED = 19.0        # m/s im Sturzflug
CRUISE_SPEED = 17.0


def segment_clear(world, a, b, r=0.6, skip_end=0.0):
    """Keine statische Box auf der Strecke a->b (Kugel r), die letzten skip_end m ausgenommen."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = float(np.linalg.norm(b - a))
    if L < 1e-6:
        return True
    n = max(2, int((L - skip_end) / 0.5) + 1)
    t = np.linspace(0.0, max(0.0, (L - skip_end) / L), n)
    pts = a + (b - a) * t[:, None]
    lo, hi = pts.min(axis=0) - r - 1, pts.max(axis=0) + r + 1
    m = np.all((world.bc + world.brad[:, None] > lo) & (world.bc - world.brad[:, None] < hi), axis=1)
    idx = np.nonzero(m)[0]
    if not len(idx):
        return True
    d = pts[:, None, :] - world.bc[idx][None]
    cs, sn = world.bcos[idx][None], world.bsin[idx][None]
    lx = cs * d[..., 0] - sn * d[..., 2]
    lz = sn * d[..., 0] + cs * d[..., 2]
    q = np.maximum(np.abs(np.stack((lx, d[..., 1], lz), axis=-1)) - world.bh[idx][None], 0.0)
    return not np.any(np.einsum("ijk,ijk->ij", q, q) < r * r)


class BombAutopilot:
    """Fliegt das aktuelle Bomben-Ziel an (Personen, Autos, Busse bewegen sich) und stürzt hinein.

    Weiß, wo Häuser, Bäume und Leitungen stehen (Weltmodell), und plant laufend neu:
    senkrecht auf Reiseflughöhe, oben hin zum Ziel, dann ein freier Sturzflug-Korridor zum
    vorausberechneten Treffpunkt (Ziel läuft/fährt weiter). Ist der direkte Weg verbaut, sucht er
    einen Anflugpunkt rundherum, von dem aus die Bahn frei ist."""

    def __init__(self, world, rates, thrust, entities):
        self.world, self.entities = world, entities
        self.rates, self.thrust = rates, thrust
        self.reset()

    def reset(self):
        g = race_gains()
        self.ctl = FlightController(self.rates, self.thrust, g)
        self.phase = "climb"
        self.cmd = None
        self.n = 0
        self.via = None
        self.last_target = None
        self.tpos = None
        self.tvel = np.zeros(3)
        self.done = False
        self.info = ""
        self.blocked_since = None
        self.diving = False
        self.route = []

    def _target(self, idx, t):
        e = self.entities
        lo, hi, c = e.bounds(idx)
        p = np.array(c, float)
        if self.tpos is not None and self.last_target == idx and t > self.tpos[1]:
            v = (p - self.tpos[0]) / (t - self.tpos[1])
            self.tvel = 0.7 * self.tvel + 0.3 * v
        elif self.last_target != idx:
            self.tvel = np.zeros(3)
            self.phase = "climb" if self.phase == "climb" else "cruise"
            self.via = None
        self.tpos, self.last_target = (p, t), idx
        return p

    def step(self, state, target_idx):
        if self.cmd is None or self.n % CONTROL_EVERY == 0:
            self.cmd = self._control(state, target_idx).as_tuple()
        self.n += 1
        return self.cmd

    def _control(self, s, idx):
        self.ctl.observe(s)
        pos = np.array(s.pos, float)
        if idx is None:
            self.info = "kein Ziel"
            return self.ctl.track(s, (pos[0], max(pos[1], 3.0), pos[2]), (0, 0, 0), (0, 0, 0), (0, 0, 1))
        P = self._target(idx, s.t)
        # Treffpunkt: wo das Ziel ist, wenn wir ankommen
        I = P.copy()
        for _ in range(3):
            tgo = np.linalg.norm(I - pos) / DIVE_SPEED
            I = P + self.tvel * min(tgo, 3.0)
        I[1] = P[1]
        person = self.entities.kind[idx] == "person"
        horiz = math.hypot(I[0] - pos[0], I[2] - pos[2])
        if self.phase == "climb":
            self.info = "steigt"
            if pos[1] > CRUISE - 2.0:
                self.phase = "cruise"
            return self._go(s, (pos[0], CRUISE, pos[2]), 8.0, face=I - pos)
        if self.phase == "cruise":
            self.info = f"Anflug {horiz:.0f} m"
            if horiz < ATTACK_RANGE:
                self.phase = "attack"
            else:
                return self._go(s, (I[0], CRUISE, I[2]), CRUISE_SPEED)
        # Angriff: direkte Bahn frei (Häuser, Bäume, Leitungen und andere Figuren)?
        dist = float(np.linalg.norm(I - pos))
        elev = math.degrees(math.atan2(pos[1] - I[1], max(1e-6, horiz)))
        if person and elev < 50 and not self.diving and not self.route:
            # Personen stehen dicht beieinander: erst über das Ziel, dann steil hinunter
            # Anflugseite wählen: quer zum Gehsteig (zur Drohne hin, dann die andere Seite), sonst von hinten;
            # genommen wird die erste Richtung, deren Sturzbahn frei von Häusern, Zäunen und anderen Leuten ist
            lead = P + self.tvel * 1.0
            spd = np.linalg.norm(self.tvel[[0, 2]])
            n = self.entities._n[idx]
            side = np.array((n[0], 0.0, n[1]))
            if np.dot(side[[0, 2]], (pos - P)[[0, 2]]) < 0:
                side = -side
            behind = -self.tvel / spd if spd > 0.5 else (pos - I) / max(1e-6, np.linalg.norm(pos - I))
            S = None
            for back in (side, -side, behind):
                back = np.array((back[0], 0.0, back[2])) / max(1e-6, math.hypot(back[0], back[2]))
                cand = np.array((lead[0], P[1] + 12.0, lead[2])) + back * 3.5
                if segment_clear(self.world, cand, I, 0.5, skip_end=0.3) and self._no_bystander(cand, I, idx):
                    S = cand
                    break
            if S is None:
                S = np.array((lead[0], P[1] + 12.0, lead[2])) + side * 3.5
            if segment_clear(self.world, pos, S, 0.6):
                self.info = "über das Ziel"
                return self._go(s, S, 16.0, face=I - pos, carry=self.tvel)
        dist = float(np.linalg.norm(I - pos))
        committed = self.diving and dist < 9.0 and segment_clear(self.world, pos, I, 0.25, skip_end=0.3)
        if committed or (segment_clear(self.world, pos, I, 0.5, skip_end=0.3) and self._no_bystander(pos, I, idx)):
            self.diving = True
            self.info = "Sturzflug"
            self.blocked_since = None
            d = (I - pos) / max(1e-6, np.linalg.norm(I - pos))
            v_ref = d * DIVE_SPEED
            p_ref = pos + d * 3.0
            return self.ctl.track(s, tuple(p_ref), tuple(v_ref), (0.0, 0.0, 0.0), tuple(d))
        self.diving = False
        if self.blocked_since is None:
            self.blocked_since = s.t
        # verbaut: schräg hinter/über dem Ziel mitfliegen, bis die Bahn frei wird
        spd = np.linalg.norm(self.tvel[[0, 2]])
        back = -self.tvel / spd if spd > 0.5 else (pos - I) / max(1e-6, np.linalg.norm(pos - I))
        back = np.array((back[0], 0.0, back[2]))
        back /= max(1e-6, np.linalg.norm(back))
        lead = P + self.tvel * 1.5
        S = np.array((lead[0], P[1] + 13.0, lead[2])) + back * 7.0
        if self.route:                                   # Umweg zu einem freien Anflugpunkt
            if np.linalg.norm(self.route[0] - pos) < 2.5:
                self.route.pop(0)
            if self.route:
                self.info = "Umweg zum Anflugpunkt"
                return self._go(s, self.route[0], 16.0 if len(self.route) > 1 else 10.0, face=I - pos)
        if s.t - self.blocked_since > 1.5:                # zu lange verbaut: Anflugpunkt rundherum suchen
            route = self._approach(pos, I)
            if route:
                self.route = route
                self.blocked_since = s.t
                return self._go(s, route[0], 12.0, face=I - pos)
        if not segment_clear(self.world, pos, S, 0.6):
            S = np.array((pos[0], CRUISE, pos[2])) if pos[1] < CRUISE - 2 else np.array((S[0], CRUISE, S[2]))
        self.info = "wartet auf freie Bahn"
        return self._go(s, S, 16.0, face=I - pos, carry=self.tvel)

    def _no_bystander(self, pos, I, idx):
        """Keine andere Figur (jetzt oder in 1 s) nahe der Sturzbahn."""
        e = self.entities
        d = I - pos
        L = np.linalg.norm(d)
        if L < 1e-6:
            return True
        u = d / L
        for k in np.nonzero(e.visible)[0]:
            if k == idx:
                continue
            for p in (e.pos[k], e.pos[k] + np.array((math.sin(e.yaw[k]), 0, math.cos(e.yaw[k]))) * e.speed[k] * e.alive[k]):
                c = p + np.array((0.0, e.half[k][1], 0.0))
                a = float(np.dot(c - pos, u))
                margin = 0.9 if e.kind[k] != "person" else 0.3   # Fahrzeuge großzügig, Leute nur direkt auf der Bahn
                if 0 < a < L - 0.8 and np.linalg.norm(c - pos - u * a) < np.linalg.norm(e.half[k][[0, 2]]) + margin:
                    return False
        return True

    def _approach(self, pos, I):
        """Wegpunkte zu einem Anflugpunkt S mit freier Bahn S->Ziel: direkt, sonst über die Reiseflughöhe."""
        best, best_cost = None, None
        up = np.array((pos[0], CRUISE, pos[2]))
        for el in (55, 70, 40, 85, 25, 12):              # zuerst steil, zuletzt flach über die Straße
            for k in range(16):
                az = 2 * math.pi * k / 16
                for dist in (12.0, 20.0):
                    e = math.radians(el)
                    S = I + dist * np.array((math.cos(e) * math.sin(az), math.sin(e), math.cos(e) * math.cos(az)))
                    if S[1] < 1.6:
                        continue
                    if not segment_clear(self.world, S, I, 0.5, skip_end=0.3):
                        continue
                    if segment_clear(self.world, pos, S, 0.6):
                        route, cost = [S], np.linalg.norm(S - pos)
                    else:
                        top = np.array((S[0], CRUISE, S[2]))
                        if not (segment_clear(self.world, pos, up, 0.6) and segment_clear(self.world, top, S, 0.6)):
                            continue
                        route = [up, top, S]
                        cost = (CRUISE - pos[1]) + np.linalg.norm(top - up) + (CRUISE - S[1]) + 10.0
                    cost += 0.1 * dist
                    if best_cost is None or cost < best_cost:
                        best, best_cost = route, cost
            if best is not None:
                return best
        return None

    def _go(self, s, goal, speed, face=None, carry=None):
        pos = np.array(s.pos, float)
        to = np.asarray(goal, float) - pos
        d = float(np.linalg.norm(to))
        u = to / d if d > 1e-6 else np.zeros(3)
        v = min(speed, 1.2 * d)                            # vor dem Ziel abbremsen
        p_ref = pos + u * min(d, 3.0)
        if carry is not None:                              # mit dem Ziel mitfahren
            return self.ctl.track(s, tuple(p_ref), tuple(u * v + np.asarray(carry) * (d < 6)), (0.0, 0.0, 0.0),
                                  tuple(self._face(face, to, d)))
        f = face if face is not None else (to if d > 1 else (0, 0, 1))
        f = np.array((f[0], 0.0, f[2]))
        nf = np.linalg.norm(f)
        f = f / nf if nf > 1e-6 else np.array((0.0, 0.0, 1.0))
        return self.ctl.track(s, tuple(p_ref), tuple(u * v), (0.0, 0.0, 0.0), tuple(f))

    @staticmethod
    def _face(face, to, d):
        f = face if face is not None else (to if d > 1 else (0, 0, 1))
        f = np.array((f[0], 0.0, f[2]))
        nf = np.linalg.norm(f)
        return f / nf if nf > 1e-6 else np.array((0.0, 0.0, 1.0))


# ============================================================================ Nur Kamera
class CameraAutopilot:
    """Keine Rennlinie, keine Torliste: Tore nur aus dem Kamerabild (vision.ColorGateDetector),
    VisionPilot aus visionfly.py fliegt zum nächsten gesehenen Tor und plant dabei laufend neu,
    Hindernisse nur aus dem Tiefenbild derselben Kamera (vision.DepthGuard)."""

    FRAME_DT = 1 / 30        # s Simulationszeit zwischen zwei Kamerabildern
    MIN_DET_PX = 11          # px Mindestbreite einer Tor-Erkennung (960-px-Bild)

    def __init__(self, world, rates, thrust, ctx=None, speed=6.0):
        import moderngl
        from types import SimpleNamespace
        from ..control import Gains
        from ..sysid import load_camera
        from ..visionfly import GateTracker
        from .vision import CameraView, ColorGateDetector, DepthGuard, GuardedController
        self.cam = load_camera(960)                    # 960 px: Tore schon aus ~60 m erkennbar
        self.ctx = ctx or moderngl.create_standalone_context(require=330)
        self.view = CameraView(self.ctx, world, self.cam)
        self.detect = ColorGateDetector()
        self.guard = DepthGuard(self.cam)
        self.rates, self.thrust, self.speed = rates, thrust, speed
        self._Gains, self._GuardedController, self._GateTracker = Gains, GuardedController, GateTracker
        self._ns = SimpleNamespace
        self.reset()

    def reset(self):
        from ..visionfly import VisionPilot
        ctl = FlightController(self.rates, self.thrust, self._Gains(tilt=12, yaw=3.0, pos=2.5, vel=3.0))
        self.ctl = self._GuardedController(ctl, self.guard)
        self.per = self._ns(tracker=self._GateTracker())
        self.pilot = VisionPilot(self.ctl, self.per, speed=self.speed)
        self.cmd = None
        self.n = 0
        self.next_frame = 0.0
        self.last_dets = []
        self.frames = 0
        self.vision_ms = 0.0

    def step(self, state, craters=None):
        if state.t >= self.next_frame:
            t0 = time.perf_counter()
            bgr, depth = self.view.grab(state.pos, state.quat, craters)
            # winzige Erkennungen (< MIN_DET_PX breit, also weiter als ~60 m) sind meist Rauschen: 3 davon
            # gleich nach dem Start ergaben ein Phantom-Tor 6 m hoch vor der Scheune, und bei 10 m/s flog der
            # Pilot hinter Tor 3 dorthin ins Scheunendach (20.11., Simons Absturz „nach Tor 4 oder 5“)
            self.last_dets = [d for d in self.detect(bgr) if d.box[2] - d.box[0] >= self.MIN_DET_PX]
            self.per.tracker.update(self.cam, state.quat, state.pos, self.last_dets, time.perf_counter())
            self._merge()
            self.guard.update(depth, state.pos, state.quat, state.vel)
            self.next_frame = state.t + self.FRAME_DT
            self.frames += 1
            self.vision_ms = 0.9 * self.vision_ms + 0.1 * (time.perf_counter() - t0) * 1000
        if self.cmd is None or self.n % CONTROL_EVERY == 0:
            self.ctl.observe(state)
            self.cmd = self.pilot.step(state, CONTROL_EVERY * 0.002).as_tuple()
        self.n += 1
        return self.cmd

    def _merge(self, dist=3.5):
        """Zwei Spuren desselben Tors zusammenlegen (frühe, ferne PnP-Schätzungen liegen oft 2-3 m daneben;
        Tore stehen hier mindestens 15 m auseinander). Die Spur mit mehr Bildern behält die Nummer."""
        tr = self.per.tracker
        now = time.perf_counter()
        with tr.lock:
            for g in tr.gates:                            # unmögliche Tore: unter der Wiese, zu hoch, falsche Größe,
                # oder nur ein paar Mal kurz gesehen und seit Sekunden nicht mehr (Phantom aus Bildrauschen)
                if g.obs and not g.passed and (g.center[1] < 0.7 or g.center[1] > 14.0 or
                                               (g.triangulated and not 1.2 < g.width < 7.0) or
                                               (g.hits < 8 and not g.triangulated and now - g.last_seen > 3.0)):
                    g.obs = []
                    if self.pilot.target is g:
                        self.pilot.target = None
            gs = [g for g in tr.gates if g.obs]
            for a in gs:
                for b in gs:
                    if a is b or not a.obs or not b.obs or a.passed != b.passed:
                        continue
                    if math.dist(a.center, b.center) < dist:
                        keep, drop = (a, b) if a.hits >= b.hits else (b, a)
                        keep.obs = keep.obs + drop.obs
                        drop.obs = []
                        keep.refresh()
                        if self.pilot.target is drop:
                            self.pilot.target = keep

    @property
    def done(self):
        return self.pilot.done


if __name__ == "__main__":
    main(sys.argv[1:])
