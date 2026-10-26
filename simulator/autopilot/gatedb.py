"""Exact gate and obstacle geometry from Liftoff's own prefabs (instead of guessed sizes).

  python -m autopilot.gatedb extract        # ~10 min, writes tracks/gatedb.json (game data, not in git)
  python -m autopilot.gatedb show InflatableArchBrandless01

Every track item in Liftoff is a prefab. Gates carry a child with the `RaceCheckpoint` script and a
trigger collider: that volume is what Liftoff counts as "passed". The frame itself has normal
colliders (boxes, capsules, meshes) the drone can hit. Both are stored per item as boxes in the
item's own frame (pivot = blueprint position), each box as origin + three edge vectors
(a parallelepiped, so nested rotations and non-uniform scales stay exact).

This works for every track built from Liftoff items - official, community or self-made - as long
as the item names are in the database.
"""
import glob
import json
import math
import sys
import time
import warnings
from pathlib import Path

from .geometry import qrot

GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Liftoff\Liftoff_Data")
BUNDLES = GAME / "StreamingAssets/aa/StandaloneWindows64"
DB_PATH = Path(__file__).resolve().parent / "tracks" / "gatedb.json"
_DB = None


# ---------------------------------------------------------------------------- geometry helpers
def box_corners(center, half):
    cx, cy, cz = center
    hx, hy, hz = half
    return [(cx + sx * hx, cy + sy * hy, cz + sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def as_parallelepiped(corners):
    """8 corners in box_corners order -> (origin, e1, e2, e3)."""
    o = corners[0]
    e = lambda i: tuple(corners[i][k] - o[k] for k in range(3))
    return [list(o), list(e(4)), list(e(2)), list(e(1))]     # x edge, y edge, z edge


def pp_corners(pp):
    o, a, b, c = pp
    return [tuple(o[k] + i * a[k] + j * b[k] + l * c[k] for k in range(3))
            for i in (0, 1) for j in (0, 1) for l in (0, 1)]


def _solve3(m, v):
    """Solve m (columns a, b, c) * u = v (Cramer)."""
    a, b, c = m
    det = lambda x, y, z: (x[0] * (y[1] * z[2] - y[2] * z[1]) - y[0] * (x[1] * z[2] - x[2] * z[1])
                           + z[0] * (x[1] * y[2] - x[2] * y[1]))
    d = det(a, b, c)
    if abs(d) < 1e-12:
        return None
    return det(v, b, c) / d, det(a, v, c) / d, det(a, b, v) / d


def pp_contains(pp, p, margin=0.0):
    """Point inside the parallelepiped grown by `margin` metres on every face."""
    o, a, b, c = pp
    u = _solve3((a, b, c), tuple(p[k] - o[k] for k in range(3)))
    if u is None:
        return False
    for ui, e in zip(u, (a, b, c)):
        n = math.sqrt(sum(x * x for x in e)) or 1e-9
        m = margin / n
        if ui < -m or ui > 1 + m:
            return False
    return True


def transform_pp(pp, pos, quat, scale=(1.0, 1.0, 1.0)):
    """Item frame -> world (blueprint position / rotation / scale)."""
    def tp(p):
        q = qrot(quat, (p[0] * scale[0], p[1] * scale[1], p[2] * scale[2]))
        return (q[0] + pos[0], q[1] + pos[1], q[2] + pos[2])

    def tv(v):
        return qrot(quat, (v[0] * scale[0], v[1] * scale[1], v[2] * scale[2]))
    o, a, b, c = pp
    return [list(tp(o)), list(tv(a)), list(tv(b)), list(tv(c))]


# ---------------------------------------------------------------------------- database access
def db():
    global _DB
    if _DB is None:
        _DB = json.loads(DB_PATH.read_text(encoding="utf-8")) if DB_PATH.exists() else {}
    return _DB


def item(name):
    d = db()
    return d.get(name) or d.get(name.strip())


# ---------------------------------------------------------------------------- extraction
def _quat(q):
    return (q.x, q.y, q.z, q.w)


def _vec(v):
    return (v.x, v.y, v.z)


# Unity's built-in meshes ("unity default resources", not in any bundle): local id -> half extents
BUILTIN_MESHES = {10202: (0.5, 0.5, 0.5), 10206: (0.5, 1.0, 0.5), 10207: (0.5, 0.5, 0.5),
                  10208: (0.5, 1.0, 0.5), 10209: (5.0, 0.0, 5.0), 10210: (0.5, 0.5, 0.0)}


class _Extractor:
    def __init__(self, env):
        self.env = env
        self.errors = []

    def walk(self, go, chain, out):
        comps = []
        for c in go.m_Component:
            p = getattr(c, "component", None) or (c[1] if isinstance(c, tuple) else c)
            try:
                comps.append(p.read())
            except Exception:
                pass
        tr = next((c for c in comps if type(c).__name__ in ("Transform", "RectTransform")), None)
        if tr is None:
            return
        if not chain:
            out["root_scale"] = list(_vec(tr.m_LocalScale))
        chain = chain + [(_vec(tr.m_LocalPosition), _quat(tr.m_LocalRotation), _vec(tr.m_LocalScale))]
        scripts = set()
        for c in comps:
            if type(c).__name__ == "MonoBehaviour":
                try:
                    scripts.add(c.m_Script.read().m_ClassName)
                except Exception:
                    pass
        is_cp = "RaceCheckpoint" in scripts
        if go.m_IsActive is not False:
            for c in comps:
                shape = self.collider(c)
                if shape is None:
                    continue
                trig = bool(getattr(c, "m_IsTrigger", False))
                pp = self.to_root(shape, chain)
                if is_cp and trig:
                    out["checkpoint"].append(pp)
                elif not trig and getattr(c, "m_Enabled", True):
                    out["colliders"].append(pp)
        for ch in tr.m_Children:
            try:
                self.walk(ch.read().m_GameObject.read(), chain, out)
            except Exception:
                pass

    @staticmethod
    def to_root(corners, chain):
        pts = corners
        for pos, quat, sc in reversed(chain[1:]):           # the root's own transform is the blueprint's
            pts = [tuple(a + b for a, b in zip(qrot(quat, (p[0] * sc[0], p[1] * sc[1], p[2] * sc[2])), pos))
                   for p in pts]
        return as_parallelepiped(pts)

    def collider(self, c):
        n = type(c).__name__
        if n == "BoxCollider":
            s = _vec(c.m_Size)
            return box_corners(_vec(c.m_Center), (s[0] / 2, s[1] / 2, s[2] / 2))
        if n == "SphereCollider":
            r = c.m_Radius
            return box_corners(_vec(c.m_Center), (r, r, r))
        if n == "CapsuleCollider":
            r, h = c.m_Radius, max(c.m_Height, 2 * c.m_Radius)
            half = [r, r, r]
            half[c.m_Direction] = h / 2
            return box_corners(_vec(c.m_Center), tuple(half))
        if n == "MeshCollider":
            try:
                b = c.m_Mesh.read().m_LocalAABB
                return box_corners(_vec(b.m_Center), _vec(b.m_Extent))
            except Exception as exc:
                ext = BUILTIN_MESHES.get(getattr(c.m_Mesh, "m_PathID", None))
                if ext is not None:
                    return box_corners((0.0, 0.0, 0.0), ext)
                self.errors.append(f"mesh {getattr(c.m_Mesh, 'm_PathID', '?')}: {exc!r}"[:120])
                return None
        return None


def item_names():
    from .track import TRACK_DIR, load_track
    names = set()
    for p in list(TRACK_DIR.glob("*Track*.xml")) + list((Path.home() / "AppData/LocalLow/LuGus Studios/Liftoff/Tracks").glob("*.xml")):
        try:
            names.update(b.item for b in load_track(p)["blueprints"])
        except Exception:
            pass
    return names


def extract():
    warnings.filterwarnings("ignore")
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
    want = item_names()
    print(f"{len(want)} item types in the tracks, scanning {len(list(BUNDLES.glob('*.bundle')))} bundles ...")
    where = {}
    t0 = time.time()
    for i, f in enumerate(sorted(BUNDLES.glob("*.bundle"))):
        try:
            env = UnityPy.load(str(f))
            for obj in env.objects:
                if obj.type.name != "GameObject":
                    continue
                try:
                    name = obj.peek_name()
                except Exception:
                    continue
                if name in want and name not in where:
                    where[name] = f.name
        except Exception:
            pass
        if i % 40 == 0:
            print(f"  {i} bundles, {len(where)} items, {time.time() - t0:.0f} s", flush=True)
    files = set(where.values())
    # meshes live in other bundles: CAB-<hash> is <hash>.bundle
    for f in list(files):
        env = UnityPy.load(str(BUNDLES / f))
        for bf in env.files.values():
            for sf in getattr(bf, "files", {}).values():
                for ex in getattr(sf, "externals", []) or []:
                    h = ex.path.rsplit("CAB-", 1)[-1].split("/")[0]
                    if (BUNDLES / f"{h}.bundle").exists():
                        files.add(f"{h}.bundle")
    print(f"loading {len(files)} bundles for the geometry ...")
    env = UnityPy.load(*[str(BUNDLES / f) for f in sorted(files)])
    out = {}
    ex = _Extractor(env)
    for obj in env.objects:
        if obj.type.name != "GameObject":
            continue
        try:
            name = obj.peek_name()
        except Exception:
            continue
        if name not in want:
            continue
        go = obj.read()
        rec = {"checkpoint": [], "colliders": []}
        try:
            ex.walk(go, [], rec)
        except Exception as exc:
            rec["error"] = repr(exc)
        # the same prefab can be in several bundles (some copies without checkpoint): keep the richest
        old = out.get(name)
        if old is None or (len(rec["checkpoint"]), len(rec["colliders"])) > (len(old["checkpoint"]), len(old["colliders"])):
            out[name] = rec
    DB_PATH.parent.mkdir(exist_ok=True)
    DB_PATH.write_text(json.dumps(out), encoding="utf-8")
    n_cp = sum(1 for v in out.values() if v["checkpoint"])
    print(f"{len(out)} items written ({n_cp} with checkpoint volume), missing: {sorted(want - set(out))}")
    for e in sorted(set(ex.errors))[:10]:
        print("  ", e)


def show(name):
    rec = item(name)
    if rec is None:
        print("not in database")
        return
    for kind in ("checkpoint", "colliders"):
        print(kind, len(rec[kind]))
        for pp in rec[kind][:12]:
            cs = pp_corners(pp)
            lo = [min(c[k] for c in cs) for k in range(3)]
            hi = [max(c[k] for c in cs) for k in range(3)]
            print("   x %6.2f..%6.2f  y %6.2f..%6.2f  z %6.2f..%6.2f" % (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))


if __name__ == "__main__":
    if sys.argv[1] == "extract":
        extract()
    elif sys.argv[1] == "show":
        show(sys.argv[2])
