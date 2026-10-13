"""
Liftoff hover middleware (EasyPilot phase 2 prototype)
Physical radio -> (pass-through | hover controller) -> vJoy -> Liftoff

  python hover.py calibrate   teach axes + hover button (writes config.json)
  python hover.py monitor     show raw inputs + telemetry live
  python hover.py             normal operation

vJoy layout for Liftoff: X=roll, Y=pitch, Z=throttle, RX=yaw (see write_vjoy_sticks)
"""
import ctypes
import json
import math
import os
import socket
import struct
import sys
import threading
import time
from pathlib import Path

os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"  # keep reading input while Liftoff has focus
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402

CONFIG_PATH = Path(__file__).with_name("config.json")
G = 9.81

DEFAULT_CONFIG = {
    "controller_name": "",           # empty = first non-vJoy controller
    "vjoy_device": 1,
    "vjoy_dll": r"C:\Program Files\vJoy\x64\vJoyInterface.dll",
    "telemetry_port": 9001,
    "loop_hz": 250,
    # Axes: raw = center + norm * (full - center); norm in [-1, 1], throttle in [0, 1]
    "axes": {
        "throttle": {"index": 0, "low": -1.0, "high": 1.0},
        "yaw":      {"index": 3, "center": 0.0, "full": 1.0},
        "pitch":    {"index": 2, "center": 0.0, "full": 1.0},
        "roll":     {"index": 1, "center": 0.0, "full": 1.0},
    },
    "toggle": {"type": "button", "index": 0, "threshold": 0.5},
    "flight_mode": "acro",           # "acro" or "angle"
    "angle_mode_max_deg": 55.0,      # angle mode only: angle at full stick
    "center_rate_dps": 200.0,        # acro: rate at full stick near center (RC rate * 200)
    "attitude_sign": {"pitch": 1, "roll": 1, "yaw": 1},
    "gains": {
        "att_p": 6.0,                # (deg/s) per deg attitude error
        "yaw_p": 3.0,
        "pos_p": 1.2,                # m/s^2 per m
        "pos_d": 2.2,                # m/s^2 per m/s
        "alt_p": 1.5,                # (m/s) target climb rate per m height error
        "alt_d": 3.0,                # m/s^2 per m/s climb rate error
        "alt_i": 0.10,               # throttle per (m/s * s)
        "max_tilt_deg": 25.0,
        "max_stick": 0.6,
    },
    "hover_throttle": 0.30,          # learned automatically during manual flight
    "blend_out_s": 0.5,
}


# ----------------------------------------------------------------------------- config

def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_PATH.exists():
        user = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------------- vJoy

class VJoy:
    AXES = [0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37]  # X Y Z RX RY RZ SL0 SL1

    def __init__(self, dll_path, device):
        if not Path(dll_path).exists():
            sys.exit(f"vJoyInterface.dll not found: {dll_path}\n-> install vJoy.")
        self.dll = ctypes.WinDLL(dll_path)
        self.id = device
        if not self.dll.vJoyEnabled():
            sys.exit("vJoy driver is not enabled.")
        status = self.dll.GetVJDStatus(device)
        if status not in (0, 1):  # OWN, FREE
            sys.exit(f"vJoy device {device} not available (status {status}). Is the script already running?")
        if not self.dll.AcquireVJD(device):
            sys.exit(f"could not acquire vJoy device {device}.")
        self.n_axes = sum(1 for a in self.AXES if self.dll.GetVJDAxisExist(device, a))
        self.n_buttons = self.dll.GetVJDButtonNumber(device)
        self.dll.ResetVJD(device)

    def set_axis(self, i, value):
        """value in [-1, 1]"""
        if i >= len(self.AXES):
            return
        v = max(-1.0, min(1.0, value))
        self.dll.SetAxis(int(1 + (v + 1.0) * 0.5 * 32767), self.id, self.AXES[i])

    def set_button(self, i, pressed):
        if i < self.n_buttons:
            self.dll.SetBtn(bool(pressed), self.id, i + 1)

    def close(self):
        self.dll.ResetVJD(self.id)
        self.dll.RelinquishVJD(self.id)


# ----------------------------------------------------------------------------- math

def quat_rotate(q, v):
    x, y, z, w = q
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx))


def wrap_deg(a):
    return (a + 180.0) % 360.0 - 180.0


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# ----------------------------------------------------------------------------- telemetry

class Telemetry(threading.Thread):
    """Reads Liftoff UDP telemetry (Timestamp, Position, Attitude, Gyro, Input) and derives the state."""

    def __init__(self, port, signs):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", port))
        self.sock.settimeout(0.5)
        self.signs = signs
        self.lock = threading.Lock()
        self.last_rx = 0.0
        self.packets = 0
        self.reset_flag = False
        self.state = None
        self._prev = None
        self._vel = [0.0, 0.0, 0.0]

    def run(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            if len(data) < 60:
                continue
            f = struct.unpack_from("<15f", data)
            t, pos, quat, gyro, inp = f[0], f[1:4], f[4:8], f[8:11], f[11:15]
            self._update(t, pos, quat, gyro, inp)

    def _update(self, t, pos, quat, gyro, inp):
        if self._prev is not None:
            pt, ppos = self._prev
            dt = t - pt
            jump = math.dist(pos, ppos)
            if dt <= 0 or dt > 0.5 or jump > 5.0:
                # reset / respawn in Liftoff
                self._vel = [0.0, 0.0, 0.0]
                self.reset_flag = True
            else:
                a = clamp(dt / 0.04, 0.0, 1.0)  # ~40 ms low-pass
                for i in range(3):
                    self._vel[i] += a * ((pos[i] - ppos[i]) / dt - self._vel[i])
        self._prev = (t, pos)

        # world "up" in the body frame (Unity: x right, y up, z forward)
        qi = (-quat[0], -quat[1], -quat[2], quat[3])
        ub = quat_rotate(qi, (0.0, 1.0, 0.0))
        # nose down -> world up leans backwards in the body (-z); right side down -> leans left (-x)
        pitch = math.degrees(math.atan2(-ub[2], ub[1])) * self.signs["pitch"]  # + = nose down
        roll = math.degrees(math.atan2(-ub[0], ub[1])) * self.signs["roll"]    # + = right side down
        fwd = quat_rotate(quat, (0.0, 0.0, 1.0))
        yaw = math.degrees(math.atan2(fwd[0], fwd[2])) * self.signs["yaw"]     # + = turning right
        tilt = math.degrees(math.acos(clamp(ub[1], -1.0, 1.0)))

        with self.lock:
            self.state = {
                "t": t, "pos": pos, "vel": tuple(self._vel), "pitch": pitch, "roll": roll,
                "yaw": yaw, "tilt": tilt, "gyro": gyro, "input": inp,
            }
            self.last_rx = time.perf_counter()
            self.packets += 1

    def get(self):
        with self.lock:
            fresh = time.perf_counter() - self.last_rx < 0.25
            return (self.state if fresh else None), self._take_reset()

    def _take_reset(self):
        r, self.reset_flag = self.reset_flag, False
        return r


# ----------------------------------------------------------------------------- controller

class HoverController:
    def __init__(self, cfg):
        self.cfg = cfg
        self.g = cfg["gains"]
        self.hover_thr = cfg["hover_throttle"]
        self.active = False

    def engage(self, s, manual_thr):
        self.active = True
        self.tgt_pos = [s["pos"][0], s["pos"][2]]
        self.tgt_h = s["pos"][1]
        self.tgt_yaw = s["yaw"]
        self.h_locked = False
        self.xy_locked = False
        self.alt_i = 0.0
        self.t_active = 0.0

    def disengage(self):
        self.active = False

    def learn_hover(self, s, thr, dt):
        """Learn the hover throttle during calm, almost level manual flight."""
        if s and abs(s["vel"][1]) < 0.3 and s["tilt"] < 12 and 0.05 < thr < 0.9:
            thr_level = thr * math.cos(math.radians(s["tilt"]))
            self.hover_thr += clamp(dt / 2.0, 0, 1) * (thr_level - self.hover_thr)

    def step(self, s, dt):
        g = self.g
        x, h, z = s["pos"]
        vx, vy, vz = s["vel"]
        speed = math.hypot(vx, vz)

        # braking phase: the target follows the drone until it stops, then the position is locked
        self.t_active += dt
        if not self.xy_locked:
            self.tgt_pos = [x, z]
            if speed < 0.8 or self.t_active > 4.0:
                self.xy_locked = True
        if not self.h_locked:
            self.tgt_h = h
            if abs(vy) < 0.3 or self.t_active > 1.5:
                self.h_locked = True

        # position -> desired acceleration (world) -> heading frame
        ax = g["pos_p"] * (self.tgt_pos[0] - x) - g["pos_d"] * vx
        az = g["pos_p"] * (self.tgt_pos[1] - z) - g["pos_d"] * vz
        yr = math.radians(s["yaw"])
        a_fwd = ax * math.sin(yr) + az * math.cos(yr)
        a_right = ax * math.cos(yr) - az * math.sin(yr)
        max_tilt = g["max_tilt_deg"]
        pitch_des = clamp(math.degrees(math.atan2(a_fwd, G)), -max_tilt, max_tilt)
        roll_des = clamp(math.degrees(math.atan2(a_right, G)), -max_tilt, max_tilt)

        # attitude -> sticks
        ms = g["max_stick"]
        if self.cfg["flight_mode"] == "angle":
            m = self.cfg["angle_mode_max_deg"]
            pitch_cmd = clamp(pitch_des / m, -ms, ms)
            roll_cmd = clamp(roll_des / m, -ms, ms)
        else:
            cr = self.cfg["center_rate_dps"]
            pitch_cmd = clamp(g["att_p"] * (pitch_des - s["pitch"]) / cr, -ms, ms)
            roll_cmd = clamp(g["att_p"] * (roll_des - s["roll"]) / cr, -ms, ms)
        yaw_cmd = clamp(g["yaw_p"] * wrap_deg(self.tgt_yaw - s["yaw"]) / self.cfg["center_rate_dps"], -ms, ms)

        # height -> target climb rate -> throttle; the integral on the climb rate error absorbs a wrong hover throttle
        vz_des = clamp(g["alt_p"] * (self.tgt_h - h), -3.0, 3.0) if self.h_locked else 0.0
        ev = vz_des - vy
        self.alt_i = clamp(self.alt_i + g["alt_i"] * ev * dt, -0.25, 0.25)
        a_up = g["alt_d"] * ev
        cos_t = max(math.cos(math.radians(min(s["tilt"], 60))), 0.5)
        thr = (self.hover_thr * (1 + a_up / G) + self.alt_i) / cos_t
        thr = clamp(thr, 0.02, 0.95)

        return thr, yaw_cmd, pitch_cmd, roll_cmd

    def status(self):
        return "BRAKING" if not (self.xy_locked and self.h_locked) else "HOLDING"


# ----------------------------------------------------------------------------- input

def init_joystick(index):
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() <= index:
        names = [pygame.joystick.Joystick(i).get_name() for i in range(pygame.joystick.get_count())]
        sys.exit(f"Controller #{index} not found. Found: {names or 'none'}")
    js = pygame.joystick.Joystick(index)
    js.init()
    return js


def pick_physical_index(cfg):
    """vJoy shows up as a joystick too, so take the first non-vJoy controller (optionally filtered by name)."""
    pygame.init()
    pygame.joystick.init()
    want = cfg.get("controller_name", "").lower()
    for i in range(pygame.joystick.get_count()):
        name = pygame.joystick.Joystick(i).get_name().lower()
        if "vjoy" not in name and want in name:
            return i
    sys.exit("No physical controller found.")


def read_raw(js):
    pygame.event.pump()
    axes = [js.get_axis(i) for i in range(js.get_numaxes())]
    buttons = [js.get_button(i) for i in range(js.get_numbuttons())]
    return axes, buttons


def raw_to_norm(ax_cfg, raw):
    span = ax_cfg["full"] - ax_cfg["center"]
    return clamp((raw - ax_cfg["center"]) / span, -1.0, 1.0) if span else 0.0


# Fixed vJoy layout (map it once like this in Liftoff):
#   X = roll (+right), Y = pitch (+forward), Z = throttle (-1 off .. +1 full), RX = yaw (+right), rest = 0
VJOY_ROLL, VJOY_PITCH, VJOY_THROTTLE, VJOY_YAW = 0, 1, 2, 3


def write_vjoy_sticks(vj, thr01, yaw, pitch, roll):
    vj.set_axis(VJOY_ROLL, roll)
    vj.set_axis(VJOY_PITCH, pitch)
    vj.set_axis(VJOY_THROTTLE, thr01 * 2.0 - 1.0)
    vj.set_axis(VJOY_YAW, yaw)
    for i in range(4, 8):
        vj.set_axis(i, 0.0)


def raw_to_thr(ax_cfg, raw):
    span = ax_cfg["high"] - ax_cfg["low"]
    return clamp((raw - ax_cfg["low"]) / span, 0.0, 1.0) if span else 0.0


def toggle_level(cfg, axes, buttons):
    t = cfg["toggle"]
    if t["type"] == "button":
        return t["index"] < len(buttons) and buttons[t["index"]] == 1
    v = axes[t["index"]] if t["index"] < len(axes) else 0.0
    return (v > t["threshold"]) if t.get("above", True) else (v < t["threshold"])


# ----------------------------------------------------------------------------- modes

def calibrate():
    cfg = load_config()
    js = init_joystick(pick_physical_index(cfg))
    print(f"Controller: {js.get_name()}  ({js.get_numaxes()} axes, {js.get_numbuttons()} buttons)\n")

    def settle():
        for _ in range(20):
            pygame.event.pump()
            time.sleep(0.01)
        return read_raw(js)

    input("1) Pitch/roll/yaw CENTERED, throttle fully DOWN. Then Enter ...")
    base_axes, base_btn = settle()
    used = set()

    def detect(prompt):
        input(prompt)
        axes, _ = settle()
        deltas = [(abs(axes[i] - base_axes[i]), i) for i in range(len(axes)) if i not in used]
        d, i = max(deltas)
        if d < 0.3:
            print(f"   !! Hardly any movement detected ({d:.2f}). Again.")
            return detect(prompt)
        used.add(i)
        print(f"   -> axis {i}: {base_axes[i]:+.2f} -> {axes[i]:+.2f}")
        return i, axes[i]

    i, v = detect("2) Throttle fully UP, Enter ...")
    cfg["axes"]["throttle"] = {"index": i, "low": base_axes[i], "high": v}
    for name, prompt in [("yaw", "3) Throttle back down. Yaw fully RIGHT, Enter ..."),
                         ("pitch", "4) Release yaw. Pitch fully FORWARD (away from you), Enter ..."),
                         ("roll", "5) Release pitch. Roll fully RIGHT, Enter ...")]:
        i, v = detect(prompt)
        cfg["axes"][name] = {"index": i, "center": base_axes[i], "full": v}

    input("6) Release everything, Enter ...")
    base_axes, base_btn = settle()
    print("7) Now press the HOVER BUTTON ...")
    while True:
        axes, btn = read_raw(js)
        hit = next((b for b in range(len(btn)) if btn[b] != base_btn[b]), None)
        if hit is not None:
            cfg["toggle"] = {"type": "button", "index": hit, "threshold": 0.5}
            print(f"   -> button {hit}")
            break
        hit = next((a for a in range(len(axes)) if a not in used and abs(axes[a] - base_axes[a]) > 0.5), None)
        if hit is not None:
            thr = (axes[hit] + base_axes[hit]) / 2
            cfg["toggle"] = {"type": "axis", "index": hit, "threshold": thr, "above": axes[hit] > base_axes[hit]}
            print(f"   -> axis {hit} used as button (threshold {thr:+.2f})")
            break
        time.sleep(0.01)

    save_config(cfg)
    print(f"\nSaved: {CONFIG_PATH}")


def monitor():
    cfg = load_config()
    js = init_joystick(pick_physical_index(cfg))
    tel = Telemetry(cfg["telemetry_port"], cfg["attitude_sign"])
    tel.start()
    print(f"Controller: {js.get_name()}   Ctrl+C quits\n")
    try:
        while True:
            axes, btn = read_raw(js)
            s, _ = tel.get()
            line = "AX " + " ".join(f"{i}:{a:+.2f}" for i, a in enumerate(axes))
            pressed = [i for i, b in enumerate(btn) if b]
            line += f" | BTN {pressed}"
            if s:
                line += (f" | h={s['pos'][1]:6.2f} v={math.hypot(s['vel'][0], s['vel'][2]):4.1f}"
                         f" P={s['pitch']:+6.1f} R={s['roll']:+6.1f} Y={s['yaw']:+6.1f}"
                         f" IN(t,y,p,r)={' '.join(f'{v:+.2f}' for v in s['input'])}")
            else:
                line += " | no telemetry"
            print("\r" + line.ljust(170), end="", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print()


def run():
    cfg = load_config()
    if not CONFIG_PATH.exists():
        print("Note: no config.json -> run 'python hover.py calibrate' first.")
    ctypes.windll.winmm.timeBeginPeriod(1)
    js = init_joystick(pick_physical_index(cfg))
    vj = VJoy(cfg["vjoy_dll"], cfg["vjoy_device"])
    tel = Telemetry(cfg["telemetry_port"], cfg["attitude_sign"])
    tel.start()
    ctl = HoverController(cfg)
    A = cfg["axes"]
    idx = {k: A[k]["index"] for k in A}

    print(f"Controller: {js.get_name()} -> vJoy #{cfg['vjoy_device']} ({vj.n_axes} axes, {vj.n_buttons} buttons)")
    print("Hover button: on/off.  Ctrl+C quits.\n")

    period = 1.0 / cfg["loop_hz"]
    last_toggle = toggle_level(cfg, *read_raw(js))
    blend = 0.0           # 1 = full autopilot, 0 = full manual
    last_auto = None
    last = time.perf_counter()
    next_print = 0.0
    msg = ""
    try:
        while True:
            now = time.perf_counter()
            dt = now - last
            last = now
            axes, buttons = read_raw(js)
            s, was_reset = tel.get()
            manual_thr = raw_to_thr(A["throttle"], axes[idx["throttle"]])

            level = toggle_level(cfg, axes, buttons)
            if level and not last_toggle:
                if ctl.active:
                    ctl.disengage()
                    msg = "MANUAL"
                elif s is None:
                    msg = "!! no telemetry - hover not possible"
                else:
                    ctl.engage(s, manual_thr)
                    msg = "HOVER ON"
            last_toggle = level

            if ctl.active and (s is None or was_reset):
                ctl.disengage()
                msg = "!! telemetry lost / reset -> MANUAL"

            if ctl.active:
                last_auto = ctl.step(s, dt)
                blend = 1.0
            else:
                ctl.learn_hover(s, manual_thr, dt)
                blend = max(0.0, blend - dt / cfg["blend_out_s"]) if last_auto else 0.0

            manual = (manual_thr, raw_to_norm(A["yaw"], axes[idx["yaw"]]),
                      raw_to_norm(A["pitch"], axes[idx["pitch"]]), raw_to_norm(A["roll"], axes[idx["roll"]]))
            cmd = manual
            if blend > 0 and last_auto:
                cmd = tuple(blend * a + (1 - blend) * m for a, m in zip(last_auto, manual))
            write_vjoy_sticks(vj, *cmd)
            for i, b in enumerate(buttons):
                vj.set_button(i, b)

            if now >= next_print:
                next_print = now + 0.1
                mode = f"HOVER/{ctl.status()}" if ctl.active else ("BLEND" if blend > 0 else "MANUAL")
                tel_txt = (f"h={s['pos'][1]:6.2f}m v={math.hypot(s['vel'][0], s['vel'][2]):4.1f}m/s "
                           f"tilt={s['tilt']:4.1f}" if s else "no telemetry")
                print(f"\r[{mode:13}] {tel_txt} | thr man={manual_thr:.2f} hover={ctl.hover_thr:.2f} | {msg}".ljust(120),
                      end="", flush=True)

            sleep = period - (time.perf_counter() - now)
            if sleep > 0:
                time.sleep(sleep)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        vj.close()
        cfg["hover_throttle"] = round(ctl.hover_thr, 3)
        if CONFIG_PATH.exists():
            save_config(cfg)
        ctypes.windll.winmm.timeEndPeriod(1)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"calibrate": calibrate, "monitor": monitor, "run": run}.get(mode, run)()
