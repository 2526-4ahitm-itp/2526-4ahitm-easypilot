"""Racing line around solid items: elastic-band repair (used by build_line in race.py).

Chosen 16.11. from three strategies built and measured side by side (iterative vias, elastic band,
corridor search) on all 92 official races: planned lines touching a known item 46 -> 28, contact
points 356 -> 156, clean simulator flights at stage 3 49 -> 68 (stage 1 53 -> 74, stage 5 27 -> 39),
no race lost, fewer vias and less bending, every real gate still passed exactly, planning ~3x faster.

1. plan the line through the gates (align vias as before), no obstacle vias yet
2. sample it (0.5 m) and find the stretches that touch a solid item (numpy, exact pp_contains maths)
3. per stretch: the cheapest common escape direction perpendicular to the line (exact ray/box slab
   test against every nearby item + terrain), required push per sample
4. elastic band on the displacement field: stiffness (2nd difference) + a little tension, obstacle
   constraints as inequalities (active set), zero displacement and zero slope at the window ends,
   real gate knots never move
5. fit a few well spaced vias to the band (peak first, >= 3 m apart, >= 1.5 m from real gates,
   existing vias in the window are moved with the band instead of adding new ones next to them)
6. rebuild the RacingLine and verify the final spline; repeat for what is still touching with more
   clearance there; keep the best line
Items whose box contains a real gate centre (mesh bounds of light gates over the whole opening) are
passable by design and cannot be avoided without moving the gate: they are ignored.
Floors / platforms count as ground only from above: below them (ceiling) the normal margin applies.

The via fit runs in up to three passes (build_line), each going on from the best line so far:
  A  plain fit: one via at the band peak / worst node (cheap, most races are clean after it)
  B  only if still touching: vias further out (gain 1.3 / 1.6), two vias at the ends of a wide band,
     existing (align) vias pushed along the band
  C  only if still touching: free 3D band (each node pushed along its own cheapest escape direction)
The line with the fewest touching samples (then fewest vias) wins. Real gate knots are never moved.
"""
import math

import numpy as np

import threading

from .envdb import GROUND_CLEARANCE, ObstacleSet
from .planner import Gate, Limits, RacingLine

CHECK_R = 0.40        # detection margin (line_hits uses 0.35)
BAND_R = 0.60         # clearance the band pushes to
BAND_R_STEP = 0.20    # more clearance per retry at the same spot
GROUND_EXTRA = 0.25   # band: extra room above terrain / floors
GATE_FIX = 1.0        # m around a real gate knot: band does not move the line
VIA_GATE = 1.6        # m min distance via <-> real gate knot
VIA_SPACING = 3.0     # m between vias of one band
EXT = 7.0             # m band window beyond the touching stretch
NODE = 0.5            # m band node spacing
ROUNDS = 4
UP_W = 0.6      # vertical bumps cost speed (no pulling down harder than g)
DOWN_W = 1.0  # below: sag at speed, ground
IGNORE_R = 2.5       # m around a gate its own blocking item is passable
START_SKIP = 1.5      # m: the start point itself cannot move


# ------------------------------------------------------------------ fast obstacle queries
class FastObs:
    def __init__(self, obs):
        items = obs.items
        k = len(items)
        pp = np.array([it[1] for it in items], float).reshape(-1, 4, 3)
        self.O = pp[:, 0, :]
        m = np.transpose(pp[:, 1:, :], (0, 2, 1))          # columns = edges
        det = np.linalg.det(m) if k else np.zeros(0)
        self.ok = np.abs(det) > 1e-12
        inv = np.zeros_like(m)
        if self.ok.any():
            inv[self.ok] = np.linalg.inv(m[self.ok])
        self.Inv = inv                                       # rows: dual vectors, u = Inv @ (p - o)
        # clamp only edges of exactly zero length, like gatedb.pp_contains: a slab 2e-16 m thin
        # (MinusTwo "Fake Floor") otherwise lost its whole margin and the band flew through it
        L = np.linalg.norm(pp[:, 1:, :], axis=2)
        self.L = np.where(L > 0, L, 1e-9)
        self.floor = np.zeros(k, bool)
        if obs.floor:
            self.floor[list(obs.floor)] = True
        self.grid, self.cell, self.terrain = obs.grid, obs.cell, obs.terrain
        self.ignore = np.zeros(k, bool)
        self.ign_c = {}
        # floors (platforms, roofs) are only ground from above: their underside is a ceiling the drone
        # passes below - there it keeps the normal clearance (HannoverRace03: climbing out from under
        # a platform at 0.3 m the drone scraped its edge). Vertical edge axis and on which side "below" is.
        ey = pp[:, 1:, 1] / self.L                             # (k, 3) vertical share of each edge
        self.fax = np.argmax(np.abs(ey), axis=1)
        self.fdown = ey[np.arange(k), self.fax] > 0             # edge points up: below is u < 0

    def with_gates(self, centers):
        """Copy that treats items containing a real gate centre as passable right at that gate
        (mesh bounds of light gates span the whole opening) - a big item elsewhere still counts."""
        import copy
        fo = copy.copy(self)
        fo.ignore = np.zeros(len(self.ok), bool)
        fo.ign_c = {}
        for c in centers:
            idx = self.candidates(np.array([c], float), 0.5)
            if len(idx):
                ins = self._inside(np.array([c], float), idx, 0.35)[0]
                for i in idx[ins]:
                    fo.ignore[i] = True
                    fo.ign_c.setdefault(int(i), []).append(np.asarray(c, float))
        return fo

    def _mask_ignored(self, P, idx, inside):
        """Clear `inside` for gate items near the gate they contain."""
        cols = np.nonzero(self.ignore[idx])[0]
        for col in cols:
            cs = np.array(self.ign_c[int(idx[col])])
            d = np.linalg.norm(P[:, None, :] - cs[None], axis=2).min(axis=1)
            inside[d < IGNORE_R, col] = False
        return inside

    def candidates(self, P, r):
        c = self.cell
        lo = np.floor((P.min(axis=0) - r - 1.0) / c).astype(int)
        hi = np.floor((P.max(axis=0) + r + 1.0) / c).astype(int)
        out = set()
        for i in range(lo[0], hi[0] + 1):
            for j in range(lo[2], hi[2] + 1):
                out.update(self.grid.get((i, j), ()))
        if not out:
            return np.zeros(0, int)
        idx = np.fromiter(out, int)
        return idx[self.ok[idx]]

    def _bounds(self, idx, margin):
        # floors / roofs: the drone itself only - but the band pushes a bit past that, else the
        # repaired line ends exactly on the check boundary
        fl = GROUND_CLEARANCE + (GROUND_EXTRA if margin > CHECK_R + 1e-6 and CONF['floor_extra'] else 0.0)
        fi = self.floor[idx]
        m = np.where(fi, fl, margin)
        tol_lo = np.repeat(m[:, None], 3, axis=1) / self.L[idx]
        tol_hi = tol_lo.copy()
        if CEILING and fi.any():
            r = np.nonzero(fi)[0]
            ax = self.fax[idx[r]]
            ceil = max(margin, fl) / self.L[idx[r], ax]
            dn = self.fdown[idx[r]]
            tol_lo[r[dn], ax[dn]] = ceil[dn]
            tol_hi[r[~dn], ax[~dn]] = ceil[~dn]
        return -tol_lo, 1.0 + tol_hi

    def _inside(self, P, idx, margin):
        """bool (N, M): point n inside item idx[m] grown by margin."""
        u = np.einsum("mij,nmj->nmi", self.Inv[idx], P[:, None, :] - self.O[idx][None])
        lo, hi = self._bounds(idx, margin)
        return np.all((u >= lo[None]) & (u <= hi[None]), axis=2)

    def ground(self, x, z):
        g = np.full(np.shape(x), -np.inf)
        for t in self.terrain:
            u = (x - t.origin[0]) / t.size[0] * (t.nx - 1)
            v = (z - t.origin[2]) / t.size[2] * (t.nz - 1)
            ok = (u >= 0) & (u <= t.nx - 1) & (v >= 0) & (v <= t.nz - 1)
            if not ok.any():
                continue
            uu, vv = np.clip(u, 0, t.nx - 1), np.clip(v, 0, t.nz - 1)
            i0, j0 = uu.astype(int), vv.astype(int)
            i1, j1 = np.minimum(i0 + 1, t.nx - 1), np.minimum(j0 + 1, t.nz - 1)
            fu, fv = uu - i0, vv - j0
            h = t.h
            hh = (h[j0, i0].astype(float) * (1 - fu) * (1 - fv) + h[j0, i1].astype(float) * fu * (1 - fv) +
                  h[j1, i0].astype(float) * (1 - fu) * fv + h[j1, i1].astype(float) * fu * fv) + float(t.origin[1])
            g = np.where(ok, np.maximum(g, hh), g)
        return g

    def blocked(self, P, margin, gmargin=GROUND_CLEARANCE, use_ignore=True, chunk=48):
        """bool (N,) like ObstacleSet.blocked(p, margin) (ignored items left out)."""
        P = np.asarray(P, float)
        out = np.zeros(len(P), bool)
        if self.terrain:
            out |= P[:, 1] < self.ground(P[:, 0], P[:, 2]) + gmargin
        for a in range(0, len(P), chunk):
            Q = P[a:a + chunk]
            idx = self.candidates(Q, margin)
            if len(idx):
                ins = self._inside(Q, idx, margin)
                if use_ignore:
                    ins = self._mask_ignored(Q, idx, ins)
                out[a:a + chunk] |= ins.any(axis=1)
        return out

    def ray_escape(self, P, dirs, margin, gmargin, tmax=8.0):
        """(G, D): distance along each direction until the point is free of every item (and the
        terrain), exact slab maths for the boxes; inf if more than tmax."""
        dirs = np.asarray(dirs, float)
        if dirs.ndim == 2:
            dirs = np.broadcast_to(dirs[None], (len(P),) + dirs.shape)
        P = np.asarray(P, float)
        if len(P) > 12:
            # consecutive line samples are close together: small chunks see few items each
            return np.concatenate([self.ray_escape(P[a:a + 12], dirs[a:a + 12], margin, gmargin, tmax)
                                   for a in range(0, len(P), 12)])
        G, Dn = dirs.shape[0], dirs.shape[1]
        idx = self.candidates(P, tmax + margin)
        t = np.zeros((G, Dn))
        if len(idx):
            inv = self.Inv[idx]
            lo, hi = self._bounds(idx, margin)                       # (M, 3)
            u0 = np.einsum("mij,gmj->gmi", inv, P[:, None, :] - self.O[idx][None])   # G,M,3
            wb = np.einsum("mij,gdj->gdmi", inv, dirs)               # G,D,M,3
            u0b = u0[:, None]                                        # G,1,M,3
            small = np.abs(wb) < 1e-12
            with np.errstate(divide="ignore", invalid="ignore"):
                ta = (lo - u0b) / np.where(small, 1.0, wb)
                tb = (hi - u0b) / np.where(small, 1.0, wb)
            tmn, tmx = np.minimum(ta, tb), np.maximum(ta, tb)
            insl = (u0b >= lo) & (u0b <= hi)
            tmn = np.where(small, np.where(insl, -np.inf, np.inf), tmn)
            tmx = np.where(small, np.where(insl, np.inf, -np.inf), tmx)
            t0, t1 = tmn.max(axis=3), tmx.min(axis=3)               # G,D,M
            valid = t0 < t1
            # a gate's own blocking item does not count right at that gate (per start point)
            for col in np.nonzero(self.ignore[idx])[0]:
                cs = np.array(self.ign_c[int(idx[col])])
                close = np.linalg.norm(P[:, None, :] - cs[None], axis=2).min(axis=1) < IGNORE_R
                valid[close, :, col] = False
        low = np.zeros(t.shape, bool)
        for _ in range(40):
            if len(idx):
                for _ in range(30):
                    cov = valid & (t0 <= t[..., None]) & (t1 > t[..., None])
                    nt = np.maximum(t, np.where(cov, t1, -np.inf).max(axis=2) + 1e-4)
                    if np.array_equal(nt, t):
                        break
                    t = np.minimum(nt, tmax + 1.0)
            if not self.terrain:
                break
            Q = P[:, None, :] + t[..., None] * dirs
            deficit = self.ground(Q[..., 0], Q[..., 2]) + gmargin - Q[..., 1]
            low = (deficit > 0) & (t <= tmax)
            if not low.any():
                break
            step = np.clip(deficit / np.maximum(dirs[..., 1], 0.1), 0.1, 2.0)
            t = np.where(low, t + step, t)
        t = np.where(low, np.inf, t)
        return np.where(t > tmax, np.inf, t)


# ------------------------------------------------------------------ helpers
def _knot_index(seq, start, step=0.25):
    """Index into line.points of every knot of seq (RacingLine._sample layout, laps=1)."""
    pts = [start] + [g.center for g in seq]
    idx, n = [], 0
    for a, b in zip(pts, pts[1:]):
        d = math.dist(a, b)
        n += max(2, int(d / step * 1.3))
        idx.append(n)
    return idx


def _via(center, direction):
    g = Gate(tuple(float(v) for v in center), tuple(float(v) for v in direction), 6.0, 6.0, "via")
    g.via = True
    g.band = True
    return g


def _hit_count(line, fo, radius=0.35, step=0.5):
    """line_hits-style count (every >= 0.5 m), ignored gate items left out."""
    s = np.asarray(line.s)
    keep, last = [], -1e9
    for i, si in enumerate(s):
        if si - last >= step:
            keep.append(i)
            last = si
    P = np.asarray(line.points)[keep]
    return int(fo.blocked(P, radius).sum())


def _frames(T):
    """Per node unit side / up vectors perpendicular to the tangents T (n, 3)."""
    T = T / (np.linalg.norm(T, axis=1, keepdims=True) + 1e-12)
    side = np.cross(np.array([0.0, 1.0, 0.0])[None], T)
    bad = np.linalg.norm(side, axis=1) < 1e-6
    side[bad] = (1.0, 0.0, 0.0)
    side /= np.linalg.norm(side, axis=1, keepdims=True)
    up = np.cross(T, side)
    up /= np.linalg.norm(up, axis=1, keepdims=True)
    return side, up


N_ANG = 16
_ANG = np.arange(N_ANG) * 2 * math.pi / N_ANG


def _dirs(side, up, ang):
    """(n, len(ang), 3) escape directions at a fixed angle in each node's frame."""
    return np.cos(ang)[None, :, None] * side[:, None] + np.sin(ang)[None, :, None] * up[:, None]


def _solve_band(n, pins, fixed, beta=1.0, alpha=0.05, W=1e6):
    """Displacement (n, 3) minimising stiffness (2nd difference) + tension with pinned nodes.
    Symmetric pentadiagonal system: banded Cholesky (scipy) or dense fallback."""
    diag = np.zeros(n)
    off1 = np.zeros(n - 1)
    off2 = np.zeros(n - 2)
    # beta * D2^T D2
    for k in range(n - 2):
        idx = (k, k + 1, k + 2)
        c = (1.0, -2.0, 1.0)
        for a in range(3):
            diag[idx[a]] += beta * c[a] * c[a]
        off1[k] += beta * c[0] * c[1]
        off1[k + 1] += beta * c[1] * c[2]
        off2[k] += beta * c[0] * c[2]
    # alpha * D1^T D1
    diag[:-1] += alpha
    diag[1:] += alpha
    off1 -= alpha
    rhs = np.zeros((n, 3))
    for i in fixed:
        diag[i] += W
    for i, v in pins.items():
        diag[i] += W
        rhs[i] += W * v
    if _solveh_banded is not None:
        ab = np.zeros((3, n))
        ab[0, 2:] = off2
        ab[1, 1:] = off1
        ab[2] = diag
        return _solveh_banded(ab, rhs)
    A = np.diag(diag) + np.diag(off1, 1) + np.diag(off1, -1) + np.diag(off2, 2) + np.diag(off2, -2)
    return np.linalg.solve(A, rhs)


try:
    from scipy.linalg import solveh_banded as _solveh_banded
except Exception:          # pragma: no cover
    _solveh_banded = None


def _interp(s_nodes, s_all, A):
    return np.stack([np.interp(s_nodes, s_all, A[:, k]) for k in range(3)], axis=1)


def _scalar_band(n, need, fixed):
    """Scalar displacement f (n,) >= need where given, smooth (active set on the stiffness band)."""
    pins = {}
    f = np.zeros(n)
    for _ in range(30):
        f = _solve_band(n, {i: np.array([v, 0.0, 0.0]) for i, v in pins.items()}, fixed)[:, 0]
        viol = [(i, v - f[i]) for i, v in sorted(need.items()) if i not in pins and v - f[i] > 0.02]
        if not viol:
            break
        groups, cur = [], [viol[0]]
        for x in viol[1:]:
            if x[0] - cur[-1][0] <= 2:
                cur.append(x)
            else:
                groups.append(cur)
                cur = [x]
        groups.append(cur)
        for g in groups:
            i = max(g, key=lambda x: x[1])[0]
            pins[i] = need[i]
    return f


def _repair_window(line, fo, lo_hit, hi_hit, iv, base, spots, P_all, s_all, T_all):
    """Elastic band around the touching stretch [lo_hit, hi_hit] inside the free interval iv.
    One escape angle (in the local side/up frame) for the stretch, scalar push profile."""
    centre = _interp(np.array([(lo_hit + hi_hit) / 2]), s_all, P_all)[0]
    key = tuple(np.round(centre / 2.0).astype(int))
    # count from the start of the round: with laps > 1 the same spot comes once per lap, lap 2 got
    # more margin than lap 1 and a worse line (MinusTwo04 two laps: 18 contacts in lap 2, 16.11.)
    margin = BAND_R + BAND_R_STEP * base.get(key, 0)
    spots[key] = base.get(key, 0) + 1
    gm = GROUND_CLEARANCE + GROUND_EXTRA
    sh = np.arange(lo_hit, hi_hit + 1e-6, NODE)
    Ph, Th = _interp(sh, s_all, P_all), _interp(sh, s_all, T_all)
    hit = fo.blocked(Ph, CHECK_R)
    if not hit.any():
        return None
    side, up = _frames(Th[hit])
    Te = fo.ray_escape(Ph[hit], _dirs(side, up, _ANG), margin, gm)          # (G, N_ANG)
    R = Te.max(axis=0)
    dy = np.sin(_ANG)
    cost = R * (1.0 + UP_W * np.maximum(0.0, dy) + DOWN_W * np.maximum(0.0, -dy))
    w = 1.0 + UP_W * np.maximum(0.0, dy) + DOWN_W * np.maximum(0.0, -dy)
    order = [int(x) for x in np.argsort(cost) if np.isfinite(cost[x])][:TRY_ANGLES]
    if CONF.get("vec") and order:
        res = _band_vec(fo, lo_hit, hi_hit, iv, R[order[0]], margin, gm, P_all, s_all, T_all, w)
        if res is not None:
            return res[2]
    best = None
    for a in order:
        res = _band_at(fo, lo_hit, hi_hit, iv, _ANG[a:a + 1], R[a], margin, gm, P_all, s_all, T_all)
        if res is None:
            continue
        ok, fmax, band = res
        key_ = (not ok, fmax * w[a])
        if best is None or key_ < best[0]:
            best = (key_, band)
    return best[1] if best else None


TRY_ANGLES = 3


def _band_at(fo, lo_hit, hi_hit, iv, ang, r0, margin, gm, P_all, s_all, T_all):
    ext = min(25.0, max(EXT, 4.0 * r0))
    sa, sb = max(iv[0], lo_hit - ext), min(iv[1], hi_hit + ext)
    s_nodes = np.arange(sa, sb + 1e-6, NODE)
    n = len(s_nodes)
    if n < 6:
        return None
    P0, T0 = _interp(s_nodes, s_all, P_all), _interp(s_nodes, s_all, T_all)
    side, up = _frames(T0)
    d = _dirs(side, up, ang)[:, 0]                                        # (n, 3)
    # window ends in free flight blend in with zero slope; at a gate's fixed zone only the
    # displacement is zero (the spline through the gate knot sets the direction there)
    fixed = [0, n - 1]
    if sa > iv[0] + 1e-6 or not END_FREE:
        fixed.append(1)
    if sb < iv[1] - 1e-6 or not END_FREE:
        fixed.append(n - 2)
    free = np.ones(n, bool)
    free[fixed] = False
    need = {}
    f = np.zeros(n)
    ok = False
    for _ in range(4):
        B = P0 + f[:, None] * d
        h = np.nonzero(fo.blocked(B, CHECK_R) & free)[0]
        if not len(h):
            ok = True
            break
        t = fo.ray_escape(B[h], d[h][:, None, :], margin, gm)[:, 0]
        if not np.all(np.isfinite(t)):
            return None
        for i, ti in zip(h, t):
            need[int(i)] = max(need.get(int(i), 0.0), f[i] + ti + CONF['extra'])
        f = _scalar_band(n, need, fixed)
        if np.abs(f).max() > MAX_PUSH:
            return None
    else:
        ok = not (fo.blocked(P0 + f[:, None] * d, CHECK_R) & free).any()
    if np.abs(f).max() < 0.02:
        return None
    return ok, float(np.abs(f).max()), (s_nodes, f[:, None] * d, P0, T0)


MAX_PUSH = 8.0


def _band_vec(fo, lo_hit, hi_hit, iv, r0, margin, gm, P_all, s_all, T_all, w):
    """Elastic band with a free 3D displacement per node: every node still inside an item is pushed
    out along its own cheapest escape direction (from where the band is now), the band in between
    relaxes (stiffness + tension, pinned nodes), a few rounds."""
    ext = min(25.0, max(EXT, 4.0 * r0))
    sa, sb = max(iv[0], lo_hit - ext), min(iv[1], hi_hit + ext)
    s_nodes = np.arange(sa, sb + 1e-6, NODE)
    n = len(s_nodes)
    if n < 6:
        return None
    P0, T0 = _interp(s_nodes, s_all, P_all), _interp(s_nodes, s_all, T_all)
    side, up = _frames(T0)
    fixed = [0, n - 1]
    if sa > iv[0] + 1e-6 or not END_FREE:
        fixed.append(1)
    if sb < iv[1] - 1e-6 or not END_FREE:
        fixed.append(n - 2)
    free = np.ones(n, bool)
    free[fixed] = False
    pins = {}
    D = np.zeros((n, 3))
    ok = False
    for _ in range(6):
        B = P0 + D
        h = np.nonzero(fo.blocked(B, CHECK_R) & free)[0]
        if not len(h):
            ok = True
            break
        dirs = _dirs(side[h], up[h], _ANG)                                  # (H, A, 3)
        t = fo.ray_escape(B[h], dirs, margin, gm)                          # (H, A)
        c = t * w[None]
        for r, i in enumerate(h):
            a = int(np.argmin(c[r]))
            if not np.isfinite(c[r, a]):
                return None
            pins[int(i)] = D[i] + dirs[r, a] * (t[r, a] + CONF["extra"])
        D = _solve_band(n, pins, fixed)
        if np.linalg.norm(D, axis=1).max() > MAX_PUSH:
            return None
    else:
        ok = not (fo.blocked(P0 + D, CHECK_R) & free).any()
    fmax = float(np.linalg.norm(D, axis=1).max())
    if fmax < 0.02:
        return None
    return ok, fmax, (s_nodes, D, P0, T0)
END_FREE = True


# ------------------------------------------------------------------ local spline (RacingLine._sample)
def _unit(v, fb=(0.0, 0.0, 1.0)):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else np.asarray(fb, float)


def _local_points(W, start, start_dir, ka, kb, step=0.25, scale=0.9):
    """Spline samples between knots ka..kb of [start] + W, exactly like RacingLine (laps=1)."""
    n_k = len(W) + 1
    ka, kb = max(0, ka), min(n_k - 1, kb)

    def pos(j):
        return np.asarray(start if j == 0 else W[j - 1].center, float)

    def tan(j):
        if j == 0:
            return _unit(start_dir)
        g = W[j - 1]
        if getattr(g, "via", False) and 0 < j < n_k - 1:
            return _unit(pos(j + 1) - pos(j - 1), g.normal)
        return _unit(g.normal)
    out = []
    for j in range(ka, kb):
        p0, p1 = pos(j), pos(j + 1)
        d = float(np.linalg.norm(p1 - p0))
        m0, m1 = tan(j) * d * scale, tan(j + 1) * d * scale
        n = max(2, int(d / step * 1.3))
        t = np.arange(1, n + 1)[:, None] / n
        t2, t3 = t * t, t * t * t
        out.append((2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1)
    return np.concatenate(out) if out else np.zeros((0, 3))


MAX_VIAS = 4          # per band window


def _kappa_max(Q):
    """Max curvature of a polyline, smoothed like RacingLine._curvature."""
    n = len(Q)
    if n < 6:
        return 0.0
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    T = Q[np.minimum(np.arange(n) + 1, n - 1)] - Q[np.maximum(np.arange(n) - 1, 0)]
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    i0, i1 = np.maximum(np.arange(n) - 2, 0), np.minimum(np.arange(n) + 2, n - 1)
    ds = np.maximum(s[i1] - s[i0], 1e-6)
    kv = (T[i1] - T[i0]) / ds[:, None]
    for _ in range(3):
        kv = (kv[np.maximum(np.arange(n) - 1, 0)] + kv + kv[np.minimum(np.arange(n) + 1, n - 1)]) / 3
    return float(np.linalg.norm(kv, axis=1)[3:-3].max())


KAPPA_GROW = 1.4      # a band via may make the local line at most this much tighter ...
KAPPA_FREE = 0.8      # ... or this tight (1/m) - whichever is more
MAX_GAIN = 2.0


def _fit_window(W, ws, start, start_dir, fo, band, real_s, real_g):
    """Fit vias to the band: greedy, every candidate checked on the rebuilt local spline (hits,
    curvature). Candidates: a via on the band (peak / worst still touching node), pushing one of
    our vias further out, and - for touches next to a gate - a via on the gate axis (straight
    approach / exit). Changes W/ws in place."""
    s_nodes, D, P0, T0 = band
    f = np.linalg.norm(D, axis=1)
    real_c = np.array([g.center for g in real_g], float).reshape(-1, 3)

    def knot_range():
        a = max([e for e, sk in enumerate(ws) if sk < s_nodes[0]], default=-1)
        b = min([e for e, sk in enumerate(ws) if sk > s_nodes[-1]], default=len(W) - 1)
        return a, b + 2                                   # knot index = element index + 1

    def local():
        ka, kb = knot_range()
        return _local_points(W, start, start_dir, ka, kb)

    def hits_of(Q):
        """Every touching sample of the local spline (0.5 m apart, the whole knot range - a via must
        not just move the touch elsewhere): band node index, -1 if away from the band."""
        if not len(Q):
            return []
        hit = fo.blocked(Q, CHECK_R)
        if len(real_c):
            hit &= np.min(np.linalg.norm(Q[:, None] - real_c[None], axis=2), axis=1) > GATE_FIX
        hit &= np.linalg.norm(Q - np.asarray(start), axis=1) > START_SKIP
        H = Q[hit]
        if not len(H):
            return []
        dn = np.linalg.norm(H[:, None] - P0[None], axis=2)
        j = dn.argmin(axis=1)
        return [int(x) if dd < 3.0 else -1 for x, dd in zip(j, dn.min(axis=1)) if dd < 3.0 or CONF['wide']]

    Q = local()
    k_lim = max(KAPPA_GROW * _kappa_max(Q), KAPPA_FREE)
    rel = hits_of(Q)
    changed = False
    # existing vias inside the window move with the band
    snapshot = (list(W), list(ws))
    for e, (g, sk) in enumerate(zip(W, ws)):
        if getattr(g, "via", False) and s_nodes[0] <= sk <= s_nodes[-1]:
            dk = np.array([np.interp(sk, s_nodes, D[:, c]) for c in range(3)])
            if np.linalg.norm(dk) > 0.05:
                v = _via(np.asarray(g.center) + dk, g.normal)
                if getattr(g, "role", None):
                    v.role = g.role
                W[e] = v
                changed = True
    if changed:
        Qn = local()
        rn = hits_of(Qn)
        if _kappa_max(Qn) <= k_lim and len(rn) <= len(rel):
            Q, rel = Qn, rn
        else:
            W[:], ws[:] = snapshot
            changed = False
    allowed = f > 0.05
    if len(real_s):
        allowed &= np.min(np.abs(s_nodes[:, None] - real_s[None]), axis=1) >= VIA_GATE
    added = {}                                            # s -> (node index, gain) of our band vias

    def place(i, gain):
        c = P0[i] + D[i] * gain
        if gain > 1.0:
            c = c + _unit(D[i]) * 0.4 * (gain - 1.0)
        return _via(c, T0[i])

    def too_close(si):
        return any(abs(sk - si) < VIA_SPACING for sk, g in zip(ws, W) if getattr(g, "via", False))

    def insert(si, via):
        e = next((e for e, sk in enumerate(ws) if sk > si), len(W))
        W.insert(e, via)
        ws.insert(e, si)

    tried_axis = set()
    for it in range(MAX_VIAS):
        if not rel:
            break
        cands = []                                        # apply-functions
        ok = np.nonzero(allowed)[0]
        # 1. a via on the band: at the peak and at the worst still touching node, a few gains
        nodes = set()
        inband = sorted(set(rel) - {-1}, key=lambda x: -f[x])
        if len(ok) and (CONF['pair'] or not added):
            nodes.add(int(ok[np.argmax(f[ok])]))
        if len(ok) and added:
            for x in inband[:2 if CONF['pair'] else 1]:
                nodes.add(int(ok[np.argmin(np.abs(ok - x))]))
        elif len(ok) and CONF['pair']:
            for x in inband[:2]:
                nodes.add(int(ok[np.argmin(np.abs(ok - x))]))
        for i in nodes:
            si = float(s_nodes[i])
            near = [sv for sv in added if abs(sv - si) < VIA_SPACING]
            if near:
                sv = near[0]
                iv, gain = added[sv]
                for g2 in ((gain + 0.25, gain + 0.5) if CONF['pair'] else (gain + 0.25,)):
                    if g2 <= CONF['max_gain'] + 1e-9:
                        def act(sv=sv, iv=iv, g2=g2):
                            e = next(e for e, sk in enumerate(ws) if sk == sv and getattr(W[e], "band", False))
                            W[e] = place(iv, g2)
                            added[sv] = (iv, g2)
                        cands.append(act)
            elif not too_close(si):
                for g2 in CONF['gains']:
                    def act(si=si, i=i, g2=g2):
                        insert(si, place(i, g2))
                        added[si] = (i, g2)
                    cands.append(act)
        # 1a. a via that is already there (align / earlier repair) pushed further along the band
        for e, (g, sk) in enumerate(zip(W, ws) if CONF['push_old'] else ()):
            if not getattr(g, "via", False) or getattr(g, "band", False) or not (s_nodes[0] <= sk <= s_nodes[-1]):
                continue
            dk = np.array([np.interp(sk, s_nodes, D[:, c]) for c in range(3)])
            if np.linalg.norm(dk) < 0.05:
                continue
            for extra in (0.5, 1.0):
                def act(e=e, g=g, dk=dk, extra=extra):
                    v = _via(np.asarray(g.center) + dk * extra + _unit(dk) * 0.2, g.normal)
                    v.band = False
                    if getattr(g, "role", None):
                        v.role = g.role
                    W[e] = v
                cands.append(act)
        # 1b. a wide band (long wall): two vias at the ends of its plateau follow it better than one
        if not added and len(ok) and CONF['pair']:
            fm = f[ok].max()
            pl = ok[f[ok] >= PLATEAU * fm]
            if len(pl) >= 2:
                i1, i2 = int(pl[0]), int(pl[-1])
                s1, s2 = float(s_nodes[i1]), float(s_nodes[i2])
                if s2 - s1 >= VIA_SPACING and not too_close(s1) and not too_close(s2):
                    for g2 in CONF['gains']:
                        def act(i1=i1, i2=i2, s1=s1, s2=s2, g2=g2):
                            insert(s1, place(i1, g2))
                            insert(s2, place(i2, g2))
                            added[s1] = (i1, g2)
                            added[s2] = (i2, g2)
                        cands.append(act)
        # 2. touching right before / behind a gate: a via on the gate axis straightens the passage
        hs = s_nodes[sorted(set(rel) - {-1})]
        for sg, g in zip(real_s, real_g):
            for side in (-1.0, 1.0):
                sel = hs[(np.sign(hs - sg) == side) & (np.abs(hs - sg) < AXIS_RANGE)]
                if not len(sel) or (sg, side) in tried_axis:
                    continue
                dist = float(np.clip(np.abs(sel - sg).max() + 1.0, 2.0, AXIS_RANGE + 1.0))
                sv = sg + side * dist
                if too_close(sv):
                    continue
                c = np.asarray(g.center, float) + side * dist * _unit(g.normal)

                def act(sv=sv, c=c, g=g, key=(sg, side)):
                    insert(sv, _via(c, g.normal))
                    tried_axis.add(key)
                cands.append(act)
        best = None
        for act in cands:
            before = (list(W), list(ws), dict(added), set(tried_axis))
            act()
            Qn = local()
            rn = hits_of(Qn)
            kn = _kappa_max(Qn)
            if kn <= k_lim and len(rn) < len(rel):
                key = (len(rn), kn)
                if best is None or key < best[0]:
                    best = (key, (list(W), list(ws), dict(added), set(tried_axis)), Qn, rn)
            W[:], ws[:] = before[0], before[1]
            added.clear()
            added.update(before[2])
            tried_axis.clear()
            tried_axis.update(before[3])
        if best is None:
            break
        _, state, Q, rel = best
        W[:], ws[:] = state[0], state[1]
        added.clear()
        added.update(state[2])
        tried_axis.clear()
        tried_axis.update(state[3])
        changed = True
    return changed


AXIS_RANGE = 6.0      # m: touches this close to a gate may be fixed by a via on its axis
GAINS = (1.0, 1.3, 1.6)   # a single knot does not reach the band between knots: try it a bit further out
PLATEAU = 0.7
CONF_A = dict(gains=(1.0,), push_old=False, pair=False, max_gain=1.5, wide=False, floor_extra=False, extra=0.0)
CONF_B = dict(gains=(1.0, 1.3, 1.6), push_old=True, pair=True, max_gain=2.0, wide=False, floor_extra=True, extra=0.05)
CONF_C = dict(CONF_B, vec=True)
CONF = dict(CONF_A)


def _repair(line, seq, start, start_dir, fo):
    """New sequence with vias fitted to elastic bands around every touching stretch, or None."""
    s_all = np.asarray(line.s)
    P_all = np.asarray(line.points)
    T_all = np.asarray(line.tangent)
    kappa = np.asarray(line.kappa)
    kidx = _knot_index(seq, start)
    if kidx[-1] >= len(s_all) or np.linalg.norm(P_all[kidx[-1]] - np.asarray(seq[-1].center)) > 1e-6:
        return None
    knot_s = s_all[kidx]
    is_real = [not getattr(g, "via", False) for g in seq]
    real_s = np.array([sk for sk, r in zip(knot_s, is_real) if r])
    real_g = [g for g, r in zip(seq, is_real) if r]
    sel = np.nonzero(np.diff(np.floor(s_all / 0.25), prepend=-1) > 0)[0]
    hit = fo.blocked(P_all[sel], CHECK_R)
    sh = s_all[sel][hit]
    sh = sh[sh > START_SKIP]
    if len(real_s) and len(sh):
        sh = sh[np.min(np.abs(sh[:, None] - real_s[None]), axis=1) > GATE_FIX]
    if not len(sh):
        return None
    zones = [START_SKIP - GATE_FIX] + sorted(real_s.tolist()) + [s_all[-1] + GATE_FIX]
    free_iv = [(a + GATE_FIX, b - GATE_FIX) for a, b in zip(zones, zones[1:]) if b - a > 2 * GATE_FIX + 1.0]
    wins = []                                   # touching stretches (gaps < 4 m merged) per free interval
    for x in sh:
        iv = next(((lo, hi) for lo, hi in free_iv if lo <= x <= hi), None)
        if iv is None:
            continue
        if wins and wins[-1][2] == iv and x - wins[-1][1] < 4.0:
            wins[-1][1] = x
        else:
            wins.append([x, x, iv])
    W, ws = list(seq), list(knot_s)
    changed = False
    base = dict(_repair.spots)
    for a, b, iv in wins:
        band = _repair_window(line, fo, a, b, iv, base, _repair.spots, P_all, s_all, T_all)
        if band is None:
            continue
        changed |= _fit_window(W, ws, start, start_dir, fo, band, real_s, real_g)
    return W if changed else None


_repair.spots = {}
_FO_CACHE = {}


def _fast(colliders, gates):
    """Numpy view of the obstacle set (cached per ObstacleSet - in-flight replanning reuses it)."""
    hit = _FO_CACHE.get(id(colliders))
    if hit is None or hit[0] is not colliders:
        if len(_FO_CACHE) > 4:
            _FO_CACHE.clear()
        hit = (colliders, FastObs(colliders))
        _FO_CACHE[id(colliders)] = hit
    return hit[1].with_gates([g.center for g in gates])


_LOCK = threading.Lock()          # CONF and _repair.spots are module state; replanning runs in a thread


def build_line(gates, start, start_dir, laps, aggressiveness, max_speed=40.0, colliders=None, iterations=10):
    with _LOCK:
        return _build_line(gates, start, start_dir, laps, aggressiveness, max_speed, colliders)


def _build_line(gates, start, start_dir, laps, aggressiveness, max_speed=40.0, colliders=None):
    """Band repair with the plain via fit (A); where the line still touches, again with the wider fit
    (B: further out, pairs of vias, existing vias pushed) and with the free 3D band (C) - the best
    line wins (touching samples, then fewer vias)."""
    best = None
    try:
        for conf in (CONF_A, CONF_B, CONF_C):
            CONF.clear()
            CONF.update(conf)
            # B and C go on from the best line so far (its vias stay): only what still touches is
            # repaired again - cheap enough for in-flight replanning
            alt = _build(gates, start, start_dir, laps, aggressiveness, max_speed, colliders,
                         init=best if CHAIN else None)
            if best is None or (alt.touching, alt.vias) < (best.touching, best.vias):
                best = alt
            if not colliders or best.touching == 0:
                break
    finally:
        CONF.clear()
        CONF.update(CONF_A)
    return best


CHAIN = True
CEILING = True


def _build(gates, start, start_dir, laps, aggressiveness, max_speed=40.0, colliders=None, init=None):
    from . import race
    limits = Limits.from_thrust(race.USABLE_ACCEL, max_speed=max_speed, drag=race.DRAG)
    seq = race.align_vias(race.course(gates, laps))

    def plan(sq):
        ln = RacingLine(sq, start=start, start_dir=start_dir, laps=1, limits=limits,
                        aggressiveness=aggressiveness, finish_extra=4.0, launch_speed=9.0)
        ln.vias = sum(1 for g in ln.gates if getattr(g, "via", False))
        return ln
    if init is not None:
        seq, line = list(init.gates), init
    else:
        line = plan(seq)
        line.touching = 0
    if not colliders:
        return line
    if not isinstance(colliders, ObstacleSet):
        colliders = ObstacleSet(colliders)
    fo = _fast(colliders, [g for g in seq if not getattr(g, "via", False)])
    _repair.spots = {}
    best = (init.touching, init.vias, init) if init is not None else (_hit_count(line, fo), line.vias, line)
    stale = 0
    for _ in range(ROUNDS):
        if best[0] == 0:
            break
        trial = _repair(line, seq, start, start_dir, fo)
        if trial is None:
            break
        cand = plan(trial)
        h = _hit_count(cand, fo)
        seq, line = trial, cand
        if (h, cand.vias) < best[:2]:
            best, stale = (h, cand.vias, cand), 0
        else:
            stale += 1
            if stale >= 2:
                break
    line = best[2]
    line.touching = best[0]
    return line


