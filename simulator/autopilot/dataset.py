"""Self-labelling gate dataset for the YOLO detector.

  python -m autopilot.dataset collect StrawBaleRace01 0.5 0.8 1.0   # fly laps, record frames + poses
  python -m autopilot.dataset label                               # project XML gates -> YOLO pose labels
  python -m autopilot.dataset preview <session>                   # draw labels for a visual check

Each gate becomes one object "gate" with 4 keypoints = corners of the opening
(bottom-left, top-left, top-right, bottom-right seen in travel direction). Because
gate poses (track XML) and camera poses (telemetry) are exact, no hand labelling is needed.
"""
import json
import zlib
import math
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from .camera import Camera
from .geometry import cross, unit
from .sysid import load_camera
from .track import PIVOT_AT_CENTER, center_lift, gate_size, load_race_with_track, load_track, race_gates

DATA = Path(__file__).resolve().parent / "runs" / "dataset"
IMG_W = 640


def opening_corners(g):
    side = unit(cross((0.0, 1.0, 0.0), g.normal), (1.0, 0.0, 0.0))
    c, w, h = g.center, g.width / 2, g.height / 2
    pts = []
    for sx, sy in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
        pts.append(tuple(c[i] + side[i] * sx * w + (h * sy if i == 1 else 0.0) for i in range(3)))
    return pts


def frame_pose_ok(cam, quat, pos, g, max_dist=70.0):
    d = math.dist(pos, g.center)
    return 0.8 < d < max_dist


def visible(img, row, min_white=0.02):
    """Reject labels of gates hidden behind terrain or bales: the arch must show white pixels."""
    h, w = img.shape[:2]
    cx, cy, bw, bh = row[1] * w, row[2] * h, row[3] * w, row[4] * h
    x0, x1 = int(max(0, cx - bw / 2)), int(min(w, cx + bw / 2 + 1))
    y0, y1 = int(max(0, cy - bh / 2)), int(min(h, cy + bh / 2 + 1))
    roi = img[y0:y1, x0:x1]
    if roi.size == 0:
        return False
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    white = ((hsv[:, :, 1] < 60) & (hsv[:, :, 2] > 170)).mean()
    return white >= min_white


def label_frame(cam, quat, pos, gates, margin=0.25, img=None, max_area=0.5):
    """YOLO pose rows for all gates visible in this frame."""
    rows = []
    for g in gates:
        if not frame_pose_ok(cam, quat, pos, g):
            continue
        corners = opening_corners(g)
        uv = [cam.project(quat, pos, p) for p in corners]
        if any(p is None for p in uv):
            continue
        # outer frame: opening plus the tube of the arch
        side = unit(cross((0.0, 1.0, 0.0), g.normal), (1.0, 0.0, 0.0))
        outer = []
        for p, (sx, sy) in zip(corners, ((-1, -1), (-1, 1), (1, 1), (1, -1))):
            outer.append(tuple(p[i] + side[i] * sx * margin + (margin * max(0, sy) if i == 1 else 0.0) for i in range(3)))
        ouv = [cam.project(quat, pos, p) for p in outer]
        if any(p is None for p in ouv):
            continue
        xs = [p[0] for p in ouv + uv]
        ys = [p[1] for p in ouv + uv]
        x0, x1 = max(0.0, min(xs)), min(cam.width - 1.0, max(xs))
        y0, y1 = max(0.0, min(ys)), min(cam.height - 1.0, max(ys))
        if x1 - x0 < 6 or y1 - y0 < 6:
            continue
        full_w, full_h = max(xs) - min(xs), max(ys) - min(ys)
        if (x1 - x0) * (y1 - y0) < 0.35 * full_w * full_h:   # mostly outside the image
            continue
        kps = []
        for u, v in uv:
            vis = 2 if 0 <= u < cam.width and 0 <= v < cam.height else 0
            kps += [u / cam.width, v / cam.height, vis] if vis else [0.0, 0.0, 0]
        row = [0, (x0 + x1) / 2 / cam.width, (y0 + y1) / 2 / cam.height,
               (x1 - x0) / cam.width, (y1 - y0) / cam.height] + kps
        if row[3] * row[4] > max_area:          # flying through: only a fragment is visible
            continue
        if img is not None and not visible(img, row):
            continue
        rows.append(row)
    return rows


def all_gates(track):
    """Every gate blueprint of a track (not only race checkpoints), oriented arbitrarily."""
    from .planner import Gate
    from .geometry import qrot
    out = []
    for b in track["blueprints"]:
        size = gate_size(b.item, b.extra.get("scale"))
        if not size or b.item.startswith(PIVOT_AT_CENTER):   # invisible trigger volumes are no gates to see
            continue
        w, h = size
        q = b.quat
        up = qrot(q, (0.0, 1.0, 0.0))
        n = qrot(q, (0.0, 0.0, 1.0))
        c = tuple(b.pos[i] + up[i] * center_lift(b.item, h) for i in range(3))
        out.append(Gate(c, n, w, h, b.item))
    return out


def collect(race_name, ks, laps=1):
    from .control import FlightController, Gains
    from .capture import FrameStream
    from .geometry import body_axes
    from .liftoff import Session
    from .race import DRAG, build_line, launch
    from .racer import Racer
    from .sysid import load_model
    race, track = load_race_with_track(race_name)
    gates = race_gates(race, track)
    rates, thrust = load_model()
    for k in ks:
        out = DATA / "raw" / f"{race_name}-{k}-{time.strftime('%Y%m%d-%H%M%S')}"
        out.mkdir(parents=True)
        sess = Session(f"collect-{k}", log=False)
        sess.reset_drone(settle=4.5)   # race mode countdown
        frames = FrameStream(IMG_W, fps=40)
        frames.start()
        s0 = sess.tel.wait()
        _, _, fwd = body_axes(s0.quat)
        # vary height a little per run for more viewpoints
        dy = random.uniform(-0.3, 0.6)
        shifted = [type(g)((g.center[0], g.center[1] + dy * 0.5, g.center[2]), g.normal, g.width, g.height, g.name)
                   for g in gates]
        line = build_line(shifted, *launch(shifted[0], s0.pos), laps, k)
        racer = Racer(line, FlightController(rates, thrust, Gains(tilt=16, yaw=4.0, pos=6.0, vel=5.0, drag=DRAG)))
        meta, st = [], {"last": 0.0}

        def step(s, dt):
            c = racer.step(s)
            stamp, img = frames.latest()
            if img is not None and stamp > st["last"]:
                st["last"] = stamp
                fs = sess.tel.at(stamp - 0.012) or s
                name = f"{len(meta):05d}.jpg"
                cv2.imwrite(str(out / name), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
                meta.append({"file": name, "pos": fs.pos, "quat": fs.quat, "speed": fs.speed})
            return None if racer.done else c.as_tuple()

        ok = sess.loop(step, max_time=line.lap_time_estimate * 2.5 + 10)
        frames.close()
        sess.close()
        (out / "meta.json").write_text(json.dumps({"race": race_name, "track": track["name"], "k": k, "frames": meta}))
        print(k, ok, sess.reason, len(meta), "frames,", len(racer.progress.gate_times), "gates ->", out)


def label(val_every=7):
    cam_full = load_camera(IMG_W)
    images = {"train": DATA / "images" / "train", "val": DATA / "images" / "val"}
    labels = {"train": DATA / "labels" / "train", "val": DATA / "labels" / "val"}
    for p in list(images.values()) + list(labels.values()):
        p.mkdir(parents=True, exist_ok=True)
    tracks = {}
    n_img = n_obj = 0
    for run in sorted((DATA / "raw").glob("*")):
        meta_file = run / "meta.json"
        if not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text())
        if meta["race"] not in tracks:
            _, track = load_race_with_track(meta["race"])
            tracks[meta["race"]] = all_gates(track)
        gates = tracks[meta["race"]]
        split = "val" if zlib.crc32(run.name.encode()) % val_every == 0 else "train"
        for f in meta["frames"]:
            img = run / f["file"]
            pic = cv2.imread(str(img))
            cam = Camera(pic.shape[1], pic.shape[0], cam_full.hfov_deg, cam_full.tilt_deg)
            rows = label_frame(cam, tuple(f["quat"]), tuple(f["pos"]), gates, img=pic)
            stem = f"{run.name}_{Path(f['file']).stem}"
            target = images[split] / f"{stem}.jpg"
            if not target.exists():
                target.write_bytes(img.read_bytes())
            (labels[split] / f"{stem}.txt").write_text("\n".join(" ".join(f"{v:.6f}" if i else str(v) for i, v in enumerate(r)) for r in rows))
            n_img += 1
            n_obj += len(rows)
    (DATA / "gates.yaml").write_text(
        f"path: {DATA.as_posix()}\ntrain: images/train\nval: images/val\nkpt_shape: [4, 3]\n"
        "flip_idx: [3, 2, 1, 0]\nnames:\n  0: gate\n")
    print(n_img, "images,", n_obj, "gates labelled ->", DATA / "gates.yaml")


def preview(run_name, n=12):
    run = DATA / "raw" / run_name
    meta = json.loads((run / "meta.json").read_text())
    _, track = load_race_with_track(meta["race"])
    gates = all_gates(track)
    frames = meta["frames"][::max(1, len(meta["frames"]) // n)][:n]
    tiles = []
    for f in frames:
        img = cv2.imread(str(run / f["file"]))
        cam = Camera(img.shape[1], img.shape[0], *(lambda c: (c.hfov_deg, c.tilt_deg))(load_camera()))
        for r in label_frame(cam, tuple(f["quat"]), tuple(f["pos"]), gates, img=img):
            cx, cy, bw, bh = r[1] * img.shape[1], r[2] * img.shape[0], r[3] * img.shape[1], r[4] * img.shape[0]
            cv2.rectangle(img, (int(cx - bw / 2), int(cy - bh / 2)), (int(cx + bw / 2), int(cy + bh / 2)), (0, 255, 255), 1)
            for j in range(4):
                if r[7 + 3 * j]:
                    cv2.circle(img, (int(r[5 + 3 * j] * img.shape[1]), int(r[6 + 3 * j] * img.shape[0])), 3, (0, 0, 255), -1)
        tiles.append(img)
    while len(tiles) % 3:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)])
    out = run / "preview.jpg"
    cv2.imwrite(str(out), sheet)
    print(out)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "collect":
        collect(sys.argv[2], [float(k) for k in sys.argv[3:]] or [0.6])
    elif cmd == "label":
        label()
    elif cmd == "preview":
        preview(sys.argv[2])
