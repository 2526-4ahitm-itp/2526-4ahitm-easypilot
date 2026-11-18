"""vJoy output for Liftoff.

Fixed layout, matching the Rewired maps in Liftoff (see README):
  axis 0 X  = roll   (+right)        button 0 = Confirm (menu)
  axis 1 Y  = pitch  (+forward)      button 1 = Cancel  (menu)
  axis 2 Z  = throttle (-1 off..+1)  button 2 = Reset drone
  axis 3 RX = yaw    (+right)        button 3 = Pause
  axis 4 RY = menu horizontal        button 4 = Exit
  axis 5 RZ = menu vertical
"""
import ctypes
import json
import os
import shutil
import socket
import struct
import subprocess
import threading
import sys
import time
from pathlib import Path

DEFAULT_DLL = r"C:\Program Files\vJoy\x64\vJoyInterface.dll"
AXES = [0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37]  # X Y Z RX RY RZ SL0 SL1

ROLL, PITCH, THROTTLE, YAW, MENU_X, MENU_Y = range(6)
BTN_CONFIRM, BTN_CANCEL, BTN_RESET, BTN_PAUSE, BTN_EXIT = range(5)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class VJoy:
    """vJoy device on Windows; on macOS the same API drives an OpenJoystickDriver virtual gamepad."""

    def __new__(cls, *args, **kwargs):
        if cls is VJoy and sys.platform == "darwin":
            return super().__new__(MacVJoy)
        return super().__new__(cls)

    def __init__(self, device=1, dll_path=DEFAULT_DLL):
        if not Path(dll_path).exists():
            sys.exit(f"vJoyInterface.dll not found: {dll_path}")
        self.dll = ctypes.WinDLL(dll_path)
        self.id = device
        if not self.dll.vJoyEnabled():
            sys.exit("vJoy driver not enabled")
        status = self.dll.GetVJDStatus(device)
        if status not in (0, 1):  # OWN, FREE
            sys.exit(f"vJoy device {device} busy (status {status}) - is another script running?")
        if not self.dll.AcquireVJD(device):
            sys.exit(f"could not acquire vJoy device {device}")
        self.n_buttons = self.dll.GetVJDButtonNumber(device)
        self.idle()

    def axis(self, i, value):
        """value in [-1, 1]"""
        v = clamp(value, -1.0, 1.0)
        self.dll.SetAxis(int(1 + (v + 1.0) * 0.5 * 32767), self.id, AXES[i])

    def button(self, i, pressed):
        if i < self.n_buttons:
            self.dll.SetBtn(bool(pressed), self.id, i + 1)

    def sticks(self, throttle01, yaw, pitch, roll):
        self.axis(ROLL, roll)
        self.axis(PITCH, pitch)
        self.axis(THROTTLE, throttle01 * 2.0 - 1.0)
        self.axis(YAW, yaw)
        self.flush()

    def flush(self):
        """The last SetAxis only reaches Windows with the next report, so write an unused axis."""
        self.axis(7, 0.0)

    def idle(self):
        """Throttle off, sticks and menu axes centred, no buttons."""
        self.sticks(0.0, 0.0, 0.0, 0.0)
        for i in range(4, 8):
            self.axis(i, 0.0)
        for b in range(min(self.n_buttons, 8)):
            self.button(b, False)

    def tap(self, b, hold=0.12):
        self.button(b, True)
        self.flush()
        time.sleep(hold)
        self.button(b, False)
        self.flush()

    def nudge(self, axis_index, direction, hold=0.15):
        self.axis(axis_index, direction)
        self.flush()
        time.sleep(hold)
        self.axis(axis_index, 0.0)
        self.flush()

    def close(self):
        self.idle()
        self.dll.RelinquishVJD(self.id)


class OjdGamepad(VJoy):
    """macOS: virtual gamepad from OpenJoystickDriver (notarized, no sudo, no game mod).

    Owned by the long-running helper simulator/mac/ojdpad.py (see MacVJoy for why).

    Runs `ojd virtual feed --as game-controller-compatible` (Liftoff sees an "Xbox Wireless
    Controller"; the "generic" profile shows up in Rewired but its axes stay at 0) and writes the
    state to its stdin as one JSON frame every 10 ms (ojd plays each frame for >= 8 ms, so a faster
    rate would queue up). The gamepad disappears when this process ends or ojd gets no frame for 2 s.

    Layout: every flight axis gets an element of its own. Rewired treats the two stick axes of
    one thumbstick as a circle (throttle -1 with yaw +0.5 came out as -0.89 / +0.45), so no two
    flight axes may share a thumbstick:
      roll     -> LeftStickX            pitch -> RightStickY
      throttle -> LeftTrigger (0..1)    yaw   -> RightTrigger (0..1), centre 0.5
      menu x/y -> left stick (Liftoff's Xbox menu map); y flipped because ojd sticks run Y down
      buttons  -> confirm South (A), cancel East (B), reset East (B in the flight map),
                  pause Guide, exit North (Y). In Liftoff's Xbox defaults the triggers
                  were bound to FPV Noise / Fisheye Toggle; clear both (Controls > Buttons).
    Liftoff manual calibration (Options > Controls > Controller > Calibrate > Manual), all axes
    centred while selecting: right horizontal = ch 0, right vertical = ch 3,
    left vertical = ch 4, left horizontal = ch 5, deadband 0, mode 2. SIGNS sets the directions,
    found in flight on 18.11.2026: Liftoff's telemetry Input then equals the command for pitch,
    throttle and yaw and is negated for roll; with roll -1 the drone diverged within 2 s, with
    +1 hovertest holds 3 m and flies a 3 m / 3 m step at ~98 Hz.
    """

    BUTTONS = ("South", "East", "East", "Guide", "North", "West", "LeftShoulder", "RightShoulder")
    SIGNS = (1.0, -1.0, 1.0, 1.0)  # roll, pitch, throttle, yaw (Liftoff 1.7.8, 18.11.2026)
    PERIOD = 0.010

    def __init__(self, device=1, dll_path=None, ojd=None):
        self.id = device
        self.n_buttons = len(self.BUTTONS)
        exe = ojd or shutil.which("ojd") or "/Applications/OpenJoystickDriver.app/Contents/MacOS/OpenJoystickDriver"
        if not Path(exe).exists():
            sys.exit("OpenJoystickDriver not found - see simulator/mac/README.md")
        self.axes = [0.0] * 8
        self.buttons = 0
        self.lock = threading.Lock()
        profile = os.environ.get("EASYPILOT_OJD_PROFILE", "game-controller-compatible")
        self.proc = subprocess.Popen([exe, "--no-input", "virtual", "feed", "--as", profile],
                                     stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                     text=True, bufsize=1)
        self.running = True
        self._write()
        time.sleep(0.5)
        if self.proc.poll() is not None:
            err = self.proc.stderr.read().strip()
            sys.exit(f"ojd virtual feed failed: {err or self.proc.returncode} (is OpenJoystickDriver running "
                     "with Input Monitoring + Accessibility allowed?)")
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        # A trigger only reaches the game once it changes; until then Liftoff reads it as 0 (= -1,
        # full left yaw). Nudge both triggers so the centred value is delivered.
        self.axis(THROTTLE, -0.98)
        self.axis(YAW, 0.02)
        time.sleep(0.1)
        self.idle()

    def _frame(self):
        with self.lock:
            v = list(self.axes)
            pressed = sorted({n for i, n in enumerate(self.BUTTONS) if self.buttons >> i & 1})
        roll, pitch, thr, yaw = (v[i] * self.SIGNS[i] for i in range(4))
        axes = {
            "LeftStickX": v[MENU_X] if v[MENU_X] else roll,
            "LeftStickY": -v[MENU_Y],
            "RightStickY": pitch,
            "LeftTrigger": (thr + 1.0) * 0.5,
            "RightTrigger": (yaw + 1.0) * 0.5,
        }
        return json.dumps({"axes": {k: round(x, 4) for k, x in axes.items()}, "buttons": pressed}) + "\n"

    def _write(self):
        try:
            self.proc.stdin.write(self._frame())
        except (BrokenPipeError, ValueError, OSError):
            self.running = False

    def _loop(self):
        nxt = time.perf_counter()
        while self.running:
            self._write()
            nxt += self.PERIOD
            time.sleep(max(0.0, nxt - time.perf_counter()))

    def axis(self, i, value):
        with self.lock:
            self.axes[i] = clamp(value, -1.0, 1.0)

    def button(self, i, pressed):
        if i < self.n_buttons:
            with self.lock:
                self.buttons = self.buttons | (1 << i) if pressed else self.buttons & ~(1 << i)

    def flush(self):
        pass  # the writer thread sends the state every 10 ms

    def close(self):
        self.idle()
        time.sleep(3 * self.PERIOD)
        self.running = False
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=2)
        except Exception:
            self.proc.kill()


MAC_PORT = 9101


class MacVJoy(VJoy):
    """macOS: sends the joystick state to simulator/mac/ojdpad.py (UDP 127.0.0.1:9101).

    ojdpad keeps one OpenJoystickDriver gamepad alive across runs, like the vJoy device on
    Windows. If the gamepad disappeared between runs, Liftoff would read a centred trigger,
    i.e. half throttle, and the drone would climb away. Protocol: 8 x int16 axes + uint32
    buttons (20 bytes, little endian), "PING" -> "PONG"; no packet for 0.5 s -> idle.
    """

    def __init__(self, device=1, dll_path=None, port=MAC_PORT):
        self.id = device
        self.n_buttons = len(OjdGamepad.BUTTONS)
        self.addr = ("127.0.0.1", port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)
        try:
            self.sock.sendto(b"PING", self.addr)
            if self.sock.recv(16) != b"PONG":
                raise OSError
        except OSError:
            sys.exit("ojdpad not running - start it first: simulator/.venv/bin/python simulator/mac/ojdpad.py")
        self.axes = [0] * 8
        self.buttons = 0
        self.idle()

    def _send(self):
        self.sock.sendto(struct.pack("<8hI", *self.axes, self.buttons), self.addr)

    def axis(self, i, value):
        self.axes[i] = int(round(clamp(value, -1.0, 1.0) * 32767))
        self._send()

    def button(self, i, pressed):
        if i < self.n_buttons:
            self.buttons = self.buttons | (1 << i) if pressed else self.buttons & ~(1 << i)
            self._send()

    def flush(self):
        self._send()

    def close(self):
        self.idle()
        self.sock.close()


BIND_TARGETS = {"roll": ROLL, "pitch": PITCH, "throttle": THROTTLE, "yaw": YAW, "menu-x": MENU_X, "menu-y": MENU_Y,
                "confirm": BTN_CONFIRM, "cancel": BTN_CANCEL, "reset": BTN_RESET, "pause": BTN_PAUSE, "exit": BTN_EXIT}
AXIS_NAMES = ("roll", "pitch", "throttle", "yaw", "menu-x", "menu-y")


def bind(name, delay=4.0):
    """Wiggle one axis / press one button after `delay` s, while Liftoff waits for input in its controller setup.

      python -m autopilot.vjoy bind roll      # then click 'Roll' in Liftoff's binding screen
    """
    joy = VJoy()
    print(f"{name}: switch to Liftoff and start the binding - input follows in {delay:.0f} s")
    time.sleep(delay)
    target = BIND_TARGETS[name]
    try:
        if name in AXIS_NAMES:
            for v in (1.0, -1.0, 1.0, -1.0, 0.0):
                end = time.perf_counter() + 0.6
                while time.perf_counter() < end:
                    joy.axis(target, v)
                    time.sleep(0.02)
            if name == "throttle":
                joy.axis(target, -1.0)
        else:
            for _ in range(3):
                joy.tap(target, 0.2)
                time.sleep(0.4)
    finally:
        joy.close()
    print("done")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "bind" and sys.argv[2] in BIND_TARGETS:
        bind(sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 4.0)
    else:
        sys.exit("usage: python -m autopilot.vjoy bind {" + ",".join(BIND_TARGETS) + "} [delay_s]")
