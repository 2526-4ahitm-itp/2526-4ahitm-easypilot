"""Liftoff adapter: telemetry in, vJoy sticks out, with the safety rules for real game runs.

Every autonomous mode (sysid, racing, waypoint flight) runs through `Session.loop`:
  - stops (throttle 0) when telemetry is stale, Liftoff loses focus or the drone resets
  - logs every control step to runs/<name>-<time>.csv for later analysis
"""
import csv
import ctypes
import math
import time
from pathlib import Path

from . import window
from .telemetry import Telemetry
from .vjoy import BTN_RESET, VJoy

RUNS = Path(__file__).resolve().parent / "runs"
user32 = ctypes.windll.user32
VK_F9 = 0x78


def key_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


class Session:
    def __init__(self, name="run", rate_hz=250, focus=True, log=True):
        self.name = name
        self.period = 1.0 / rate_hz
        self.tel = Telemetry()
        self.tel.start()
        self.joy = VJoy()
        ctypes.windll.winmm.timeBeginPeriod(1)
        if focus:
            window.focus_liftoff(hard=False)
        self.log_rows = [] if log else None
        self.log_header = None
        self.reason = ""

    def reset_drone(self, settle=1.5):
        """Press the Reset button (Rewired action 'Reset' on vJoy button 2) and wait for the respawn."""
        self.joy.idle()
        before = self.tel.resets
        self.joy.tap(BTN_RESET, 0.15)
        end = time.perf_counter() + 3.0
        while time.perf_counter() < end and self.tel.resets == before:
            time.sleep(0.02)
        time.sleep(settle)
        return self.tel.resets != before

    def loop(self, step, max_time=120.0, need_focus=True):
        """Call step(state, dt) -> (throttle, yaw, pitch, roll) or None (= finished)."""
        s = self.tel.wait(5.0)
        if s is None:
            self.reason = "no telemetry - is a level loaded and TelemetryConfiguration.json set?"
            return False
        if max(abs(v) for v in s.pos) < 1e-3:
            self.reason = "position (0, 0, 0): Liftoff shows a menu or the finish screen, no drone in flight"
            return False
        resets0 = self.tel.resets
        t0 = last = time.perf_counter()
        last_t = s.t
        try:
            while True:
                now = time.perf_counter()
                if now - t0 > max_time:
                    self.reason = "time limit"
                    return True
                if key_down(VK_F9):
                    self.reason = "F9 pressed"
                    return False
                s = self.tel.latest(0.1)
                if s is None:
                    self.reason = "telemetry stale"
                    return False
                if self.tel.resets != resets0:
                    self.reason = "drone reset / crash respawn"
                    return False
                if need_focus and not window.is_focused():
                    self.reason = "Liftoff lost focus"
                    return False
                if s.t == last_t:
                    time.sleep(0.0005)
                    continue
                dt = now - last
                last, last_t = now, s.t
                cmd = step(s, dt)
                if cmd is None:
                    self.reason = "done"
                    return True
                self.joy.sticks(*cmd)
                sleep = self.period - (time.perf_counter() - now)
                if sleep > 0:
                    time.sleep(sleep)
        finally:
            self.joy.idle()

    def log(self, **row):
        if self.log_rows is None:
            return
        if self.log_header is None:
            self.log_header = list(row)
        self.log_rows.append([row.get(k, "") for k in self.log_header])

    def close(self):
        self.joy.close()
        self.tel.close()
        ctypes.windll.winmm.timeEndPeriod(1)
        if self.log_rows:
            RUNS.mkdir(exist_ok=True)
            path = RUNS / f"{self.name}-{time.strftime('%Y%m%d-%H%M%S')}.csv"
            with path.open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(self.log_header)
                w.writerows(self.log_rows)
            return path
        return None


def state_row(s):
    return dict(t=round(s.t, 4), x=s.pos[0], y=s.pos[1], z=s.pos[2], qx=s.quat[0], qy=s.quat[1], qz=s.quat[2],
                qw=s.quat[3], vx=s.vel[0], vy=s.vel[1], vz=s.vel[2], gx=s.gyro[0], gy=s.gyro[1], gz=s.gyro[2],
                in_t=s.sticks[0], in_y=s.sticks[1], in_p=s.sticks[2], in_r=s.sticks[3],
                speed=math.sqrt(sum(v * v for v in s.vel)))
