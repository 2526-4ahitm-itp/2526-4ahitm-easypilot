"""Small vector/quaternion helpers (pure Python, no numpy needed in the 500 Hz loop).

Quaternions are (x, y, z, w) like Unity. The algebra is the standard Hamilton one,
which is also what Unity uses internally, so in Unity's left-handed world:
  rotation about +x = nose down, about +y = yaw right, about +z = right side up.
"""
import math


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a, fallback=(0.0, 1.0, 0.0)):
    n = norm(a)
    return mul(a, 1.0 / n) if n > 1e-9 else fallback


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def qconj(q):
    return (-q[0], -q[1], -q[2], q[3])


def qnormalize(q):
    n = math.sqrt(sum(v * v for v in q))
    return tuple(v / n for v in q)


def qrot(q, v):
    """Rotate vector v by quaternion q (body -> world)."""
    x, y, z, w = q
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx))


def qinvrot(q, v):
    """World -> body."""
    return qrot(qconj(q), v)


def axis_angle(axis, angle):
    h = angle / 2
    s = math.sin(h)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(h))


def body_axes(q):
    """(right, up, forward) unit vectors of the body in world coordinates."""
    return qrot(q, (1.0, 0.0, 0.0)), qrot(q, (0.0, 1.0, 0.0)), qrot(q, (0.0, 0.0, 1.0))


def heading(v):
    """Yaw angle of a world vector, 0 = +z, positive towards +x."""
    return math.atan2(v[0], v[2])


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def integrate(q, omega_body, dt):
    """q_dot = 0.5 q (x) (omega, 0); exact for constant omega."""
    angle = norm(omega_body) * dt
    if angle < 1e-12:
        return q
    return qnormalize(qmul(q, axis_angle(unit(omega_body), angle)))
