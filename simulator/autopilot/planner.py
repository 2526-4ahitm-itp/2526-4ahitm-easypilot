"""Racing line through gates: Hermite spline + speed profile at the performance limit.

Gates are passed perpendicular to their opening. The speed profile limits
  lateral acceleration in curves (v^2 * kappa <= a_lat),
  acceleration and braking along the path (forward/backward pass).
`aggressiveness` (0..1) scales all limits, so tests can step up to full speed.
"""
import bisect
import math
from dataclasses import dataclass

from .geometry import add, cross, dot, mul, norm, sub, unit


@dataclass
class Gate:
    center: tuple          # world position of the opening centre [m]
    normal: tuple          # unit vector, direction of travel through the gate
    width: float = 2.0
    height: float = 2.0
    name: str = ""

    def crossed(self, p0, p1, margin=0.0):
        """True if the segment p0->p1 passes through the opening in travel direction."""
        a = dot(sub(p0, self.center), self.normal)
        b = dot(sub(p1, self.center), self.normal)
        if not (a < 0 <= b):
            return False
        t = a / (a - b)
        hit = add(p0, mul(sub(p1, p0), t))
        rel = sub(hit, self.center)
        side = unit(cross((0.0, 1.0, 0.0), self.normal), (1.0, 0.0, 0.0))
        up = cross(self.normal, side)
        return abs(dot(rel, side)) <= self.width / 2 - margin and abs(dot(rel, up)) <= self.height / 2 - margin


@dataclass
class Limits:
    max_speed: float = 40.0     # m/s
    lat_accel: float = 30.0     # m/s^2, centripetal
    accel: float = 18.0         # m/s^2 along the path
    brake: float = 22.0         # m/s^2 along the path
    drag: float = 0.0           # 1/m, quadratic drag: eats acceleration, helps braking

    def scaled(self, k):
        return Limits(self.max_speed * k, self.lat_accel * k, self.accel * k, self.brake * k, self.drag)

    @staticmethod
    def from_thrust(max_accel, max_speed=45.0, lateral_share=0.6, longitudinal_share=0.55, drag=0.0):
        """Limits that leave the controller a reserve: shares of the horizontal thrust at level height."""
        horizontal = (max(0.0, max_accel ** 2 - 9.81 ** 2)) ** 0.5
        return Limits(max_speed, horizontal * lateral_share, horizontal * longitudinal_share,
                      horizontal * longitudinal_share, drag)


def hermite(p0, m0, p1, m1, t):
    t2, t3 = t * t, t * t * t
    h00, h10, h01, h11 = 2 * t3 - 3 * t2 + 1, t3 - 2 * t2 + t, -2 * t3 + 3 * t2, t3 - t2
    return tuple(h00 * a + h10 * b + h01 * c + h11 * d for a, b, c, d in zip(p0, m0, p1, m1))


class RacingLine:
    def __init__(self, gates, start=None, start_dir=None, laps=1, limits=Limits(), aggressiveness=0.6,
                 step=0.25, tangent_scale=0.9, finish_extra=8.0):
        self.gates = list(gates)
        self.laps = laps
        self.limits = limits.scaled(aggressiveness)
        knots = []  # (point, unit tangent)
        if start is not None:
            first = self.gates[0].center
            knots.append((start, unit(start_dir or sub(first, start))))
        for _ in range(laps):
            knots += [(g.center, unit(g.normal)) for g in self.gates]
        last_c, last_n = knots[-1]
        knots.append((add(last_c, mul(last_n, finish_extra)), last_n))
        self.points = self._sample(knots, step, tangent_scale)
        self._arc_length()
        self._curvature()
        self._speed_profile()
        # gate order along the line (index into points), used for progress/timing
        self.gate_sequence = [g for _ in range(laps) for g in self.gates]

    def _sample(self, knots, step, tangent_scale):
        pts = [knots[0][0]]
        for (p0, d0), (p1, d1) in zip(knots, knots[1:]):
            dist = norm(sub(p1, p0))
            m0, m1 = mul(d0, dist * tangent_scale), mul(d1, dist * tangent_scale)
            n = max(2, int(dist / step * 1.3))
            for i in range(1, n + 1):
                pts.append(hermite(p0, m0, p1, m1, i / n))
        return pts

    def _arc_length(self):
        self.s = [0.0]
        for a, b in zip(self.points, self.points[1:]):
            self.s.append(self.s[-1] + norm(sub(b, a)))
        self.length = self.s[-1]
        n = len(self.points)
        self.tangent = []
        for i in range(n):
            a, b = self.points[max(0, i - 1)], self.points[min(n - 1, i + 1)]
            self.tangent.append(unit(sub(b, a), (0.0, 0.0, 1.0)))

    def _curvature(self):
        n = len(self.points)
        self.kappa_vec = []
        for i in range(n):
            i0, i1 = max(0, i - 2), min(n - 1, i + 2)
            ds = self.s[i1] - self.s[i0]
            if ds <= 1e-6:
                self.kappa_vec.append((0.0, 0.0, 0.0))
                continue
            self.kappa_vec.append(mul(sub(self.tangent[i1], self.tangent[i0]), 1.0 / ds))
        # smooth curvature (a racing drone cannot change its acceleration instantly)
        for _ in range(3):
            self.kappa_vec = [mul(add(add(self.kappa_vec[max(0, i - 1)], self.kappa_vec[i]),
                                      self.kappa_vec[min(n - 1, i + 1)]), 1 / 3) for i in range(n)]
        self.kappa = [norm(k) for k in self.kappa_vec]

    def _speed_profile(self):
        lim = self.limits
        v = [min(lim.max_speed, math.sqrt(lim.lat_accel / k) if k > 1e-6 else lim.max_speed) for k in self.kappa]
        v[-1] = min(v[-1], lim.max_speed)
        for i in range(1, len(v)):
            ds = self.s[i] - self.s[i - 1]
            # thrust left for accelerating after drag and climbing
            climb = 9.81 * max(0.0, self.tangent[i][1])
            a = max(0.5, lim.accel - lim.drag * v[i - 1] ** 2 - climb)
            v[i] = min(v[i], math.sqrt(v[i - 1] ** 2 + 2 * a * ds))
        for i in range(len(v) - 2, -1, -1):
            ds = self.s[i + 1] - self.s[i]
            v[i] = min(v[i], math.sqrt(v[i + 1] ** 2 + 2 * (lim.brake + 0.5 * lim.drag * v[i + 1] ** 2) * ds))
        self.speed = v
        self.lap_time_estimate = sum((self.s[i + 1] - self.s[i]) / max(0.5, 0.5 * (v[i] + v[i + 1]))
                                     for i in range(len(v) - 1))

    def closest(self, p, hint=0, window=400):
        """Index of the closest point, searched forward from `hint` (progress is monotonic)."""
        lo = max(0, hint - 20)
        hi = min(len(self.points), hint + window)
        best, best_d = hint, float("inf")
        for i in range(lo, hi):
            q = self.points[i]
            d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 + (q[2] - p[2]) ** 2
            if d < best_d:
                best, best_d = i, d
        return best

    def index_at(self, s):
        return min(len(self.s) - 1, bisect.bisect_left(self.s, s))

    def reference(self, i, lookahead_s=0.0):
        """Reference position, velocity and acceleration at path index i (+ lookahead)."""
        j = self.index_at(self.s[i] + lookahead_s)
        t, v = self.tangent[j], self.speed[j]
        # longitudinal acceleration from the profile
        k = min(len(self.s) - 1, j + 1)
        ds = max(1e-6, self.s[k] - self.s[j])
        a_long = (self.speed[k] ** 2 - v ** 2) / (2 * ds)
        a = add(mul(t, a_long), mul(self.kappa_vec[j], v * v))
        return self.points[j], mul(t, v), a, t
