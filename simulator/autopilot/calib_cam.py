"""Camera calibration flight: hover, turn in steps, capture still frames, fit FOV and uptilt.

  python -m autopilot.calib_cam [record|fit] [dir]
Captures are taken only when the drone has been still for a moment, so the capture
latency of the screen grab does not matter.
"""
import json
import math
import sys
import time

import cv2
import numpy as np

from .camera import Camera
from .capture import Grabber
from .control import FlightController, Gains
from .geometry import qinvrot
from .liftoff import RUNS, Session
from .sysid import load_model


def record():
    out = RUNS / f"calib-{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True)
    rates, thrust = load_model()
    ctl = FlightController(rates, thrust, Gains(tilt=10, yaw=3.0, pos=2.0, vel=2.5))
    sess = Session("calib", log=False)
    sess.reset_drone(settle=2.0)
    grab = Grabber(960)
    shots, st = [], {"k": 0, "t": time.perf_counter(), "taken": False}
    steps = [math.radians(a) for a in range(0, 181, 15)]

    def step(s, dt):
        if "p" not in st:
            st["p"] = (s.pos[0], s.pos[1] + 5.0, s.pos[2])
            st["yaw0"] = math.atan2(2 * (s.quat[0] * s.quat[2] + s.quat[3] * s.quat[1]), 1 - 2 * (s.quat[0] ** 2 + s.quat[1] ** 2))
        el = time.perf_counter() - st["t"]
        yaw = st["yaw0"] + steps[st["k"]]
        ctl.observe(s)
        c = ctl.track(s, st["p"], (0, 0, 0), (0, 0, 0), (math.sin(yaw), 0, math.cos(yaw)))
        still = math.sqrt(sum(g * g for g in s.gyro)) < 2.0 and s.speed < 0.3
        if el > (5.0 if st["k"] == 0 else 2.5) and still and not st["taken"]:
            q0 = s.quat
            img = grab.grab()
            name = f"{st['k']:02d}.png"
            cv2.imwrite(str(out / name), img)
            shots.append({"file": name, "quat": q0, "pos": s.pos})
            st["taken"] = True
        if st["taken"] and el > 3.2:
            st["k"] += 1
            st["t"], st["taken"] = time.perf_counter(), False
            if st["k"] >= len(steps):
                return None
        return c.as_tuple()

    ok = sess.loop(step, max_time=60)
    sess.close()
    (out / "shots.json").write_text(json.dumps(shots, indent=1))
    print(ok, sess.reason, len(shots), "shots in", out)
    return out


def fit(d):
    shots = json.loads((d / "shots.json").read_text())
    imgs = [cv2.imread(str(d / s["file"]), 0) for s in shots]
    h, w = imgs[0].shape
    mask = np.full((h, w), 255, np.uint8)
    mask[:275, 750:] = 0
    mask[:100, :] = 0
    mask[420:, 380:600] = 0
    orb = cv2.ORB_create(3000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    feats = [orb.detectAndCompute(im, mask) for im in imgs]
    pairs = []
    for i in range(len(imgs) - 1):
        (k1, d1), (k2, d2) = feats[i], feats[i + 1]
        m = sorted(bf.match(d1, d2), key=lambda x: x.distance)[:300]
        pairs.append((i, [k1[x.queryIdx].pt for x in m], [k2[x.trainIdx].pt for x in m]))

    def err(hfov, tilt):
        cam = Camera(w, h, hfov, tilt)
        e = []
        for i, a, b in pairs:
            qa, qb = tuple(shots[i]["quat"]), cam.cam_quat(tuple(shots[i + 1]["quat"]))
            for (ua, va), (ub, vb) in zip(a, b):
                p = qinvrot(qb, cam.ray(qa, ua, va))
                if p[2] > 0:
                    e.append(math.hypot(w / 2 + cam.f * p[0] / p[2] - ub, h / 2 - cam.f * p[1] / p[2] - vb))
        return float(np.percentile(e, 30))

    best = min(((err(f, t), f, t) for f in range(100, 151, 5) for t in range(20, 41, 5)))
    _, f0, t0 = best
    best = min(((err(f, t), f, t) for f in np.arange(f0 - 5, f0 + 5.1, 1) for t in np.arange(t0 - 5, t0 + 5.1, 1)))
    print("best: error %.2f px  hfov %.1f  tilt %.1f" % best)
    return best


if __name__ == "__main__":
    from pathlib import Path
    if len(sys.argv) > 2 and sys.argv[1] == "fit":
        fit(Path(sys.argv[2]))
    else:
        fit(record())
