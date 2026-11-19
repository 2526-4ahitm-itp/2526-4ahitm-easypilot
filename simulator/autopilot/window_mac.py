"""macOS version of window.py: find, focus and click the Liftoff window (Quartz + AppKit).

Coordinates are macOS points (what CGEvent and the window server use). On a Retina screen a
capture has twice as many pixels; capture_mac scales for that.

Needs, for the terminal that runs Python, in System Settings > Privacy & Security:
  Accessibility     (clicks, window position)
  Screen Recording  (window bounds with title, capture)
"""
import subprocess
import time

import AppKit
import Quartz

APP_NAME = "Liftoff"
# pyobjc resolves Quartz names lazily and that is not thread-safe: two Studio windows polling at
# once gave KeyError: 'CGWindowListCopyWindowInfo' (19.11.). Resolve them once at import.
for _name in ("CGWindowListCopyWindowInfo", "CGDisplayBounds", "CGMainDisplayID", "CGEventCreateMouseEvent",
              "CGEventPost", "CGEventSourceKeyState"):
    getattr(Quartz, _name)

TITLE_BAR = 28          # windowed Liftoff has a standard title bar above the game image
_front_cache = (0.0, None)


def _windows():
    opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    return Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []


def _liftoff_windows():
    # all windows, not only on-screen ones: a hidden or minimised Liftoff must still be found
    # (Studio then unhides it in focus_liftoff)
    wins = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID) or []
    return [w for w in wins if w.get("kCGWindowOwnerName") == APP_NAME and w.get("kCGWindowLayer", 1) == 0
            and w["kCGWindowBounds"]["Width"] > 200]


def find_window(title="liftoff"):
    """The main Liftoff window (dict from the window server) or None."""
    wins = _liftoff_windows()
    if not wins:
        return None
    # Liftoff also owns an invisible 500x500 helper window; prefer the titled game window
    return max(wins, key=lambda w: (w.get("kCGWindowName") == APP_NAME, bool(w.get("kCGWindowIsOnscreen")),
                                    w["kCGWindowBounds"]["Width"] * w["kCGWindowBounds"]["Height"]))


def _app(win=None):
    win = win or find_window()
    if win is None:
        return None
    return AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(win["kCGWindowOwnerPID"])


def focus_liftoff(hard=True):
    """Bring Liftoff to the front. `hard` hides and shows it once (a real activation for Unity)."""
    win = find_window()
    if win is None:
        raise RuntimeError("Liftoff window not found")
    app = _app(win)
    if app.isHidden():
        app.unhide()
    if hard:
        app.hide()
        time.sleep(0.4)
        app.unhide()
    app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
    time.sleep(0.8 if hard else 0.2)
    return win


def refocus_quick():
    app = _app()
    if app is not None:
        app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)


def is_focused():
    """True when the frontmost normal window belongs to Liftoff (cached for 50 ms: called at 250 Hz)."""
    global _front_cache
    now = time.perf_counter()
    if now - _front_cache[0] < 0.05:
        return _front_cache[1]
    front = next((w for w in _windows() if w.get("kCGWindowLayer", 1) == 0), None)
    result = front is not None and front.get("kCGWindowOwnerName") == APP_NAME
    _front_cache = (now, result)
    return result


def _screen_size():
    b = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
    return b.size.width, b.size.height


def client_rect(hwnd=None):
    """(left, top, width, height) of the game image in screen points."""
    win = hwnd or find_window()
    b = win["kCGWindowBounds"]
    left, top, w, h = b["X"], b["Y"], b["Width"], b["Height"]
    sw, sh = _screen_size()
    if not (w >= sw and h >= sh):           # windowed, not fullscreen: skip the title bar
        top, h = top + TITLE_BAR, h - TITLE_BAR
    return int(left), int(top), int(w), int(h)


def _mouse(kind, x, y):
    ev = Quartz.CGEventCreateMouseEvent(None, kind, (x, y), Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def click(x, y, frame=None):
    """Left click at screen points; with `frame=(w, h)` x/y are scaled from a full-screen capture of that size."""
    if frame:
        sw, sh = _screen_size()
        x, y = x * sw / frame[0], y * sh / frame[1]
    _mouse(Quartz.kCGEventMouseMoved, x, y)
    time.sleep(0.05)
    _mouse(Quartz.kCGEventMouseMoved, x + 1, y)   # tiny move so Unity updates the pointer
    time.sleep(0.05)
    _mouse(Quartz.kCGEventLeftMouseDown, x, y)
    time.sleep(0.08)
    _mouse(Quartz.kCGEventLeftMouseUp, x, y)


def key_down_f9():
    """Physical F9 (key code 101). On a Mac keyboard press fn+F9 unless F-keys are standard keys."""
    return bool(Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateCombinedSessionState, 101))


def arrange(left, top, width, height):
    """Move/resize the Liftoff window via System Events (Accessibility permission)."""
    script = (f'tell application "System Events" to tell process "{APP_NAME}" to set {{position, size}} '
              f'of window 1 to {{{{{left}, {top}}}, {{{width}, {height}}}}}')
    return subprocess.run(["osascript", "-e", script], capture_output=True).returncode == 0
