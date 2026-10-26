"""GPS waypoint flight in Liftoff: take off, fly low to a coordinate around obstacles, land.

  python -m autopilot.goto --gps 48.268700 14.252000 --track StrawBaleRace01
  python -m autopilot.goto --rel 12 -6 --track StrawBaleRace01 --speed 6
  python -m autopilot.goto --rel 0 30 --no-xml --track StrawBaleRace01     # camera only

--gps LAT LON    goal as GPS coordinate; the drone's position at the start is the reference point
                 (default HTL Leonding, change with --ref LAT,LON), +z in Liftoff = north
--rel E N        goal in metres east/north of the start
--track NAME     race or track whose items are put into the map (and used to check clearances)
--no-xml         do not put the track items into the map (camera only; clearance still checked)
--no-camera      map only from the track file
--speed V        max speed in m/s (default 6), --alt H flight height above ground (default 1.5)
--reset          respawn the drone at the start first (Liftoff reset button)
--plan-only      print the planned path and the map picture, do not fly

Obstacle map: track items as boxes (obstacles.py) + camera motion stereo (depth.py).
Collision check while flying: impact = measured acceleration above 35 m/s^2 (the drone never
commands more than ~15 m/s^2 here), stuck = navigator wants speed but the drone stands still.
Afterwards the flown path is checked against the track items (minimum distance).
"""
import json
import math
import sys
import time

import cv2
import numpy as np

from .control import FlightController, Gains
from .geometry import add, mul, norm, sub
from .liftoff import RUNS, Session, state_row
from .nav import GeoReference, Navigator, NavLimits, OccupancyGrid
from .obstacles import add_to_grid, min_clearance, track_boxes
from .sysid import load_model
from .track import load_race_with_track

DRAG = 0.033
IMPACT_ACCEL = 35.0
MAX_ACCEL = 9.0


def parse(argv):
    o = {"gps": None, "rel": None, "track": None, "xml": True, "camera": True, "speed": 6.0, "alt": 1.5,
         "ref": (48.268611, 14.251944), "plan_only": False, "max_time": 90.0, "reset": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--gps":
            o["gps"] = (float(argv[i + 1]), float(argv[i + 2]))
            i += 2
        elif a == "--rel":
            o["rel"] = (float(argv[i + 1]), float(argv[i + 2]))
            i += 2
        elif a == "--track":
            o["track"] = argv[i + 1]
            i += 1
        elif a == "--ref":
            o["ref"] = tuple(float(v) for v in argv[i + 1].split(","))
            i += 1
        elif a in ("--speed", "--alt", "--max-time"):
            o[a[2:].replace("-", "_")] = float(argv[i + 1])
            i += 1
        elif a == "--no-xml":
            o["xml"] = False
        elif a == "--no-camera":
            o["camera"] = False
        elif a == "--reset":
            o["reset"] = True
        elif a == "--plan-only":
            o["plan_only"] = True
        else:
            raise SystemExit(f"unknown argument {a}\n{__doc__}")
        i += 1
    if not (o["gps"] or o["rel"]):
        raise SystemExit(__doc__)
    return o


def map_picture(grid, boxes, start, goal, path=None, flown=None, cam_cells=(), scale=12, margin=10.0):
    """Top view for the report: track items grey, camera obstacles red, plan blue, flight green."""
    xs = [start[0], goal[0]] + ([p[0] for p in flown] if flown else [])
    zs = [start[1], goal[1]] + ([p[2] for p in flown] if flown else [])
    x0, x1, z0, z1 = min(xs) - margin, max(xs) + margin, min(zs) - margin, max(zs) + margin
    w, h = int((x1 - x0) * scale), int((z1 - z0) * scale)
    img = np.full((h, w, 3), 245, np.uint8)

    def px(x, z):
        return int((x - x0) * scale), int((z1 - z) * scale)      # north up
    c = grid.cell
    for k, top in grid.top.items():
        cx, cz = grid.center(k)
        if x0 <= cx <= x1 and z0 <= cz <= z1:
            col = (60, 60, 220) if k in cam_cells else (150, 150, 150)
            if top - grid.default_ground < 0.6:
                col = (215, 215, 215)          # low, flown over
            a, b = px(cx - c / 2, cz + c / 2), px(cx + c / 2, cz - c / 2)
            cv2.rectangle(img, a, b, col, -1)
    for bx in boxes:
        pts = np.array([px(*p) for p in bx.corners()], np.int32)
        cv2.polylines(img, [pts], True, (90, 90, 90), 1)
    if path:
        for p, q in zip(path, path[1:]):
            cv2.line(img, px(*p), px(*q), (220, 120, 30), 2)
    if flown:
        for p, q in zip(flown, flown[1:]):
            cv2.line(img, px(p[0], p[2]), px(q[0], q[2]), (40, 170, 40), 2)
    cv2.circle(img, px(*start), 6, (0, 0, 0), 2)
    cv2.drawMarker(img, px(*goal), (0, 0, 200), cv2.MARKER_CROSS, 18, 3)
    cv2.putText(img, "N", (w - 25, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.line(img, (10, h - 12), (10 + 5 * scale, h - 12), (0, 0, 0), 2)
    cv2.putText(img, "5 m", (12, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    return img


def main(argv):
    o = parse(argv)
    boxes = []
    if o["track"]:
        _, track = load_race_with_track(o["track"])
        boxes, skipped = track_boxes(track)
        if skipped:
            print("unknown item types (default box):", skipped)
    rates, thrust = load_model()
    sess = Session("goto")
    if o["reset"]:
        sess.tel.wait(5)
        time.sleep(0.5)                    # first vJoy input right after acquiring is lost
        # right after the focus switch Liftoff sometimes misses the button: try again (a reset
        # at the spawn point does not show up in the telemetry, so two misses = already there)
        if not sess.reset_drone(settle=1.5) and not sess.reset_drone(settle=1.5):
            print("no reset seen - drone already at the spawn point?")
    s0 = sess.tel.wait(5)
    if s0 is None or max(abs(v) for v in s0.pos) < 1e-3:
        sess.close()
        raise SystemExit("no drone in flight (menu?) - start Free Flight first")
    ground = s0.pos[1] if s0.speed < 0.3 else s0.pos[1] - o["alt"]
    ref = GeoReference(o["ref"][0], o["ref"][1], origin_xz=(s0.pos[0], s0.pos[2]))
    if o["gps"]:
        goal = ref.to_world(*o["gps"])
    else:
        goal = (s0.pos[0] + o["rel"][0], s0.pos[2] + o["rel"][1])
    goal_gps = ref.to_gps(*goal)
    grid = OccupancyGrid(cell=0.5, ground_y=ground)
    if o["xml"] and boxes:
        add_to_grid(grid, boxes)
    # the drone stands on the start pad: its items (lights, pad) must not lock the start in
    for k in [k for k in grid.top if math.dist(grid.center(k), (s0.pos[0], s0.pos[2])) < 1.0]:
        del grid.top[k]
    xml_cells = set(grid.top)
    limits = NavLimits(max_speed=o["speed"], altitude=o["alt"], clearance=0.9, sensor_range=12.0,
                       brake=7.0, reaction=0.35)
    nav = Navigator(grid, goal, limits, background=not o["plan_only"], lead=False)
    start_xz = (s0.pos[0], s0.pos[2])
    print(f"start {start_xz[0]:.1f} {start_xz[1]:.1f} = GPS {ref.to_gps(*start_xz)[0]:.6f}, "
          f"{ref.to_gps(*start_xz)[1]:.6f}; goal {goal[0]:.1f} {goal[1]:.1f} = GPS {goal_gps[0]:.6f}, "
          f"{goal_gps[1]:.6f}; distance {math.dist(start_xz, goal):.1f} m; map cells {len(grid.top)}")
    if o["plan_only"]:
        nav.replan(s0.pos)
        print("path:", [(round(x, 1), round(z, 1)) for x, z in nav.path or []], nav.status)
        out = RUNS / f"goto-plan-{time.strftime('%H%M%S')}.png"
        RUNS.mkdir(exist_ok=True)
        cv2.imwrite(str(out), map_picture(grid, boxes, start_xz, goal, nav.path))
        print(out)
        sess.close()
        return

    mapper = None
    if o["camera"]:
        from .depth import CameraMapper
        mapper = CameraMapper(sess.tel, grid, debug_dir=RUNS / f"goto-cam-{time.strftime('%Y%m%d-%H%M%S')}")
        mapper.start()
    # low and slow: soft gains, at most 300 deg/s, small disturbance estimate. The race gains
    # (tilt 16, 560 deg/s) asked for ~400 deg/s at the switch from take-off to flight; Liftoff's
    # airmode turned that into an upward kick, the disturbance estimate took the kick for a
    # disturbance and the drone flipped over (test 3, 19.10.)
    ctl = FlightController(rates, thrust, Gains(tilt=8.0, yaw=2.0, max_rate_dps=300.0, pos=3.0, vel=3.5,
                                                disturbance_max=6.0, drag=DRAG))
    st = {"phase": "TAKEOFF", "t0": None, "last_v": None, "last_t": None, "impacts": [], "stuck": 0.0,
          "flown": [], "phases": [], "vbuf": [], "vmax": 0.0, "arrive_t": None, "land_y": None, "first_path": None, "a_max": 0.0,
          "v_cmd": 0.0, "look": None, "abort": ""}
    hover_y = ground + o["alt"]

    def step(s, dt):
        if st["t0"] is None:
            st["t0"] = s.t
        t = s.t - st["t0"]
        ctl.observe(s)
        # collision check: velocity change over 30 ms the controller never asks for (single-sample
        # telemetry jumps of ~0.5 m/s happen without contact, a crash at >2 m/s does not fit that)
        buf = st["vbuf"]
        buf.append((s.t, s.vel))
        if len(buf) > 4:
            buf.pop(0)
            span = buf[-1][0] - buf[0][0]
            if 0.02 < span < 0.1 and t > 1.0:
                a = math.dist(buf[-1][1], buf[0][1]) / span
                st["a_max"] = max(st["a_max"], a)
                if a > IMPACT_ACCEL and (not st["impacts"] or t - st["impacts"][-1][0] > 0.5):
                    st["impacts"].append((round(t, 2), round(a, 1), [round(v, 2) for v in s.pos]))
        st["flown"].append(s.pos)
        st["phases"].append(st["phase"])
        st["vmax"] = max(st["vmax"], s.speed)
        if st["phase"] == "TAKEOFF":
            p, v, a, look = (start_xz[0], hover_y, start_xz[1]), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)
            dx, dz = goal[0] - s.pos[0], goal[1] - s.pos[2]
            look = (dx / (math.hypot(dx, dz) or 1), 0.0, dz / (math.hypot(dx, dz) or 1))
            if s.pos[1] > hover_y - 0.25:
                st["phase"] = "FLY"
        elif st["phase"] == "FLY":
            p, v, a, look = nav.reference(s.pos, s.vel)
            if st["first_path"] is None and nav.path:
                st["first_path"] = list(nav.path)
            want = math.hypot(v[0], v[2])
            st["stuck"] = st["stuck"] + dt if (want > 2.0 and s.speed < 0.4) else 0.0
            if st["stuck"] > 1.5:
                return None
            if nav.status == "ARRIVED":
                st["phase"], st["arrive_t"] = "LAND", t
                st["land_y"] = s.pos[1]
        if st["phase"] == "LAND":
            st["land_y"] -= 0.6 * dt
            p, v, a, look = (nav.goal_xz[0], st["land_y"], nav.goal_xz[1]), (0.0, -0.6, 0.0), (0.0, 0.0, 0.0), \
                (0.0, 0.0, 1.0)
            if s.pos[1] < ground + 0.12 or st["land_y"] < ground - 0.5:
                return None
        # smooth commands: speed may rise with 3 m/s^2 only (free-space limit can drop at once),
        # total commanded acceleration at most 9 m/s^2 - so anything above IMPACT_ACCEL is a contact
        sp = math.hypot(v[0], v[2])
        cap = st["v_cmd"] + 3.0 * dt
        if sp > cap and sp > 1e-6:
            v = (v[0] * cap / sp, v[1], v[2] * cap / sp)
            sp = cap
        st["v_cmd"] = sp
        acc = add(a, add(mul(sub(p, s.pos), ctl.gains.pos), mul(sub(v, s.vel), ctl.gains.vel)))
        n = norm(acc)
        if n > MAX_ACCEL:
            acc = mul(acc, MAX_ACCEL / n)
        # turn the heading with at most 90 deg/s
        cur = st["look"] or look
        ang_cur, ang_new = math.atan2(cur[0], cur[2]), math.atan2(look[0], look[2])
        if abs(look[0]) + abs(look[2]) > 1e-6:
            diff = (ang_new - ang_cur + math.pi) % (2 * math.pi) - math.pi
            step_max = math.radians(90) * dt
            ang = ang_cur + max(-step_max, min(step_max, diff))
            look = (math.sin(ang), 0.0, math.cos(ang))
        else:
            look = cur
        st["look"] = look
        # safety: upside down or climbing away -> stop (throttle off)
        up_y = 1 - 2 * (s.quat[0] ** 2 + s.quat[2] ** 2)
        if up_y < 0.0 or s.pos[1] > ground + o["alt"] + 4.0:
            st["abort"] = "flipped" if up_y < 0.0 else "too high"
            return None
        cmd = ctl.accel_command(s, acc, look)
        d = nav.debug
        sess.log(phase=st["phase"], status=nav.status, v_nav=d.get("v", 0), free=d.get("free", 0),
                 remaining=d.get("remaining", 0), replans=nav.replans,
                 cam_cells=len(mapper.confirmed) if mapper else 0, px=p[0], py=p[1], pz=p[2],
                 cmd_t=cmd.throttle, cmd_y=cmd.yaw, cmd_p=cmd.pitch, cmd_r=cmd.roll, **state_row(s))
        return cmd.as_tuple()

    ok = sess.loop(step, max_time=o["max_time"])
    if mapper:
        mapper.close()
    log = sess.close()
    flown = st["flown"]
    end = flown[-1] if flown else s0.pos
    # clearance to the track items while flying (not the start pad the drone stands on, not the
    # touchdown at the goal)
    pad = [b for b in boxes if math.hypot(b.cx - start_xz[0], b.cz - start_xz[1]) < 1.6]
    check = [b for b in boxes if b not in pad]
    airborne = [p for p, ph in zip(flown, st["phases"]) if ph == "FLY" or (ph == "LAND" and p[1] > ground + 0.5)]
    clearance, closest = min_clearance(check, airborne[::3]) if check and airborne else (None, "")
    cam_cells = mapper.confirmed if mapper else set()
    result = {
        "goal_gps": [round(v, 7) for v in goal_gps], "goal_xz": [round(v, 2) for v in goal],
        "distance_m": round(math.dist(start_xz, goal), 1),
        "arrived": nav.status == "ARRIVED" or st["phase"] == "LAND",
        "end_error_m": round(math.dist((end[0], end[2]), nav.goal_xz), 2),
        "goal_moved_m": round(math.dist(nav.goal_xz, goal), 2),
        "time_s": st["arrive_t"], "v_max": round(st["vmax"], 1),
        "flown_m": round(sum(math.dist(a, b) for a, b in zip(flown, flown[1:])), 1),
        "height_min_max": [round(min(p[1] for p in flown[100:]) - ground, 2) if len(flown) > 100 else None,
                           round(max(p[1] for p in flown) - ground, 2) if flown else None],
        "impacts": st["impacts"][:5], "a_max": round(st["a_max"], 1), "stuck": st["stuck"] > 1.5,
        "min_clearance_m": round(clearance, 2) if clearance is not None else None, "closest_item": closest,
        "abort": st["abort"], "replans": nav.replans, "map_xml_cells": len(xml_cells) if o["xml"] else 0,
        "camera_cells": len(cam_cells), "camera_points": mapper.points_total if mapper else 0,
        "camera_pairs": mapper.stereo.pairs if mapper and mapper.stereo else 0,
        "camera_removed": mapper.removed if mapper else 0, "camera_fps": round(mapper.fps, 1) if mapper else 0,
        "camera_error": mapper.error if mapper else "", "ok": ok, "reason": sess.reason, "log": str(log),
        "options": {k: o[k] for k in ("track", "xml", "camera", "speed", "alt")},
    }
    pic = map_picture(grid, boxes, start_xz, goal, st["first_path"], flown, cam_cells)
    out = RUNS / f"goto-{time.strftime('%Y%m%d-%H%M%S')}.png"
    cv2.imwrite(str(out), pic)
    result["picture"] = str(out)
    print(json.dumps(result, indent=1))
    with (RUNS / "goto_results.jsonl").open("a") as f:
        f.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
