"""Menu input + own screen grab in one go (the screenshot tool steals Unity's focus).

  python -m autopilot.look out.jpg [menu words...]
"""
import sys
import time

import cv2

from . import capture, menu


def main(argv):
    out, words = argv[0], argv[1:]
    if words:
        menu.main(words)
        time.sleep(1.0)
    cv2.imwrite(out, capture.Grabber(1280).grab())


if __name__ == "__main__":
    main(sys.argv[1:])
