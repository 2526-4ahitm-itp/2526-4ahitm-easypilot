"""Drive Liftoff's menus through vJoy (Liftoff ignores injected mouse/keyboard input).

  python -m autopilot.menu down down right ok back reset pause exit wait
"""
import sys
import time

from . import window
from .vjoy import (BTN_CANCEL, BTN_CONFIRM, BTN_EXIT, BTN_PAUSE, BTN_RESET,
                   MENU_X, MENU_Y, VJoy)

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
    window.focus_liftoff()
    joy = VJoy()
    try:
        for word in argv:
            name, _, count = word.partition("*")
            for _ in range(int(count or 1)):
                ACTIONS[name](joy)
                time.sleep(0.35)
    finally:
        joy.close()


if __name__ == "__main__":
    main(sys.argv[1:])
