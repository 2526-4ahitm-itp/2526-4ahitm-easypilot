"""Human pilot: the visitor's controller is passed through to vJoy.

Liftoff listens to one controller only, and for the autopilot that is vJoy. Instead of
switching the controller in Liftoff's menu between every run, the event program reads the
real controller (RC transmitter in USB joystick mode or gamepad) and writes its sticks to vJoy.
That also gives a fair start: the sticks are held at zero until the countdown says GO.

  python -m autopilot.pilot list          # connected controllers
  python -m autopilot.pilot calibrate     # once per controller, saves controller.local.json
  python -m autopilot.pilot test          # live stick values
"""
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")   # Liftoff has the focus, not us
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

CONFIG = Path(__file__).resolve().parent / "controller.local.json"
STICKS = ("throttle", "yaw", "pitch", "roll")


def _pygame():
    if sys.platform == "darwin":
        # Studio reads the controller from a worker thread; SDL's Cocoa video driver may only start
        # on the main thread (NSInternalInconsistencyException). Joysticks work without it.
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
    import pygame
    if not pygame.get_init():
        pygame.init()
    pygame.joystick.init()
    return pygame


def _is_virtual(joy):
    """vJoy on Windows; on macOS the OpenJoystickDriver pad of mac/ojdpad.py. It shows up as an
    Xbox Wireless Controller (045e:0b13, the Bluetooth product id) on the USB bus, which a real
    pad does not: over USB a real Xbox Series pad reports 0b12, over Bluetooth bus 05."""
    if "vjoy" in joy.get_name().lower():
        return True
    guid = joy.get_guid() if hasattr(joy, "get_guid") else ""
    return sys.platform == "darwin" and guid.startswith("0300") and guid[8:20] == "5e040000130b"


def _is_ojd_generic(joy):
    """OJD's republished pad of a controller it holds (DJI RC 3). SDL reads it as zeros on macOS,
    so it is listed through IOKit instead (hid_mac)."""
    guid = joy.get_guid() if hasattr(joy, "get_guid") else ""
    return sys.platform == "darwin" and guid[8:20] == "09120000" + "4f4a"


def controllers():
    """(index, name) of all joysticks except the virtual one the autopilot drives. On macOS a
    controller that OpenJoystickDriver holds exclusively (DJI FPV RC 3) has the index "hid"."""
    pg = _pygame()
    pg.event.pump()        # SDL only sees a controller plugged in after start when events are pumped
    out = []
    for i in range(pg.joystick.get_count()):
        joy = pg.joystick.Joystick(i)
        if not _is_virtual(joy) and not _is_ojd_generic(joy):
            out.append((i, joy.get_name()))
    if sys.platform == "darwin":
        from . import hid_mac
        out += [("hid", n) for n in hid_mac.find()[:1]]
    return out


def _open(idx):
    """(joystick-like object, pump function) for an index from controllers()."""
    if idx == "hid":
        from . import hid_mac
        return hid_mac.HidPad(), lambda: None
    pg = _pygame()
    joy = pg.joystick.Joystick(idx)
    joy.init()
    return joy, pg.event.pump


def calibrated():
    """True if controller.local.json belongs to a connected controller. A config of another
    controller would map the wrong axes (Controller() falls back to the first one)."""
    try:
        name = json.loads(CONFIG.read_text(encoding="utf-8"))["name"]
    except (OSError, ValueError, KeyError):
        return False
    return any(n == name for _, n in controllers())


class Controller:
    """Calibrated stick reading: throttle 0..1, yaw/pitch/roll -1..1 (+right / +forward / +right)."""

    def __init__(self, config=CONFIG):
        cfg = json.loads(Path(config).read_text(encoding="utf-8"))
        self.cfg = cfg
        match = [i for i, name in controllers() if name == cfg["name"]] or [i for i, _ in controllers()]
        if not match:
            raise RuntimeError("no controller connected (the virtual pad does not count)")
        self.joy, self.pump = _open(match[0])
        self.name = self.joy.get_name()

    def _axis(self, spec):
        v = self.joy.get_axis(spec["axis"])
        lo, mid, hi = spec["min"], spec["center"], spec["max"]
        if spec.get("unipolar"):
            r = (v - lo) / (hi - lo) if hi != lo else 0.0
            return min(1.0, max(0.0, r))
        r = (v - mid) / (hi - mid) if v >= mid else (v - mid) / (mid - lo)
        r = r if abs(r) > spec.get("deadband", 0.02) else 0.0
        return min(1.0, max(-1.0, r))

    def read(self):
        self.pump()
        a = self.cfg["axes"]
        return (self._axis(a["throttle"]), self._axis(a["yaw"]), self._axis(a["pitch"]), self._axis(a["roll"]))

    def button(self, name):
        b = self.cfg.get("buttons", {}).get(name)
        self.pump()
        return b is not None and self.joy.get_button(b)


def _sample(joy, pump, seconds):
    vals = []
    end = time.time() + seconds
    while time.time() < end:
        pump()
        vals.append([joy.get_axis(i) for i in range(joy.get_numaxes())])
        time.sleep(0.01)
    return vals


def calibrate():
    found = controllers()
    if not found:
        sys.exit("kein Controller gefunden (Fernsteuerung im USB-Joystick-Modus anstecken)")
    idx, name = found[0]
    joy, pump = _open(idx)
    print(f"Controller: {name}, {joy.get_numaxes()} Achsen, {joy.get_numbuttons()} Knöpfe")

    def step(msg, seconds=2.5):
        input(f"\n{msg}  [Enter]")
        print("  messe ...")
        v = _sample(joy, pump, seconds)
        return [sum(c) / len(c) for c in zip(*v)], [max(c) - min(c) for c in zip(*v)]

    rest, _ = step("Alle Sticks loslassen (mittig), Gas ganz UNTEN.")
    axes = {}
    for stick, low_msg, high_msg in (
            ("throttle", None, "Gas ganz OBEN halten."),
            ("yaw", "Gas unten, Yaw (Gieren) ganz LINKS halten.", "Yaw ganz RECHTS halten."),
            ("pitch", "Pitch (Nicken) ganz ZURÜCK halten.", "Pitch ganz NACH VORNE halten."),
            ("roll", "Roll (Rollen) ganz LINKS halten.", "Roll ganz RECHTS halten.")):
        lo = rest if low_msg is None else step(low_msg)[0]
        hi = step(high_msg)[0]
        diff = [h - l for h, l in zip(hi, lo)]
        used = {a["axis"] for a in axes.values()}
        ax = max((i for i in range(len(diff)) if i not in used), key=lambda i: abs(diff[i]))
        if abs(diff[ax]) < 0.3:
            sys.exit(f"{stick}: keine Achse hat sich deutlich bewegt - nochmal versuchen")
        spec = {"axis": ax, "min": lo[ax], "max": hi[ax], "center": rest[ax]}
        if stick == "throttle":
            spec["unipolar"] = True
        axes[stick] = spec
        print(f"  {stick}: Achse {ax} ({lo[ax]:+.2f} .. {hi[ax]:+.2f})")
    cfg = {"name": name, "axes": axes, "buttons": {}}
    CONFIG.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    print(f"\ngespeichert: {CONFIG}")


def test():
    c = Controller()
    print(c.name)
    while True:
        t, y, p, r = c.read()
        print(f"\rGas {t:4.2f}  Yaw {y:+5.2f}  Pitch {p:+5.2f}  Roll {r:+5.2f}", end="")
        time.sleep(0.05)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for i, n in controllers():
            print(i, n)
        if not controllers():
            print("kein Controller (außer vJoy) gefunden")
    elif cmd == "calibrate":
        calibrate()
    elif cmd == "test":
        test()
