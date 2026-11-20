"""Physik „Liftoff-nah“: Acro-Quad, Parameter aus echten Liftoff-Flügen gefittet.

sim.py bleibt das einfache Modell für die Liftoff-Tests („Klassisch“). Dieses Modell hat dieselbe
Schnittstelle (step(gas, gier, nick, roll, dt), pos/quat/vel/omega, state()) und dazu die Effekte,
die das Fluggefühl in Liftoff bestimmen. Gefittet mit fit_physics.py auf ~200 000 Telemetrie-Zeilen
aus ~/EasyPilot/runs (Armattan Mongoose, Liftoff 1.7.6), gleiche Stickfolge wie in der Aufnahme:

  Drehung     Betaflight-Rates wie in drone.json, Liftoffs Raten-Regler als System 2. Ordnung
              (Eigenfrequenz RATE_WN, Dämpfung RATE_ZETA) mit begrenzter Winkelbeschleunigung
              (Trägheit/Motormoment), statt eines einfachen Tiefpasses.
  Motoren     Drehzahl-Zustand je Gas, hochdrehen und abbremsen mit eigenen Zeitkonstanten
              (Gas 0 = Propeller bremsen aktiv, Airmode hält eine Mindestdrehzahl bei Stickausschlag).
  Schub       k·n² + k1·n, minus Inflow n·v_axial (Luft von oben kostet Schub, von unten bringt Schub).
  Luftwiderstand im Drohnen-Koordinatensystem, je Achse eigen: von vorn am wenigsten (0,0195/m),
              von der Seite am meisten (0,0356/m), von oben 0,0289/m, dazu ein kleiner linearer Anteil
              (Rotor-Widerstand); sim.py hat rundum 0,033/m.
  Bodeneffekt mehr Schub dicht über dem Boden (Cheeseman-Bennett, nicht aus Liftoff-Daten belegt).
  Propwash    beim Sinken in die eigene Abluft: Schubverlust und Wackeln (nicht aus Liftoff-Daten belegt,
              in den Aufnahmen gibt es kaum senkrechte Sinkflüge).
  Akku        optional (battery=True): Spannung sinkt unter Last und über die Flugzeit.
"""
import math
from dataclasses import dataclass

from ..geometry import integrate, qinvrot, qrot
from ..telemetry import State

G = 9.81
REF_HOVER = 0.281       # Schwebegas der vermessenen Drohne (drone.json); hover_throttle skaliert k
REF_DRAG = 0.033        # game.DRAG: drag skaliert alle Widerstandsbeiwerte (für Domain-Randomisierung)


@dataclass
class LiftoffParams:
    # Schub [m/s²] = k n² + k1 n - inflow n v_eff,  v_eff = vsat tanh(v_axial / vsat)
    k: float = 114.5
    k1: float = 2.36
    inflow: float = 1.59
    vsat: float = 240.0          # Sättigung des Inflows: der Fit will praktisch keine (fast linear)
    # Motor-Drehzahl n folgt dem Gas (bzw. der Airmode-Mindestdrehzahl)
    tau_up: float = 0.025        # Fit: 3-25 ms gleich gut, 25 ms ist plausibel für 5"-Motoren
    tau_down: float = 0.020      # abbremsen etwas schneller (aktives Bremsen, Gas 0)
    air_n: float = 0.334         # Mindestdrehzahl bei vollem Stickausschlag (Airmode), skaliert mit |Stick|
    # Luftwiderstand im Drohnen-System: a = -(c_i |v| + lin_i) v_i,  x rechts, y oben, z vorn
    cx: float = 0.0356
    cy: float = 0.0289
    cz: float = 0.0195
    lin: float = 0.0126
    lin_y: float = 0.0033
    # Raten-Regler (pro Achse: Nick, Gier, Roll)
    rate_wn: float = 40.0        # rad/s
    rate_zeta: float = 0.7
    max_ang_acc: float = 210.0   # rad/s² (12 000 °/s²)
    # Bodeneffekt / Propwash / Akku
    ground_radius: float = 0.25  # m, wirksamer Rotorradius für den Bodeneffekt (0 = aus)
    propwash: float = 1.0        # Stärke (0 = aus)
    battery: bool = False
    # Kompatibilität mit SimParams (train_nn randomisiert diese beiden)
    hover_throttle: float = REF_HOVER
    drag: float = REF_DRAG
    wind: tuple = (0.0, 0.0, 0.0)


class LiftoffDrone:
    """Gleiche Schnittstelle wie sim.SimDrone."""

    def __init__(self, pos=(0.0, 1.0, 0.0), quat=(0.0, 0.0, 0.0, 1.0), vel=(0.0, 0.0, 0.0),
                 params=None, rates=None):
        from ..rates import Rates
        self.pos, self.quat, self.vel = tuple(pos), tuple(quat), tuple(vel)
        self.p = params or LiftoffParams()
        self.rates = rates or Rates()
        self.omega = (0.0, 0.0, 0.0)
        self.domega = [0.0, 0.0, 0.0]
        self.motor = math.sqrt(REF_HOVER ** 2)      # Drehzahl, startet auf Schwebe-Niveau wie sim.py (thrust=G)
        self.thrust = G
        self.t = 0.0
        self.ground = 0.0          # Boden-Klemme wie sim.py (Flight setzt -1e9 und regelt selbst)
        self.ground_level = 0.0    # Höhe der Wiese für den Bodeneffekt
        self.sticks = (0.0, 0.0, 0.0, 0.0)
        self.wash = 0.0            # Propwash-Stärke 0..1 (für OSD/Tests)
        self.charge = 1.0          # Akku 1 = voll
        self._ph = 0.0

    def step(self, throttle, yaw, pitch, roll, dt):
        p, r = self.p, self.rates
        # --- Drehung: Liftoffs Raten-Regler als gedämpftes System 2. Ordnung
        target = (math.radians(r.pitch.rate(pitch)), math.radians(r.yaw.rate(yaw)), -math.radians(r.roll.rate(roll)))
        wn2, c = p.rate_wn * p.rate_wn, 2.0 * p.rate_zeta * p.rate_wn
        amax = p.max_ang_acc
        om = list(self.omega)
        dom = self.domega
        for i in range(3):
            dom[i] += (wn2 * (target[i] - om[i]) - c * dom[i]) * dt
            if dom[i] > amax:
                dom[i] = amax
            elif dom[i] < -amax:
                dom[i] = -amax
            om[i] += dom[i] * dt

        # --- Motoren: Drehzahl folgt Gas, Airmode hält eine Mindestdrehzahl
        thr = 0.0 if throttle < 0.0 else 1.0 if throttle > 1.0 else throttle
        stick = max(abs(pitch), abs(roll), abs(yaw))
        cmd = max(thr, p.air_n * stick)
        n = self.motor
        tau = p.tau_up if cmd > n else p.tau_down
        n += (cmd - n) * (dt / (tau + dt))
        self.motor = n

        # --- Schub mit Inflow (sättigend)
        q = self.quat
        wx, wy, wz = p.wind
        air = (self.vel[0] - wx, self.vel[1] - wy, self.vel[2] - wz)
        bx, by, bz = qinvrot(q, air)                       # Luft im Drohnen-System
        vs = p.vsat
        v_eff = vs * math.tanh(by / vs)
        scale = (REF_HOVER / p.hover_throttle) ** 2
        T = scale * (p.k * n * n + p.k1 * n) - p.inflow * n * v_eff

        # Bodeneffekt
        if p.ground_radius > 0.0:
            h = self.pos[1] - self.ground_level
            if h < 2.0:
                up_y = qrot(q, (0.0, 1.0, 0.0))[1]
                z = max(0.08, h / max(0.3, up_y))
                f = (p.ground_radius / (4.0 * z)) ** 2
                T *= min(1.25, 1.0 / (1.0 - min(0.2, f)))

        # Propwash: Sinken entlang der Schubachse in die eigene Abluft, wenig Fahrt quer
        wash = 0.0
        if p.propwash > 0.0 and by < -1.0 and n > 0.12:
            edge = bx * bx + bz * bz
            wash = min(1.0, (-by - 1.0) / 4.0) * math.exp(-edge / 16.0) * p.propwash
            if wash > 1e-3:
                self._ph += dt
                ph = self._ph
                wobble = (math.sin(37.0 * ph) + 0.6 * math.sin(83.0 * ph + 1.3) + 0.4 * math.sin(151.0 * ph + 2.1))
                T *= 1.0 - 0.18 * wash * (0.6 + 0.4 * wobble / 2.0)
                k_w = 14.0 * wash * dt * n
                om[0] += k_w * (math.sin(61.0 * ph) + 0.5 * math.sin(127.0 * ph + 0.7))
                om[2] += k_w * (math.sin(53.0 * ph + 2.0) + 0.5 * math.sin(113.0 * ph + 1.1))
        self.wash = wash

        # Akku: unter Last und über die Zeit etwas weniger Schub
        if p.battery:
            self.charge = max(0.0, self.charge - dt * (0.0006 + 0.004 * n * n * n))
            T *= (0.88 + 0.12 * self.charge) * (1.0 - 0.08 * n * n)
        if T < 0.0:
            T = 0.0
        self.thrust = T

        # --- Luftwiderstand je Achse im Drohnen-System
        d = p.drag / REF_DRAG
        sp = math.sqrt(bx * bx + by * by + bz * bz)
        db = (-(p.cx * sp + p.lin) * d * bx, -(p.cy * sp + p.lin_y) * d * by, -(p.cz * sp + p.lin) * d * bz)
        dw = qrot(q, db)
        up = qrot(q, (0.0, 1.0, 0.0))
        ax = up[0] * T + dw[0]
        ay = up[1] * T + dw[1] - G
        az = up[2] * T + dw[2]
        v = self.vel
        self.vel = (v[0] + ax * dt, v[1] + ay * dt, v[2] + az * dt)
        v = self.vel
        self.pos = (self.pos[0] + v[0] * dt, self.pos[1] + v[1] * dt, self.pos[2] + v[2] * dt)
        if self.pos[1] < self.ground:
            self.pos = (self.pos[0], self.ground, self.pos[2])
            self.vel = (v[0] * 0.5, max(0.0, v[1]), v[2] * 0.5)
        self.omega = (om[0], om[1], om[2])
        self.quat = integrate(q, self.omega, dt)
        self.t += dt
        self.sticks = (throttle, yaw, pitch, roll)

    def state(self):
        return State(self.t, self.pos, self.quat, self.vel, tuple(math.degrees(w) for w in self.omega),
                     self.sticks, self.t)


def thrust_model(base, params=None):
    """ThrustModel für die Regler (Autopiloten), passend zu dieser Physik.

    Statische Schubkurve k n² + k1 n als k' n^p angenähert (gleicher Schwebepunkt, gleiche Steigung bis
    Gas 0,7), Inflow und Airmode wie gefittet. base: ThrustModel aus sysid.load_model (min/max bleiben)."""
    import dataclasses
    p = params or LiftoffParams()
    f = lambda n: p.k * n * n + p.k1 * n
    lo, hi = 0.0, 1.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) < G else (lo, mid)
    hover = 0.5 * (lo + hi)
    expo = math.log(f(0.7) / G) / math.log(0.7 / hover)
    return dataclasses.replace(base, hover_throttle=round(hover, 4), exponent=round(expo, 3),
                               inflow=p.inflow, airmode=round(p.k * p.air_n ** 2, 2))


PHYSICS = {"classic": "Klassisch", "liftoff": "Liftoff-nah"}


def make_drone(kind, pos, rates, thrust, drag, quat=(0.0, 0.0, 0.0, 1.0)):
    """Drohne für Flight: kind 'classic' (sim.py, wie bisher) oder 'liftoff' (dieses Modell)."""
    if kind == "liftoff":
        return LiftoffDrone(pos=pos, quat=quat, params=LiftoffParams(), rates=rates)
    from ..sim import SimDrone, SimParams
    p = SimParams(hover_throttle=thrust.hover_throttle, thrust_exponent=thrust.exponent,
                  drag=drag, inflow=thrust.inflow, airmode=thrust.airmode)
    return SimDrone(pos=pos, quat=quat, params=p, rates=rates)
