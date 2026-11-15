"""Records an autonomous run: FPV video for the split screen + frames with poses for the detector.

Runs in its own thread next to the control loop:
  - video: every grabbed frame with its time since GO -> H.264 mp4 (ffmpeg) that the browser plays
    in sync with a live run ("Autopilot" half of the split screen)
  - dataset: every n-th frame as 640 px jpg + telemetry pose -> runs/dataset/raw/<run>/meta.json,
    labelled later by `python -m autopilot.dataset label` (exact gates from gatedb.py)
"""
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import cv2

from .liftoff import RUNS

VIDEO_DIR = RUNS / "videos"
DATASET_RAW = RUNS / "dataset" / "raw"


def video_path(race_name, stage):
    return VIDEO_DIR / race_name / f"stage{stage}.mp4"


class Recorder(threading.Thread):
    def __init__(self, tel, race_name, stage, k, fps=30, width=960, dataset_every=6, latency=0.012):
        super().__init__(daemon=True)
        from .capture import COLORONCOLOR, FrameStream
        self.tel, self.race_name, self.stage, self.k = tel, race_name, stage, k
        self.fps, self.dataset_every, self.latency = fps, dataset_every, latency
        self.frames = FrameStream(width, fps=fps, mode=COLORONCOLOR)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.tmp = VIDEO_DIR / "_tmp" / f"{race_name}-{stage}-{stamp}"
        self.raw = DATASET_RAW / f"{race_name}-{k}-{stamp}"
        self.meta = []
        self.t0 = None
        self.n_video = 0
        self.running = True

    def go(self):
        """Mark the start signal: video time 0."""
        self.t0 = time.perf_counter()

    def run(self):
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.raw.mkdir(parents=True, exist_ok=True)
        self.frames.start()
        last, n = 0.0, 0
        while self.running:
            stamp, img = self.frames.latest()
            if img is None or stamp == last:
                time.sleep(0.003)
                continue
            last = stamp
            if self.t0 is None or stamp < self.t0:
                continue
            # constant frame rate for the video: repeat/skip frames to stay on the wall clock
            target = int((stamp - self.t0) * self.fps)
            while self.n_video <= target:
                cv2.imwrite(str(self.tmp / f"{self.n_video:05d}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
                self.n_video += 1
            n += 1
            if n % self.dataset_every == 0:
                s = self.tel.at(stamp - self.latency)
                if s is not None and max(abs(v) for v in s.pos) > 1e-3:
                    name = f"{len(self.meta):05d}.jpg"
                    small = cv2.resize(img, (640, int(round(img.shape[0] * 640 / img.shape[1]))),
                                       interpolation=cv2.INTER_AREA)
                    cv2.imwrite(str(self.raw / name), small, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    self.meta.append({"file": name, "pos": s.pos, "quat": s.quat, "speed": s.speed})
        self.frames.close()

    def finish(self, keep_video=True):
        """Stop, write the dataset meta and encode the video. Returns the mp4 path or None."""
        self.running = False
        self.join(timeout=3)
        if self.meta:
            (self.raw / "meta.json").write_text(json.dumps({"race": self.race_name, "k": self.k,
                                                            "frames": self.meta}))
        else:
            shutil.rmtree(self.raw, ignore_errors=True)
        out = None
        if keep_video and self.n_video > self.fps:
            out = self.tmp.with_suffix(".mp4")
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(self.fps),
                                "-i", str(self.tmp / "%05d.jpg"), "-c:v", "libx264", "-preset", "veryfast",
                                "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                print("ffmpeg:", r.stderr[-300:])
                out = None
        shutil.rmtree(self.tmp, ignore_errors=True)
        return out


def keep_as_reference(mp4, race_name, stage):
    """Make this run's video the split-screen video of race/stage (called for a new best time)."""
    dst = video_path(race_name, stage)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(mp4), str(dst))
    return dst
