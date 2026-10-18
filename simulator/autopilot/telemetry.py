"""Liftoff UDP telemetry receiver.

Liftoff sends one little-endian float32 packet per physics step (~500 Hz) with the
fields listed in TelemetryConfiguration.json, in that order. World frame is Unity:
x right, y up, z forward (left-handed), attitude is a quaternion (x, y, z, w).
"""
import collections
import json
import math
import socket
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / "AppData/LocalLow/LuGus Studios/Liftoff/TelemetryConfiguration.json"
FIELD_SIZES = {"Timestamp": 1, "Position": 3, "Attitude": 4, "Velocity": 3, "Gyro": 3,
               "Input": 4, "Battery": 2, "MotorRPM": 5}
DEFAULT_FORMAT = ["Timestamp", "Position", "Attitude", "Gyro", "Input", "Velocity"]


@dataclass
class State:
    t: float                 # simulator time [s]
    pos: tuple               # world position [m]
    quat: tuple              # (x, y, z, w)
    vel: tuple               # world velocity [m/s]
    gyro: tuple              # body rates as sent by Liftoff (pitch, roll, yaw) [deg/s]
    sticks: tuple            # (throttle, yaw, pitch, roll) as Liftoff sees them
    received: float          # time.perf_counter() at reception

    @property
    def speed(self):
        return math.sqrt(sum(v * v for v in self.vel))


def read_format(path=CONFIG_PATH):
    try:
        cfg = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return cfg["StreamFormat"], int(cfg["EndPoint"].rsplit(":", 1)[1])
    except (OSError, KeyError, ValueError):
        return DEFAULT_FORMAT, 9001


class Telemetry(threading.Thread):
    """Background receiver; `latest()` returns the newest State or None when stale."""

    def __init__(self, port=None, fmt=None, on_state=None):
        super().__init__(daemon=True)
        cfg_fmt, cfg_port = read_format()
        self.fmt = list(fmt or cfg_fmt)
        self.port = port or cfg_port
        self.size = 4 * sum(FIELD_SIZES[f] for f in self.fmt)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", self.port))
        self.sock.settimeout(0.2)
        self.on_state = on_state
        self.lock = threading.Lock()
        self.state = None
        self.packets = 0
        self.resets = 0
        self._prev = None
        self._fd_vel = (0.0, 0.0, 0.0)
        self.history = collections.deque(maxlen=400)  # (received, State) for matching camera frames
        self.running = True

    def decode(self, data, now):
        values = struct.unpack_from("<%df" % (self.size // 4), data)
        fields, i = {}, 0
        for name in self.fmt:
            n = FIELD_SIZES[name]
            fields[name] = values[i:i + n]
            i += n
        t = fields["Timestamp"][0]
        pos = fields["Position"]
        vel = fields.get("Velocity")
        if vel is None:
            vel = self._finite_difference(t, pos)
        return State(t, pos, fields["Attitude"], tuple(vel), fields.get("Gyro", (0.0, 0.0, 0.0)),
                     fields.get("Input", (0.0, 0.0, 0.0, 0.0)), now)

    def _finite_difference(self, t, pos):
        if self._prev is not None:
            pt, ppos = self._prev
            dt = t - pt
            if 0 < dt < 0.1:
                a = min(1.0, dt / 0.03)
                self._fd_vel = tuple(v + a * ((p - q) / dt - v) for v, p, q in zip(self._fd_vel, pos, ppos))
        self._prev = (t, pos)
        return self._fd_vel

    def run(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            if len(data) < self.size:
                continue
            s = self.decode(data, time.perf_counter())
            with self.lock:
                old = self.state
                if old is not None and (s.t < old.t or math.dist(s.pos, old.pos) > 5.0):
                    self.resets += 1  # respawn / reset in Liftoff
                self.state = s
                self.packets += 1
                self.history.append(s)
            if self.on_state:
                self.on_state(s)

    def latest(self, max_age=0.25):
        with self.lock:
            s = self.state
        if s is None or time.perf_counter() - s.received > max_age:
            return None
        return s

    def at(self, stamp):
        """State received closest to perf_counter time `stamp` (pose of a camera frame)."""
        with self.lock:
            hist = list(self.history)
        if not hist:
            return None
        return min(hist, key=lambda s: abs(s.received - stamp))

    def wait(self, timeout=10.0):
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            s = self.latest()
            if s is not None:
                return s
            time.sleep(0.02)
        return None

    def close(self):
        self.running = False
        self.sock.close()
