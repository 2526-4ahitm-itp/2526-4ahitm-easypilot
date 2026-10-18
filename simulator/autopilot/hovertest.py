"""Smoke test in Liftoff: climb 3 m above the current position, hold, optionally move.

  python -m autopilot.hovertest [seconds] [dx dz]
"""
import sys
import time

from .control import FlightController, Gains
from .geometry import body_axes
from .liftoff import Session, state_row
from .sysid import load_model


def main(argv):
    seconds = float(argv[0]) if argv else 6.0
    dx, dz = (float(argv[1]), float(argv[2])) if len(argv) >= 3 else (0.0, 0.0)
    rates, thrust = load_model()
    ctl = FlightController(rates, thrust, Gains(tilt=10, yaw=2.0, pos=2.0, vel=2.5))
    sess = Session("hover")
    sess.reset_drone(settle=2.0)
    ref = {}
    t_start = time.perf_counter()

    def step(s, dt):
        if "p" not in ref:
            ref["p0"] = s.pos
            ref["p"] = (s.pos[0], s.pos[1] + 3.0, s.pos[2])
            ref["look"] = body_axes(s.quat)[2]
        el = time.perf_counter() - t_start
        if el > seconds:
            return None
        p = ref["p"] if el < seconds / 2 else (ref["p"][0] + dx, ref["p"][1], ref["p"][2] + dz)
        ctl.observe(s)
        c = ctl.track(s, p, (0, 0, 0), (0, 0, 0), ref["look"])
        sess.log(cmd_t=c.throttle, cmd_y=c.yaw, cmd_p=c.pitch, cmd_r=c.roll,
                 tilt_err=ctl.debug["tilt_err_deg"], dx=ctl.disturbance[0], dy=ctl.disturbance[1],
                 dz=ctl.disturbance[2], **state_row(s))
        return c.as_tuple()

    ok = sess.loop(step, max_time=seconds + 1)
    print("result:", ok, sess.reason, "log:", sess.close())


if __name__ == "__main__":
    main(sys.argv[1:])
