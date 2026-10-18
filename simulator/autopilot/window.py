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


def focus_liftoff():
    hwnd = find_window()
    if hwnd is None:
        raise RuntimeError("Liftoff window not found")
    if user32.GetForegroundWindow() != hwnd:
        user32.keybd_event(0x12, 0, 0, 0)  # an ALT tap allows SetForegroundWindow from a background process
        user32.keybd_event(0x12, 0, 2, 0)
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.3)
    return hwnd


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
