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
    """accel along body-up [m/s^2] = k * throttle^p - inflow * throttle * v_axial  (p fitted by sysid).

    v_axial = velocity along body-up. Air coming from above (nose-down cruise) costs thrust, air from
    below (braking belly-first) adds thrust: 1.37 m/s^2 per m/s and full throttle, fitted from
    40 Liftoff runs (15.11.), residual 0.6 m/s^2. Without it the drone climbed 3 m when braking."""
    hover_throttle: float = 0.28
    exponent: float = 1.0
    min_throttle: float = 0.0
    max_throttle: float = 1.0
    inflow: float = 0.0          # Liftoff drone: 1.37 (sysid.load_model)

    @property
    def k(self):
        return G / self.hover_throttle ** self.exponent

    @property
    def max_accel(self):
        return self.k * self.max_throttle ** self.exponent

    def throttle(self, accel, v_axial=0.0):
        if accel <= 0:
            return self.min_throttle
        t = (accel / self.k) ** (1.0 / self.exponent)
        c = self.inflow * v_axial
        if c:
            for _ in range(6):        # Newton on k t^p - c t - accel = 0
                f = self.k * t ** self.exponent - c * t - accel
                df = self.k * self.exponent * t ** (self.exponent - 1) - c
                if df <= 1e-6:
                    break
                t = max(1e-4, t - f / df)
        return clamp(t, self.min_throttle, self.max_throttle)

    def accel(self, throttle, v_axial=0.0):
        t = max(0.0, throttle)
        return max(0.0, self.k * t ** self.exponent - self.inflow * t * v_axial)


@dataclass
class Gains:
    tilt: float = 14.0          # 1/s, tilt error -> body rate
    yaw: float = 4.0            # 1/s
    max_rate_dps: float = 560.0
    pos: float = 4.0            # 1/s^2
    vel: float = 4.5            # 1/s
    disturbance_tau: float = 0.25   # s, low-pass of the sideways disturbance estimate (world frame)
    disturbance_max: float = 15.0   # m/s^2
    thrust_tau: float = 0.12        # s, low-pass of the thrust error along the body axis
    thrust_offset_max: float = 25.0  # m/s^2
    drag: float = 0.0               # 1/m, quadratic drag a = -drag*|v|*v, measured in Liftoff
    min_vertical_accel: float = 0.8  # never command less than this along +y net of gravity (avoid inversion)
    dir_min_vertical: float = 4.9    # m/s^2: vertical part used for the thrust direction (tilt <= 63 deg unless braking/turning)
    idle_rate_share: float = 0.5     # body rate limit at idle throttle (airmode lift)
    hold_height: bool = True         # collective from the vertical need, not the projection (see accel_command)


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
        self.reset()
        self.debug = {}

    def reset(self):
        self.disturbance = (0.0, 0.0, 0.0)   # world, perpendicular to the body axis
        self.thrust_offset = 0.0              # m/s^2 along the body axis (thrust model error, ram air)
        self._last_vel = self._last_t = self._last_cmd_accel = self._last_up = None
        self._last_throttle, self._last_tilt_err = 1.0, 0.0

    @property
    def total_disturbance(self):
        up = self._last_up or (0.0, 1.0, 0.0)
        return add(self.disturbance, mul(up, self.thrust_offset))

    # ------------------------------------------------------------------ estimation
    def observe(self, state):
        """Update the estimates from the measured acceleration.

        The residual (measured minus nominal model) is split: along the body axis it is a thrust
        error (Liftoff's thrust changes with the air flowing through the props: less at speed, much
        more when the drone brakes belly-first), across it a slow world disturbance. Before the
        split, one world vector held both: when braking, the thrust surge of +20 m/s^2 turned into
        "go down", the target attitude flipped, the estimate followed the attitude and the drone
        tumbled with full sticks (Liftoff run AutumnFields01, 15.11.)."""
        if self._last_t is not None and self._last_cmd_accel is not None:
            dt = state.t - self._last_t
            # at idle or while the attitude still swings around, Liftoff's airmode raises the motors
            # for the rate demand: that is no thrust error, and learning it starts a tumble
            steady = self._last_throttle > 0.08 and self._last_tilt_err < math.radians(45)
            if 0.0005 < dt < 0.05 and not steady:
                pass
            elif 0.0005 < dt < 0.05:
                g = self.gains
                measured = mul(sub(state.vel, self._last_vel), 1.0 / dt)
                error = sub(measured, self._last_cmd_accel)
                up = self._last_up
                along = dot(error, up)
                a = clamp(dt / g.thrust_tau, 0.0, 1.0)
                self.thrust_offset = clamp(self.thrust_offset + (along - self.thrust_offset) * a,
                                           -g.thrust_offset_max, g.thrust_offset_max)
                across = sub(error, mul(up, along))
                a = clamp(dt / g.disturbance_tau, 0.0, 1.0)
                d = add(self.disturbance, mul(sub(across, self.disturbance), a))
                n = norm(d)
                if n > g.disturbance_max:
                    d = mul(d, g.disturbance_max / n)
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
        right, up, fwd = body_axes(state.quat)
        v_axial = dot(state.vel, up)
        full = self.thrust.accel(self.thrust.max_throttle, v_axial)
        max_a = max(0.5 * self.thrust.max_accel, full + self.thrust_offset) * 0.97
        n = norm(thrust_vec)
        if n > max_a:
            vert = thrust_vec[1]
            if vert >= max_a:
                thrust_vec = (0.0, max_a, 0.0)
            else:
                horiz = math.sqrt(max(0.0, max_a ** 2 - vert ** 2))
                h = math.hypot(thrust_vec[0], thrust_vec[2])
                thrust_vec = (thrust_vec[0] * horiz / h, vert, thrust_vec[2] * horiz / h)
        # direction: wanting to sink faster than gravity is no reason to lie flat - the tilt would
        # jump towards 90 deg, the full-stick rotation makes Liftoff's airmode spin the motors up and
        # the drone climbs instead (AutumnFields01, 15.11.). Cut the throttle and keep the tilt calm.
        b3_des = unit((thrust_vec[0], max(thrust_vec[1], g.dir_min_vertical), thrust_vec[2]))
        # collective: project the desired thrust on the current body axis
        # collective: while the attitude still turns, the projection on the current body axis gives
        # too much vertical thrust when braking (the drone climbs into the top bar of the next gate,
        # Liftoff test 15.11.). Keep the vertical component right instead, as long as the body is
        # upright enough; the horizontal part follows once the tilt is there.
        collective = max(0.0, dot(thrust_vec, up))
        if g.hold_height and up[1] > 0.35 and thrust_vec[1] > 0:
            collective = min(max(collective, 0.0) * 1.6 + 1.0, thrust_vec[1] / up[1])
        # the thrust error only changes the throttle, never the target attitude
        throttle = self.thrust.throttle(collective - self.thrust_offset, v_axial)
        # nominal model acceleration; observe() attributes the rest to the estimates
        self._last_cmd_accel = add(sub(mul(up, self.thrust.accel(throttle, v_axial)), (0.0, G, 0.0)), drag)
        self._last_up = up
        self._last_throttle = throttle

        # tilt: rotate current up onto desired up
        axis_w = cross(up, b3_des)
        s = norm(axis_w)
        c = clamp(dot(up, b3_des), -1.0, 1.0)
        angle = math.atan2(s, c)
        self._last_tilt_err = angle
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
        if throttle < 0.1:              # at idle every rate demand turns into airmode thrust
            max_r *= g.idle_rate_share
        omega = tuple(clamp(w, -max_r, max_r) for w in omega)
        cmd = self.rates_to_sticks(omega, throttle)
        self.debug = {"tilt_err_deg": math.degrees(angle), "collective": collective, "omega": omega,
                      "b3_des": b3_des, "dist": self.disturbance,
                      "thrust_offset": self.thrust_offset}
        return cmd

    def rates_to_sticks(self, omega_body, throttle):
        """Body rates [rad/s] (Hamilton, Unity axes) -> sticks. +x pitch down, +y yaw right, -z roll right."""
        r = self.rates
        pitch = r.pitch.stick(math.degrees(omega_body[0]))
        yaw = r.yaw.stick(math.degrees(omega_body[1]))
        roll = r.roll.stick(math.degrees(-omega_body[2]))
        return Command(throttle, yaw, pitch, roll)
