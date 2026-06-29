#!/usr/bin/env python3
"""Builds EasyPilot-iOS.pdf — same layout as the PPTX (blue accent, icon grid).

Slide canvas: 13.333 x 7.5 in = 960 x 540 pt. Coordinates are given as top-left
inches (matching the pptx) and converted to reportlab's bottom-left points.
"""
import os
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.enums import TA_LEFT, TA_CENTER

HERE  = os.path.dirname(os.path.abspath(__file__))
LOGOS = os.path.join(HERE, "logos")
OUT   = os.path.join(HERE, "EasyPilot-iOS.pdf")
W, H = 960.0, 540.0
def IN(v): return v * 72.0

NAVY   = HexColor("#2C3649")
TEAL   = HexColor("#103A50")
ACCENT = HexColor("#2F80ED")
INK    = HexColor("#333B47")
MUTED  = HexColor("#6B7482")
CARD   = HexColor("#F6F8FB")
BORDER = HexColor("#DDE1E7")

SERIF, SANS, SANSB = "Times-Roman", "Helvetica", "Helvetica-Bold"
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
    (c.drawCentredString if align == TA_CENTER else c.drawString)(x, y, s)


def para(x_in, y_in, w_in, h_in, html, size, col, leading=None, font=SANS,
         align=TA_LEFT, space=6):
    st = ParagraphStyle("p", fontName=font, fontSize=size, textColor=col,
                        leading=leading or size*1.2, alignment=align, spaceAfter=space)
    Frame(IN(x_in), H - IN(y_in) - IN(h_in), IN(w_in), IN(h_in),
          leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0
          ).addFromList([Paragraph(html, st)], c)


def poly(pts_in, fill):
    c.setFillColor(fill); p = c.beginPath()
    p.moveTo(IN(pts_in[0][0]), H - IN(pts_in[0][1]))
    for x, y in pts_in[1:]:
        p.lineTo(IN(x), H - IN(y))
    p.close(); c.drawPath(p, fill=1, stroke=0)


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


# ===================== Slide 1 — Title =====================
rect(0, 0, SW_IN, SH_IN, white)
poly([(0, SH_IN*0.80), (SW_IN, SH_IN*0.42), (SW_IN, SH_IN), (0, SH_IN)], NAVY)
c.setFont(SERIF, 60); ty = H - IN(0.85) - 60
c.setFillColor(TEAL); c.drawString(IN(0.9), ty, "EasyPilot ")
c.setFillColor(ACCENT); c.drawString(IN(0.9) + c.stringWidth("EasyPilot ", SERIF, 60), ty, "iOS")
rect(0.95, 2.12, 2.3, 0.05, ACCENT)
para(0.95, 2.45, 11.0, 1.0,
     "SwiftUI-Companion-App für die EasyPilot-Drohne – findet die Drohne "
     "selbst im WLAN, zeigt Live-Telemetrie und fliegt einen 3D-Simulator.",
     21, MUTED, leading=28)
text(0.95, 3.90, "Simon Eder", SANS, 18, INK)
text(0.95, 4.33, "Creator", SANS, 14, MUTED)
c.showPage()

# ===================== Slide 2 — Was ist EasyPilot iOS =====================
rect(0, 0, SW_IN, SH_IN, white)
para(0.85, 0.7, 11.6, 1.0, "Was ist EasyPilot iOS", 36, TEAL, font=SERIF, leading=40)
line(0.85, 1.75, 12.48, 1.75, ACCENT, 2.25)  # line through the section
bullets = [
    "EasyPilot ist unser 4AHITM-Drohnenprojekt: eine selbstgebaute Drohne mit ESP32-Steuerung.",
    "Die iOS-App ist der mobile Co-Pilot – komplett in SwiftUI, nur mit Apple-Frameworks.",
    "Sie findet die Drohne automatisch im WLAN – ohne Eintippen einer IP-Adresse.",
    "Live-Telemetrie mit 10 Hz, ein 3D-Flugsimulator und das Senden von Flugbefehlen – alles auf dem iPhone.",
]
html = "".join(f'<font color="#2F80ED">●</font>&nbsp;&nbsp;{b}<br/><br/>' for b in bullets)
para(0.85, 2.25, 6.4, 4.6, html, 16.5, INK, leading=23)

def devbox(label, sub, x, y, w, h, accent):
    rect(x, y, w, h, white, stroke=accent, sw=2, rad=0.12)
    text(x + w/2, y + h/2 - 0.18, label, SANSB, 18, TEAL, align=TA_CENTER)
    text(x + w/2, y + h/2 + 0.12, sub, SANS, 12, MUTED, align=TA_CENTER)

devbox("iPhone", "EasyPilot App (SwiftUI)", 8.0, 2.45, 4.4, 1.25, ACCENT)
devbox("ESP32-C3", "Drohne · WLAN", 8.0, 5.45, 4.4, 1.25, NAVY)
line(8.75, 3.7, 8.75, 5.45, NAVY, 2.25, arrow=True)
line(11.65, 5.45, 11.65, 3.7, NAVY, 2.25, arrow=True)
text(10.2, 4.35, "WLAN-Discovery · 10 Hz", SANS, 12, MUTED, align=TA_CENTER)
text(10.2, 4.65, "Befehle ↑ · Telemetrie ↓", SANS, 12, MUTED, align=TA_CENTER)
c.showPage()

# ===================== Slide 3 — Tech Stack (icon grid) =====================
rect(0, 0, SW_IN, SH_IN, white)
rect(0, 0, SW_IN, 1.6, NAVY)
text(0.85, 0.62, "EasyPilot iOS – Tech Stack", SERIF, 34, white)
tech = [
    ("swift.png",     "Swift",        "Sprache der App"),
    ("swiftui.png",   "SwiftUI",      "Benutzeroberfläche"),
    ("wifi.png",      "WLAN",         "Findet die Drohne automatisch"),
    ("websocket.png", "WebSocket",    "Live-Verbindung zur Drohne"),
    ("cube3d.png",    "3D-Simulator", "Flugsimulator am iPhone"),
    ("chip.png",      "ESP32",        "Mikrocontroller der Drohne"),
]
cols = 3
mx, top0, gx, gy, chh = 0.85, 2.0, 0.45, 0.28, 2.35
cw = (SW_IN - 2*mx - (cols-1)*gx) / cols
for i, (img, name, sub) in enumerate(tech):
    cc, rr = i % cols, i // cols
    x = mx + cc*(cw + gx)
    y = top0 + rr*(chh + gy)
    rect(x, y, cw, chh, CARD, stroke=BORDER, sw=1, rad=0.06)
    icon(img, x + cw/2, y + 0.32, 1.5, 1.0)
    text(x + cw/2, y + 1.5, name, SANSB, 18, TEAL, align=TA_CENTER)
    text(x + cw/2, y + 1.95, sub, SANS, 12.5, MUTED, align=TA_CENTER)
c.showPage()

# ===================== Slide 4 — Live Demo =====================
rect(0, 0, SW_IN, SH_IN, NAVY)
text(0.95, SH_IN/2 - 0.75, "Live Demo", SERIF, 64, white)
rect(1.0, 4.55, 2.2, 0.05, ACCENT)
c.showPage()

c.save()
print("saved", OUT)
