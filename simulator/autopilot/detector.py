"""Live gate detection (YOLO pose, 4 opening corners) and camera-based correction of the gate map.

The track file gives every gate approximately; for some item types the opening is not
where the pivot suggests (MultiGP frames on poles, inflatables). Each detection is
matched to the map gate whose projection is closest, its 3-D pose is solved with PnP
from the four corners, and a low-pass filtered offset corrects that gate. The racer
re-plans when a correction becomes significant.
"""
import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .camera import Camera
from .geometry import cross, qrot, unit
from .planner import Gate

MODEL = Path(__file__).resolve().parent / "models" / "gates.pt"


@dataclass
class Detection:
    box: tuple            # x0, y0, x1, y1 (pixels)
    conf: float
    kps: np.ndarray       # (4, 2) bottom-left, top-left, top-right, bottom-right
    kp_conf: np.ndarray   # (4,)

    @property
    def center(self):
        good = self.kp_conf > 0.5
        if good.sum() >= 3:
            return tuple(self.kps[good].mean(axis=0))
        return ((self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2)


class GateDetector:
    def __init__(self, model=MODEL, conf=0.35, imgsz=640):
        from ultralytics import YOLO
        self.model = YOLO(str(model))
        self.conf, self.imgsz = conf, imgsz

    def detect(self, bgr):
        r = self.model.predict(bgr, imgsz=self.imgsz, conf=self.conf, verbose=False, device=0)[0]
        out = []
        if r.boxes is None or len(r.boxes) == 0:
            return out
        boxes = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        kps = r.keypoints.xy.cpu().numpy() if r.keypoints is not None else np.zeros((len(boxes), 4, 2))
        kpc = r.keypoints.conf.cpu().numpy() if r.keypoints is not None and r.keypoints.conf is not None \
            else np.ones((len(boxes), 4))
        for b, c, k, kc in zip(boxes, confs, kps, kpc):
            out.append(Detection(tuple(float(v) for v in b), float(c), k, kc))
        return out


def opening_corners(g):
    side = unit(cross((0.0, 1.0, 0.0), g.normal), (1.0, 0.0, 0.0))
    c, w, h = g.center, g.width / 2, g.height / 2
    return [tuple(c[i] + side[i] * sx * w + (h * sy if i == 1 else 0.0) for i in range(3))
            for sx, sy in ((-1, -1), (-1, 1), (1, 1), (1, -1))]


def solve_gate_center(cam: Camera, quat, pos, det: Detection, gate: Gate):
    """World position of the detected opening centre, using the map gate's size and orientation."""
    good = det.kp_conf > 0.5
    if good.sum() < 4:
        return None
    w, h = gate.width / 2, gate.height / 2
    obj = np.array([[-w, -h, 0], [-w, h, 0], [w, h, 0], [w, -h, 0]], dtype=np.float64)
    K = np.array([[cam.f, 0, cam.width / 2], [0, cam.f, cam.height / 2], [0, 0, 1]], dtype=np.float64)
    ok, rvec, tvec = cv2.solvePnP(obj, det.kps.astype(np.float64), K, None, flags=cv2.SOLVEPNP_IPPE)
    if not ok:
        return None
    # OpenCV camera: x right, y down, z forward -> Unity camera: x right, y up, z forward
    t = tvec.ravel()
    p_cam = (t[0], -t[1], t[2])
    if not 0.5 < p_cam[2] < 80:
        return None
    q = cam.cam_quat(quat)
    d = qrot(q, p_cam)
    return tuple(pos[i] + d[i] for i in range(3))


@dataclass
class GateMap:
    """Map gates plus camera-based corrections (one offset per gate).

    Single PnP solutions are noisy (a few dm at 10 m), so a gate is only corrected when the
    evidence is consistent: median of the last measurements, enough of them, small spread, and
    larger than a dead band. Correctly mapped gates therefore stay untouched.
    """
    gates: list
    max_correction: float = 2.5     # m, larger differences are a wrong association, not a map error
    min_hits: int = 8
    dead_band: float = 0.6          # m, smaller offsets are noise (arch corners are only virtual) and passable
    max_spread: float = 0.6         # m, median absolute deviation allowed
    min_dist: float = 4.0           # m, closer the gate is cut off by the image border
    max_dist: float = 25.0          # m, farther the corners are too small
    commit_dist: float = 12.0       # m, closer than this the line is frozen (no sideways jump at speed)
    fixed: set = field(default_factory=set)     # indices never corrected (e.g. the start gate)
    offsets: dict = field(default_factory=dict)
    samples: dict = field(default_factory=dict)
    hits: dict = field(default_factory=dict)
    version: int = 0

    def corrected(self, i):
        g = self.gates[i]
        o = self.offsets.get(i, (0.0, 0.0, 0.0))
        return Gate(tuple(g.center[k] + o[k] for k in range(3)), g.normal, g.width, g.height, g.name)

    def all_corrected(self):
        return [self.corrected(i) for i in range(len(self.gates))]

    def associate(self, cam, quat, pos, det, max_px=None):
        """Index of the map gate whose projected (corrected) centre is closest to the detection."""
        u, v = det.center
        best, best_d = None, max_px or 0.25 * cam.width
        for i in range(len(self.gates)):
            g = self.corrected(i)
            if math.dist(pos, g.center) > 60:
                continue
            uv = cam.project(quat, pos, g.center)
            if uv is None:
                continue
            d = math.hypot(uv[0] - u, uv[1] - v)
            if d < best_d:
                best, best_d = i, d
        return best

    def _estimate(self, i):
        xs = self.samples[i]
        if len(xs) < self.min_hits:
            return None
        med = tuple(sorted(x[k] for x in xs)[len(xs) // 2] for k in range(3))
        mad = sorted(math.dist(x, med) for x in xs)[len(xs) // 2]
        if mad > self.max_spread:
            return None
        return med

    def candidates(self, cam, quat, pos, det, max_px=None):
        """Map gates whose projected (corrected) centre lies near the detection in the image."""
        u, v = det.center
        limit = max_px or 0.25 * cam.width
        out = []
        for i in range(len(self.gates)):
            g = self.corrected(i)
            if math.dist(pos, g.center) > 60:
                continue
            uv = cam.project(quat, pos, g.center)
            if uv is not None and math.hypot(uv[0] - u, uv[1] - v) < limit:
                out.append(i)
        return out

    def match(self, cam, quat, pos, det):
        """(index, solved centre) of the gate that fits the detection best in 3-D.

        Gates standing in a row look alike and overlap in the image; the depth from PnP tells
        them apart, a 2-D nearest-projection rule does not.
        """
        best, best_err, best_c = None, self.max_correction, None
        for i in self.candidates(cam, quat, pos, det):
            c = solve_gate_center(cam, quat, pos, det, self.gates[i])
            if c is None:
                continue
            err = math.dist(c, self.corrected(i).center)
            if err < best_err:
                best, best_err, best_c = i, err, c
        return best, best_c

    def update(self, cam, quat, pos, detections):
        changed = []
        for det in detections:
            i, c = self.match(cam, quat, pos, det)
            if i is None or i in self.fixed:
                continue
            if not self.min_dist < math.dist(pos, self.gates[i].center) < self.max_dist:
                continue
            raw = tuple(c[k] - self.gates[i].center[k] for k in range(3))
            # keep only the offset within the gate plane: that decides whether the drone passes.
            # Along the normal (= roughly the flight direction) the frame-to-telemetry latency
            # dominates (30 ms at 27 m/s = 0.8 m), and there the map error does not matter.
            n = self.gates[i].normal
            along = sum(raw[k] * n[k] for k in range(3))
            raw = tuple(raw[k] - along * n[k] for k in range(3))
            self.samples.setdefault(i, []).append(raw)
            self.samples[i] = self.samples[i][-40:]
            self.hits[i] = self.hits.get(i, 0) + 1
            est = self._estimate(i)
            if est is None or math.dist(pos, self.gates[i].center) < self.commit_dist:
                continue
            old = self.offsets.get(i, (0.0, 0.0, 0.0))
            new = est if math.sqrt(sum(x * x for x in est)) > self.dead_band else (0.0, 0.0, 0.0)
            if math.dist(new, old) > 0.25:
                self.offsets[i] = new
                changed.append(i)
        if changed:
            self.version += 1
        return changed


class DetectorThread(threading.Thread):
    """Grabs frames, runs YOLO, updates the GateMap with the telemetry pose of each frame."""

    def __init__(self, frames, telemetry, cam: Camera, gate_map: GateMap, latency=0.012):
        super().__init__(daemon=True)
        self.frames, self.tel, self.cam, self.map = frames, telemetry, cam, gate_map
        self.latency = latency
        self.det = GateDetector()
        self.running = True
        self.last = (None, [], None)     # (frame, detections, state) for the overlay
        self.fps = 0.0

    def run(self):
        last_stamp, n, t0 = 0.0, 0, time.perf_counter()
        while self.running:
            stamp, img = self.frames.latest()
            if img is None or stamp == last_stamp:
                time.sleep(0.003)
                continue
            last_stamp = stamp
            s = self.tel.at(stamp - self.latency)
            dets = self.det.detect(img)
            if s is not None:
                self.map.update(self.cam, s.quat, s.pos, dets)
            self.last = (img, dets, s)
            n += 1
            if time.perf_counter() - t0 > 1.0:
                self.fps, n, t0 = n / (time.perf_counter() - t0), 0, time.perf_counter()

    def close(self):
        self.running = False


def draw_overlay(img, dets, state, cam, gate_map, info=""):
    """Image for the audience: detections (green), map gates (red), corrected gates (yellow)."""
    out = img.copy()
    for d in dets:
        x0, y0, x1, y1 = (int(v) for v in d.box)
        cv2.rectangle(out, (x0, y0), (x1, y1), (60, 220, 60), 2)
        pts = d.kps.astype(np.int32)
        cv2.polylines(out, [pts], True, (60, 220, 60), 1)
        cv2.putText(out, f"Tor {d.conf:.2f}", (x0, max(12, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 220, 60), 1)
    if state is not None:
        for i, g in enumerate(gate_map.gates):
            if math.dist(state.pos, g.center) > 60:
                continue
            for gg, col in ((g, (60, 60, 230)), (gate_map.corrected(i), (0, 220, 255))):
                uv = cam.project(state.quat, state.pos, gg.center)
                if uv is not None and 0 <= uv[0] < cam.width and 0 <= uv[1] < cam.height:
                    cv2.circle(out, (int(uv[0]), int(uv[1])), 4, col, -1)
    cv2.putText(out, info, (10, cam.height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    return out
