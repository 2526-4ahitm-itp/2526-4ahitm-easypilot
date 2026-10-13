"""
Closed-loop tests for the hover controller.

A small rigid-body model (acro rate mode, thrust along body-up, linear drag) is
fed through the same Telemetry math Liftoff data goes through, so attitude
conventions (Unity quaternion, left-handed, Y up) are covered as well.

Run: python -m unittest test_hover.py
"""
import json
import math
import threading
import unittest

import hover

DT = 0.004  # 250 Hz, same as the middleware loop


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def axis_q(axis, deg):
    h = math.radians(deg) / 2
    return (axis[0] * math.sin(h), axis[1] * math.sin(h), axis[2] * math.sin(h), math.cos(h))


def unity_rotation(yaw, pitch_down, roll_right):
    """Unity order: rotation = qY * qX * qZ. +X tilts the nose down, +Z lifts the right side."""
    return qmul(axis_q((0, 1, 0), yaw), qmul(axis_q((1, 0, 0), pitch_down), axis_q((0, 0, 1), -roll_right)))


def make_telemetry():
    tel = hover.Telemetry.__new__(hover.Telemetry)
    tel.signs = {"pitch": 1, "roll": 1, "yaw": 1}
    tel._prev = None
    tel._vel = [0.0, 0.0, 0.0]
    tel.reset_flag = False
    tel.lock = threading.Lock()
    tel.packets = 0
    tel.last_rx = 0.0
    return tel


class SimDrone:
    """Acro drone: body rates = stick * center_rate, thrust = throttle / true_hover * g."""

    def __init__(self, q, pos, vel, true_hover, center_rate):
        self.q, self.pos, self.vel = q, list(pos), list(vel)
        self.true_hover, self.center_rate = true_hover, center_rate

    def step(self, thr, yaw, pitch, roll):
        cr = self.center_rate * DT
        w = qmul(axis_q((1, 0, 0), pitch * cr), qmul(axis_q((0, 1, 0), yaw * cr), axis_q((0, 0, 1), -roll * cr)))
        q = qmul(self.q, w)
        n = math.sqrt(sum(c * c for c in q))
        self.q = tuple(c / n for c in q)
        up = hover.quat_rotate(self.q, (0, 1, 0))
        thrust = thr / self.true_hover * hover.G
        for i in range(3):
            acc = up[i] * thrust - (hover.G if i == 1 else 0) - 0.3 * self.vel[i]
            self.vel[i] += acc * DT
            self.pos[i] += self.vel[i] * DT


def fly(drone, cfg, seconds):
    tel = make_telemetry()
    t = 0.0
    tel._update(t, tuple(drone.pos), drone.q, (0, 0, 0), (0, 0, 0, 0))
    t += DT
    tel._update(t, tuple(drone.pos), drone.q, (0, 0, 0), (0, 0, 0, 0))
    tel._vel = list(drone.vel)
    tel.state["vel"] = tuple(drone.vel)

    ctl = hover.HoverController(cfg)
    ctl.engage(tel.state, 0.5)
    for _ in range(int(seconds / DT)):
        drone.step(*ctl.step(tel.state, DT))
        t += DT
        tel._update(t, tuple(drone.pos), drone.q, (0, 0, 0), (0, 0, 0, 0))
    return ctl, tel.state


class AttitudeConventionTest(unittest.TestCase):

    def test_nose_down_is_positive_pitch(self):
        tel = make_telemetry()
        tel._update(0.0, (0, 0, 0), unity_rotation(0, 20, 0), (0, 0, 0), (0, 0, 0, 0))
        self.assertAlmostEqual(tel.state["pitch"], 20, delta=0.5)

    def test_right_side_down_is_positive_roll(self):
        tel = make_telemetry()
        tel._update(0.0, (0, 0, 0), unity_rotation(0, 0, 15), (0, 0, 0), (0, 0, 0, 0))
        self.assertAlmostEqual(tel.state["roll"], 15, delta=0.5)

    def test_turning_right_is_positive_yaw(self):
        tel = make_telemetry()
        tel._update(0.0, (0, 0, 0), unity_rotation(70, 0, 0), (0, 0, 0), (0, 0, 0, 0))
        self.assertAlmostEqual(tel.state["yaw"], 70, delta=0.5)

    def test_respawn_jump_sets_reset_flag(self):
        tel = make_telemetry()
        tel._update(0.0, (0, 0, 0), (0, 0, 0, 1), (0, 0, 0), (0, 0, 0, 0))
        tel._update(0.01, (50, 0, 0), (0, 0, 0, 1), (0, 0, 0), (0, 0, 0, 0))
        self.assertTrue(tel.reset_flag)


class HoverControllerTest(unittest.TestCase):

    def setUp(self):
        # Defaults only, independent of a local config.json.
        self.cfg = json.loads(json.dumps(hover.DEFAULT_CONFIG))

    def test_brakes_and_holds_position_heading_and_height(self):
        drone = SimDrone(unity_rotation(70, 20, -10), (0, 10, 0), (6, 1, 2),
                         true_hover=0.30, center_rate=self.cfg["center_rate_dps"])
        ctl, s = fly(drone, self.cfg, seconds=15)

        self.assertEqual(ctl.status(), "HOLDING")
        self.assertLess(math.hypot(s["vel"][0], s["vel"][2]), 0.05)
        self.assertLess(abs(s["vel"][1]), 0.05)
        self.assertLess(math.dist((s["pos"][0], s["pos"][2]), ctl.tgt_pos), 0.1)
        self.assertLess(abs(s["pos"][1] - ctl.tgt_h), 0.1)
        self.assertAlmostEqual(s["yaw"], 70, delta=1)
        self.assertLess(s["tilt"], 1)

    def test_wrong_hover_throttle_estimate_is_corrected(self):
        # Learned estimate 0.30, real drone needs 0.45: the integral has to close the gap.
        drone = SimDrone(unity_rotation(0, 0, 0), (0, 20, 0), (0, 0, 0),
                         true_hover=0.45, center_rate=self.cfg["center_rate_dps"])
        ctl, s = fly(drone, self.cfg, seconds=10)

        self.assertLess(abs(s["pos"][1] - ctl.tgt_h), 0.2)
        self.assertLess(abs(s["vel"][1]), 0.05)

    def test_outputs_stay_within_stick_limits(self):
        drone = SimDrone(unity_rotation(0, 45, 30), (0, 30, 0), (15, -5, 0),
                         true_hover=0.30, center_rate=self.cfg["center_rate_dps"])
        tel = make_telemetry()
        tel._update(0.0, tuple(drone.pos), drone.q, (0, 0, 0), (0, 0, 0, 0))
        tel._update(DT, tuple(drone.pos), drone.q, (0, 0, 0), (0, 0, 0, 0))
        tel.state["vel"] = tuple(drone.vel)
        ctl = hover.HoverController(self.cfg)
        ctl.engage(tel.state, 0.5)
        thr, yaw, pitch, roll = ctl.step(tel.state, DT)
        ms = self.cfg["gains"]["max_stick"]
        self.assertTrue(0.0 <= thr <= 1.0)
        for v in (yaw, pitch, roll):
            self.assertLessEqual(abs(v), ms)


class StickMappingTest(unittest.TestCase):

    def test_raw_to_norm_uses_calibrated_center(self):
        ax = {"index": 1, "center": 0.05, "full": 1.0}
        self.assertAlmostEqual(hover.raw_to_norm(ax, 0.05), 0.0)
        self.assertAlmostEqual(hover.raw_to_norm(ax, 1.0), 1.0)
        self.assertAlmostEqual(hover.raw_to_norm(ax, -0.9), -1.0)

    def test_inverted_axis(self):
        ax = {"index": 0, "center": 0.0, "full": -1.0}
        self.assertAlmostEqual(hover.raw_to_norm(ax, -0.5), 0.5)

    def test_throttle_range(self):
        ax = {"index": 2, "low": -1.0, "high": 1.0}
        self.assertAlmostEqual(hover.raw_to_thr(ax, -1.0), 0.0)
        self.assertAlmostEqual(hover.raw_to_thr(ax, 0.0), 0.5)
        self.assertAlmostEqual(hover.raw_to_thr(ax, 1.0), 1.0)


if __name__ == "__main__":
    unittest.main()
