"""Find and focus the Liftoff window. Liftoff only reads joystick input while focused."""
import ctypes
import ctypes.wintypes as wt
import time

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    user32.SetProcessDPIAware()


def find_window(title="liftoff"):
    found = []

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value.lower() == title:
                found.append(hwnd)
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(callback), 0)
    return found[0] if found else None


def focus_liftoff(hard=True):
    """Bring Liftoff to the front so that Unity really has focus.

    SetForegroundWindow alone is not enough: Unity (and Rewired's UI module) keeps
    ignoring all input until it gets a real activation, so `hard` minimises and
    restores the window once. Screenshot tools that briefly take focus cause the
    same state, so call this again before sending input.
    """
    hwnd = find_window()
    if hwnd is None:
        raise RuntimeError("Liftoff window not found")
    if hard:
        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        time.sleep(0.4)
    user32.keybd_event(0x12, 0, 0, 0)  # an ALT tap allows SetForegroundWindow from a background process
    user32.keybd_event(0x12, 0, 2, 0)
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.8 if hard else 0.2)
    return hwnd


def click(x, y, frame=None):
    """Left click at screen pixels; with `frame=(w, h)` x/y are scaled from a full-screen screenshot of that size."""
    if frame:
        x, y = x * user32.GetSystemMetrics(0) / frame[0], y * user32.GetSystemMetrics(1) / frame[1]
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(0x0001, 1, 0, 0, 0)  # tiny relative move so Unity updates the pointer
    time.sleep(0.05)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.08)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def refocus_quick():
    """Take the foreground back without waiting (inside the control loop)."""
    hwnd = find_window()
    if hwnd is not None:
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(hwnd)


def is_focused():
    hwnd = find_window()
    return hwnd is not None and user32.GetForegroundWindow() == hwnd


def client_rect(hwnd=None):
    """(left, top, width, height) of the game image in physical screen pixels."""
    hwnd = hwnd or find_window()
    rect = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return origin.x, origin.y, rect.right, rect.bottom
