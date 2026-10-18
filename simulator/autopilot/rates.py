"""Betaflight rate curve (as configured on the Liftoff drone) and its inverse.

Liftoff stores the rates per drone in DroneConfigurations/*.drone:
  <Rate>155</Rate> <Expo>30</Expo> <SuperExpo>73</SuperExpo>
which are Betaflight's RC rate 1.55, expo 0.30 and super rate 0.73.
"""
import math
import re
from dataclasses import dataclass
from pathlib import Path

DRONE_DIR = Path.home() / "AppData/LocalLow/LuGus Studios/Liftoff/DroneConfigurations"


@dataclass(frozen=True)
class AxisRate:
    rc_rate: float = 1.55
    expo: float = 0.30
    super_rate: float = 0.73

    def rate(self, stick):
        """stick in [-1, 1] -> body rate [deg/s] (Betaflight 'BETAFLIGHT' rates)."""
        s = max(-1.0, min(1.0, stick))
        a = abs(s)
        if self.expo:
            s = s * a ** 3 * self.expo + s * (1 - self.expo)
            a = abs(s)
        rc_rate = self.rc_rate if self.rc_rate <= 2.0 else self.rc_rate + 14.54 * (self.rc_rate - 2.0)
        deg = 200.0 * rc_rate * s
        if self.super_rate:
            deg /= max(0.01, 1.0 - a * self.super_rate)
        return deg

    @property
    def max_rate(self):
        return self.rate(1.0)

    def stick(self, deg_per_s):
        """Inverse of rate(): bisection on the monotonic curve."""
        target = max(-self.max_rate, min(self.max_rate, deg_per_s))
        lo, hi = -1.0, 1.0
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if self.rate(mid) < target:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)


@dataclass(frozen=True)
class Rates:
    roll: AxisRate = AxisRate()
    pitch: AxisRate = AxisRate()
    yaw: AxisRate = AxisRate(1.00, 0.30, 0.73)
    camera_angle_deg: float = 30.0
    name: str = "default Luma 5"


def load_drone(path=None):
    """Read rates and camera uptilt from the newest Liftoff drone configuration."""
    if path is None:
        files = sorted(DRONE_DIR.glob("*/*.drone"), key=lambda p: p.stat().st_mtime)
        if not files:
            return Rates()
        path = files[-1]
    text = Path(path).read_text(encoding="utf-8-sig")

    def axis(name, default):
        m = re.search(rf"<{name}>\s*<Rate>([\d.]+)</Rate>\s*<Expo>([\d.]+)</Expo>\s*<SuperExpo>([\d.]+)</SuperExpo>", text)
        if not m:
            return default
        return AxisRate(float(m.group(1)) / 100, float(m.group(2)) / 100, float(m.group(3)) / 100)

    cam = re.search(r"<camera>.*?<angle>([\d.-]+)</angle>", text, re.S)
    name = re.search(r"<name>(.*?)</name>", text)
    return Rates(axis("Roll", AxisRate()), axis("Pitch", AxisRate()), axis("Yaw", AxisRate(1.0, 0.3, 0.73)),
                 float(cam.group(1)) if cam else 30.0, name.group(1) if name else str(path))


if __name__ == "__main__":
    r = load_drone()
    print(r.name, "camera", r.camera_angle_deg)
    for s in (0.1, 0.25, 0.5, 0.75, 1.0):
        print(f"stick {s:.2f}: roll {r.roll.rate(s):7.1f} deg/s  yaw {r.yaw.rate(s):7.1f} deg/s")
    assert math.isclose(r.roll.stick(r.roll.rate(0.42)), 0.42, abs_tol=1e-6)
