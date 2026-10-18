"""Gate (Torbogen) detection in the Liftoff FPV image.

Liftoff's race arches are thin white inverted-U shapes. Classical pipeline, no training data:
  1. white mask (low saturation, high value), HUD areas removed
  2. connected components, keep thin curved shapes: low fill ratio of the bounding box,
     both lower corners occupied (the two legs), top centre occupied, inside empty
  3. score by shape; the opening (inner rectangle between the legs) is the gate
"""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class GateDetection:
    x: int          # bounding box in image pixels
    y: int
    w: int
    h: int
    score: float

    @property
    def center(self):
        """Centre of the opening (between the legs, below the arch top)."""
        return (self.x + self.w / 2, self.y + self.h * 0.6)

    @property
    def feet(self):
        return (self.x + self.w * 0.08, self.y + self.h), (self.x + self.w * 0.92, self.y + self.h)


def hud_mask(h, w):
    """255 where the image shows the scene, 0 on Liftoff HUD elements."""
    m = np.full((h, w), 255, np.uint8)
    m[: int(0.12 * h), :] = 0                                   # timer, compass
    m[int(0.12 * h): int(0.75 * h), int(0.86 * w):] = 0          # ALT/SPD + ghost list
    m[:, : int(0.03 * w)] = 0
    m[int(0.92 * h):, : int(0.08 * w)] = 0                       # Rec.
    return m


_KERNELS = {}


def white_mask(bgr):
    """Thin bright, unsaturated structures. The top-hat removes large bright areas (sky, clouds, tents)."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v, s = hsv[:, :, 2], hsv[:, :, 1]
    scale = bgr.shape[1] / 960
    sizes = tuple(max(5, int(k * scale) | 1) for k in (9, 21, 41))
    if sizes not in _KERNELS:
        _KERNELS[sizes] = [cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)) for k in sizes]
    th = np.maximum.reduce([cv2.morphologyEx(v, cv2.MORPH_TOPHAT, k) for k in _KERNELS[sizes]])
    m = ((th > 35) & (s < 70) & (v > 150)).astype(np.uint8) * 255
    m &= hud_mask(*m.shape)
    return m


def detect_gates(bgr, min_size=12):
    m = white_mask(bgr)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    h_img, w_img = m.shape
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w < min_size or h < min_size or w > 0.9 * w_img:
            continue
        aspect = w / h
        if not 0.6 < aspect < 2.6:
            continue
        fill = area / (w * h)
        if not 0.08 < fill < 0.55:
            continue
        comp = (labels[y:y + h, x:x + w] == i)
        bx, by = max(1, w // 5), max(1, h // 4)
        left = comp[h // 2:, :bx].mean()
        right = comp[h // 2:, -bx:].mean()
        top = comp[:by, w // 3: 2 * w // 3].mean()
        inside = comp[by + h // 6: h - 2, bx + w // 10: w - bx - w // 10].mean() if h > 8 and w > 8 else 1.0
        if left < 0.06 or right < 0.06 or top < 0.15 or inside > 0.12:
            continue
        # the legs should reach down; a cloud or tent is filled or flat
        score = min(left, right) * 2 + top - inside * 3 + min(1.0, (w * h) / 4000) * 0.3
        out.append(GateDetection(int(x), int(y), int(w), int(h), float(score)))
    return sorted(out, key=lambda g: -g.w * g.h)


def draw(bgr, gates, color=(0, 255, 255)):
    img = bgr.copy()
    for g in gates:
        cv2.rectangle(img, (g.x, g.y), (g.x + g.w, g.y + g.h), color, 2)
        cx, cy = g.center
        cv2.drawMarker(img, (int(cx), int(cy)), color, cv2.MARKER_CROSS, 12, 2)
    return img
