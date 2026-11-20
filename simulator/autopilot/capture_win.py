"""Windows capture: GDI StretchBlt, the GPU scales the 4K image down in a few milliseconds."""
import ctypes
import ctypes.wintypes as wt

import numpy as np

from . import window

gdi32 = ctypes.windll.gdi32
user32 = ctypes.windll.user32
SRCCOPY = 0x00CC0020
HALFTONE = 4
COLORONCOLOR = 3      # no filtering: half the time of HALFTONE (17 vs 33 ms at 1080p), fine for tracking

_H = ctypes.c_void_p
user32.GetDC.restype = _H
user32.GetDC.argtypes = [_H]
user32.ReleaseDC.argtypes = [_H, _H]
gdi32.CreateCompatibleDC.restype = _H
gdi32.CreateCompatibleDC.argtypes = [_H]
gdi32.CreateCompatibleBitmap.restype = _H
gdi32.CreateCompatibleBitmap.argtypes = [_H, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = _H
gdi32.SelectObject.argtypes = [_H, _H]
gdi32.SetStretchBltMode.argtypes = [_H, ctypes.c_int]
gdi32.StretchBlt.argtypes = [_H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             _H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.DWORD]
gdi32.GetDIBits.argtypes = [_H, _H, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]
gdi32.DeleteObject.argtypes = [_H]
gdi32.DeleteDC.argtypes = [_H]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class Grabber:
    def __init__(self, width=640, rect=None, mode=HALFTONE):
        self.rect = rect or window.client_rect()
        left, top, w, h = self.rect
        self.width = width
        self.height = int(round(width * h / w))
        self.src = user32.GetDC(0)
        self.mem = gdi32.CreateCompatibleDC(self.src)
        self.bmp = gdi32.CreateCompatibleBitmap(self.src, self.width, self.height)
        gdi32.SelectObject(self.mem, self.bmp)
        gdi32.SetStretchBltMode(self.mem, mode)
        self.info = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), self.width, -self.height, 1, 32, 0, 0, 0, 0, 0, 0)
        self.buf = np.empty((self.height, self.width, 4), dtype=np.uint8)

    def grab(self):
        """BGR uint8 image (height, width, 3)."""
        left, top, w, h = self.rect
        gdi32.StretchBlt(self.mem, 0, 0, self.width, self.height, self.src, left, top, w, h, SRCCOPY)
        gdi32.GetDIBits(self.mem, self.bmp, 0, self.height, self.buf.ctypes.data, ctypes.byref(self.info), 0)
        return self.buf[:, :, :3].copy()

    def close(self):
        gdi32.DeleteObject(self.bmp)
        gdi32.DeleteDC(self.mem)
        user32.ReleaseDC(0, self.src)
