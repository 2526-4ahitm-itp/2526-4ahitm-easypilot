"""Click Liftoff UI elements by coordinates in a 1280-wide capture, then save a new capture.

  python -m autopilot.ui out.jpg 710,494 [x,y ...]
Never use an external screenshot tool in between: it takes Unity's focus away.
"""
import sys
import time

import cv2

from . import capture, window

FRAME_W = 1280


def click_capture(x, y):
    left, top, w, h = window.client_rect()
    window.click(left + x * w / FRAME_W, top + y * w / FRAME_W)


def main(argv):
    out = argv[0]
    window.focus_liftoff(hard=False)
    for xy in argv[1:]:
        if xy.startswith("wait"):
            time.sleep(float(xy[4:] or 1))
            continue
        x, y = (float(v) for v in xy.split(","))
        click_capture(x, y)
        time.sleep(0.8)
    time.sleep(0.5)
    cv2.imwrite(out, capture.Grabber(FRAME_W).grab())


if __name__ == "__main__":
    main(sys.argv[1:])
