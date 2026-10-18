"""Climb, turn 360 degrees slowly and record FPV frames with the telemetry pose.

  python -m autopilot.scan [height] [seconds]
Frames + poses go to runs/scan-<time>/ (used to develop and test gate detection).
"""
import json
import math
import sys
import time

import cv2

from .capture import FrameStream
from .control import FlightController, Gains
from .liftoff import RUNS, Session
from .sysid import load_model


def main(argv):
    height = float(argv[0]) if argv else 4.0
    seconds = float(argv[1]) if len(argv) > 1 else 16.0
    out = RUNS / f"scan-{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True)
    rates, thrust = load_model()
    ctl = FlightController(rates, thrust, Gains(tilt=10, yaw=3.0, pos=2.0, vel=2.5))
    sess = Session("scan", log=False)
    sess.reset_drone(settle=2.0)
    frames = FrameStream(960, fps=30)
    frames.start()
    ref, poses = {}, []
    t0 = time.perf_counter()
    last_saved = [0.0]

    def step(s, dt):
        el = time.perf_counter() - t0
        if "p" not in ref:
            ref["p"] = (s.pos[0], s.pos[1] + height, s.pos[2])
            ref["yaw0"] = 0.0
        if el > seconds + 3:
            return None
        yaw = 0.0 if el < 3 else 2 * math.pi * (el - 3) / seconds
        look = (math.sin(yaw), 0.0, math.cos(yaw))
        ctl.observe(s)
        c = ctl.track(s, ref["p"], (0, 0, 0), (0, 0, 0), look)
        stamp, img = frames.latest()
        if img is not None and el > 2.5 and stamp - last_saved[0] > 0.33:
            last_saved[0] = stamp
            name = f"{len(poses):04d}.jpg"
            cv2.imwrite(str(out / name), img)
            poses.append({"file": name, "t": s.t, "pos": s.pos, "quat": s.quat, "lag": time.perf_counter() - stamp})
        return c.as_tuple()

    ok = sess.loop(step, max_time=seconds + 5)
    frames.close()
    sess.close()
    (out / "poses.json").write_text(json.dumps(poses, indent=1))
    print("result:", ok, sess.reason, len(poses), "frames in", out)


if __name__ == "__main__":
    main(sys.argv[1:])
