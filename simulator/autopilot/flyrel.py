"""Fly relative waypoints (heading frame of the spawn) slowly and record frames + poses.

  python -m autopilot.flyrel "0,2,0 0,2,20" [speed] [--no-reset]
Coordinates: right, up, forward in metres relative to the start pose.
"""
import json
import math
import sys
import time

import cv2

from .capture import FrameStream
from .control import FlightController, Gains
from .geometry import body_axes, norm, sub, unit
from .liftoff import RUNS, Session, state_row
from .sysid import load_model


def main(argv):
    pts = [tuple(float(v) for v in p.split(",")) for p in argv[0].split()]
    speed = float(argv[1]) if len(argv) > 1 and not argv[1].startswith("--") else 3.0
    out = RUNS / f"fly-{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True)
    rates, thrust = load_model()
    ctl = FlightController(rates, thrust, Gains(tilt=12, yaw=3.0, pos=2.5, vel=3.0))
    sess = Session("fly")
    if "--no-reset" not in argv:
        sess.reset_drone(settle=2.0)
    frames = FrameStream(960, fps=30)
    frames.start()
    st = {"i": 0, "saved": 0.0}
    poses = []

    def step(s, dt):
        if "origin" not in st:
            _, _, fwd = body_axes(s.quat)
            f = unit((fwd[0], 0.0, fwd[2]))
            r = (f[2], 0.0, -f[0])
            st["origin"], st["f"], st["r"] = s.pos, f, r
            st["wps"] = [tuple(s.pos[k] + p[0] * r[k] + p[1] * (k == 1) + p[2] * f[k] for k in range(3)) for p in pts]
            st["ref"] = s.pos
        wps = st["wps"]
        target = wps[st["i"]]
        # move the reference towards the target at `speed`
        d = sub(target, st["ref"])
        n = norm(d)
        stepm = speed * min(dt, 0.05)
        if n <= stepm:
            st["ref"] = target
            if norm(sub(target, s.pos)) < 0.6:
                st["i"] += 1
                if st["i"] >= len(wps):
                    return None
        else:
            st["ref"] = tuple(a + b / n * stepm for a, b in zip(st["ref"], d))
        v_ref = tuple(b / n * speed for b in d) if n > stepm else (0.0, 0.0, 0.0)
        ctl.observe(s)
        c = ctl.track(s, st["ref"], v_ref, (0, 0, 0), st["f"])
        stamp, img = frames.latest()
        if img is not None and stamp - st["saved"] > 0.05:
            st["saved"] = stamp
            fs = sess.tel.at(stamp - 0.015) or s
            name = f"{len(poses):04d}.jpg"
            cv2.imwrite(str(out / name), img)
            poses.append({"file": name, "t": fs.t, "pos": fs.pos, "quat": fs.quat, "vel": fs.vel})
        sess.log(cmd_t=c.throttle, wp=st["i"], **state_row(s))
        return c.as_tuple()

    ok = sess.loop(step, max_time=60)
    frames.close()
    print("result:", ok, sess.reason, "log:", sess.close())
    (out / "poses.json").write_text(json.dumps(poses, indent=1))
    print(len(poses), "frames in", out)


if __name__ == "__main__":
    main(sys.argv[1:])
