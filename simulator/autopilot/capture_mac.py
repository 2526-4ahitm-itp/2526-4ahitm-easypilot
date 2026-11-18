"""macOS capture: mss grabs the Liftoff window region, OpenCV scales it down.

Needs Screen Recording permission for the terminal (System Settings > Privacy & Security).
mss works in screen points and returns Retina pixels; the resize to `width` hides that.
"""
import cv2
import mss
import numpy as np

from . import window

HALFTONE = cv2.INTER_AREA         # same names as on Windows: smooth ...
COLORONCOLOR = cv2.INTER_NEAREST  # ... or fast


class Grabber:
    def __init__(self, width=640, rect=None, mode=HALFTONE):
        self.rect = rect or window.client_rect()
        left, top, w, h = self.rect
        self.width = width
        self.height = int(round(width * h / w))
        self.mode = mode
        self.sct = mss.mss()
        self.region = {"left": left, "top": top, "width": w, "height": h}

    def grab(self):
        """BGR uint8 image (height, width, 3)."""
        shot = np.asarray(self.sct.grab(self.region))[:, :, :3]
        return cv2.resize(shot, (self.width, self.height), interpolation=self.mode)

    def close(self):
        self.sct.close()
