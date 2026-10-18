"""Fast downscaled capture of the Liftoff FPV image (GDI StretchBlt, no extra packages).

The game renders at 4K; vision only needs ~640 px wide frames, so the GPU-side
scaling of StretchBlt keeps a grab at a few milliseconds.
"""
import ctypes
import ctypes.wintypes as wt
import threading
import time

import numpy as np

from . import window

gdi32 = ctypes.windll.gdi32
user32 = ctypes.windll.user32
SRCCOPY = 0x00CC0020
HALFTONE = 4

_H = ctypes.c_void_p
user32.GetDC.restype = _H
user32.GetDC.argtypes = [_H]
user32.ReleaseDC.argtypes = [_H, _H]
gdi32.CreateCompatibleDC.restype = _H
gdi32.CreateCompatibleDC.argtypes = [_H]
gdi32.CreateCompatibleBitmap.restype = _H
gdi32.CreateCompatibleBitmap.argtypes = [_H, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = _H
gdi32.SelectObject.argtypes = [_H, _H]
gdi32.SetStretchBltMode.argtypes = [_H, ctypes.c_int]
gdi32.StretchBlt.argtypes = [_H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             _H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.DWORD]
gdi32.GetDIBits.argtypes = [_H, _H, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]
gdi32.DeleteObject.argtypes = [_H]
gdi32.DeleteDC.argtypes = [_H]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class Grabber:
    def __init__(self, width=640, rect=None):
        self.rect = rect or window.client_rect()
        left, top, w, h = self.rect
        self.width = width
        self.height = int(round(width * h / w))
        self.src = user32.GetDC(0)
        self.mem = gdi32.CreateCompatibleDC(self.src)
        self.bmp = gdi32.CreateCompatibleBitmap(self.src, self.width, self.height)
        gdi32.SelectObject(self.mem, self.bmp)
        gdi32.SetStretchBltMode(self.mem, HALFTONE)
        self.info = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), self.width, -self.height, 1, 32, 0, 0, 0, 0, 0, 0)
        self.buf = np.empty((self.height, self.width, 4), dtype=np.uint8)

    def grab(self):
        """BGR uint8 image (height, width, 3)."""
        left, top, w, h = self.rect
        gdi32.StretchBlt(self.mem, 0, 0, self.width, self.height, self.src, left, top, w, h, SRCCOPY)
        gdi32.GetDIBits(self.mem, self.bmp, 0, self.height, self.buf.ctypes.data, ctypes.byref(self.info), 0)
        return self.buf[:, :, :3].copy()

    def close(self):
        gdi32.DeleteObject(self.bmp)
        gdi32.DeleteDC(self.mem)
        user32.ReleaseDC(0, self.src)


class FrameStream(threading.Thread):
    """Grabs continuously in the background; `latest()` returns (perf_counter time, frame)."""

    def __init__(self, width=640, fps=60):
        super().__init__(daemon=True)
        self.width, self.period = width, 1.0 / fps
        self.lock = threading.Lock()
        self.frame = None
        self.stamp = 0.0
        self.count = 0
        self.running = True

    def run(self):
        grabber = Grabber(self.width)
        try:
            while self.running:
                t0 = time.perf_counter()
                img = grabber.grab()
                with self.lock:
                    self.frame, self.stamp = img, t0
                    self.count += 1
                time.sleep(max(0.0, self.period - (time.perf_counter() - t0)))
        finally:
            grabber.close()

    def latest(self):
        with self.lock:
            return self.stamp, self.frame

    def close(self):
        self.running = False


if __name__ == "__main__":
    import cv2
    g = Grabber(640)
    t = time.perf_counter()
    for _ in range(30):
        img = g.grab()
    print(f"{(time.perf_counter() - t) / 30 * 1000:.1f} ms per frame, {img.shape}")
    cv2.imwrite("capture_test.png", img)
