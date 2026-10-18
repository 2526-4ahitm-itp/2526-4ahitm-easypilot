"""System identification flight in Liftoff (free flight, open space above the spawn).

  python -m autopilot.sysid

1. take off and hover with the hover estimate -> hover throttle
2. throttle steps while level -> thrust curve accel = k * throttle^p
3. rate steps on roll/pitch/yaw -> check the Betaflight curve against the gyro
Results go to autopilot/drone.local.json and are used by every other mode.
"""
import json
import math
import time
from pathlib import Path

from .control import FlightController, Gains, ThrustModel
from .geometry import body_axes, sub
from .liftoff import Session, state_row
from .rates import load_drone

OUT = Path(__file__).resolve().parent / "drone.local.json"
G = 9.81


def load_model():
    rates = load_drone()
    thrust = ThrustModel()
    if OUT.exists():
        d = json.loads(OUT.read_text())
        thrust = ThrustModel(d["hover_throttle"], d.get("thrust_exponent", 1.0))
    return rates, thrust


def main():
    rates = load_drone()
    ctl = FlightController(rates, ThrustModel(0.28), Gains(tilt=10, pos=2.0, vel=2.5))
    sess = Session("sysid")
    results = {"drone": rates.name}
    phase = {"name": "takeoff", "t0": None}
    target = {}
    samples = {"hover": [], "steps": [], "rates": []}
    plan = [("takeoff", 3.0), ("hover", 4.0)] + [(f"thr{v}", 0.6) for v in (0.35, 0.5, 0.65, 0.8)] + \
           [("settle", 3.0)] + [(f"rate_{ax}_{s}", 0.35) for ax in ("pitch", "roll", "yaw") for s in (0.3, 0.6, -0.3)]
    order = iter(plan)
    current = [next(order)]
    state = {"start": None, "prev": None}

    def step(s, dt):
        now = time.perf_counter()
        if state["start"] is None:
            state["start"] = now
            target["p"] = (s.pos[0], s.pos[1] + 4.0, s.pos[2])
        name, dur = current[0]
        if now - state["start"] > dur:
            try:
                current[0] = next(order)
            except StopIteration:
                return None
            state["start"] = now
            name, dur = current[0]
            if name == "settle":
                target["p"] = (s.pos[0], target["p"][1], s.pos[2])
        ctl.observe(s)
        _, up, fwd = body_axes(s.quat)
        if name.startswith("thr"):
            thr = float(name[3:])
            cmd = (thr, 0.0, 0.0, 0.0)
            if state["prev"] is not None:
                p = state["prev"]
                dtt = s.t - p.t
                if dtt > 0:
                    acc = tuple((a - b) / dtt for a, b in zip(s.vel, p.vel))
                    samples["steps"].append((thr, acc[1] + G, up[1], s.speed))
        elif name.startswith("rate_"):
            _, ax, val = name.split("_")
            val = float(val)
            base = ctl.track(s, target["p"], (0, 0, 0), (0, 0, 0), fwd)
            sticks = {"pitch": (base.throttle, 0.0, val, 0.0), "roll": (base.throttle, 0.0, 0.0, val),
                      "yaw": (base.throttle, val, 0.0, 0.0)}[ax]
            samples["rates"].append((ax, val, s.gyro))
            cmd = sticks
        else:
            c = ctl.track(s, target["p"], (0, 0, 0), (0, 0, 0), fwd)
            cmd = c.as_tuple()
            if name == "hover" and abs(s.vel[1]) < 0.3 and s.speed < 1.0:
                samples["hover"].append(c.throttle * up[1])
        state["prev"] = s
        sess.log(phase=name, cmd_t=cmd[0], cmd_y=cmd[1], cmd_p=cmd[2], cmd_r=cmd[3], **state_row(s))
        return cmd

    ok = sess.loop(step, max_time=40.0)
    path = sess.close()
    print("loop:", ok, sess.reason, "log:", path)
    if samples["hover"]:
        hover = sorted(samples["hover"])[len(samples["hover"]) // 2]
        results["hover_throttle"] = round(hover, 4)
    # thrust curve: use samples after 0.15 s of each step (motor lag), level attitude
    pts = [(t, a / max(0.5, u)) for t, a, u, v in samples["steps"] if u > 0.9 and v < 12]
    if pts and "hover_throttle" in results:
        logs = [(math.log(t / results["hover_throttle"]), math.log(a / G)) for t, a in pts if a > 1]
        if logs:
            n = len(logs)
            mx = sum(x for x, _ in logs) / n
            my = sum(y for _, y in logs) / n
            sxx = sum((x - mx) ** 2 for x, _ in logs)
            p = sum((x - mx) * (y - my) for x, y in logs) / sxx if sxx else 1.0
            results["thrust_exponent"] = round(p, 3)
            results["max_accel"] = round(G * (1 / results["hover_throttle"]) ** p, 2)
    rate_check = {}
    for ax, val, gyro in samples["rates"]:
        rate_check.setdefault(f"{ax}{val:+}", []).append(gyro)
    results["gyro_at_steps"] = {k: [round(sum(g[i] for g in v[-20:]) / max(1, len(v[-20:])), 1) for i in range(3)]
                                for k, v in rate_check.items()}
    results["expected_rates"] = {f"{ax}{v:+}": round(getattr(rates, ax).rate(v), 1)
                                 for ax in ("pitch", "roll", "yaw") for v in (0.3, 0.6, -0.3)}
    print(json.dumps(results, indent=2))
    if "hover_throttle" in results:
        OUT.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
