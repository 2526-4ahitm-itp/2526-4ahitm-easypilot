"""macOS capture: mss grabs the Liftoff window region, OpenCV scales it down.

Needs Screen Recording permission for the terminal (System Settings > Privacy & Security).
mss works in screen points and returns Retina pixels; the resize to `width` hides that.

mss grabs a screen region, not the window itself (CGWindowListCreateImage returns nothing on
macOS 15), so the region has to follow the window: Studio keeps one stream alive for hours while
Liftoff goes from fullscreen to the top-left quarter. The rect is re-read every REFRESH_S seconds.
"""
import time

import cv2
import mss
import numpy as np

from . import window

HALFTONE = cv2.INTER_AREA         # same names as on Windows: smooth ...
COLORONCOLOR = cv2.INTER_NEAREST  # ... or fast
REFRESH_S = 1.0                   # how often the Liftoff window rect is looked up again


class Grabber:
    def __init__(self, width=640, rect=None, mode=HALFTONE):
        self.width = width
        self.mode = mode
        self.follow = rect is None       # a fixed rect from the caller stays fixed
        self.sct = mss.mss()
        self.rect = None
        self._set_rect(rect or window.client_rect())
        self._checked = time.perf_counter()

    def _set_rect(self, rect):
        """Clip to the screens and derive the region and output height; False if nothing is left."""
        left, top, w, h = rect
        screens = self.sct.monitors[0]   # union of all displays
        x0, y0 = max(left, screens["left"]), max(top, screens["top"])
        x1 = min(left + w, screens["left"] + screens["width"])
        y1 = min(top + h, screens["top"] + screens["height"])
        if x1 - x0 < 16 or y1 - y0 < 16:
            if self.rect is not None:    # window off screen / minimised: keep the last region
                return False
            x0, y0, x1, y1 = left, top, left + w, top + h
        self.rect = (int(x0), int(y0), int(x1 - x0), int(y1 - y0))
        self.region = {"left": self.rect[0], "top": self.rect[1], "width": self.rect[2], "height": self.rect[3]}
        self.height = int(round(self.width * self.rect[3] / self.rect[2]))
        return True

    def refresh(self, force=False):
        """Follow the Liftoff window when it moved or changed size. True if the region changed."""
        now = time.perf_counter()
        if not self.follow or (not force and now - self._checked < REFRESH_S):
            return False
        self._checked = now
        try:
            rect = window.client_rect()
        except Exception:                # Liftoff gone or window list unavailable: keep the old region
            return False
        if rect == self.rect:
            return False
        old = self.rect
        return self._set_rect(rect) and self.rect != old

    def grab(self):
        """BGR uint8 image (height, width, 3)."""
        self.refresh()
        shot = np.asarray(self.sct.grab(self.region))[:, :, :3]
        return cv2.resize(shot, (self.width, self.height), interpolation=self.mode)

    def close(self):
        self.sct.close()
