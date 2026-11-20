"""Read a HID gamepad on macOS straight through IOKit (no SDL).

Why: OpenJoystickDriver (needed for the autopilot's virtual pad) grabs the DJI FPV Remote
Controller 3 exclusively, so neither SDL nor anyone else can open it. OJD republishes it as a
virtual "OpenJoystickDriver Generic HID Gamepad" (profile `generic`, see mac/README.md). SDL 2.28
reads that pad as all zeros, IOKit reads it fine. Measured 19.11.2026: OJD raw report -> virtual
pad value at IOKit median 0.5 ms, so this path adds no noticeable latency.

IOKit pushes every value change into a callback on our own run loop thread; get_axis() only
returns the latest value, so Controller.read() stays as cheap as with pygame.
"""
import ctypes
import ctypes.util
import threading

OJD_GENERIC = (0x1209, 0x4A4F)      # vendor/product of OJD's "generic" virtual pad

_vp = ctypes.c_void_p
_io = ctypes.cdll.LoadLibrary(ctypes.util.find_library("IOKit"))
_cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
for fn, res, args in (
        ("IOHIDManagerCreate", _vp, [_vp, ctypes.c_uint32]),
        ("IOHIDManagerSetDeviceMatching", None, [_vp, _vp]),
        ("IOHIDManagerOpen", ctypes.c_int32, [_vp, ctypes.c_uint32]),
        ("IOHIDManagerCopyDevices", _vp, [_vp]),
        ("IOHIDManagerScheduleWithRunLoop", None, [_vp, _vp, _vp]),
        ("IOHIDManagerRegisterInputValueCallback", None, [_vp, _vp, _vp]),
        ("IOHIDDeviceGetProperty", _vp, [_vp, _vp]),
        ("IOHIDDeviceCopyMatchingElements", _vp, [_vp, _vp, ctypes.c_uint32]),
        ("IOHIDDeviceGetValue", ctypes.c_int32, [_vp, _vp, ctypes.POINTER(_vp)]),
        ("IOHIDValueGetElement", _vp, [_vp]),
        ("IOHIDValueGetIntegerValue", ctypes.c_long, [_vp]),
        ("IOHIDElementGetUsagePage", ctypes.c_uint32, [_vp]),
        ("IOHIDElementGetUsage", ctypes.c_uint32, [_vp]),
        ("IOHIDElementGetLogicalMin", ctypes.c_long, [_vp]),
        ("IOHIDElementGetLogicalMax", ctypes.c_long, [_vp]),
        ("IOHIDElementGetCookie", ctypes.c_uint32, [_vp])):
    f = getattr(_io, fn)
    f.restype, f.argtypes = res, args
for fn, res, args in (
        ("CFRunLoopGetCurrent", _vp, []),
        ("CFRunLoopRun", None, []),
        ("CFRunLoopStop", None, [_vp]),
        ("CFStringCreateWithCString", _vp, [_vp, ctypes.c_char_p, ctypes.c_uint32]),
        ("CFStringGetCString", ctypes.c_bool, [_vp, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]),
        ("CFDictionaryCreateMutable", _vp, [_vp, ctypes.c_long, _vp, _vp]),
        ("CFDictionarySetValue", None, [_vp, _vp, _vp]),
        ("CFNumberCreate", _vp, [_vp, ctypes.c_int, _vp]),
        ("CFSetGetCount", ctypes.c_long, [_vp]),
        ("CFSetGetValues", None, [_vp, ctypes.POINTER(_vp)]),
        ("CFArrayGetCount", ctypes.c_long, [_vp]),
        ("CFArrayGetValueAtIndex", _vp, [_vp, ctypes.c_long]),
        ("CFRelease", None, [_vp])):
    f = getattr(_cf, fn)
    f.restype, f.argtypes = res, args

_UTF8 = 0x08000100
_RUNLOOP_MODE = _vp.in_dll(_cf, "kCFRunLoopDefaultMode")
_CALLBACK = ctypes.CFUNCTYPE(None, _vp, ctypes.c_int, _vp, _vp)
AXIS_USAGES = range(0x30, 0x39)      # X Y Z Rx Ry Rz Slider Dial Wheel


def _cfstr(s):
    return _cf.CFStringCreateWithCString(None, s.encode(), _UTF8)


def _matching(vendor, product):
    d = _cf.CFDictionaryCreateMutable(
        None, 0, ctypes.addressof(ctypes.c_char.in_dll(_cf, "kCFTypeDictionaryKeyCallBacks")),
        ctypes.addressof(ctypes.c_char.in_dll(_cf, "kCFTypeDictionaryValueCallBacks")))
    for key, val in (("VendorID", vendor), ("ProductID", product)):
        n = ctypes.c_int32(val)
        _cf.CFDictionarySetValue(d, _cfstr(key), _cf.CFNumberCreate(None, 3, ctypes.byref(n)))
    return d


def _devices(mgr):
    s = _io.IOHIDManagerCopyDevices(mgr)
    if not s:
        return []
    n = _cf.CFSetGetCount(s)
    arr = (_vp * n)()
    _cf.CFSetGetValues(s, arr)
    return list(arr)


def _name(dev):
    ref = _io.IOHIDDeviceGetProperty(dev, _cfstr("Product"))
    buf = ctypes.create_string_buffer(256)
    if ref and _cf.CFStringGetCString(ref, buf, 256, _UTF8):
        return buf.value.decode()
    return "HID Gamepad"


def find(vendor_product=OJD_GENERIC):
    """Names of connected devices with this vendor/product id (no exclusive open needed)."""
    mgr = _io.IOHIDManagerCreate(None, 0)
    _io.IOHIDManagerSetDeviceMatching(mgr, _matching(*vendor_product))
    try:
        return [_name(d) for d in _devices(mgr)]
    finally:
        _cf.CFRelease(mgr)


class HidPad:
    """pygame.joystick-like reader: get_name, get_numaxes, get_axis (-1..1), get_numbuttons, get_button."""

    def __init__(self, vendor_product=OJD_GENERIC):
        self.axes, self.buttons, self.values = [], [], {}
        ready, err = threading.Event(), []
        self._loop = None

        def on_value(_ctx, _res, _sender, val):
            el = _io.IOHIDValueGetElement(val)
            self.values[_io.IOHIDElementGetCookie(el)] = _io.IOHIDValueGetIntegerValue(val)

        self._cb = _CALLBACK(on_value)       # keep a reference, IOKit calls it from the thread

        def run():
            mgr = _io.IOHIDManagerCreate(None, 0)
            _io.IOHIDManagerSetDeviceMatching(mgr, _matching(*vendor_product))
            rc = _io.IOHIDManagerOpen(mgr, 0)
            devs = _devices(mgr)
            if rc != 0 or not devs:
                err.append(f"HID {vendor_product[0]:04x}:{vendor_product[1]:04x} nicht offen (rc={rc:#x}, {len(devs)} Geräte)")
                ready.set()
                return
            dev = devs[0]
            self.name = _name(dev)
            elems = _io.IOHIDDeviceCopyMatchingElements(dev, None, 0)
            axes, buttons = {}, {}
            for i in range(_cf.CFArrayGetCount(elems)):
                el = _cf.CFArrayGetValueAtIndex(elems, i)
                page, usage = _io.IOHIDElementGetUsagePage(el), _io.IOHIDElementGetUsage(el)
                spec = (_io.IOHIDElementGetCookie(el), _io.IOHIDElementGetLogicalMin(el),
                        _io.IOHIDElementGetLogicalMax(el))
                if page == 1 and usage in AXIS_USAGES:
                    axes.setdefault(usage, spec)
                elif page == 9:
                    buttons.setdefault(usage, spec)
                if page in (1, 9):           # start from the current state, not from zero
                    ref = _vp()
                    if _io.IOHIDDeviceGetValue(dev, el, ctypes.byref(ref)) == 0 and ref:
                        self.values[spec[0]] = _io.IOHIDValueGetIntegerValue(ref)
            self.axes = [axes[u] for u in sorted(axes)]
            self.buttons = [buttons[u] for u in sorted(buttons)]
            _io.IOHIDManagerRegisterInputValueCallback(mgr, self._cb, None)
            self._loop = _cf.CFRunLoopGetCurrent()
            _io.IOHIDManagerScheduleWithRunLoop(mgr, self._loop, _RUNLOOP_MODE)
            ready.set()
            _cf.CFRunLoopRun()

        threading.Thread(target=run, daemon=True, name="hid-pad").start()
        ready.wait(5)
        if err:
            raise RuntimeError(err[0])
        if not hasattr(self, "name"):
            raise RuntimeError("HID-Gamepad antwortet nicht")

    def init(self):
        pass

    def get_name(self):
        return self.name

    def get_numaxes(self):
        return len(self.axes)

    def get_axis(self, i):
        cookie, lo, hi = self.axes[i]
        v = self.values.get(cookie, (lo + hi) / 2)
        return max(-1.0, min(1.0, 2.0 * (v - lo) / (hi - lo) - 1.0)) if hi != lo else 0.0

    def get_numbuttons(self):
        return len(self.buttons)

    def get_button(self, i):
        return bool(self.values.get(self.buttons[i][0], 0)) if i < len(self.buttons) else False

    def close(self):
        if self._loop:
            _cf.CFRunLoopStop(self._loop)
