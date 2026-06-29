#!/usr/bin/env python3
"""Draws a small set of clean, uniform concept icons (transparent PNG, colored
glyph) used by the EasyPilot iOS deck: WiFi, WebSocket, 3D-cube, microchip."""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
LOGOS = os.path.join(HERE, "logos")
os.makedirs(LOGOS, exist_ok=True)

BLUE = (0x2F, 0x80, 0xED, 255)
NAVY = (0x2C, 0x36, 0x49, 255)
TEAL = (0x14, 0x9E, 0xB8, 255)
RED  = (0xE0, 0x55, 0x2B, 255)
S = 512


def canvas():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def wifi():
    img, d = canvas()
    cx, cy = S / 2, S * 0.74
    for rr, w in [(70, 34), (150, 34), (230, 34)]:
        bb = [cx - rr, cy - rr, cx + rr, cy + rr]
        d.arc(bb, start=225, end=315, fill=BLUE, width=w)
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=BLUE)
    img.save(os.path.join(LOGOS, "wifi.png"))


def websocket():
    img, d = canvas()
    # two opposing horizontal arrows = bidirectional live link
    y1, y2 = S * 0.40, S * 0.60
    d.line([(S * 0.18, y1), (S * 0.82, y1)], fill=NAVY, width=30)
    d.polygon([(S * 0.86, y1), (S * 0.72, y1 - 42), (S * 0.72, y1 + 42)], fill=NAVY)
    d.line([(S * 0.18, y2), (S * 0.82, y2)], fill=NAVY, width=30)
    d.polygon([(S * 0.14, y2), (S * 0.28, y2 - 42), (S * 0.28, y2 + 42)], fill=NAVY)
    img.save(os.path.join(LOGOS, "websocket.png"))


def cube3d():
    img, d = canvas()
    cx, cy, r = S / 2, S * 0.50, 165
    top   = [(cx, cy - r), (cx + r, cy - r / 2), (cx, cy), (cx - r, cy - r / 2)]
    left  = [(cx - r, cy - r / 2), (cx, cy), (cx, cy + r), (cx - r, cy + r / 2)]
    right = [(cx + r, cy - r / 2), (cx, cy), (cx, cy + r), (cx + r, cy + r / 2)]
    d.polygon(top,   fill=TEAL)
    d.polygon(left,  fill=(0x0F, 0x76, 0x8C, 255))
    d.polygon(right, fill=(0x18, 0xB6, 0xD2, 255))
    img.save(os.path.join(LOGOS, "cube3d.png"))


def chip():
    img, d = canvas()
    a, b = S * 0.28, S * 0.72          # chip body bounds
    d.rounded_rectangle([a, a, b, b], radius=34, fill=RED)
    d.rounded_rectangle([a + 44, a + 44, b - 44, b - 44], radius=18,
                        outline=(255, 255, 255, 255), width=14)
    # pins on all four sides
    pin = 26
    for t in (0.42, 0.58):
        d.rectangle([S * t - 14, a - pin, S * t + 14, a], fill=RED)          # top
        d.rectangle([S * t - 14, b, S * t + 14, b + pin], fill=RED)          # bottom
        d.rectangle([a - pin, S * t - 14, a, S * t + 14], fill=RED)          # left
        d.rectangle([b, S * t - 14, b + pin, S * t + 14], fill=RED)          # right
    img.save(os.path.join(LOGOS, "chip.png"))


def gyro():
    img, d = canvas()
    cx, cy, R, w = S/2, S/2, 175, 26
    col = (0x7C, 0x5C, 0xFF, 255)
    d.ellipse([cx-R, cy-R, cx+R, cy+R], outline=col, width=w)                 # outer ring
    d.ellipse([cx-R*0.42, cy-R, cx+R*0.42, cy+R], outline=col, width=w)       # vertical gimbal
    d.ellipse([cx-R, cy-R*0.42, cx+R, cy+R*0.42], outline=col, width=w)       # horizontal gimbal
    d.ellipse([cx-24, cy-24, cx+24, cy+24], fill=col)                         # rotor hub
    img.save(os.path.join(LOGOS, "gyro.png"))


wifi(); websocket(); cube3d(); chip(); gyro()
print("icons written to", LOGOS)
