"""FPV camera model: pinhole, mounted with an uptilt on the drone.

Camera axes follow Unity: x right, y up, z = viewing direction. The camera is
pitched up by `tilt_deg` relative to the body (rotation about body x by -tilt).
Image coordinates: u to the right, v downwards, origin top-left.
"""
import math
from dataclasses import dataclass

from .geometry import axis_angle, qinvrot, qmul, qrot


@dataclass
class Camera:
    width: int = 960
    height: int = 531
    hfov_deg: float = 125.0
    tilt_deg: float = 30.0

    @property
    def f(self):
        return (self.width / 2) / math.tan(math.radians(self.hfov_deg) / 2)

    def scaled(self, width):
        return Camera(width, int(round(self.height * width / self.width)), self.hfov_deg, self.tilt_deg)

    def cam_quat(self, body_quat):
        """World orientation of the camera."""
        return qmul(body_quat, axis_angle((1.0, 0.0, 0.0), -math.radians(self.tilt_deg)))

    def project(self, body_quat, cam_pos, world_point):
        q = self.cam_quat(body_quat)
        p = qinvrot(q, tuple(a - b for a, b in zip(world_point, cam_pos)))
        if p[2] <= 0.05:
            return None
        return (self.width / 2 + self.f * p[0] / p[2], self.height / 2 - self.f * p[1] / p[2])

    def ray(self, body_quat, u, v):
        """Unit world direction of pixel (u, v)."""
        d = ((u - self.width / 2) / self.f, -(v - self.height / 2) / self.f, 1.0)
        n = math.sqrt(sum(x * x for x in d))
        return qrot(self.cam_quat(body_quat), tuple(x / n for x in d))
