"""Liftoff-like quadcopter model for offline tests (acro mode).

Not Liftoff's physics, but the same interface and the effects that matter for the
controller: rate tracking lag, motor lag, thrust curve, quadratic drag, gravity.
"""
import math
from dataclasses import dataclass

from .geometry import add, integrate, mul, norm, qrot, sub
from .rates import Rates
from .telemetry import State

G = 9.81


@dataclass
class SimParams:
    hover_throttle: float = 0.28
    thrust_exponent: float = 1.0
    rate_tau: float = 0.03      # s, Liftoff PID tracking lag
    motor_tau: float = 0.03     # s
    drag: float = 0.025         # 1/m, a_drag = -drag * |v| * v
    wind: tuple = (0.0, 0.0, 0.0)


class SimDrone:
    def __init__(self, pos=(0.0, 1.0, 0.0), quat=(0.0, 0.0, 0.0, 1.0), vel=(0.0, 0.0, 0.0),
                 params=SimParams(), rates=Rates()):
        self.pos, self.quat, self.vel = tuple(pos), tuple(quat), tuple(vel)
        self.p, self.rates = params, rates
        self.omega = (0.0, 0.0, 0.0)
        self.thrust = G
        self.t = 0.0
        self.sticks = (0.0, 0.0, 0.0, 0.0)

    def step(self, throttle, yaw, pitch, roll, dt):
        p = self.p
        target = (math.radians(self.rates.pitch.rate(pitch)), math.radians(self.rates.yaw.rate(yaw)),
                  -math.radians(self.rates.roll.rate(roll)))
        a = min(1.0, dt / p.rate_tau)
        self.omega = tuple(w + a * (tw - w) for w, tw in zip(self.omega, target))
        k = G / p.hover_throttle ** p.thrust_exponent
        thrust_target = k * max(0.0, throttle) ** p.thrust_exponent
        self.thrust += min(1.0, dt / p.motor_tau) * (thrust_target - self.thrust)
        up = qrot(self.quat, (0.0, 1.0, 0.0))
        air = sub(self.vel, p.wind)
        acc = add(mul(up, self.thrust), (0.0, -G, 0.0))
        acc = add(acc, mul(air, -p.drag * norm(air)))
        self.vel = add(self.vel, mul(acc, dt))
        self.pos = add(self.pos, mul(self.vel, dt))
        if self.pos[1] < 0.0:  # ground
            self.pos = (self.pos[0], 0.0, self.pos[2])
            self.vel = (self.vel[0] * 0.5, max(0.0, self.vel[1]), self.vel[2] * 0.5)
        self.quat = integrate(self.quat, self.omega, dt)
        self.t += dt
        self.sticks = (throttle, yaw, pitch, roll)

    def state(self):
        return State(self.t, self.pos, self.quat, self.vel, tuple(math.degrees(w) for w in self.omega),
                     self.sticks, self.t)
