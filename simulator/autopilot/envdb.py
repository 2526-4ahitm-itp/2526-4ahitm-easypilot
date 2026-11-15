"""The level itself as an obstacle map: buildings, walls, trees and terrain of every Liftoff environment.

  python -m autopilot.envdb extract            # all environments, ~20-40 min, writes tracks/env/*.npz
  python -m autopilot.envdb extract BandoCity  # one environment
  python -m autopilot.envdb show BandoCity

Track files only list the placed items (gates, flags, barriers). The level scene has everything else:
static colliders (box, sphere, capsule, mesh bounds) and the terrain height map. Both come from the
scene bundles in Liftoff's files, so every track in an environment - official or custom - knows its
walls and hills. Scenes are matched to environments by object names (and Player.log when known).

Data per environment (game data, not in git): colliders as parallelepipeds (origin + 3 edges, world
coordinates) and terrain tiles (origin, size, height grid).
"""
import json
import math
import sys
import time
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .gatedb import BUNDLES, BUILTIN_MESHES, as_parallelepiped, box_corners, pp_contains
from .geometry import qrot

ENV_DIR = Path(__file__).resolve().parent / "tracks" / "env"
ENVS = ["AutumnFields", "BandoCity", "BardwellsYard", "DubaiLegends", "Hall26", "HangarC03", "Hannover",
        "LiftoffArena", "MarinaBay", "MinusTwo", "ParisDroneFestival", "Permafrost", "PineValley", "Rustline",
        "ShortCircuit", "StrawBale", "Surtur", "TheGreen", "ThePit", "TheRussianWoodpecker"]
GROUND_CLEARANCE = 0.3  # m above terrain / floors
MIN_MATCH = 0.6         # scene <-> environment match needed to trust the level geometry
MAX_SPAN = 80.0          # colliders larger than this in two directions are floors/ceilings, not obstacles


# ---------------------------------------------------------------------------- runtime: obstacle set
class ObstacleSet:
    """Track item colliders + level colliders + terrain with a grid index for fast queries."""

    def __init__(self, colliders=(), terrain=(), cell=8.0):
        self.cell = cell
        self.items = list(colliders)                 # [(name, pp)]
        self.terrain = list(terrain)                 # [Terrain]
        self.grid = defaultdict(list)
        self.floor = set()                           # flat slabs (floors, roofs, ground planes)
        for k, (name, pp) in enumerate(self.items):
            cs = _corners(pp)
            lo = np.min(cs, axis=0)
            hi = np.max(cs, axis=0)
            if hi[0] - lo[0] > 6.0 and hi[2] - lo[2] > 6.0 and hi[1] - lo[1] < 1.5:
                self.floor.add(k)
            for i in range(int(math.floor(lo[0] / cell)), int(math.floor(hi[0] / cell)) + 1):
                for j in range(int(math.floor(lo[2] / cell)), int(math.floor(hi[2] / cell)) + 1):
                    self.grid[(i, j)].append(k)

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def near(self, p, radius=2.0):
        """(name, pp) of all items whose grid cells are within `radius` of p (x/z)."""
        c = self.cell
        seen = set()
        for i in range(int(math.floor((p[0] - radius) / c)), int(math.floor((p[0] + radius) / c)) + 1):
            for j in range(int(math.floor((p[2] - radius) / c)), int(math.floor((p[2] + radius) / c)) + 1):
                for k in self.grid.get((i, j), ()):
                    if k not in seen:
                        seen.add(k)
                        yield self.items[k]

    def ground(self, x, z):
        """Terrain height at x/z, or None outside every terrain tile."""
        hs = [t.height(x, z) for t in self.terrain]
        hs = [h for h in hs if h is not None]
        return max(hs) if hs else None

    def blocked(self, p, margin, below=0.0):
        """Is p (or p lowered by `below`) closer than `margin` to an obstacle or the terrain?"""
        # ground (terrain, floors, roofs): only the drone itself must stay clear - gates are often
        # just 1.3 m above it, a safety margin below would push the whole line up all the time
        g = self.ground(p[0], p[2])
        if g is not None and p[1] < g + GROUND_CLEARANCE:
            return "terrain"
        low = (p[0], p[1] - below, p[2])
        c = self.cell
        for i in range(int(math.floor((p[0] - margin - below - 1) / c)), int(math.floor((p[0] + margin + below + 1) / c)) + 1):
            for j in range(int(math.floor((p[2] - margin - below - 1) / c)), int(math.floor((p[2] + margin + below + 1) / c)) + 1):
                for k in self.grid.get((i, j), ()):
                    name, pp = self.items[k]
                    if k in self.floor:
                        if pp_contains(pp, p, GROUND_CLEARANCE):
                            return name
                    elif pp_contains(pp, p, margin) or (below and pp_contains(pp, low, margin)):
                        return name
        return None


def _corners(pp):
    o, a, b, c = (np.asarray(v, float) for v in pp)
    return np.array([o + i * a + j * b + k * c for i in (0, 1) for j in (0, 1) for k in (0, 1)])


class Terrain:
    def __init__(self, origin, size, heights):
        self.origin, self.size = tuple(origin), tuple(size)
        self.h = np.asarray(heights, np.float32)        # [z, x] grid
        self.nz, self.nx = self.h.shape

    def height(self, x, z):
        u = (x - self.origin[0]) / self.size[0] * (self.nx - 1)
        v = (z - self.origin[2]) / self.size[2] * (self.nz - 1)
        if not (0 <= u <= self.nx - 1 and 0 <= v <= self.nz - 1):
            return None
        i0, j0 = int(u), int(v)
        i1, j1 = min(i0 + 1, self.nx - 1), min(j0 + 1, self.nz - 1)
        fu, fv = u - i0, v - j0
        h = (self.h[j0, i0] * (1 - fu) * (1 - fv) + self.h[j0, i1] * fu * (1 - fv) +
             self.h[j1, i0] * (1 - fu) * fv + self.h[j1, i1] * fu * fv)
        return self.origin[1] + float(h)


def load(env, bounds=None, margin=60.0):
    """ObstacleSet of an environment, optionally cut to a box (x0, z0, x1, z1) plus margin."""
    f = ENV_DIR / f"{env}.npz"
    if not f.exists():
        return ObstacleSet()
    d = np.load(f, allow_pickle=False)
    # an uncertain scene match would put walls where there are none (wild evasive moves): skip it
    if "match" not in d.files or float(d["match"]) < MIN_MATCH:
        return ObstacleSet()
    pps = d["pps"]
    names = json.loads(str(d["names"]))
    keep = np.ones(len(pps), bool)
    if bounds is not None and len(pps):
        x0, z0, x1, z1 = bounds
        o = pps[:, 0, :]
        keep = (o[:, 0] > x0 - margin) & (o[:, 0] < x1 + margin) & (o[:, 2] > z0 - margin) & (o[:, 2] < z1 + margin)
    cols = [(names[i] if i < len(names) else "level", pps[i].tolist()) for i in np.nonzero(keep)[0]]
    ters = []
    for k in range(int(d["n_terrain"])):
        ters.append(Terrain(d[f"t{k}_origin"], d[f"t{k}_size"], d[f"t{k}_h"]))
    return ObstacleSet(cols, ters)


def for_track(track, extra=None):
    """Obstacles for a track: its own solid items (gatedb) + the level around it (walls, terrain)."""
    if extra is None:
        from .gatedb import track_colliders
        extra = track_colliders(track)
    pts = [b.pos for b in track["blueprints"]]
    xs, zs = [p[0] for p in pts], [p[2] for p in pts]
    level = load(track["environment"], (min(xs), min(zs), max(xs), max(zs))) if pts else ObstacleSet()
    # level blocks (mostly mesh bounds) that contain a gate or its guide points are passable by design
    # - a wall with a doorway, a hall the course runs through
    from . import gatedb
    probes = []
    for b in track["blueprints"]:
        rec = gatedb.item(b.item)
        if not rec or not rec.get("checkpoint"):
            continue
        scale = b.extra.get("scale") or tuple(rec.get("root_scale", (1.0, 1.0, 1.0)))
        for q in [rec.get("target", (0.0, 0.0, 0.0))] + list(rec.get("guides", [])):
            probes.append(gatedb.transform_point(q, b.pos, b.quat, scale))
    keep = []
    idx = ObstacleSet(level.items)
    drop = set()
    for q in probes:
        for i, k in enumerate(idx.grid.get((int(math.floor(q[0] / idx.cell)), int(math.floor(q[2] / idx.cell))), ())):
            if k not in drop and pp_contains(idx.items[k][1], q, 0.3):
                drop.add(k)
    keep = [it for k, it in enumerate(level.items) if k not in drop]
    return ObstacleSet(list(extra) + keep, level.terrain)


# ---------------------------------------------------------------------------- extraction
def _mat(pos, quat, scale):
    m = np.eye(4)
    r = np.array([qrot(quat, (1.0, 0.0, 0.0)), qrot(quat, (0.0, 1.0, 0.0)), qrot(quat, (0.0, 0.0, 1.0))]).T
    m[:3, :3] = r * np.asarray(scale)[None, :]
    m[:3, 3] = pos
    return m


class _Scene:
    def __init__(self, env_obj):
        self.env = env_obj
        self.world = {}
        self.active = {}

    def transform(self, tr):
        """World matrix of a Transform (cached), parents first."""
        key = tr.object_reader.path_id if hasattr(tr, "object_reader") else id(tr)
        m = self.world.get(key)
        if m is not None:
            return m
        p = tr.m_LocalPosition, tr.m_LocalRotation, tr.m_LocalScale
        local = _mat((p[0].x, p[0].y, p[0].z), (p[1].x, p[1].y, p[1].z, p[1].w), (p[2].x, p[2].y, p[2].z))
        parent = None
        try:
            if tr.m_Father and tr.m_Father.path_id:
                parent = tr.m_Father.read()
        except Exception:
            parent = None
        m = self.transform(parent) @ local if parent is not None else local
        self.world[key] = m
        return m


def extract_bundle(path):
    """(colliders [(name, pp)], terrains [(origin, size, heights)], name counts) of one scene bundle."""
    import UnityPy
    env = UnityPy.load(str(path))
    key = next(iter(env.container.keys()), "") if env.container else ""
    sc = _Scene(env)
    cols, ters = [], []
    names = Counter()
    for obj in env.objects:
        t = obj.type.name
        if t in ("GameObject", "TerrainData", "Material"):
            try:
                n = obj.peek_name().lower().replace(" ", "").replace("_", "")
            except Exception:
                continue
            for e in ENVS:
                if e.lower() in n:
                    names[e] += 1
            if t != "GameObject":
                continue
            continue
        if t not in ("BoxCollider", "SphereCollider", "CapsuleCollider", "MeshCollider", "TerrainCollider"):
            continue
        try:
            c = obj.read()
            if getattr(c, "m_IsTrigger", False) or not getattr(c, "m_Enabled", True):
                continue
            go = c.m_GameObject.read()
            if go.m_IsActive is False:
                continue
            tr = next(x.read() for x in (getattr(cc, "component", None) or cc for cc in go.m_Component)
                      if x.type.name in ("Transform", "RectTransform"))
            m = sc.transform(tr)
        except Exception:
            continue
        if t == "TerrainCollider":
            try:
                td = c.m_TerrainData.read()
                hm = td.m_Heightmap
                res = hm.m_Resolution
                sc_ = hm.m_Scale
                h = np.array(hm.m_Heights, dtype=np.float32).reshape(res, res) / 32766.0 * sc_.y
                step = max(1, res // 513)                  # ~1-2 m grid is enough for planning
                h = h[::step, ::step]
                size = ((res - 1) * sc_.x, sc_.y, (res - 1) * sc_.z)
                ters.append((m[:3, 3].tolist(), size, h))
            except Exception:
                pass
            continue
        if t == "BoxCollider":
            s = c.m_Size
            local = box_corners((c.m_Center.x, c.m_Center.y, c.m_Center.z), (s.x / 2, s.y / 2, s.z / 2))
        elif t == "SphereCollider":
            r = c.m_Radius
            local = box_corners((c.m_Center.x, c.m_Center.y, c.m_Center.z), (r, r, r))
        elif t == "CapsuleCollider":
            r, hgt = c.m_Radius, max(c.m_Height, 2 * c.m_Radius)
            half = [r, r, r]
            half[c.m_Direction] = hgt / 2
            local = box_corners((c.m_Center.x, c.m_Center.y, c.m_Center.z), tuple(half))
        else:
            try:
                b = c.m_Mesh.read().m_LocalAABB
                local = box_corners((b.m_Center.x, b.m_Center.y, b.m_Center.z),
                                    (b.m_Extent.x, b.m_Extent.y, b.m_Extent.z))
            except Exception:
                ext = BUILTIN_MESHES.get(getattr(c.m_Mesh, "m_PathID", None))
                if ext is None:
                    continue
                local = box_corners((0.0, 0.0, 0.0), ext)
        world = [tuple((m @ np.array([*p, 1.0]))[:3]) for p in local]
        pp = as_parallelepiped(world)
        spans = sorted(math.sqrt(sum(x * x for x in e)) for e in pp[1:])
        if t == "MeshCollider" and spans[1] > MAX_SPAN:     # bounds of a huge mesh say nothing
            continue
        try:
            nm = go.m_Name
        except Exception:
            nm = "level"
        cols.append((nm, pp))
    names["__key__"] = 0
    return cols, ters, names, key


def scene_bundles():
    """Bundles that contain a level scene (terrain or many colliders)."""
    import UnityPy
    out = []
    for f in sorted(BUNDLES.glob("*.bundle"), key=lambda p: -p.stat().st_size):
        if f.stat().st_size < 20e6:
            break
        try:
            env = UnityPy.load(str(f))
            c = Counter(o.type.name for o in env.objects)
        except Exception:
            continue
        # a level scene (not a prefab collection): has render settings and many colliders or a terrain
        if c.get("RenderSettings") and (c.get("TerrainCollider") or c.get("MeshCollider", 0) + c.get("BoxCollider", 0) > 300):
            out.append(f)
    return out


def env_items():
    """Blueprint positions of all tracks per environment (official + custom)."""
    from .track import TRACK_DIR, USER_DIR, load_track
    out = defaultdict(list)
    for d in (TRACK_DIR, USER_DIR / "Tracks"):
        for p in (d.glob("*.xml") if d.exists() else []):
            head = p.read_text(encoding="utf-8", errors="ignore")[:400]
            if "<Track" not in head:
                continue
            try:
                t = load_track(p)
            except Exception:
                continue
            out[t["environment"]] += [b.pos for b in t["blueprints"]]
    return out


def match_score(cols, ters, items):
    """How well a scene fits an environment's items: share of items inside the scene, and for terrain
    scenes the share of items standing on the terrain (pivot within 0.5 m of the height map)."""
    if not items:
        return 0.0
    pts = np.array(items)
    if ters:
        tset = [Terrain(*t) for t in ters]
        on = 0
        for p in pts[:: max(1, len(pts) // 300)]:
            hs = [t.height(p[0], p[2]) for t in tset]
            hs = [h for h in hs if h is not None]
            on += any(abs(h - p[1]) < 0.5 for h in hs)
        return on / len(pts[:: max(1, len(pts) // 300)]) + 0.01 * len(cols) / 1e5
    if not cols:
        return 0.0
    # indoor levels: items stand on floors / platforms of the scene
    obs = ObstacleSet(cols)
    sample = pts[:: max(1, len(pts) // 200)]
    on = 0
    for p in sample:
        q = (float(p[0]), float(p[1]) - 0.15, float(p[2]))
        on += any(pp_contains(pp, q, 0.25) for _, pp in obs.near(q, 1.0))
    return on / len(sample)


def extract(only=None):
    warnings.filterwarnings("ignore")
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
    ENV_DIR.mkdir(parents=True, exist_ok=True)
    known = json.loads((ENV_DIR / "scenes.json").read_text()) if (ENV_DIR / "scenes.json").exists() else {}
    t0 = time.time()
    bundles = scene_bundles()
    print(f"{len(bundles)} scene bundles, {time.time() - t0:.0f} s", flush=True)
    items = env_items()
    scenes = []
    for f in bundles:
        cols, ters, names, key = extract_bundle(f)
        names.pop("__key__", None)
        scores = {e: match_score(cols, ters, items.get(e, [])) for e in ENVS}
        best_env = max(scores, key=scores.get)
        print(f"  {f.name}: best {best_env} {scores[best_env]:.2f} (names {dict(names.most_common(2))}), "
              f"{len(cols)} colliders, {len(ters)} terrains, {time.time() - t0:.0f} s", flush=True)
        scenes.append((f, cols, ters, key, scores))
    # each environment takes the scene Liftoff loads (Player.log); the rest one-to-one by best match
    assign = {}
    for env in ENVS:
        sc = next((x for x in scenes if known.get(env) == x[3]), None)
        if sc is not None:
            assign[env] = sc
    pairs = sorted(((sc[4][e], e, i) for i, sc in enumerate(scenes) for e in ENVS), reverse=True)
    used = {id(x) for x in assign.values()}
    for score, env, i in pairs:
        if env in assign or id(scenes[i]) in used or score < 0.3:
            continue
        assign[env] = scenes[i]
        used.add(id(scenes[i]))
    for env in ENVS:
        if only and env not in only:
            continue
        if env not in assign:
            print(f"{env}: no matching scene")
            continue
        f, cols, ters, key, scores = assign[env]
        data = {"pps": np.array([pp for _, pp in cols], np.float32).reshape(-1, 4, 3),
                "names": json.dumps([n for n, _ in cols]), "n_terrain": len(ters), "scene": key,
                "match": 1.0 if known.get(env) == key else float(scores[env])}
        for k, (o, s_, h) in enumerate(ters):
            data[f"t{k}_origin"] = np.array(o, np.float32)
            data[f"t{k}_size"] = np.array(s_, np.float32)
            data[f"t{k}_h"] = h.astype(np.float16)
        np.savez_compressed(ENV_DIR / f"{env}.npz", **data)
        print(f"{env}: {f.name} (match {scores[env]:.2f}), {len(cols)} colliders, {len(ters)} terrain tiles")


def show(env):
    o = load(env)
    print(f"{env}: {len(o)} colliders, {len(o.terrain)} terrain tiles")
    for t in o.terrain[:4]:
        print("  terrain", [round(v, 1) for v in t.origin], [round(v, 1) for v in t.size], t.h.shape,
              "height range", round(float(t.h.min()), 1), round(float(t.h.max()), 1))


if __name__ == "__main__":
    if sys.argv[1] == "extract":
        extract(set(sys.argv[2:]) or None)
    elif sys.argv[1] == "show":
        show(sys.argv[2])
