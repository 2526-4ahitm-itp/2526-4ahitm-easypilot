#!/usr/bin/env python3
"""Builds EasyPilot-iOS.pdf — same modern style as the PPTX.

Slide canvas 13.333 x 7.5 in = 960 x 540 pt; top-left inches are converted to
reportlab's bottom-left points. Segoe UI is registered for visual parity.
"""
import os
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

HERE  = os.path.dirname(os.path.abspath(__file__))
LOGOS = os.path.join(HERE, "logos")
OUT   = os.path.join(HERE, "EasyPilot-iOS.pdf")
W, H = 960.0, 540.0
def IN(v): return v * 72.0

NAVY   = HexColor("#222B3C")
TEAL   = HexColor("#162133")
ACCENT = HexColor("#2F80ED")
INK    = HexColor("#2B3340")
MUTED  = HexColor("#6B7482")
LIGHT  = HexColor("#C4CEDE")
CARD   = HexColor("#F4F7FB")
BORDER = HexColor("#E2E7EE")

# Segoe UI for parity with the pptx; fall back to Helvetica if unavailable.
SANS, SANSB = "Helvetica", "Helvetica-Bold"
try:
    pdfmetrics.registerFont(TTFont("Segoe", r"C:\Windows\Fonts\segoeui.ttf"))
    pdfmetrics.registerFont(TTFont("Segoe-Bold", r"C:\Windows\Fonts\segoeuib.ttf"))
    SANS, SANSB = "Segoe", "Segoe-Bold"
except Exception:
    pass

SH_IN, SW_IN = 7.5, 13.333
c = canvas.Canvas(OUT, pagesize=(W, H))


def rect(x_in, y_in, w_in, h_in, fill, stroke=None, sw=1, rad=None):
    x, w, h = IN(x_in), IN(w_in), IN(h_in)
    y = H - IN(y_in) - h
    if fill is not None:
        c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke); c.setLineWidth(sw)
    if rad:
        c.roundRect(x, y, w, h, IN(rad), fill=1 if fill else 0, stroke=1 if stroke else 0)
    else:
        c.rect(x, y, w, h, fill=1 if fill else 0, stroke=1 if stroke else 0)


def line(x1, y1, x2, y2, col, lw, arrow=False):
    c.setStrokeColor(col); c.setLineWidth(lw)
    X1, Y1, X2, Y2 = IN(x1), H - IN(y1), IN(x2), H - IN(y2)
    c.line(X1, Y1, X2, Y2)
    if arrow:
        c.setFillColor(col); d = 6; up = 1 if Y2 > Y1 else -1
        p = c.beginPath(); p.moveTo(X2, Y2)
        p.lineTo(X2 - d, Y2 - up*2*d); p.lineTo(X2 + d, Y2 - up*2*d); p.close()
        c.drawPath(p, fill=1, stroke=0)


def text(x_in, y_in, s, font, size, col, align=TA_LEFT):
    c.setFillColor(col); c.setFont(font, size)
    x, y = IN(x_in), H - IN(y_in) - size
    if align == TA_CENTER:
        c.drawCentredString(x, y, s)
    elif align == TA_RIGHT:
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


def para(x_in, y_in, w_in, h_in, html, size, col, leading=None, font=SANS,
         align=TA_LEFT, space=6):
    st = ParagraphStyle("p", fontName=font, fontSize=size, textColor=col,
                        leading=leading or size*1.2, alignment=align, spaceAfter=space)
    Frame(IN(x_in), H - IN(y_in) - IN(h_in), IN(w_in), IN(h_in),
          leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0
          ).addFromList([Paragraph(html, st)], c)


def fit(path, maxw, maxh):
    iw, ih = Image.open(path).size
    ar = iw / ih
    w, h = maxw, maxw / ar
    if h > maxh:
        h, w = maxh, maxh * ar
    return w, h


def icon(name, cx_in, top_in, box_w, box_h):
    path = os.path.join(LOGOS, name)
    w, h = fit(path, box_w, box_h)
    x = cx_in - w/2
    y = top_in + (box_h - h)/2
    c.drawImage(path, IN(x), H - IN(y) - IN(h), IN(w), IN(h), mask='auto')


def header_band(title, num):
    rect(0, 0, SW_IN, 1.35, NAVY)
    rect(0.85, 0.5, 0.34, 0.34, ACCENT)
    text(1.4, 0.46, title, SANSB, 30, white)
    text(12.9, 0.52, num, SANSB, 16, ACCENT, align=TA_RIGHT)


# ===================== Slide 1 — Title (full navy) =====================
rect(0, 0, SW_IN, SH_IN, NAVY)
rect(0, 0, 0.16, SH_IN, ACCENT)
text(0.95, 1.5, "EASYPILOT  ·  4AHITM DROHNENPROJEKT", SANSB, 14, ACCENT)
c.setFont(SANSB, 62); ty = H - IN(2.25) - 62
c.setFillColor(white); c.drawString(IN(0.9), ty, "EasyPilot ")
c.setFillColor(ACCENT); c.drawString(IN(0.9) + c.stringWidth("EasyPilot ", SANSB, 62), ty, "iOS")
rect(0.95, 3.62, 1.5, 0.055, ACCENT)
para(0.95, 3.95, 11.0, 1.2,
     "SwiftUI-Companion-App für die EasyPilot-Drohne – findet die Drohne "
     "selbst im WLAN, zeigt Live-Telemetrie und fliegt einen 3D-Flugsimulator.",
     20, LIGHT, leading=27)
text(0.95, 6.1, "Simon Eder", SANSB, 19, white)
text(0.95, 6.5, "Creator", SANS, 14, LIGHT)
c.showPage()

# ===================== Slide 2 — Was ist EasyPilot iOS =====================
rect(0, 0, SW_IN, SH_IN, white)
header_band("Was ist EasyPilot iOS", "02")
bullets = [
    "EasyPilot ist unser 4AHITM-Drohnenprojekt: eine selbstgebaute Drohne mit ESP32-Steuerung.",
    "Die iOS-App ist der mobile Co-Pilot – komplett in SwiftUI, nur mit Apple-Frameworks.",
    "Sie findet die Drohne automatisch im WLAN – ohne Eintippen einer IP-Adresse.",
    "Live-Telemetrie mit 10 Hz, ein 3D-Flugsimulator und das Senden von Flugbefehlen – alles auf dem iPhone.",
]
html = "".join(f'<font color="#2F80ED">▪</font>&nbsp;&nbsp;{b}<br/><br/>' for b in bullets)
para(0.85, 1.95, 6.3, 4.8, html, 16.5, INK, leading=23)
line(7.55, 2.05, 7.55, 6.65, ACCENT, 1.75)  # vertical divider

def devbox(label, sub, x, y, w, h, accent):
    rect(x, y, w, h, CARD, stroke=accent, sw=1.75, rad=0.10)
    text(x + w/2, y + h/2 - 0.18, label, SANSB, 18, TEAL, align=TA_CENTER)
    text(x + w/2, y + h/2 + 0.12, sub, SANS, 12, MUTED, align=TA_CENTER)

devbox("iPhone", "EasyPilot App (SwiftUI)", 8.1, 2.35, 4.3, 1.2, ACCENT)
devbox("ESP32-C3", "Drohne · WLAN", 8.1, 5.3, 4.3, 1.2, NAVY)
line(8.9, 3.55, 8.9, 5.3, NAVY, 2.25, arrow=True)
line(11.6, 5.3, 11.6, 3.55, NAVY, 2.25, arrow=True)
text(10.25, 4.3, "Auto-Discovery · 10 Hz", SANS, 12, MUTED, align=TA_CENTER)
text(10.25, 4.6, "Befehle ↑ · Telemetrie ↓", SANS, 12, MUTED, align=TA_CENTER)
c.showPage()

# ===================== Slide 3 — Tech Stack (icon grid, real names) =====================
rect(0, 0, SW_IN, SH_IN, white)
header_band("Tech Stack", "03")
tech = [
    ("swift.png",     "Swift",              "Programmiersprache"),
    ("swiftui.png",   "SwiftUI",            "User Interface"),
    ("cube3d.png",    "SceneKit",           "3D-Flugsimulator"),
    ("websocket.png", "WebSocket",          "Live-Telemetrie · 10 Hz"),
    ("wifi.png",      "Network.framework",  "Auto-Discovery im WLAN"),
    ("chip.png",      "ESP32-C3",           "Mikrocontroller der Drohne"),
]
cols = 3
mx, top0, gx, gy, chh = 0.85, 1.95, 0.45, 0.28, 2.3
cw = (SW_IN - 2*mx - (cols-1)*gx) / cols
for i, (img, name, sub) in enumerate(tech):
    cidx, ridx = i % cols, i // cols
    x = mx + cidx*(cw + gx)
    y = top0 + ridx*(chh + gy)
    rect(x, y, cw, chh, CARD, stroke=BORDER, sw=1, rad=0.05)
    icon(img, x + cw/2, y + 0.3, 1.45, 0.95)
    text(x + cw/2, y + 1.42, name, SANSB, 17, TEAL, align=TA_CENTER)
    rect(x + cw/2 - 0.28, y + 1.86, 0.56, 0.035, ACCENT)
    text(x + cw/2, y + 1.98, sub, SANS, 12, MUTED, align=TA_CENTER)
c.showPage()

# ===================== Slide 4 — Live Demo (full navy) =====================
rect(0, 0, SW_IN, SH_IN, NAVY)
rect(0, 0, 0.16, SH_IN, ACCENT)
text(0.95, 2.7, "04  ·  DEMO", SANSB, 14, ACCENT)
text(0.9, 3.2, "Live Demo", SANSB, 66, white)
rect(0.95, 4.75, 1.6, 0.055, ACCENT)
c.showPage()

c.save()
print("saved", OUT)
