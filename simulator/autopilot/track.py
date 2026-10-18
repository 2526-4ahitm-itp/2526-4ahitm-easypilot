"""Liftoff track and race definitions (XML inside the game's Addressables bundles).

  python -m autopilot.track extract          # dump all official race/track XMLs to tracks/
  python -m autopilot.track show StrawBaleRace01

A Track lists blueprints (itemID, instanceID, position, rotation in degrees, Unity
euler order Z-X-Y). A Race lists checkpoint passages in order; checkPointID is the
instanceID of the gate and `directionality` tells from which side it is passed.
Gate size is encoded in the item name, e.g. AirgateBig240H300B = 2.40 m high, 3.00 m wide.
"""
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .geometry import axis_angle, qmul, qrot
from .planner import Gate

GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Liftoff\Liftoff_Data")
BUNDLES = GAME / "StreamingAssets/aa/StandaloneWindows64"
TRACK_DIR = Path(__file__).resolve().parent / "tracks"
XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"


def euler_quat(rx, ry, rz):
    """Unity Quaternion.Euler: rotation applied Z, then X, then Y (q = qy * qx * qz)."""
    qx = axis_angle((1.0, 0.0, 0.0), math.radians(rx))
    qy = axis_angle((0.0, 1.0, 0.0), math.radians(ry))
    qz = axis_angle((0.0, 0.0, 1.0), math.radians(rz))
    return qmul(qy, qmul(qx, qz))


@dataclass
class Blueprint:
    item: str
    instance: int
    kind: str
    pos: tuple
    rot: tuple                       # euler degrees
    extra: dict = field(default_factory=dict)

    @property
    def quat(self):
        return euler_quat(*self.rot)


PIVOT_AT_CENTER = ("CheckpointBox", "CheckpointSphere", "CheckpointCylinder")
# opening centre above the item pivot where it is not simply half the height, measured by
# projecting candidate heights into recorded FPV frames (calib in dataset/raw/*/fit*.jpg)
CENTER_LIFT = {"MultiGPFloatSquare10x10Frame01": 4.05, "MultiGPFloatSquare10x10Frame02": 6.45}


def center_lift(item, h):
    for prefix, lift in CENTER_LIFT.items():
        if item.startswith(prefix):
            return lift
    return 0.0 if item.startswith(PIVOT_AT_CENTER) else h / 2


def gate_size(item, scale=None):
    """(width, height) of the opening in metres, or None for non-gate items."""
    if item.startswith("CheckpointBoxFlexible") and scale:
        return scale[0], scale[1]
    m = re.match(r"CheckpointBox(\d+)mX(\d+)m", item)
    if m:
        return float(m.group(1)), float(m.group(2))
    if item.startswith("MultiGPFloatSquare10x10"):
        return 2.6, 2.3
    if item.startswith("MultiGPChampTrack8x10"):
        return 3.05, 3.05
    if item.startswith("MultiGPStandard7x6"):
        return 2.1, 1.8
    if item.startswith("InflatableArch"):
        return 3.0, 2.5
    m = re.search(r"(\d{3})H(\d{3})B", item)
    if m:
        return int(m.group(2)) / 100.0, int(m.group(1)) / 100.0   # width, height
    if "AirgateBig" in item:
        return 3.0, 2.4
    if "Airgate" in item:
        return 1.5, 1.5
    if "TrussGate" in item:
        return 2.0, 2.0
    return None


def _vec(el, name):
    v = el.find(name)
    return tuple(float(v.find(k).text) for k in ("x", "y", "z")) if v is not None else (0.0, 0.0, 0.0)


def load_track(path):
    root = ET.parse(path).getroot()
    bps = []
    for bp in root.iter("TrackBlueprint"):
        extra = {"scale": _vec(bp, "scale")} if bp.find("scale") is not None else {}
        bps.append(Blueprint(bp.findtext("itemID"), int(bp.findtext("instanceID") or -1), bp.get(XSI, ""),
                             _vec(bp, "position"), _vec(bp, "rotation"), extra))
    return {"name": root.findtext("name"), "id": root.findtext("localID/str"),
            "environment": root.findtext("environment"), "blueprints": bps}


def load_race(path):
    root = ET.parse(path).getroot()
    passages = {}
    for p in root.iter("RaceCheckpointPassage"):
        passages[p.findtext("uniqueId")] = {
            "checkpoint": int(p.findtext("checkPointID")), "type": p.findtext("passageType"),
            "direction": p.findtext("directionality"),
            "next": [s.text for s in p.find("nextPassageIDs")] if p.find("nextPassageIDs") is not None else []}
    start = next(k for k, v in passages.items() if v["type"] == "Start")
    order, k = [], start
    while k and k not in [o[0] for o in order]:
        order.append((k, passages[k]))
        k = passages[k]["next"][0] if passages[k]["next"] else None
    return {"name": root.findtext("name"), "track": root.findtext("dependencies/dependency/str"),
            "laps": int(root.findtext("requiredLaps") or 1), "passages": [p for _, p in order]}


def race_gates(race, track):
    """Ordered planner Gates (centre of the opening, travel direction) for one lap."""
    by_id = {b.instance: b for b in track["blueprints"]}
    gates = []
    for p in race["passages"]:
        b = by_id[p["checkpoint"]]
        size = gate_size(b.item, b.extra.get("scale")) or (2.0, 2.0)
        w, h = size
        q = b.quat
        # the passage plane is the gate's local XY plane; local +z is the "left" side
        n = qrot(q, (0.0, 0.0, 1.0 if p["direction"] == "RightToLeft" else -1.0))
        up = qrot(q, (0.0, 1.0, 0.0))
        lift = center_lift(b.item, h)
        c = tuple(b.pos[i] + up[i] * lift for i in range(3))
        gates.append(Gate(c, n, w, h, f"CP{p['checkpoint']} {b.item}"))
    # `directionality` is not consistent between gates; the passage order is, so orient each
    # gate normal along the course (previous -> next gate)
    k = len(gates)
    for i, g in enumerate(gates):
        a, b = gates[i - 1].center, gates[(i + 1) % k].center
        course = tuple(b[j] - a[j] for j in range(3))
        if sum(g.normal[j] * course[j] for j in range(3)) < 0:
            g.normal = tuple(-v for v in g.normal)
    return gates


def obstacles(track):
    """Everything that is not a gate, as (item, position, rotation) for the collision map."""
    return [b for b in track["blueprints"] if gate_size(b.item) is None and "TriggerBox" not in b.item]


def find(name_part):
    TRACK_DIR.mkdir(exist_ok=True)
    hits = sorted(TRACK_DIR.glob(f"*{name_part}*.xml"))
    if not hits:
        raise FileNotFoundError(f"no track/race matching {name_part} in {TRACK_DIR} - run `extract` first")
    return hits[0]


def load_race_with_track(race_name):
    race = load_race(find(race_name))
    def is_track(p):
        head = p.read_text(encoding="utf-8", errors="ignore")[:600]
        return "<Track" in head and race["track"] in head
    track_file = next(p for p in TRACK_DIR.glob("*.xml") if is_track(p))
    return race, load_track(track_file)


def extract():
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
    TRACK_DIR.mkdir(exist_ok=True)
    n = 0
    for f in BUNDLES.glob("*.bundle"):
        data = f.read_bytes()
        if b"<Track" not in data and b"<Race" not in data and len(data) > 5_000_000:
            continue
        try:
            env = UnityPy.load(str(f))
        except Exception:
            continue
        for o in env.objects:
            if o.type.name != "TextAsset":
                continue
            d = o.read()
            txt = d.m_Script
            if isinstance(txt, str):
                txt = txt.encode("utf-8", "surrogateescape")
            if b"<Track" in txt[:400] or b"<Race" in txt[:400]:
                (TRACK_DIR / f"{d.m_Name}.xml").write_bytes(txt)
                n += 1
    print(n, "files in", TRACK_DIR)


if __name__ == "__main__":
    if sys.argv[1] == "extract":
        extract()
    else:
        race, track = load_race_with_track(sys.argv[2])
        print(race["name"], "laps", race["laps"], "env", track["environment"])
        for g in race_gates(race, track):
            print(f"  {g.name:45s} c=({g.center[0]:8.2f},{g.center[1]:5.2f},{g.center[2]:8.2f}) "
                  f"n=({g.normal[0]:+.2f},{g.normal[1]:+.2f},{g.normal[2]:+.2f}) {g.width}x{g.height}")
