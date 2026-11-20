"""Flug-Logik: Acro-Drohne (sim.py „Klassisch“ oder physics.py „Liftoff-nah“), Boden, Absturz, Tore, Rundenzeit."""
import math
import os
import time

from ..geometry import qrot
from ..sim import SimDrone, SimParams
from .world import GATE_H, GATE_W, RADIUS, SPAWN

DRAG = 0.033            # 1/m, wie race.DRAG (Störgrößen-Schätzung bei 27 m/s)
# Physik für neue Flights: "classic" (sim.py) oder "liftoff" (physics.py); __main__ setzt Flight.physics
# aus Menü/--physik, die Tests ohne Fenster lesen FREEFLY_PHYSIK.
PHYSICS = os.environ.get("FREEFLY_PHYSIK", "classic")


class Flight:
    def __init__(self, world, rates, thrust):
        self.world, self.rates, self.thrust = world, rates, thrust
        self.msg = None                   # (Text, Untertitel, bis wann)
        self.last_lap = None
        self.new_best = None
        self.mode = "race"               # "race" (Tore) oder "bomb" (Ziele zerstören)
        self.target = None               # Index in entities (Bomben-Modus)
        self.entities = None
        self.hits = self.misses = 0
        self.target_since = time.perf_counter()
        self.events = []                 # ("boom", pos, groß?, Ziel-Index oder None) für main
        self.rng = __import__("random").Random(5)
        self.respawn()

    physics = PHYSICS

    def respawn(self):
        if self.physics == "liftoff":
            from .physics import make_drone
            self.drone = make_drone("liftoff", SPAWN, self.rates, self.thrust, DRAG)
        else:
            p = SimParams(hover_throttle=self.thrust.hover_throttle, thrust_exponent=self.thrust.exponent,
                          drag=DRAG, inflow=self.thrust.inflow, airmode=self.thrust.airmode)
            self.drone = SimDrone(pos=SPAWN, params=p, rates=self.rates)
        self.drone.ground = -1e9          # Boden und Absturz regelt Flight selbst
        self.armed = False
        self.crashed_at = None
        self.crash_reason = ""
        self.flight_time = 0.0
        self.next_gate = 0
        self.lap_start = None
        self.frozen = False

    def say(self, text, sub=None, seconds=2.0):
        self.msg = (text, sub, time.perf_counter() + seconds)

    def step(self, sticks, dt):
        d = self.drone
        if self.crashed_at is not None or self.frozen:
            return
        if not self.armed:
            if sticks[0] < 0.05:
                self.armed = True
            return
        vy = d.vel[1]
        prev = d.pos
        d.step(*sticks, dt)
        self.flight_time += dt
        up_y = qrot(d.quat, (0.0, 1.0, 0.0))[1]
        if d.pos[1] < RADIUS:
            if vy < -6.0:
                return self.crash(f"zu hart aufgeschlagen ({-vy:.0f} m/s)")
            if up_y < 0.25:
                return self.crash("umgekippt")
            d.pos = (d.pos[0], RADIUS, d.pos[2])
            k = math.exp(-5.0 * dt)
            d.vel = (d.vel[0] * k, max(0.0, d.vel[1]), d.vel[2] * k)
        if self.mode == "bomb" and self.entities is not None:
            ei = self.entities.hit(d.pos, RADIUS, prefer=self.target)
            if ei >= 0:
                name = self.entities.name(ei)
                if ei == self.target:
                    self.entities.destroy(ei)
                    self.hits += 1
                    took = time.perf_counter() - self.target_since
                    self.events.append(("boom", d.pos, True, ei))
                    return self.crash(f"{name} getroffen ({took:.1f} s)", hit=True)
                return self.crash(f"falsches Ziel ({name})")
        if self.world.hit_index(d.pos) >= 0:
            return self.crash("Hindernis getroffen")
        if abs(d.pos[0]) > 1500 or abs(d.pos[2]) > 1500 or d.pos[1] > 400:
            return self.crash("zu weit weg")
        self._gate(prev, d.pos)

    def _gate(self, a, b):
        g = self.world.gates[self.next_gate]
        ax, ay, az = g.local(a)
        bx, by, bz = g.local(b)
        if not (az < 0.0 <= bz):
            return
        t = -az / (bz - az)
        x, y = ax + t * (bx - ax), ay + t * (by - ay)
        if abs(x) > GATE_W / 2 or abs(y) > GATE_H / 2:
            return
        i = self.next_gate
        n = len(self.world.gates)
        self.next_gate = (i + 1) % n
        if i == 0:
            if self.lap_start is not None:
                lap = self.flight_time - self.lap_start
                self.last_lap = lap
                self.new_best = lap
                self.say(f"Runde {lap:.2f} s", None, 2.5)
            else:
                self.say("Los!", "Runde läuft", 1.0)
            self.lap_start = self.flight_time

    def crash(self, reason, hit=False):
        self.crashed_at = time.perf_counter()
        self.crash_reason = reason
        self.target_hit = hit
        self.crash_pos, self.crash_vel = self.drone.pos, self.drone.vel
        if self.mode == "bomb" and not hit:
            self.misses += 1
            self.events.append(("boom", self.drone.pos, False, None))   # daneben: Explosion, kein Treffer

    def next_target(self):
        """Neues bewegtes Ziel: lebend, 20-220 m vom Start; Personen häufiger als Autos und Busse."""
        e = self.entities
        cand = [i for i in range(len(e.kind)) if e.alive[i] and i != self.target
                and 20 < math.hypot(e.pos[i][0], e.pos[i][2]) < 220]
        if not cand:
            cand = [i for i in range(len(e.kind)) if e.alive[i]]
        if not cand:
            self.target = None
            return None
        weight = {"person": 3.0, "car": 2.0, "bus": 1.0}
        self.target = self.rng.choices(cand, [weight[e.kind[i]] for i in cand])[0]
        self.target_since = time.perf_counter()
        return self.target

    def target_info(self):
        if self.target is None or self.entities is None:
            return None
        lo, hi, c = self.entities.bounds(self.target)
        return {"name": self.entities.name(self.target), "lo": lo, "hi": hi, "center": c,
                "alive": bool(self.entities.alive[self.target])}
