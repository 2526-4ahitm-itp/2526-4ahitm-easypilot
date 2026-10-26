"""Motion stereo on rendered frames with known poses: a textured wall straight ahead and ground.

Run from simulator/:  python -m unittest autopilot.tests.test_depth -v
"""
import math
import random
import unittest

import cv2
import numpy as np

from autopilot.camera import Camera
from autopilot.depth import MotionStereo
from autopilot.geometry import axis_angle

CAM = Camera(960, 540, 125.0, 42.0)


def scene(seed=1):
    r = random.Random(seed)
    pts = []
    # obstacle: 2 m wide, 1.6 m high block 10 m ahead, slightly left of the flight line
    for _ in range(500):
        pts.append((r.uniform(-1.5, 0.5), r.uniform(0.02, 1.6), 10.0))
    for _ in range(1500):
        pts.append((r.uniform(-15, 15), 0.0, r.uniform(2, 40)))
    return pts


WALL = [(-1.5, 0.0, 10.0), (0.5, 0.0, 10.0), (0.5, 1.6, 10.0), (-1.5, 1.6, 10.0)]


def render(pts, quat, pos):
    """Painter's algorithm: far ground, opaque wall face with its texture, near ground."""
    img = np.full((CAM.height, CAM.width, 3), 90, np.uint8)

    def dots(sel):
        for i, p in sel:
            uv = CAM.project(quat, pos, p)
            if uv is None or not (-20 <= uv[0] < CAM.width + 20 and -20 <= uv[1] < CAM.height + 20):
                continue
            rad = max(2, int(14 / math.dist(p, pos)))
            shade = 40 + (i * 37) % 200
            cv2.circle(img, (int(uv[0]), int(uv[1])), rad, (shade, shade, shade), -1)
    indexed = list(enumerate(pts))
    dots([ip for ip in indexed if ip[1][1] == 0.0 and ip[1][2] > 10.0])
    face = [CAM.project(quat, pos, c) for c in WALL]
    if all(face):
        cv2.fillPoly(img, [np.array(face, np.int32)], (120, 120, 120))
    dots([ip for ip in indexed if ip[1][1] != 0.0 or abs(ip[1][2] - 10.0) < 0.06 and ip[1][1] > 0])
    dots([ip for ip in indexed if ip[1][1] == 0.0 and ip[1][2] <= 10.0])
    return cv2.GaussianBlur(img, (3, 3), 0)


class MotionStereoTest(unittest.TestCase):
    def test_wall_ahead_is_found(self):
        pts = scene()
        # flying at 1.5 m height towards +z with 4 m/s, nose down 15 deg (camera looks 27 deg up)
        quat = axis_angle((1.0, 0.0, 0.0), math.radians(15))
        ms = MotionStereo(CAM)
        found = []
        for i in range(90):            # 90 frames at 60 fps = 1.5 s, 6 m: wall from 10 m to 4 m
            t = i / 60
            pos = (0.0, 1.5, t * 4.0)
            out = ms.process(render(pts, quat, pos), quat, pos, t)
            found.extend(out)
        found = np.array(found)
        self.assertGreater(len(found), 30)
        wall = found[(found[:, 1] > 0.45)]
        ground = found[(found[:, 1] <= 0.45)]
        print(f"\n  {len(found)} points, {len(wall)} above ground, {len(ground)} ground")
        # obstacle points must lie on the block (z ~ 10 m), not in free space
        self.assertGreater(len(wall), 15)
        err = wall[:, 2] - 10.0
        self.assertLess(np.median(np.abs(err)), 0.3)
        self.assertGreater(np.mean(np.abs(err) < 1.0), 0.8)
        # outliers come from the silhouette (background seen past the edge) and lie BEHIND the wall;
        # nothing may appear in front of it, that would block free space
        self.assertGreater(err.min(), -0.7)
        # ground points really on the ground
        self.assertLess(np.median(np.abs(ground[:, 1])), 0.1)


if __name__ == "__main__":
    unittest.main()
