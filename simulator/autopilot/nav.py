"""Waypoint flight to a GPS coordinate, low over the ground, without collisions.

Pieces:
  GeoReference   GPS <-> Liftoff metres (local tangent plane around a reference point)
  OccupancyGrid  2.5-D map: per cell the highest obstacle top seen so far (+ free-space evidence)
  plan_path      A* on the grid inside the allowed height band, then shortcut smoothing
  Navigator      replans whenever the sensor adds obstacles, limits speed so that the
                 stopping distance always fits into the measured free space ahead
"""
import heapq
import math
from dataclasses import dataclass, field

from .geometry import add, mul, norm, sub, unit

EARTH_R = 6378137.0


@dataclass
class GeoReference:
    """Liftoff world origin (x right/east, z forward/north) placed at (lat0, lon0).

    `yaw_deg` rotates the map if Liftoff's +z should not point north.
    Default reference: HTL Leonding, Limesstraße 12-14.
    """
    lat0: float = 48.268611
    lon0: float = 14.251944
    origin_xz: tuple = (0.0, 0.0)
    yaw_deg: float = 0.0

    def to_world(self, lat, lon):
        north = math.radians(lat - self.lat0) * EARTH_R
        east = math.radians(lon - self.lon0) * EARTH_R * math.cos(math.radians(self.lat0))
        c, s = math.cos(math.radians(self.yaw_deg)), math.sin(math.radians(self.yaw_deg))
        x = east * c - north * s
        z = east * s + north * c
        return x + self.origin_xz[0], z + self.origin_xz[1]

    def to_gps(self, x, z):
        x, z = x - self.origin_xz[0], z - self.origin_xz[1]
        c, s = math.cos(math.radians(self.yaw_deg)), math.sin(math.radians(self.yaw_deg))
        east = x * c + z * s
        north = -x * s + z * c
        lat = self.lat0 + math.degrees(north / EARTH_R)
        lon = self.lon0 + math.degrees(east / (EARTH_R * math.cos(math.radians(self.lat0))))
        return lat, lon


class OccupancyGrid:
    """Sparse 2.5-D grid. `top[cell]` = highest obstacle point, `ground[cell]` = lowest ground seen."""

    def __init__(self, cell=0.5, ground_y=0.0):
        self.cell = cell
        self.top = {}
        self.ground = {}
        self.default_ground = ground_y
        self.version = 0

    def key(self, x, z):
        return (int(math.floor(x / self.cell)), int(math.floor(z / self.cell)))

    def center(self, k):
        return ((k[0] + 0.5) * self.cell, (k[1] + 0.5) * self.cell)

    def ground_at(self, k):
        return self.ground.get(k, self.default_ground)

    def add_point(self, p, ground_tolerance=0.35):
        """A 3-D surface point from the depth sensor. Points near the ground are ground, others obstacles."""
        k = self.key(p[0], p[2])
        g = self.ground.get(k)
        if p[1] < self.default_ground + ground_tolerance:
            if g is None or p[1] < g:
                self.ground[k] = p[1]
            return False
        if p[1] > self.top.get(k, -1e9):
            self.top[k] = p[1]
            self.version += 1
            return True
        return False

    def add_box(self, x0, z0, x1, z1, height):
        for i in range(int(math.floor(x0 / self.cell)), int(math.ceil(x1 / self.cell))):
            for j in range(int(math.floor(z0 / self.cell)), int(math.ceil(z1 / self.cell))):
                self.top[(i, j)] = max(self.top.get((i, j), -1e9), self.default_ground + height)
        self.version += 1

    def blocked(self, k, fly_y, clearance):
        """Cell blocked for flight at height fly_y (any obstacle top above fly_y - clearance)."""
        r = int(math.ceil(clearance / self.cell))
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if di * di + dj * dj > (r + 0.5) ** 2:
                    continue
                t = self.top.get((k[0] + di, k[1] + dj))
                if t is not None and t > fly_y - clearance:
                    return True
        return False

    def free_distance(self, p, direction, fly_y, clearance, max_range=40.0):
        """Distance along a horizontal direction until a blocked cell (for the speed limit)."""
        d = unit((direction[0], 0.0, direction[2]), (0.0, 0.0, 1.0))
        step = self.cell * 0.5
        s = 0.0
        while s < max_range:
            q = add(p, mul(d, s))
            if self.blocked(self.key(q[0], q[2]), fly_y, clearance):
                return s
            s += step
        return max_range


def plan_path(grid, start, goal, fly_y, clearance=0.8, max_nodes=40000, margin=25.0, closest_within=None):
    """A* (8-connected) at height fly_y; returns world (x, z) waypoints or None.

    With `closest_within` (m) an unreachable goal is replaced by the reachable cell closest to it,
    if that cell is not farther away than this.
    """
    s, g = grid.key(*start), grid.key(*goal)
    if closest_within is None and grid.blocked(g, fly_y, clearance):
        return None
    openq = [(0.0, s)]
    came = {s: None}
    cost = {s: 0.0}
    moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
             (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
    blocked_cache = {}

    def blocked(k):
        if k == s:
            return False
        b = blocked_cache.get(k)
        if b is None:
            b = blocked_cache[k] = grid.blocked(k, fly_y, clearance)
        return b

    # search only a corridor around start and goal, the grid itself is unbounded
    m = int(margin / grid.cell)
    lo_i, hi_i = min(s[0], g[0]) - m, max(s[0], g[0]) + m
    lo_j, hi_j = min(s[1], g[1]) - m, max(s[1], g[1]) + m
    n = 0
    while openq and n < max_nodes:
        _, cur = heapq.heappop(openq)
        n += 1
        if cur == g:
            break
        for di, dj, c in moves:
            nxt = (cur[0] + di, cur[1] + dj)
            if not (lo_i <= nxt[0] <= hi_i and lo_j <= nxt[1] <= hi_j) or blocked(nxt):
                continue
            if di and dj and (blocked((cur[0] + di, cur[1])) or blocked((cur[0], cur[1] + dj))):
                continue
            nc = cost[cur] + c
            if nc < cost.get(nxt, 1e18):
                cost[nxt] = nc
                came[nxt] = cur
                h = math.hypot(g[0] - nxt[0], g[1] - nxt[1])
                heapq.heappush(openq, (nc + h, nxt))
    end = g
    if g not in came:
        if closest_within is None or len(came) < 2:
            return None
        end = min(came, key=lambda k: (k[0] - g[0]) ** 2 + (k[1] - g[1]) ** 2)
        if math.hypot(end[0] - g[0], end[1] - g[1]) * grid.cell > closest_within:
            return None
        goal = grid.center(end)
    cells = []
    k = end
    while k is not None:
        cells.append(k)
        k = came[k]
    cells.reverse()
    pts = [start] + [grid.center(c) for c in cells[1:-1]] + [goal]
    return shortcut(grid, pts, fly_y, clearance)


def segment_free(grid, a, b, fly_y, clearance):
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(1, int(d / (grid.cell * 0.5)))
    for i in range(n + 1):
        t = i / n
        k = grid.key(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        if grid.blocked(k, fly_y, clearance):
            return False
    return True


def shortcut(grid, pts, fly_y, clearance):
    out = [pts[0]]
    i = 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not segment_free(grid, pts[i], pts[j], fly_y, clearance):
            j -= 1
        out.append(pts[j])
        i = j
    return out


@dataclass
class NavLimits:
    max_speed: float = 14.0       # m/s, low flight
    accel: float = 8.0            # m/s^2 used for speed planning
    brake: float = 9.0            # m/s^2 assumed available for braking
    reaction: float = 0.25        # s, sensing + control latency
    altitude: float = 1.5         # m above ground
    clearance: float = 0.9        # m, drone radius + margin
    arrive_radius: float = 0.6
    sensor_range: float = 15.0    # m, beyond this nothing is known -> treat as the end of free space


@dataclass
class Navigator:
    grid: OccupancyGrid
    goal_xz: tuple
    limits: NavLimits = field(default_factory=NavLimits)

    def __post_init__(self):
        self.requested_goal = self.goal_xz
        self.path = None
        self.grid_version = -1
        self.seg = 0
        self.status = "PLAN"
        self.debug = {}
        self.calls_without_path = 0

    def fly_y(self, x, z):
        return self.grid.ground_at(self.grid.key(x, z)) + self.limits.altitude

    def nearest_free(self, xz, y, max_radius=15.0):
        """Goal inside an obstacle (e.g. a GPS point on a house): use the closest reachable cell."""
        g = self.grid
        k0 = g.key(*xz)
        if not g.blocked(k0, y, self.limits.clearance):
            return xz
        r_max = int(max_radius / g.cell)
        for r in range(1, r_max + 1):
            ring = [(k0[0] + i, k0[1] + j) for i in range(-r, r + 1) for j in range(-r, r + 1)
                    if max(abs(i), abs(j)) == r]
            ring.sort(key=lambda k: (k[0] - k0[0]) ** 2 + (k[1] - k0[1]) ** 2)
            for k in ring:
                if not g.blocked(k, y, self.limits.clearance):
                    return g.center(k)
        return None

    def replan(self, pos):
        y = self.fly_y(pos[0], pos[2])
        self.grid_version = self.grid.version
        target = self.nearest_free(self.requested_goal, y)
        if target is None:
            self.path, self.status = None, "NO_PATH"
            return
        self.goal_xz = target
        start = (pos[0], pos[2])
        self.path = plan_path(self.grid, start, self.goal_xz, y, self.limits.clearance)
        if self.path is None:
            # e.g. the drone already stands closer to an obstacle than the margin: squeeze out slowly
            self.path = plan_path(self.grid, start, self.goal_xz, y, self.limits.clearance * 0.7)
        if self.path is None:
            # goal enclosed (inside an obstacle whose walls we have seen): closest reachable point
            self.path = plan_path(self.grid, start, self.requested_goal, y, self.limits.clearance,
                                  closest_within=15.0)
            if self.path:
                self.goal_xz = self.path[-1]
        self.grid_version = self.grid.version
        self.seg = 0
        self.status = "FLY" if self.path else "NO_PATH"

    def reference(self, pos, vel):
        """Desired position/velocity/acceleration and look direction for the FlightController."""
        lim = self.limits
        # plan only when the map changed: without a path, retrying on the same map is useless
        # (and an exhaustive A* every control step would stall the loop)
        if self.path is None:
            self.calls_without_path += 1
        retry = self.path is None and self.calls_without_path % 125 == 0     # ~every 0.5 s at 250 Hz
        if self.grid.version != self.grid_version or retry:
            if self.path is None or not self._path_still_free(pos):
                self.replan(pos)
            else:
                self.grid_version = self.grid.version
        if not self.path:
            return self._hold(pos)
        # advance along the polyline
        while self.seg < len(self.path) - 2:
            a, b = self.path[self.seg], self.path[self.seg + 1]
            ab = (b[0] - a[0], b[1] - a[1])
            l2 = ab[0] ** 2 + ab[1] ** 2
            t = ((pos[0] - a[0]) * ab[0] + (pos[2] - a[1]) * ab[1]) / l2 if l2 > 0 else 1.0
            if t >= 1.0 or math.hypot(pos[0] - b[0], pos[2] - b[1]) < 1.0:
                self.seg += 1
            else:
                break
        a, b = self.path[self.seg], self.path[self.seg + 1]
        ab = (b[0] - a[0], b[1] - a[1])
        l = math.hypot(*ab) or 1e-6
        u = (ab[0] / l, ab[1] / l)
        t = max(0.0, min(l, (pos[0] - a[0]) * u[0] + (pos[2] - a[1]) * u[1]))
        closest = (a[0] + u[0] * t, a[1] + u[1] * t)
        remaining = l - t + sum(math.dist(p, q) for p, q in zip(self.path[self.seg + 1:], self.path[self.seg + 2:]))
        goal_dist = math.hypot(pos[0] - self.goal_xz[0], pos[2] - self.goal_xz[1])
        if goal_dist < lim.arrive_radius and norm(vel) < 0.8:
            self.status = "ARRIVED"
        # speed: stop at the goal, slow down for the next corner, never faster than the free space allows
        v_goal = math.sqrt(2 * lim.brake * 0.6 * max(0.0, remaining))
        v_corner = lim.max_speed
        if self.seg + 2 < len(self.path):
            c = self.path[self.seg + 2]
            bc = (c[0] - b[0], c[1] - b[1])
            lb = math.hypot(*bc) or 1e-6
            cos_turn = (u[0] * bc[0] + u[1] * bc[1]) / lb
            v_turn = lim.max_speed * max(0.15, (1 + cos_turn) / 2)
            v_corner = math.sqrt(v_turn ** 2 + 2 * lim.brake * 0.6 * max(0.0, l - t))
        y = self.fly_y(pos[0], pos[2])
        free = self.grid.free_distance(pos, (u[0], 0.0, u[1]), y, lim.clearance * 0.8, lim.sensor_range)
        v_free = max(0.0, -lim.brake * lim.reaction + math.sqrt((lim.brake * lim.reaction) ** 2 + 2 * lim.brake * max(0.0, free - 0.5)))
        v = min(lim.max_speed, v_goal, v_corner, v_free)
        lead = min(2.0, max(0.5, 0.3 * v))
        tgt = (closest[0] + u[0] * lead, closest[1] + u[1] * lead) if remaining > lead else self.goal_xz
        p_ref = (tgt[0], y, tgt[1])
        v_ref = (u[0] * v, 0.0, u[1] * v)
        self.debug = dict(v=v, v_free=v_free, free=free, remaining=remaining, seg=self.seg)
        return p_ref, v_ref, (0.0, 0.0, 0.0), (u[0], 0.0, u[1])

    def _path_still_free(self, pos):
        y = self.fly_y(pos[0], pos[2])
        pts = [(pos[0], pos[2])] + self.path[self.seg + 1:]
        return all(segment_free(self.grid, a, b, y, self.limits.clearance) for a, b in zip(pts, pts[1:]))

    def _hold(self, pos):
        y = self.fly_y(pos[0], pos[2])
        return (pos[0], y, pos[2]), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)
