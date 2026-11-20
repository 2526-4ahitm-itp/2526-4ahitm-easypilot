"""Fast downscaled capture of the Liftoff FPV image.

The game renders at 4K; vision only needs ~640 px wide frames. Windows grabs with GDI
StretchBlt (capture_win.py), macOS with mss + OpenCV resize (capture_mac.py).
"""
import sys
import threading
import time

if sys.platform == "darwin":
    from .capture_mac import COLORONCOLOR, HALFTONE, Grabber  # noqa: F401
else:
    from .capture_win import COLORONCOLOR, HALFTONE, Grabber  # noqa: F401


class FrameStream(threading.Thread):
    """Grabs continuously in the background; `latest()` returns (perf_counter time, frame)."""

    def __init__(self, width=640, fps=60, mode=HALFTONE):
        super().__init__(daemon=True)
        self.width, self.period, self.mode = width, 1.0 / fps, mode
        self.lock = threading.Lock()
        self.frame = None
        self.stamp = 0.0
        self.count = 0
        self.running = True

    def run(self):
        grabber = Grabber(self.width, mode=self.mode)
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
