"""Racing flight controller for Liftoff in acro (rate) mode.

Cascade, 250-500 Hz:
  desired acceleration (world)  ->  thrust direction + collective thrust
  thrust direction + heading    ->  body rates (tilt first, yaw second)
  body rates                    ->  sticks through the inverse Betaflight rate curve
  collective thrust             ->  throttle through the learned thrust model

There is no tilt limit: at full speed the drone flies nose-down at 60-75 degrees.
An online disturbance estimate (measured minus commanded acceleration) absorbs drag
and thrust-model errors, similar to INDI on real racing drones.
"""
import math
from dataclasses import dataclass, field

from .geometry import (add, body_axes, clamp, cross, dot, mul, norm, qinvrot, sub, unit)
from .rates import Rates

G = 9.81
UP = (0.0, 1.0, 0.0)


@dataclass
class ThrustModel:
    """accel along body-up [m/s^2] = k * throttle^p  (p=1 linear, fitted by sysid)."""
    hover_throttle: float = 0.28
    exponent: float = 1.0
    min_throttle: float = 0.0
    max_throttle: float = 1.0

    @property
    def k(self):
        return G / self.hover_throttle ** self.exponent

    @property
    def max_accel(self):
        return self.k * self.max_throttle ** self.exponent

    def throttle(self, accel):
        if accel <= 0:
            return self.min_throttle
        return clamp((accel / self.k) ** (1.0 / self.exponent), self.min_throttle, self.max_throttle)

    def accel(self, throttle):
        return self.k * max(0.0, throttle) ** self.exponent


@dataclass
class Gains:
    tilt: float = 14.0          # 1/s, tilt error -> body rate
    yaw: float = 4.0            # 1/s
    max_rate_dps: float = 560.0
    pos: float = 4.0            # 1/s^2
    vel: float = 4.5            # 1/s
    disturbance_tau: float = 0.12   # s, low-pass of the disturbance estimate
    disturbance_max: float = 45.0   # m/s^2
    drag: float = 0.0               # 1/m, quadratic drag a = -drag*|v|*v, measured in Liftoff
    min_vertical_accel: float = 2.0  # never command less than this along +y net of gravity (avoid inversion)


@dataclass
class Command:
    throttle: float
    yaw: float
    pitch: float
    roll: float

    def as_tuple(self):
        return self.throttle, self.yaw, self.pitch, self.roll


@dataclass
class FlightController:
    rates: Rates = field(default_factory=Rates)
    thrust: ThrustModel = field(default_factory=ThrustModel)
    gains: Gains = field(default_factory=Gains)

    def __post_init__(self):
        self.disturbance = (0.0, 0.0, 0.0)
        self._last_vel = None
        self._last_t = None
        self._last_cmd_accel = None
        self.debug = {}

    def reset(self):
        self.disturbance = (0.0, 0.0, 0.0)
        self._last_vel = self._last_t = self._last_cmd_accel = None

    # ------------------------------------------------------------------ estimation
    def observe(self, state):
        """Update the disturbance estimate from measured acceleration."""
        if self._last_t is not None and self._last_cmd_accel is not None:
            dt = state.t - self._last_t
            if 0.0005 < dt < 0.05:
                measured = mul(sub(state.vel, self._last_vel), 1.0 / dt)
                error = sub(measured, self._last_cmd_accel)
                a = clamp(dt / self.gains.disturbance_tau, 0.0, 1.0)
                d = add(self.disturbance, mul(sub(error, self.disturbance), a))
                n = norm(d)
                if n > self.gains.disturbance_max:
                    d = mul(d, self.gains.disturbance_max / n)
                self.disturbance = d
            elif dt <= 0 or dt > 0.2:
                self.reset()
        self._last_vel, self._last_t = state.vel, state.t

    # ------------------------------------------------------------------ control
    def track(self, state, p_ref, v_ref, a_ref, yaw_dir):
        """PD on position/velocity plus feed-forward acceleration."""
        g = self.gains
        a = add(a_ref, add(mul(sub(p_ref, state.pos), g.pos), mul(sub(v_ref, state.vel), g.vel)))
        return self.accel_command(state, a, yaw_dir)

    def accel_command(self, state, a_des, yaw_dir):
        """a_des: desired world acceleration (without gravity). yaw_dir: world direction to face."""
        g = self.gains
        drag = mul(state.vel, -g.drag * norm(state.vel))
        a_des = sub(sub(a_des, self.disturbance), drag)
        thrust_vec = add(a_des, (0.0, G, 0.0))
        if thrust_vec[1] < g.min_vertical_accel:
            thrust_vec = (thrust_vec[0], g.min_vertical_accel, thrust_vec[2])
        # cap the horizontal part so the available thrust can still hold height
        max_a = self.thrust.max_accel * 0.97
        n = norm(thrust_vec)
        if n > max_a:
            vert = thrust_vec[1]
            if vert >= max_a:
                thrust_vec = (0.0, max_a, 0.0)
            else:
                horiz = math.sqrt(max(0.0, max_a ** 2 - vert ** 2))
                h = math.hypot(thrust_vec[0], thrust_vec[2])
                thrust_vec = (thrust_vec[0] * horiz / h, vert, thrust_vec[2] * horiz / h)
        b3_des = unit(thrust_vec)
        right, up, fwd = body_axes(state.quat)
        # collective: project the desired thrust on the current body axis
        collective = max(0.0, dot(thrust_vec, up))
        throttle = self.thrust.throttle(collective)
        # nominal model acceleration; observe() attributes the rest to the disturbance
        self._last_cmd_accel = add(sub(mul(up, self.thrust.accel(throttle)), (0.0, G, 0.0)), drag)

        # tilt: rotate current up onto desired up
        axis_w = cross(up, b3_des)
        s = norm(axis_w)
        c = clamp(dot(up, b3_des), -1.0, 1.0)
        angle = math.atan2(s, c)
        omega = (0.0, 0.0, 0.0)
        if s > 1e-9:
            omega = mul(qinvrot(state.quat, mul(axis_w, 1.0 / s)), g.tilt * angle)
        # yaw: turn the body-forward (projected on the thrust plane) towards yaw_dir
        f_des = sub(yaw_dir, mul(b3_des, dot(yaw_dir, b3_des)))
        if norm(f_des) > 1e-6:
            f_des = unit(f_des)
            f_cur = unit(sub(fwd, mul(up, dot(fwd, up))))
            yaw_err = math.atan2(dot(cross(f_cur, f_des), up), dot(f_cur, f_des))
            # weight yaw down when the tilt error is large, tilt has priority
            omega = add(omega, mul((0.0, 1.0, 0.0), g.yaw * yaw_err * max(0.2, c)))
        max_r = math.radians(g.max_rate_dps)
        omega = tuple(clamp(w, -max_r, max_r) for w in omega)
        cmd = self.rates_to_sticks(omega, throttle)
        self.debug = {"tilt_err_deg": math.degrees(angle), "collective": collective, "omega": omega,
                      "b3_des": b3_des, "dist": self.disturbance}
        return cmd

    def rates_to_sticks(self, omega_body, throttle):
        """Body rates [rad/s] (Hamilton, Unity axes) -> sticks. +x pitch down, +y yaw right, -z roll right."""
        r = self.rates
        pitch = r.pitch.stick(math.degrees(omega_body[0]))
        yaw = r.yaw.stick(math.degrees(omega_body[1]))
        roll = r.roll.stick(math.degrees(-omega_body[2]))
        return Command(throttle, yaw, pitch, roll)
