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

    def idle(self):
        """Throttle off, sticks and menu axes centred, no buttons."""
        self.sticks(0.0, 0.0, 0.0, 0.0)
        for i in range(4, 8):
            self.axis(i, 0.0)
        for b in range(min(self.n_buttons, 8)):
            self.button(b, False)

    def tap(self, b, hold=0.12):
        self.button(b, True)
        time.sleep(hold)
        self.button(b, False)

    def nudge(self, axis_index, direction, hold=0.15):
        self.axis(axis_index, direction)
        time.sleep(hold)
        self.axis(axis_index, 0.0)

    def close(self):
        self.idle()
        self.dll.RelinquishVJD(self.id)
