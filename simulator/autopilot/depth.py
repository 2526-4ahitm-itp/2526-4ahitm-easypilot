"""Obstacles from the FPV camera: motion stereo with the exact poses from the telemetry.

Liftoff gives no depth image, but it gives the drone pose at 100 Hz. A point tracked through
several FPV frames is therefore seen from known camera positions and can be triangulated:
  1. corners (goodFeaturesToTrack) are tracked frame to frame (pyramidal LK, forward-backward check)
  2. every track remembers the camera pose where it started (pose = telemetry at the frame time)
  3. once the angle between the start ray and the current ray (parallax) exceeds 2, 5 and 10 deg,
     the two rays are intersected; rays that miss each other by more than a few cm are dropped
  4. points above the ground band are obstacle evidence; a map cell becomes an obstacle only after
     several points from at least two frames (single mismatches never block a path)

Long tracks matter: straight ahead (focus of expansion) the parallax of a two-frame pair is tiny,
a track that is followed while the drone approaches collects enough of it. OSD elements that
stand still on the screen are removed by a mask and by requiring the track to move in the image.
"""
import math
import threading
import time

import cv2
import numpy as np

from .camera import Camera
from .geometry import axis_angle, qmul


def quat_matrix(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def cam_rotation(cam, body_quat):
    """Camera -> world rotation matrix (camera x right, y up, z forward)."""
    return quat_matrix(qmul(body_quat, axis_angle((1.0, 0.0, 0.0), -math.radians(cam.tilt_deg))))


def projection(cam, body_quat, pos):
    """3x4 matrix world -> pixel for the Camera model (v points down, camera y up)."""
    r_cw = cam_rotation(cam, body_quat).T
    k = np.array([[cam.f, 0, cam.width / 2], [0, -cam.f, cam.height / 2], [0, 0, 1.0]])
    t = -r_cw @ np.asarray(pos, dtype=float)
    return k @ np.hstack([r_cw, t[:, None]]), r_cw, t


def pixel_rays(cam, rot, uv):
    """World unit rays of pixels uv (N x 2) for camera rotation rot (camera -> world)."""
    d = np.column_stack([(uv[:, 0] - cam.width / 2) / cam.f, -(uv[:, 1] - cam.height / 2) / cam.f,
                         np.ones(len(uv))])
    d = d @ rot.T
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def osd_mask(h, w):
    """Liftoff OSD in flight: mode/battery top left, ALT/SPD top right, compass top centre,
    stick boxes bottom centre, Rec bottom left, logo bottom right."""
    m = np.full((h, w), 255, np.uint8)
    for x0, y0, x1, y1 in ((0, 0, .22, .12), (.86, 0, 1, .3), (.38, .13, .62, .23), (.4, .84, .6, 1),
                           (0, .92, .12, 1), (.88, .84, 1, 1)):
        m[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = 0
    return m


class MotionStereo:
    LEVELS = (2.0, 5.0, 10.0)          # parallax (deg) at which a track is triangulated

    def __init__(self, cam: Camera, max_depth=16.0, min_depth=0.7, n_features=600, max_age=4.0):
        self.cam = cam
        self.max_depth, self.min_depth = max_depth, min_depth
        self.n_features, self.max_age = n_features, max_age
        self.mask = osd_mask(cam.height, cam.width)
        self.prev = None
        self.pts = np.zeros((0, 2), np.float32)      # current pixel of every track
        self.start_uv = np.zeros((0, 2))
        self.start_c = np.zeros((0, 3))              # camera position at the track start
        self.start_d = np.zeros((0, 3))              # world ray at the track start
        self.start_t = np.zeros(0)
        self.level = np.zeros(0, int)
        self.frames = 0
        self.pairs = 0                               # frames that produced points
        self.last_points = np.zeros((0, 3))

    def _spawn(self, gray, rot, pos, t):
        need = self.n_features - len(self.pts)
        if need < self.n_features * 0.3:
            return
        mask = self.mask.copy()
        for u, v in self.pts:
            cv2.circle(mask, (int(u), int(v)), 10, 0, -1)
        new = cv2.goodFeaturesToTrack(gray, need, 0.01, 10, mask=mask, blockSize=5)
        if new is None:
            return
        new = new[:, 0].astype(np.float32)
        self.pts = np.vstack([self.pts, new])
        self.start_uv = np.vstack([self.start_uv, new])
        self.start_c = np.vstack([self.start_c, np.tile(pos, (len(new), 1))])
        self.start_d = np.vstack([self.start_d, pixel_rays(self.cam, rot, new.astype(float))])
        self.start_t = np.concatenate([self.start_t, np.full(len(new), t)])
        self.level = np.concatenate([self.level, np.zeros(len(new), int)])

    def _keep(self, k):
        self.pts, self.start_uv, self.start_c = self.pts[k], self.start_uv[k], self.start_c[k]
        self.start_d, self.start_t, self.level = self.start_d[k], self.start_t[k], self.level[k]

    def process(self, bgr, quat, pos, t):
        """Track one frame; returns newly triangulated world points (N x 3)."""
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        rot = cam_rotation(self.cam, quat)
        pos = np.asarray(pos, float)
        self.frames += 1
        out = np.zeros((0, 3))
        if self.prev is not None and len(self.pts):
            lk = dict(winSize=(21, 21), maxLevel=3,
                      criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.02))
            p0 = self.pts.reshape(-1, 1, 2)
            p1, st, _ = cv2.calcOpticalFlowPyrLK(self.prev, gray, p0, None, **lk)
            pb, st2, _ = cv2.calcOpticalFlowPyrLK(gray, self.prev, p1, None, **lk)
            p1 = p1.reshape(-1, 2)
            ok = (st[:, 0] == 1) & (st2[:, 0] == 1) & (np.linalg.norm(pb.reshape(-1, 2) - self.pts, axis=1) < 0.5)
            ok &= (p1[:, 0] >= 0) & (p1[:, 0] < self.cam.width) & (p1[:, 1] >= 0) & (p1[:, 1] < self.cam.height)
            ok &= (t - self.start_t) < self.max_age
            self.pts = p1.astype(np.float32)
            self._keep(ok)
            out = self._triangulate(rot, pos)
        self.prev = gray
        self._spawn(gray, rot, pos, t)
        if len(out):
            self.pairs += 1
        self.last_points = out
        return out

    def _triangulate(self, rot, pos):
        if not len(self.pts):
            return np.zeros((0, 3))
        d1 = pixel_rays(self.cam, rot, self.pts.astype(float))
        d0 = self.start_d
        cosp = np.clip(np.sum(d0 * d1, axis=1), -1, 1)
        par = np.degrees(np.arccos(cosp))
        thresholds = np.array(self.LEVELS + (1e9,))[np.minimum(self.level, len(self.LEVELS))]
        moved = np.linalg.norm(self.pts - self.start_uv, axis=1) > 3.0       # not a static OSD element
        due = (par > thresholds) & moved
        if not due.any():
            return np.zeros((0, 3))
        idx = np.nonzero(due)[0]
        self.level[idx] = np.searchsorted(np.array(self.LEVELS), par[idx], side="right")
        c0, a, b = self.start_c[idx], d0[idx], d1[idx]
        # closest points of the two rays c0 + s*a and pos + u*b
        w = c0 - pos
        ab = np.sum(a * b, axis=1)
        aw, bw = np.sum(a * w, axis=1), np.sum(b * w, axis=1)
        den = 1 - ab * ab
        s = (ab * bw - aw) / den
        u = (bw - ab * aw) / den
        p_a = c0 + a * s[:, None]
        p_b = pos + b * u[:, None]
        gap = np.linalg.norm(p_a - p_b, axis=1)
        X = (p_a + p_b) / 2
        keep = (s > self.min_depth) & (u > self.min_depth) & (u < self.max_depth)
        keep &= gap < 0.03 + 0.01 * u
        # enough baseline: yawing on the spot gives parallax from rotation only, then a 1 deg pose
        # error (frame vs. telemetry time) puts points at ~1 m in front of the camera
        base = np.linalg.norm(c0 - pos, axis=1)
        keep &= (base > 0.3) & (base > 0.06 * u)
        return X[keep]


class CameraMapper(threading.Thread):
    """Runs MotionStereo on the live FPV image and writes confirmed obstacles into the grid."""

    def __init__(self, tel, grid, width=960, fps=60, min_points=4, min_frames=2, ground_band=0.45,
                 latency=0.012, debug_dir=None):
        super().__init__(daemon=True)
        from .capture import COLORONCOLOR, FrameStream
        from .sysid import load_camera
        self.tel, self.grid = tel, grid
        self.frames = FrameStream(width, fps=fps, mode=COLORONCOLOR)
        self.camera_cfg = load_camera()
        self.min_points, self.min_frames, self.ground_band = min_points, min_frames, ground_band
        self.latency = latency
        self.evidence = {}           # cell -> [count, set(frame ids), max height]
        self.confirmed = set()
        self.removed = 0
        self.points_total = 0
        self.fps = 0.0
        self.running = True
        self.error = ""
        self.stereo = None
        self.debug_dir = debug_dir
        self.saved = 0.0

    def run(self):
        try:
            self._run()
        except Exception as exc:               # never take the control loop down
            import traceback
            self.error = traceback.format_exc(limit=3)

    def _run(self):
        self.frames.start()
        while self.frames.latest()[1] is None and self.running:
            time.sleep(0.01)
        h, w = self.frames.latest()[1].shape[:2]
        c = self.camera_cfg
        self.stereo = MotionStereo(Camera(w, h, c.hfov_deg, c.tilt_deg))
        last, n, t0 = 0.0, 0, time.perf_counter()
        while self.running:
            stamp, img = self.frames.latest()
            if stamp == last:
                time.sleep(0.002)
                continue
            last = stamp
            s = self.tel.at(stamp - self.latency)
            if s is None or max(abs(v) for v in s.pos) < 1e-3:
                continue
            pts = self.stereo.process(img, s.quat, s.pos, stamp)
            n += 1
            if stamp - t0 > 1.0:
                self.fps, n, t0 = n / (stamp - t0), 0, stamp
            if len(pts):
                self._add(pts, self.stereo.frames, s.pos)
                if self.debug_dir is not None and time.perf_counter() - self.saved > 0.4:
                    self.saved = time.perf_counter()
                    self._save(img, s, pts)
        self.frames.close()

    def _carve(self, cam_pos, p):
        """The ray camera -> point is free: camera cells it crosses below their top lose evidence."""
        g = self.grid
        dx, dy, dz = p[0] - cam_pos[0], p[1] - cam_pos[1], p[2] - cam_pos[2]
        dist = math.hypot(dx, dz)
        n = int(dist / (g.cell * 0.5))
        for i in range(1, n - 1):
            f = i / n
            if dist * (1 - f) < 0.6:                 # the last bit belongs to the point's own cell
                break
            k = g.key(cam_pos[0] + dx * f, cam_pos[2] + dz * f)
            if k not in self.confirmed:
                continue
            if cam_pos[1] + dy * f < g.top.get(k, -1e9) - 0.2:
                e = self.evidence[k]
                e[3] += 1
                if e[3] > 3 + e[0]:
                    self.confirmed.discard(k)
                    g.top.pop(k, None)
                    g.version += 1
                    self.removed += 1

    def _add(self, pts, frame, cam_pos=None):
        g = self.grid
        self.points_total += len(pts)
        if cam_pos is not None:
            for p in pts[::3]:
                self._carve(cam_pos, p)
        for x, y, z in pts:
            k = g.key(x, z)
            if y < g.ground_at(k) + self.ground_band:
                if y > g.default_ground - 1.0:
                    g.add_point((x, y, z))          # ground evidence
                continue
            e = self.evidence.setdefault(k, [0, set(), -1e9, 0])      # hits, frames, top, free votes
            e[0] += 1
            e[1].add(frame)
            e[2] = max(e[2], y)
            if k not in self.confirmed and e[0] >= self.min_points and len(e[1]) >= self.min_frames:
                self.confirmed.add(k)
                g.add_point((x, e[2], z))
            elif k in self.confirmed and y > g.top.get(k, -1e9):
                g.add_point((x, y, z))

    def _save(self, img, s, pts):
        """Debug frame: triangulated points, red = obstacle (above the ground band), green = ground."""
        out = img.copy()
        cam = self.stereo.cam
        for p in pts:
            uv = cam.project(s.quat, s.pos, tuple(p))
            if uv is None:
                continue
            high = p[1] > self.grid.ground_at(self.grid.key(p[0], p[2])) + self.ground_band
            d = math.dist(p, s.pos)
            cv2.circle(out, (int(uv[0]), int(uv[1])), 3, (40, 40, 230) if high else (40, 200, 40), -1)
            if high:
                cv2.putText(out, f"{d:.0f}", (int(uv[0]) + 4, int(uv[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                            (255, 255, 255), 1)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(self.debug_dir / f"{self.stereo.frames:05d}.jpg"), out)

    def close(self):
        self.running = False
