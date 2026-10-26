"""Obstacles from the Liftoff track file as oriented boxes, for the waypoint flight map.

  python -m autopilot.obstacles show StrawBaleRace01 out.jpg   # project the boxes into the FPV image

The track XML only gives item name, pivot and rotation, no size. Footprints per item type were
estimated and then checked by projecting the boxes into recorded FPV frames (`show`). Gates are
obstacles too: posts and top bar of an arch, the frame of a MultiGP gate on its pole. Terrain,
trees and the level's own props (straw bales, barns, fences) are NOT in the file - the camera
has to find those (depth.py).
"""
import math
import sys
from dataclasses import dataclass

from .geometry import qrot
from .track import center_lift, gate_size, load_race_with_track

# item prefix -> (size along local x, size along local z, height) in metres, pivot on the ground
SIZES = {
    "LiftoffCrowdControlBarrier": (0.7, 2.3, 1.15),
    "CrowdControlBarrier": (0.7, 2.3, 1.15),
    "ConcreteBarrier": (0.7, 3.0, 0.9),
    "ConstructionFencing": (3.5, 0.4, 2.0),
    "PartyTent": (3.2, 3.2, 3.2),
    "AirflagLiftoff": (0.8, 0.8, 3.6),
    "AdvertBoard": (2.2, 0.5, 1.3),
    "TlTrackLight": (0.5, 0.5, 2.6),
    "LightRigBase": (0.6, 0.6, 0.3),
    "TrafficCone": (0.4, 0.4, 0.7),
    "RaceTrackTire": (0.8, 0.8, 0.4),
    "DirectionArrow": (1.0, 1.0, 1.8),
    "SteelProfile": (1.0, 6.0, 1.0),
}
FLAT = ("DiscCone", "Tape")          # lie on the ground, never in the way
POST = 0.35                          # thickness of gate posts / frames


@dataclass
class Box:
    """Oriented box standing on y0: centre (cx, cz), half sizes along its own axes, yaw in rad."""
    name: str
    cx: float
    cz: float
    hx: float
    hz: float
    yaw: float
    y0: float
    y1: float

    def corners(self):
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        out = []
        for ex, ez in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            lx, lz = ex * self.hx, ez * self.hz
            out.append((self.cx + lx * c + lz * s, self.cz - lx * s + lz * c))
        return out

    def distance(self, p):
        """Distance from a 3-D point to the box (0 inside)."""
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        dx, dz = p[0] - self.cx, p[2] - self.cz
        lx, lz = dx * c - dz * s, dx * s + dz * c
        ox = max(0.0, abs(lx) - self.hx)
        oz = max(0.0, abs(lz) - self.hz)
        oy = max(0.0, self.y0 - p[1], p[1] - self.y1)
        return math.sqrt(ox * ox + oz * oz + oy * oy)


def size_of(item):
    for prefix, size in SIZES.items():
        if item.startswith(prefix):
            return size
    return None


def _yaw(bp):
    """Heading of the item's local x axis (rotation about world y), works for any euler order."""
    ax = qrot(bp.quat, (1.0, 0.0, 0.0))
    return math.atan2(-ax[2], ax[0])


def track_boxes(track, unknown=(1.0, 1.0, 2.0)):
    """All obstacles of a track as Boxes. Unknown item types get a conservative default box."""
    boxes, skipped = [], {}
    for bp in track["blueprints"]:
        item = bp.item
        if "TriggerBox" in item or item.startswith(FLAT) or item.startswith("Checkpoint"):
            continue
        yaw = _yaw(bp)
        gate = gate_size(item, bp.extra.get("scale"))
        if gate:
            w, h = gate
            lift = center_lift(item, h)
            top = bp.pos[1] + lift + h / 2 + POST
            bottom = bp.pos[1]                       # frames on poles: the pole reaches the ground
            # posts and bar of the gate as one wall: in a 2.5-D map a gate opening is not flyable
            # anyway, the waypoint flight goes around gates
            boxes.append(Box(item, bp.pos[0], bp.pos[2], w / 2 + POST, POST / 2 + 0.1, yaw, bottom, top))
            continue
        size = size_of(item)
        if size is None:
            skipped[item] = skipped.get(item, 0) + 1
            size = unknown
        sx, sz, h = size
        boxes.append(Box(item, bp.pos[0], bp.pos[2], sx / 2, sz / 2, yaw, bp.pos[1], bp.pos[1] + h))
    return boxes, skipped


def add_to_grid(grid, boxes):
    """Rasterise boxes into an OccupancyGrid (cell tops = box tops)."""
    for b in boxes:
        pts = b.corners()
        x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
        z0, z1 = min(p[1] for p in pts), max(p[1] for p in pts)
        i0, i1 = int(math.floor(x0 / grid.cell)), int(math.floor(x1 / grid.cell))
        j0, j1 = int(math.floor(z0 / grid.cell)), int(math.floor(z1 / grid.cell))
        half = grid.cell * 0.5
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                cx, cz = grid.center((i, j))
                # cell overlaps the box if its centre is within box + half a cell
                if b.distance((cx, b.y0, cz)) <= half * 1.42:
                    grid.top[(i, j)] = max(grid.top.get((i, j), -1e9), b.y1)
    grid.version += 1


def min_clearance(boxes, points):
    """Smallest distance between a flown path (3-D points) and any box, with the box name."""
    best = (1e9, "")
    for p in points:
        for b in boxes:
            if abs(b.cx - p[0]) > 8 or abs(b.cz - p[2]) > 8:
                continue
            d = b.distance(p)
            if d < best[0]:
                best = (d, b.name)
    return best


def draw_boxes(img, cam, state, boxes, max_dist=40.0, color=(0, 140, 255)):
    import cv2
    for b in boxes:
        d = math.hypot(b.cx - state.pos[0], b.cz - state.pos[2])
        if d > max_dist or d < 2.5:          # the camera stands inside the start pad boxes
            continue
        ring = b.corners()
        pts3 = [(x, b.y0, z) for x, z in ring] + [(x, b.y1, z) for x, z in ring]
        uv = [cam.project(state.quat, state.pos, p) for p in pts3]
        for a, c in [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]:
            if uv[a] is None or uv[c] is None:
                continue
            p, q = uv[a], uv[c]
            if max(abs(p[0]), abs(p[1]), abs(q[0]), abs(q[1])) > 5000:
                continue
            cv2.line(img, (int(p[0]), int(p[1])), (int(q[0]), int(q[1])), color, 1)
    return img


def main(argv):
    if not argv or argv[0] != "show":
        print(__doc__)
        return
    import cv2
    from .camera import Camera
    from .capture import Grabber
    from .sysid import load_camera
    from .telemetry import Telemetry
    _, track = load_race_with_track(argv[1])
    boxes, skipped = track_boxes(track)
    print(f"{len(boxes)} boxes, unknown types: {skipped}")
    tel = Telemetry()
    tel.start()
    s = tel.wait(5)
    g = Grabber(960)
    img = g.grab()
    s = tel.latest() or s
    c = load_camera()
    cam = Camera(img.shape[1], img.shape[0], c.hfov_deg, c.tilt_deg)
    cv2.imwrite(argv[2] if len(argv) > 2 else "obstacles.jpg", draw_boxes(img, cam, s, boxes))
    tel.close()


if __name__ == "__main__":
    main(sys.argv[1:])
