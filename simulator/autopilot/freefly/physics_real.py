"""Physik „Realistisch“: echte 5-Zoll-FPV-Racing-Drohne (6S, 2207-Motoren, 5,1"-Dreiblatt), kein Liftoff-Fit.

Gleiche Schnittstelle wie sim.SimDrone / physics.LiftoffDrone (step(gas, gier, nick, roll, dt), pos/quat/vel/omega,
state()), aber innen alles so, wie es an einer echten Drohne passiert:

  Starrkörper   Masse 0,70 kg mit Akku, Trägheitstensor diag(Nick, Gier, Roll), Euler-Gleichung I·ω̇ = τ − ω×(Iω + H_Rotor)
  Motoren       vier einzelne Motoren an den Armen (X-Rahmen), je ein Gleichstrom-Modell: Spannung u·V_Akku, Strom
                I = (u·V − ω/Kv)/R, Moment Kt·(I − I0) gegen Propellermoment k_m·ω² und Rotorträgheit → Drehzahl ω(t)
                (Zeitkonstante 28-32 ms ergibt sich, wird nicht vorgegeben). Schub T = k_f·ω²·C_T(J)/C_T0.
  Regler        Betaflight 4.5: Rates (die der Drohne, wie bei Liftoff-nah), rc_smoothing, PID je Achse auf dem gefilterten Gyro
                (PT1-Filter wie gyro_lpf / dterm_lpf), D auf der Messung, Feedforward aus der Setpoint-Änderung,
                I-Term-Relax, TPA, pidsum_limit, Airmode-Mixer mit Entsättigung, DShot-Idle 5,5 %.
                Die Drohne dreht so schnell, wie PID und Motoren es schaffen – nicht ideal.
  Aerodynamik   Propeller: Schubverlust mit dem Fortschrittsgrad J = v_axial/(n·D) (UIUC-Messkurven), mehr Schub
                beim Sinken (bis zum Wirbelringzustand), Translational Lift quer angeströmt, Rotor-Widerstand
                (Blade Flapping, ∝ ω·v quer zur Achse, je Rotor inkl. ω×r), Rahmenwiderstand je Achse ½ρ·CdA·|v|·v,
                Wirbelring/Propwash beim Sinken in die eigene Abluft (zufällig je Rotor → Wackeln), Bodeneffekt
                je Rotor (Cheeseman-Bennett).
  Akku          6S 1300 mAh: Leerlaufspannung je Ladung (LiPo-Kurve), Innenwiderstand → Spannungseinbruch unter Last,
                Coulomb-Zählung; weniger Spannung = weniger Drehzahl = weniger Schub. `volts`, `amps`, `mah` fürs OSD.
  Wind          optional: mittlerer Wind + Böen (Gauß-Markov-Prozess wie Dryden, je Achse), Sensorrauschen optional.

Werte, Quellen und Messungen: PHYSIK_REALISTISCH.md (gleicher Ordner). Tests: tests/test_physics_real.py.
Autopiloten bekommen bei dieser Physik ein vermessenes Schubmodell und eigene Reglerwerte (controller_thrust, gains_for).
"""
import math
import random
from dataclasses import dataclass, field

from ..geometry import integrate, qinvrot, qrot
from ..telemetry import State

G = 9.81
RHO = 1.225                    # kg/m³, Luftdichte Meereshöhe ISA
RPM = 2.0 * math.pi / 60.0     # rpm -> rad/s

# Betaflight-Skalen (src/main/flight/pid.h): Konfigurationswerte -> Regler-Einheiten, Ausgabe / 1000 = Mixer
PTERM_SCALE = 0.032029
ITERM_SCALE = 0.244381
DTERM_SCALE = 0.000529
FEEDFORWARD_SCALE = 0.013754

# mittlerer Wind m/s, Böen σ_u m/s: Dryden (MIL-F-8785C) in 10 m Höhe, σ_w = 0,1·W20, σ_u = σ_w/0,204^0,4;
# leicht W20 = 15 kn, mäßig 30 kn. Längenmaße L_u = 67 m, L_w = 10 m (h = 10 m).
WIND = {"aus": (0.0, 0.0), "leicht": (3.0, 1.45), "stark": (7.0, 2.9)}
WIND_ORDER = ("aus", "leicht", "stark")
WIND_LABEL = {"aus": "aus", "leicht": "leicht · 3 m/s", "stark": "stark · 7 m/s"}

# LiPo-Leerlaufspannung je Zelle über der Ladung (typische Entladekurve, 0 = leer ... 1 = voll)
OCV = ((0.00, 3.27), (0.05, 3.50), (0.10, 3.62), (0.20, 3.70), (0.30, 3.75), (0.40, 3.79), (0.50, 3.83),
       (0.60, 3.87), (0.70, 3.93), (0.80, 4.00), (0.90, 4.08), (1.00, 4.20))


def ocv(soc):
    soc = 0.0 if soc < 0.0 else 1.0 if soc > 1.0 else soc
    for (s0, v0), (s1, v1) in zip(OCV, OCV[1:]):
        if soc <= s1:
            return v0 + (v1 - v0) * (soc - s0) / (s1 - s0)
    return OCV[-1][1]


@dataclass
class Pid:
    """Betaflight-Werte einer Achse (Konfigurator-Zahlen)."""
    p: float
    i: float
    d: float
    f: float


@dataclass
class RealParams:
    # --- Starrkörper (x rechts = Nick, y oben = Gier, z vorn = Roll)
    mass: float = 0.700                          # kg mit 6S 1300 mAh und Action-Cam-loser Ausrüstung
    inertia: tuple = (1.9e-3, 3.8e-3, 2.2e-3)    # kg·m² um x (Nick), y (Gier), z (Roll); Sun 2022/NeuroBEM 0,75 kg:
                                                 # diag(2,5 Roll; 2,1 Nick; 4,3 Gier) g·m², auf 5" (Arm 0,113 m) verkleinert
    arm_x: float = 0.080                         # m, Motor seitlich von der Mitte (Radstand 226 mm diagonal)
    arm_z: float = 0.080                         # m, Motor vorn/hinten
    # --- Antrieb: Motor 2207 1950 KV, Propeller 5,1 x 4,6 x 3, aus Prüfstands-Daten abgeleitet (siehe derive())
    kv_rpm: float = 1950.0                       # rpm/V
    prop_d: float = 0.1295                       # m (5,1")
    bench_v: float = 23.1                        # V am Prüfstand bei Vollgas (6S unter Last)
    bench_rpm: float = 30500.0                   # rpm bei Vollgas (Koko 2207 1950 KV: 30 474 rpm, 1605 g, 37,9 A)
    bench_thrust: float = 16.7                   # N (1,70 kgf; 51433: 1,61 kgf, 51466: 1,80 kgf)
    torque_ratio: float = 0.0135                 # m, k_m / k_f (Sun 2022: 0,0157; RotorS/Flightmare 0,016); mit I0
                                                 # ergibt das ~44 A je Motor bei Vollgas (Prüfstand 38-42 A)
    i0: float = 1.3                              # A Leerlaufstrom bei Vollgas-Drehzahl (Eisen/Lager, ∝ √ω)
    esc_eff: float = 0.95                        # ESC-Wirkungsgrad (Schaltverluste)
    rotor_inertia: float = 5.0e-6                # kg·m², Glocke + Propeller
    idle: float = 0.055                          # DShot-Idle 5,5 % (Betaflight dshot_idle_value 550)
    j0: float = 0.85                             # Fortschrittsgrad mit Schub 0 (Steigung 4,6"/5,1" + Profil)
    # --- Aerodynamik
    cda: tuple = (0.0150, 0.0180, 0.0095)        # m², ½ρ·CdA je Körperachse (Seite, oben/unten, vorn)
    rotor_drag: float = 0.35                     # 1/s bei Schwebedrehzahl: a = -c·(ω/ω_h)·v_quer (Blade Flapping;
                                                 # Sun 2022: 0,26-0,28 kg/s bei 0,75 kg, Faessler 2018: 0,24-0,54 1/s)
    trans_lift: float = 0.8                      # Schubzuwachs ~ c·μ² quer angeströmt (μ ≤ 0,5)
    ground_effect: bool = True
    vrs: float = 1.0                             # Wirbelring/Propwash-Stärke (0 = aus)
    rot_damping: float = 2.0e-5                  # N·m·s, Luftdämpfung der Rahmen-Drehung
    # --- Akku 6S 1300 mAh
    cells: int = 6
    capacity_ah: float = 1.30
    r_pack: float = 0.028                        # Ω, Innenwiderstand Pack + Kabel (≈4 mΩ/Zelle + 4 mΩ)
    i_base: float = 0.9                          # A, FC + Kamera + VTX
    battery: bool = True
    soc0: float = 1.0                            # Ladung beim Start (frischer Akku)
    # --- Betaflight 4.5 Standard-PIDs (Konfigurator-Zahlen)
    pid_roll: Pid = field(default_factory=lambda: Pid(45, 80, 30, 120))
    pid_pitch: Pid = field(default_factory=lambda: Pid(47, 84, 34, 125))
    pid_yaw: Pid = field(default_factory=lambda: Pid(45, 80, 0, 120))
    gyro_lpf_hz: float = 250.0                   # gyro_lpf1 (dynamisch 250-500 Hz), hier fest
    gyro_lpf2_hz: float = 500.0                  # gyro_lpf2
    dterm_lpf_hz: float = 100.0                  # dterm_lpf1 (dynamisch 75-150 Hz)
    ff_smooth_hz: float = 25.0                   # feedforward_smoothing (RC-Glättung)
    rc_smooth_hz: float = 40.0                   # rc_smoothing (auto): Setpoint/Gas PT2 ~40 Hz bei ~125-150 Hz Funk
    iterm_relax_hz: float = 15.0                 # iterm_relax_cutoff
    iterm_limit: float = 0.40                    # iterm_windup / pidsum
    pidsum_limit: float = 0.50                   # pidsum_limit (500)
    pidsum_limit_yaw: float = 0.40               # pidsum_limit_yaw (400)
    tpa_rate: float = 0.65                       # TPA auf D über tpa_breakpoint
    tpa_breakpoint: float = 0.35                 # 1350 µs
    airmode: bool = True
    loop_hz: float = 2000.0                      # interne Unterschritte (Regler + Motoren); Betaflight: 4-8 kHz
    # --- Umwelt
    wind: str = "aus"                            # "aus" / "leicht" / "stark"
    wind_dir_deg: float = 250.0                  # woher (meteorologisch), 250° = WSW
    noise: bool = True                           # Gyro-Rauschen + Vibration (wächst mit der Drehzahl)
    seed: int = 7
    # Kompatibilität (train_nn / Flight erwarten diese Felder)
    hover_throttle: float = 0.281
    drag: float = 0.033

    def derive(self):
        """k_f, k_m und den wirksamen Wicklungs-/ESC-Widerstand aus den Prüfstands-Daten ableiten."""
        kv = self.kv_rpm * RPM                      # rad/s pro V
        w = self.bench_rpm * RPM
        kf = self.bench_thrust / (w * w)
        km = kf * self.torque_ratio
        # stationär: u·V = ω/Kv + R·I,  I = Q/Kt + I0 = k_m ω² Kv + I0  ->  R = (V - ω/Kv) / I
        r = (self.bench_v - w / kv) / (km * w * w * kv + self.i0)
        return kv, kf, km, r


class RealDrone:
    """Echte 5"-Drohne mit Betaflight. Gleiche Schnittstelle wie sim.SimDrone."""

    def __init__(self, pos=(0.0, 1.0, 0.0), quat=(0.0, 0.0, 0.0, 1.0), vel=(0.0, 0.0, 0.0),
                 params=None, rates=None):
        from ..rates import Rates
        self.p = p = params or RealParams()
        self.rates = rates or Rates()
        self.pos, self.quat, self.vel = tuple(pos), tuple(quat), tuple(vel)
        self.omega = (0.0, 0.0, 0.0)
        self.t = 0.0
        self.ground = 0.0
        self.ground_level = 0.0
        self.sticks = (0.0, 0.0, 0.0, 0.0)
        self.kv, self.kf, self.km, self.r_m = p.derive()
        self.kt = 1.0 / self.kv
        self.w_bench = p.bench_rpm * RPM
        self.area = math.pi * (p.prop_d / 2) ** 2
        # Motoren: Position im Körper (x, z), Drehsinn s (+1 = um +y), Betaflight-Reihenfolge 1 HR, 2 VR, 3 HL, 4 VL
        ax, az = p.arm_x, p.arm_z
        self.mpos = ((ax, -az), (ax, az), (-ax, -az), (-ax, az))
        self.spin = (1, -1, -1, 1)                  # „Props out“ wäre umgekehrt, für die Physik egal
        # Mixer (Betaflight-Tabelle, ±1): Moment um x aus Schub = -z·T, um z = x·T, um y = Rückdrehmoment -s·Q
        self.mix = tuple((-math.copysign(1.0, pz), -s, math.copysign(1.0, px))
                         for (px, pz), s in zip(self.mpos, self.spin))
        self.reset_state()

    # ------------------------------------------------------------------ Zustand
    def reset_state(self):
        p = self.p
        self.soc = p.soc0
        self.volts_ocv = p.cells * ocv(self.soc)
        self.volts = self.volts_ocv
        self.amps = p.i_base
        self.mah = 0.0
        self.amps_peak = 0.0
        self.volts_min = self.volts
        # Schwebedrehzahl als Startwert (wie sim.py: startet auf Schwebe-Niveau)
        w_h = math.sqrt(p.mass * G / 4.0 / self.kf)
        self.w_hover = w_h
        self.w = [w_h] * 4
        self.wdot = [0.0] * 4
        self.u = [0.0] * 4
        self.thrusts = [p.mass * G / 4.0] * 4
        self.thrust = G                              # m/s² entlang der Achse (Anzeige / Kompatibilität)
        self.motor = 0.0
        # Regler
        self.g1 = [0.0, 0.0, 0.0]                    # Gyro nach lpf1 (deg/s)
        self.g2 = [0.0, 0.0, 0.0]                    # Gyro nach lpf2 (deg/s)
        self.dlast = [0.0, 0.0, 0.0]
        self.dterm = [0.0, 0.0, 0.0]
        self.iterm = [0.0, 0.0, 0.0]
        self.sp_last = [0.0, 0.0, 0.0]
        self.ff = [0.0, 0.0, 0.0]
        self.sp_lp = [0.0, 0.0, 0.0]
        self.pidsum = [0.0, 0.0, 0.0]
        self.saturated = False
        self.rc1 = None                              # rc_smoothing: Setpoint + Gas, zwei PT1 hintereinander
        self.rc2 = None
        # Umwelt
        self.rng = random.Random(self.p.seed)
        self.gust = [0.0, 0.0, 0.0]
        self.vrs_n = [0.0] * 4
        self.wash = 0.0
        self.contact = 0.0                           # s seit dem letzten Aufprall (für Kollisionen)

    @property
    def charge(self):
        return self.soc

    @property
    def cell_volts(self):
        return self.volts / self.p.cells

    # ------------------------------------------------------------------ Wind
    def wind_vec(self, dt):
        p = self.p
        mean, sigma = WIND.get(p.wind, (0.0, 0.0))
        if mean <= 0.0 and sigma <= 0.0:
            return (0.0, 0.0, 0.0)
        a = math.radians(p.wind_dir_deg)
        # meteorologisch „woher“: Wind weht in Richtung -Herkunft; Welt: x Ost, z Nord
        mx, mz = -math.sin(a) * mean, -math.cos(a) * mean
        rng = self.rng
        # Böen: Gauß-Markov 1. Ordnung je Achse (Dryden 1. Ordnung): Korrelationszeit L/V, V = Fahrt durch die Luft
        v = max(3.0, math.sqrt(sum((self.vel[i] - ((mx, 0.0, mz)[i])) ** 2 for i in range(3))))
        for i, (L, sig) in enumerate(((67.0, sigma), (10.0, sigma * 0.53), (67.0, sigma))):
            k = min(1.0, dt * v / L)
            self.gust[i] += -self.gust[i] * k + sig * math.sqrt(2.0 * k) * rng.gauss(0.0, 1.0)
        # Bodennähe: weniger Wind (Grenzschicht, grob logarithmisch)
        h = max(0.3, self.pos[1] - self.ground_level)
        shear = min(1.0, math.log(h / 0.05) / math.log(10.0 / 0.05))
        return ((mx + self.gust[0]) * shear, self.gust[1] * shear, (mz + self.gust[2]) * shear)

    # ------------------------------------------------------------------ Schritt
    def step(self, throttle, yaw, pitch, roll, dt):
        p, r = self.p, self.rates
        n_sub = max(1, int(round(dt * p.loop_hz)))
        h = dt / n_sub
        # Setpoint (deg/s) aus den Rates, Körperachsen x = Nick, y = Gier, z = -Roll (wie Liftoff-nah)
        sp = (r.pitch.rate(pitch), r.yaw.rate(yaw), -r.roll.rate(roll))
        thr = 0.0 if throttle < 0.0 else 1.0 if throttle > 1.0 else throttle
        wind = self.wind_vec(dt)
        for _ in range(n_sub):
            self._substep(sp, thr, wind, h)
        self.t += dt
        self.sticks = (throttle, yaw, pitch, roll)

    def _substep(self, sp, thr, wind, h):
        p = self.p
        # ---------------- Betaflight: RC glätten (rc_smoothing), Gyro filtern, PID, Mixer
        raw = (sp[0], sp[1], sp[2], thr)
        if self.rc1 is None:
            self.rc1, self.rc2 = list(raw), list(raw)
        ac = h / (h + 1.0 / (2.0 * math.pi * p.rc_smooth_hz))
        r1, r2 = self.rc1, self.rc2
        for i in range(4):
            r1[i] += (raw[i] - r1[i]) * ac
            r2[i] += (r1[i] - r2[i]) * ac
        sp, thr = (r2[0], r2[1], r2[2]), r2[3]
        om = self.omega
        a1 = h / (h + 1.0 / (2.0 * math.pi * p.gyro_lpf_hz))
        a2 = h / (h + 1.0 / (2.0 * math.pi * p.gyro_lpf2_hz))
        ad = h / (h + 1.0 / (2.0 * math.pi * p.dterm_lpf_hz))
        af = h / (h + 1.0 / (2.0 * math.pi * p.ff_smooth_hz))
        ar = h / (h + 1.0 / (2.0 * math.pi * p.iterm_relax_hz))
        noise = 0.0
        if p.noise:
            u_avg = sum(self.u) * 0.25
            noise = 0.4 + 6.0 * u_avg * u_avg             # deg/s Rauschen (Rahmenvibration wächst mit der Drehzahl)
        tpa = 1.0
        if thr > p.tpa_breakpoint:
            tpa = 1.0 - p.tpa_rate * (thr - p.tpa_breakpoint) / (1.0 - p.tpa_breakpoint)
        gains = (p.pid_pitch, p.pid_yaw, p.pid_roll)
        out = [0.0, 0.0, 0.0]
        rng = self.rng
        for i in range(3):
            g = math.degrees(om[i])
            if noise:
                g += noise * rng.gauss(0.0, 1.0)
            self.g1[i] += (g - self.g1[i]) * a1
            self.g2[i] += (self.g1[i] - self.g2[i]) * a2
            gy = self.g2[i]
            k = gains[i]
            err = sp[i] - gy
            # P
            pt = PTERM_SCALE * k.p * err
            # D auf der Messung, gefiltert (Betaflight: D_min/D_max hier fest auf D)
            dg = (gy - self.dlast[i]) / h
            self.dlast[i] = gy
            self.dterm[i] += (dg - self.dterm[i]) * ad
            dt_ = -DTERM_SCALE * k.d * self.dterm[i] * tpa
            # Feedforward aus der (geglätteten) Setpoint-Änderung
            dsp = (sp[i] - self.sp_last[i]) / h
            self.sp_last[i] = sp[i]
            self.ff[i] += (dsp - self.ff[i]) * af
            ft = FEEDFORWARD_SCALE * k.f * self.ff[i] * 0.01
            # I mit I-Term-Relax (wenig I-Aufbau, solange der Setpoint schnell wechselt) und Anti-Windup
            self.sp_lp[i] += (sp[i] - self.sp_lp[i]) * ar
            relax = max(0.0, 1.0 - abs(sp[i] - self.sp_lp[i]) / 40.0) if i != 1 else 1.0
            if not self.saturated:
                self.iterm[i] += ITERM_SCALE * k.i * err * relax * h / 1000.0
            lim = p.iterm_limit
            self.iterm[i] = -lim if self.iterm[i] < -lim else lim if self.iterm[i] > lim else self.iterm[i]
            s = (pt + dt_ + ft) / 1000.0 + self.iterm[i]
            lim = p.pidsum_limit_yaw if i == 1 else p.pidsum_limit
            out[i] = -lim if s < -lim else lim if s > lim else s
        self.pidsum = out
        # Mixer mit Airmode (Betaflight mixer.c): Bereich > 1 -> herunterskalieren, sonst Gas verschieben
        mix = [c[0] * out[0] + c[1] * out[1] + c[2] * out[2] for c in self.mix]
        lo, hi = min(mix), max(mix)
        rng_ = hi - lo
        t = thr
        self.saturated = False
        if rng_ > 1.0:
            mix = [m / rng_ for m in mix]
            lo, hi = lo / rng_, hi / rng_
            t = 0.5 if p.airmode else t
            self.saturated = True
        if p.airmode:
            t = max(-lo, min(1.0 - hi, t))
        u = self.u
        for j in range(4):
            v = mix[j] + t
            v = 0.0 if v < 0.0 else 1.0 if v > 1.0 else v
            if v <= 0.0 or v >= 1.0:
                self.saturated = self.saturated or not p.airmode
            u[j] = p.idle + (1.0 - p.idle) * v

        # ---------------- Luft am Körper
        q = self.quat
        air_w = (self.vel[0] - wind[0], self.vel[1] - wind[1], self.vel[2] - wind[2])
        bx, by, bz = qinvrot(q, air_w)                   # Anströmung im Körper (Fahrt durch die Luft)
        wx, wy, wz = om
        up_y = qrot(q, (0.0, 1.0, 0.0))[1]
        hgt = self.pos[1] - self.ground_level

        # ---------------- Motoren + Propeller
        kv, kt, kf, km, rm = self.kv, self.kt, self.kf, self.km, self.r_m
        V = self.volts if p.battery else p.bench_v
        D = p.prop_d
        R = D * 0.5
        jr = p.rotor_inertia
        Fx = Fy = Fz = 0.0
        Mx = My = Mz = 0.0
        Hy = 0.0
        I_bat = p.i_base
        wash = 0.0
        w_h = self.w_hover
        for j in range(4):
            px, pz = self.mpos[j]
            s = self.spin[j]
            w = self.w[j]
            # Anströmung am Rotor: v + ω × r  (r = (px, 0, pz))
            vx = bx + (wy * pz)
            vy = by + (wz * px - wx * pz)
            vz = bz + (-wy * px)
            n = w / (2.0 * math.pi)
            vax = vy                                     # + = Luft kommt von oben (Steigen)
            J = vax / (n * D) if n > 1.0 else 0.0
            # Propeller-Kennlinie (UIUC, Dreiblatt 5"): C_T fällt mit J fast linear, C_P langsamer
            if J >= 0.0:
                ct = 1.0 - J / p.j0
                cp = 1.0 - 0.55 * J / p.j0
                if ct < -0.3:
                    ct = -0.3
                if cp < 0.15:
                    cp = 0.15
            else:                                        # Sinken: mehr Schub (bis zum Wirbelring)
                ct = 1.0 + min(0.25, -0.6 * J / p.j0)
                cp = 1.0 + min(0.15, -0.3 * J / p.j0)
            v_in = math.sqrt(vx * vx + vz * vz)
            mu = v_in / max(1.0, w * R)
            ct *= 1.0 + p.trans_lift * min(mu, 0.5) ** 2
            T = kf * w * w * ct
            # Wirbelring / Propwash: Sinkrate ~0,3-1,9 v_h entlang der Achse (Johnson NASA TP-2005-213477:
            # instabil bei Vz/vh = -0,5 ... -1,5), verschwindet mit Querfahrt (Drees: bis Vx/vh ~ 1)
            if p.vrs > 0.0 and vax < 0.0 and T > 0.05:
                vh = math.sqrt(T / (2.0 * RHO * self.area))
                x = -vax / vh
                if 0.3 < x < 1.9:
                    sev = math.sin(math.pi * (x - 0.3) / 1.6) * math.exp(-(v_in / (0.7 * vh)) ** 2) * p.vrs
                    # Turbulenz je Rotor (Gauß-Markov, ~30 Hz) -> ungleicher Schub -> Wackeln
                    nk = h / 0.03
                    self.vrs_n[j] += -self.vrs_n[j] * nk + math.sqrt(2.0 * nk) * self.rng.gauss(0.0, 1.0)
                    T *= max(0.3, 1.0 - sev * (0.30 + 0.25 * self.vrs_n[j]))
                    wash = max(wash, sev)
            # Bodeneffekt (Cheeseman-Bennett) je Rotor
            if p.ground_effect and hgt < 1.5:
                z = max(R * 0.6, (hgt + qrot(q, (px, 0.0, pz))[1]) / max(0.3, up_y))
                f = (R / (4.0 * z)) ** 2
                T /= (1.0 - min(0.3, f))
            if T < 0.0:
                T = 0.0 if J < p.j0 * 1.3 else T     # Windmühle: kein „Zug“ nach unten über 0
            self.thrusts[j] = T
            Q = km * w * w * cp
            # Gleichstrom-Motor: I = (u V - ω/Kv)/R, Moment Kt I (negativ = aktives Bremsen / Damped Light)
            uj = self.u[j]
            I_m = (uj * V - w / kv) / rm
            i0 = p.i0 * math.sqrt(w / self.w_bench) if w > 0.0 else 0.0     # Eisen-/Lagerverluste
            wdot = (kt * (I_m - i0) - Q) / jr
            self.wdot[j] = wdot
            w_new = w + wdot * h
            self.w[j] = w_new if w_new > 0.0 else 0.0
            I_bat += uj * I_m / p.esc_eff if I_m > 0.0 else uj * I_m * p.esc_eff
            # Kräfte im Körper: Schub +y, Rotor-Widerstand quer (∝ ω, Blade Flapping)
            cd = p.rotor_drag * p.mass * 0.25 * (w / w_h)
            fx = -cd * vx
            fz = -cd * vz
            Fx += fx
            Fy += T
            Fz += fz
            # Momente: r × F  (r = (px, 0, pz), F = (fx, T, fz))
            Mx += -pz * T
            My += pz * fx - px * fz
            Mz += px * T
            # Rückdrehmoment des Propellers + Hochdrehen der Rotoren um ±y
            My += -s * (Q + jr * wdot)
            Hy += s * jr * w
        self.wash = wash
        u_avg = sum(self.u) * 0.25
        self.motor = u_avg
        # ---------------- Akku
        if p.battery:
            self.amps = I_bat
            self.mah += I_bat * h / 3.6
            self.soc = max(0.0, p.soc0 - self.mah / (p.capacity_ah * 1000.0))
            self.volts_ocv = p.cells * ocv(self.soc)
            r_pack = p.r_pack * (1.0 + 1.5 * max(0.0, 0.2 - self.soc) / 0.2)   # leer: höherer Innenwiderstand
            v_target = self.volts_ocv - r_pack * I_bat
            self.volts += (max(p.cells * 2.8, v_target) - self.volts) * min(1.0, h / 0.002)   # Elko/Leitung glätten
            if I_bat > self.amps_peak:
                self.amps_peak = I_bat
            if self.volts < self.volts_min:
                self.volts_min = self.volts

        # ---------------- Rahmenwiderstand je Achse
        sp_ = math.sqrt(bx * bx + by * by + bz * bz)
        c = 0.5 * RHO * sp_
        Fx += -c * p.cda[0] * bx
        Fy += -c * p.cda[1] * by
        Fz += -c * p.cda[2] * bz
        # ---------------- Translation (Welt)
        m = p.mass
        fw = qrot(q, (Fx, Fy, Fz))
        ax_ = fw[0] / m
        ay_ = fw[1] / m - G
        az_ = fw[2] / m
        v = self.vel
        nv = (v[0] + ax_ * h, v[1] + ay_ * h, v[2] + az_ * h)
        self.vel = nv
        self.pos = (self.pos[0] + nv[0] * h, self.pos[1] + nv[1] * h, self.pos[2] + nv[2] * h)
        if self.pos[1] < self.ground:
            self.pos = (self.pos[0], self.ground, self.pos[2])
            self.vel = (nv[0] * 0.5, max(0.0, nv[1]), nv[2] * 0.5)
        self.thrust = sum(self.thrusts) / m
        # ---------------- Rotation (Körper): I ω̇ = M - ω × (I ω + H)
        Ix, Iy, Iz = p.inertia
        cr = p.rot_damping
        Mx -= cr * wx * abs(wx)
        My -= cr * wy * abs(wy)
        Mz -= cr * wz * abs(wz)
        Lx, Ly, Lz = Ix * wx, Iy * wy + Hy, Iz * wz
        gx = wy * Lz - wz * Ly
        gy = wz * Lx - wx * Lz
        gz = wx * Ly - wy * Lx
        om = (wx + (Mx - gx) / Ix * h, wy + (My - gy) / Iy * h, wz + (Mz - gz) / Iz * h)
        self.omega = om
        self.quat = integrate(q, om, h)

    def state(self):
        return State(self.t, self.pos, self.quat, self.vel, tuple(math.degrees(w) for w in self.omega),
                     self.sticks, self.t)

    # ------------------------------------------------------------------ Info
    def info(self):
        """Werte fürs OSD/Tests."""
        rpm = [w / RPM for w in self.w]
        return {"volts": self.volts, "cell": self.cell_volts, "amps": self.amps, "mah": self.mah,
                "soc": self.soc, "rpm": rpm, "wash": self.wash}


# ---------------------------------------------------------------------- Kollisionen
def collide(flight, d, vy_before, dt, radius, up_y):
    """Boden und Hindernisse für „Realistisch“: abprallen und kippen statt sofort Absturz.

    Rückgabe: None (weiterfliegen) oder Absturz-Grund. Harte Treffer bleiben Abstürze (Propeller/Rahmen
    brechen bei einer echten Drohne ab ~6-8 m/s Aufprall senkrecht zur Fläche)."""
    rng = getattr(d, "rng", random)
    d.contact = getattr(d, "contact", 0.0) + dt
    # Boden
    if d.pos[1] < radius:
        vn = -vy_before
        if vn > 7.0:
            return f"zu hart aufgeschlagen ({vn:.0f} m/s)"
        speed_h = math.hypot(d.vel[0], d.vel[2])
        if up_y < 0.0 and speed_h < 1.0 and abs(d.vel[1]) < 0.5:
            d.flip_time = getattr(d, "flip_time", 0.0) + dt
            if d.flip_time > 0.6:
                return "umgekippt (liegt auf dem Rücken)"
        else:
            d.flip_time = 0.0
        d.pos = (d.pos[0], radius, d.pos[2])
        if vn > 1.0 and d.contact > 0.05:
            _kick(d, rng, vn * 0.5 + speed_h * 0.2)
            d.contact = 0.0
        k = math.exp(-4.0 * dt)
        d.vel = (d.vel[0] * k, max(0.25 * vn if vn > 1.0 else 0.0, d.vel[1]), d.vel[2] * k)
        return None
    w = flight.world
    i = w.hit_index(d.pos)
    if i < 0:
        return None
    n, depth = box_normal(w, i, d.pos, radius)
    v = d.vel
    vn = -(v[0] * n[0] + v[1] * n[1] + v[2] * n[2])     # Geschwindigkeit in die Fläche hinein
    if vn > 6.0:
        return "Hindernis getroffen"
    # herausschieben, Normalanteil spiegeln (e = 0,3), tangential Reibung, Propeller-Schlag -> Drehung
    d.pos = (d.pos[0] + n[0] * (depth + 0.01), d.pos[1] + n[1] * (depth + 0.01), d.pos[2] + n[2] * (depth + 0.01))
    if vn > 0.0:
        e, fr = 0.3, 0.7
        vt = (v[0] + vn * n[0], v[1] + vn * n[1], v[2] + vn * n[2])
        d.vel = (vt[0] * fr + e * vn * n[0], vt[1] * fr + e * vn * n[1], vt[2] * fr + e * vn * n[2])
        if d.contact > 0.05:
            _kick(d, rng, 1.0 + vn)
        d.contact = 0.0
    if w.hit_index(d.pos) >= 0:                          # klemmt (Ecke): dann doch Absturz
        return "Hindernis getroffen"
    return None


def _kick(d, rng, strength):
    """Propeller-/Rahmenschlag: zufällige Drehung (rad/s), stärker bei härterem Aufprall."""
    s = min(25.0, 4.0 * strength)
    om = d.omega
    d.omega = (om[0] + rng.uniform(-s, s), om[1] + rng.uniform(-0.3 * s, 0.3 * s), om[2] + rng.uniform(-s, s))


def box_normal(world, i, p, radius):
    """Außennormale (Welt) und Eindringtiefe der Box i am Punkt p."""
    cx, cy, cz = world.bc[i]
    hx, hy, hz = world.bh[i]
    cs, sn = float(world.bcos[i]), float(world.bsin[i])
    dx, dy, dz = p[0] - cx, p[1] - cy, p[2] - cz
    lx = cs * dx - sn * dz
    lz = sn * dx + cs * dz
    qx, qy, qz = abs(lx) - hx, abs(dy) - hy, abs(lz) - hz
    if max(qx, qy, qz) > 0.0:                            # Mittelpunkt außerhalb: Richtung zum nächsten Punkt
        ox, oy, oz = max(qx, 0.0) * math.copysign(1, lx), max(qy, 0.0) * math.copysign(1, dy), \
            max(qz, 0.0) * math.copysign(1, lz)
        dist = math.sqrt(ox * ox + oy * oy + oz * oz) or 1e-6
        nlx, nly, nlz = ox / dist, oy / dist, oz / dist
        depth = max(0.0, radius - dist)
    else:                                                # innen: kürzester Weg hinaus
        k = max(range(3), key=lambda j: (qx, qy, qz)[j])
        nlx, nly, nlz = [(math.copysign(1, lx), 0, 0), (0, math.copysign(1, dy), 0), (0, 0, math.copysign(1, lz))][k]
        depth = radius - (qx, qy, qz)[k]
    # lokal -> Welt (Inverse der Drehung oben)
    nx = cs * nlx + sn * nlz
    nz = -sn * nlx + cs * nlz
    return (nx, nly, nz), depth


def make(pos, rates, quat=(0.0, 0.0, 0.0, 1.0), wind="aus"):
    return RealDrone(pos=pos, quat=quat, params=RealParams(wind=wind), rates=rates)


_CTL = {}


def controller_thrust(base, params=None):
    """ThrustModel für die Autopiloten, so „vermessen“ wie sysid es an der echten Drohne täte.

    Statische Beschleunigung über dem Gas bei vollem Akku (ohne Rauschen) messen und als k·Gas^p mit
    gleichem Schwebepunkt anpassen; Inflow aus der Propellerkennlinie (Schubverlust je m/s axial bei Vollgas).
    Ohne das überschätzt das Liftoff-Modell (Schweben 0,281, p = 2) den Vollgas-Schub um ~30 %."""
    import dataclasses
    key = (id(params), repr(base))
    if key in _CTL:
        return _CTL[key]
    p = dataclasses.replace(params or RealParams(), noise=False, battery=False, wind="aus", vrs=0.0, ground_effect=False)

    def accel(thr, vax=0.0):
        d = RealDrone(pos=(0.0, 50.0, 0.0), params=p)
        for _ in range(300):
            d.vel, d.pos, d.quat, d.omega = (0.0, vax, 0.0), (0.0, 50.0, 0.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0)
            d.step(thr, 0.0, 0.0, 0.0, 0.002)
        return d.thrust
    lo, hi = 0.05, 0.6
    for _ in range(20):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if accel(mid) < G else (lo, mid)
    hover = 0.5 * (lo + hi)
    full = accel(1.0)
    expo = math.log(full / G) / math.log(1.0 / hover)
    inflow = (full - accel(1.0, 10.0)) / 10.0
    _CTL[key] = m = dataclasses.replace(base, hover_throttle=round(hover, 3), exponent=round(expo, 3),
                                        inflow=round(inflow, 2))
    m.real = True                                    # Merker für gains_for (eigene Reglerwerte)
    return m


# Eigene Reglerwerte der Autopiloten für „Realistisch“ (die alten bleiben für Klassisch/Liftoff-nah): Drehraten-
# Befehle 30 ms glätten. Betaflights Airmode setzt bei gesättigtem Mixer das Gas auf 0,5 – springen die Befehle
# (Sturzflug fast senkrecht, Gierrichtung schlecht bestimmt), stieg die Drohne mit Gas 0,16 auf 240 m.
# Bomben (20 Ziele): ohne 2/20, 20 ms 9/20, 30 ms 14/20 (Liftoff-nah 15/20); Rennlinie k 0,6-1,1 unverändert 25/25.
REAL_GAINS = {"rate_smooth_tau": 0.03}


def gains_for(thrust, gains):
    """gains (control.Gains) für das Schubmodell: bei controller_thrust (Realistisch) mit REAL_GAINS."""
    if getattr(thrust, "real", False):
        import dataclasses
        return dataclasses.replace(gains, **REAL_GAINS)
    return gains


def ap_thrust(base, physics=None):
    """Schubmodell für die Autopiloten: bei Physik „Realistisch“ das vermessene, sonst unverändert base."""
    if physics is None:
        from .game import PHYSICS as physics
    return controller_thrust(base) if physics == "real" else base
