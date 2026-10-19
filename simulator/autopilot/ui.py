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
    if argv and argv[0] == "restart":
        restart_race()
        return
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


def restart_race(load_time=14.0):
    """Restart the current race from the finish screen or from flight.

    On the finish screen Liftoff streams position (0, 0, 0); there 'Retry' restarts. During a
    race the pause menu's Level Selection opens the quick setup with the same race, then Play.
    """
    from . import menu
    from .telemetry import Telemetry
    from .vjoy import BTN_PAUSE, VJoy
    tel = Telemetry()
    tel.start()
    s = tel.wait(3.0)
    tel.close()
    on_finish_screen = s is None or max(abs(v) for v in s.pos) < 1e-3
    window.focus_liftoff(hard=False)
    if on_finish_screen:
        click_capture(1199, 593)                     # Retry
    else:
        joy = VJoy()
        time.sleep(0.5)
        joy.tap(BTN_PAUSE, 0.4)
        joy.close()
        time.sleep(1.0)
        click_capture(646, 463)                      # Level Selection -> quick setup
        time.sleep(1.5)
        click_capture(590, 543)                      # Play
    time.sleep(load_time)
    menu.main(["ok"])                                # skip the goggle animation
    time.sleep(1.0)


if __name__ == "__main__":
    main(sys.argv[1:])
