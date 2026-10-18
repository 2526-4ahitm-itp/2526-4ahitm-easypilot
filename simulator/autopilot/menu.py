"""Drive Liftoff's menus through vJoy buttons or mouse clicks.

  python -m autopilot.menu down down right ok back reset pause exit wait
  python -m autopilot.menu click:491,64      (coordinates in a 1456x819 screenshot frame)

Liftoff ignores all input until Unity got a real window activation, see window.focus_liftoff(hard=False).
"""
import sys
import time

from . import window
from .vjoy import (BTN_CANCEL, BTN_CONFIRM, BTN_EXIT, BTN_PAUSE, BTN_RESET,
                   MENU_X, MENU_Y, VJoy)

SCREENSHOT_FRAME = (1456, 819)

ACTIONS = {
    "up": lambda j: j.nudge(MENU_Y, 1.0),
    "down": lambda j: j.nudge(MENU_Y, -1.0),
    "left": lambda j: j.nudge(MENU_X, -1.0),
    "right": lambda j: j.nudge(MENU_X, 1.0),
    "ok": lambda j: j.tap(BTN_CONFIRM),
    "back": lambda j: j.tap(BTN_CANCEL),
    "reset": lambda j: j.tap(BTN_RESET),
    "pause": lambda j: j.tap(BTN_PAUSE),
    "exit": lambda j: j.tap(BTN_EXIT),
    "wait": lambda j: time.sleep(1.0),
}


def main(argv):
    window.focus_liftoff(hard=False)
    joy = VJoy()
    time.sleep(0.5)  # Liftoff misses input right after the device is acquired
    try:
        for word in argv:
            if word.startswith("click:"):
                x, y = (float(v) for v in word[6:].split(","))
                window.click(x, y, SCREENSHOT_FRAME)
                time.sleep(0.6)
                continue
            name, _, count = word.partition("*")
            for _ in range(int(count or 1)):
                ACTIONS[name](joy)
                time.sleep(0.7)
    finally:
        joy.close()


if __name__ == "__main__":
    main(sys.argv[1:])
