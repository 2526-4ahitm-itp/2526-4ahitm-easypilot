#!/usr/bin/env python3
"""Builds EasyPilot-iOS.pdf — same Franklyn-style layout as the PPTX.

Slide canvas: 13.333 x 7.5 in = 960 x 540 pt. Coordinates below are given as
top-left inches (matching the pptx) and converted to reportlab's bottom-left
point system by topxy()/inch.
"""
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.enums import TA_LEFT, TA_CENTER

import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "EasyPilot-iOS.pdf")
W, H = 960.0, 540.0
def IN(v): return v * 72.0

NAVY  = HexColor("#2C3649")
TEAL  = HexColor("#103A50")
TAN   = HexColor("#C9B79C")
INK   = HexColor("#333B47")
MUTED = HexColor("#6B7482")
LIGHT = HexColor("#D7DCE3")
CARD  = HexColor("#F3F5F8")
BORDER = HexColor("#DDE1E7")

SERIF, SANS, SANSB = "Times-Roman", "Helvetica", "Helvetica-Bold"
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


def line(x1_in, y1_in, x2_in, y2_in, col, lw, arrow=False):
    c.setStrokeColor(col); c.setLineWidth(lw)
    x1, y1, x2, y2 = IN(x1_in), H - IN(y1_in), IN(x2_in), H - IN(y2_in)
    c.line(x1, y1, x2, y2)
    if arrow:  # simple triangular head at (x2,y2), assumes vertical-ish line
        c.setFillColor(col)
        d = 6
        up = 1 if y2 > y1 else -1
        c.path = None
        p = c.beginPath()
        p.moveTo(x2, y2)
        p.lineTo(x2 - d, y2 - up * 2 * d)
        p.lineTo(x2 + d, y2 - up * 2 * d)
        p.close()
        c.drawPath(p, fill=1, stroke=0)


def text(x_in, y_in, s, font, size, col, align=TA_LEFT):
    c.setFillColor(col); c.setFont(font, size)
    x, y = IN(x_in), H - IN(y_in) - size
    if align == TA_CENTER:
        c.drawCentredString(x, y, s)
    else:
        c.drawString(x, y, s)


def para(x_in, y_in, w_in, h_in, html, size, col, leading=None, font=SANS,
         align=TA_LEFT, space=6):
    st = ParagraphStyle("p", fontName=font, fontSize=size, textColor=col,
                        leading=leading or size * 1.2, alignment=align,
                        spaceAfter=space)
    fr = Frame(IN(x_in), H - IN(y_in) - IN(h_in), IN(w_in), IN(h_in),
               leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    fr.addFromList([Paragraph(html, st)], c)


def poly(pts_in, fill):
    c.setFillColor(fill)
    p = c.beginPath()
    p.moveTo(IN(pts_in[0][0]), H - IN(pts_in[0][1]))
    for x, y in pts_in[1:]:
        p.lineTo(IN(x), H - IN(y))
    p.close()
    c.drawPath(p, fill=1, stroke=0)


SH_IN, SW_IN = 7.5, 13.333

# ===================== Slide 1 — Title =====================
rect(0, 0, SW_IN, SH_IN, white)
poly([(0, SH_IN*0.78), (SW_IN, SH_IN*0.40), (SW_IN, SH_IN), (0, SH_IN)], NAVY)
# title: "EasyPilot " teal + "iOS" tan, one baseline
c.setFont(SERIF, 60)
ty = H - IN(0.85) - 60
c.setFillColor(TEAL); c.drawString(IN(0.9), ty, "EasyPilot ")
wpre = c.stringWidth("EasyPilot ", SERIF, 60)
c.setFillColor(TAN); c.drawString(IN(0.9) + wpre, ty, "iOS")
para(0.95, 2.35, 11.2, 1.0,
     "SwiftUI-Companion-App für die EasyPilot-Drohne – findet die Drohne "
     "selbst im WLAN, zeigt Live-Telemetrie und fliegt einen 3D-Simulator.",
     21, MUTED, leading=28)
text(0.95, 3.75, "Simon Eder", SANS, 18, INK)
text(0.95, 4.18, "Creator", SANS, 14, MUTED)
c.showPage()

# ===================== Slide 2 — Was ist EasyPilot iOS =====================
rect(0, 0, SW_IN, SH_IN, white)
rect(0, 0, 6.4, SH_IN, NAVY)
line(0, SH_IN*0.86, 6.4, SH_IN*0.62, TAN, 2.5)
para(0.6, 0.75, 5.6, 1.0, "Was ist EasyPilot iOS", 34, white, font=SERIF, leading=38)
bullets = [
    "EasyPilot ist unser 4AHITM-Drohnenprojekt: eine selbstgebaute Drohne mit ESP32-Steuerung.",
    "Die iOS-App ist der mobile Co-Pilot – komplett in SwiftUI mit reinen Apple-Frameworks, ohne Fremd-Bibliotheken.",
    "Sie findet die Drohne automatisch im WLAN (kein Eintippen einer IP) und verbindet sich per WebSocket.",
    "Live-Telemetrie mit 10 Hz, ein 3D-Flugsimulator und das Senden von Flugbefehlen – alles auf dem iPhone.",
]
html = "".join(f'<font color="#C9B79C">●</font>&nbsp;&nbsp;{b}<br/><br/>' for b in bullets)
para(0.62, 1.95, 5.5, 4.8, html, 16, LIGHT, leading=21)

# right device diagram
def devbox(label, sub, x, y, w, h, accent):
    rect(x, y, w, h, white, stroke=accent, sw=2, rad=0.12)
    text(x + w/2, y + h/2 - 0.18, label, SANSB, 18, TEAL, align=TA_CENTER)
    text(x + w/2, y + h/2 + 0.12, sub, SANS, 12, MUTED, align=TA_CENTER)

devbox("iPhone", "EasyPilot App (SwiftUI)", 7.5, 1.7, 4.6, 1.25, TEAL)
devbox("ESP32-C3", "Drohne · WLAN", 7.5, 4.9, 4.6, 1.25, TAN)
line(9.4, 2.95, 9.4, 4.9, NAVY, 2.25, arrow=True)
line(10.2, 4.9, 10.2, 2.95, NAVY, 2.25, arrow=True)
text(9.8, 3.55, "UDP-Discovery · Port 4242", SANS, 12, MUTED, align=TA_CENTER)
text(9.8, 3.85, "WebSocket · Port 81 · 10 Hz", SANS, 12, MUTED, align=TA_CENTER)
c.showPage()

# ===================== Slide 3 — Tech Stack =====================
rect(0, 0, SW_IN, SH_IN, white)
rect(0, 0, SW_IN, 1.75, NAVY)
text(0.85, 0.62, "EasyPilot iOS – Tech Stack", SERIF, 34, white)
text(0.85, 2.15, "APP · iPHONE", SANSB, 13, TEAL)
text(7.4, 2.15, "DROHNE · ESP32-C3", SANSB, 13, TAN)

def tile(x, y, w, h, head, sub, accent):
    rect(x, y, w, h, CARD, stroke=BORDER, sw=1, rad=0.10)
    rect(x, y, 0.08, h, accent)
    text(x + 0.28, y + 0.20, head, SANSB, 15, TEAL)
    text(x + 0.28, y + 0.52, sub, SANS, 11.5, MUTED)

aw, ah, gap = 5.4, 0.80, 0.13
app = [
    ("Swift", "Programmiersprache der App"),
    ("SwiftUI", "Deklarative UI, Live-Bindings"),
    ("Network.framework", "UDP-Discovery + WebSocket"),
    ("SceneKit", "3D-Flugsimulator (.usdz-Modell)"),
    ("CoreMotion", "Gyro/Beschleunigung @ 10 Hz"),
]
drone = [
    ("ESP32-C3", "WLAN-Mikrocontroller der Drohne"),
    ("WebSocket-Server", "Befehle + Telemetrie, Port 81"),
    ("UDP-Beacon", "\"EASYPILOT:<IP>\" · Port 4242"),
    ("Arduino / C++", "Firmware & Balancing-Algorithmus"),
]
y = 2.65
for head, sub in app:
    tile(0.85, y, aw, ah, head, sub, TEAL); y += ah + gap
y = 2.65
for head, sub in drone:
    tile(7.4, y, aw, ah, head, sub, TAN); y += ah + gap
c.showPage()

# ===================== Slide 4 — Live Demo =====================
rect(0, 0, SW_IN, SH_IN, NAVY)
text(0.95, SH_IN/2 - 0.75, "Live Demo", SERIF, 64, white)
rect(1.0, 4.55, 2.2, 0.045, TAN)
c.showPage()

c.save()
print("saved", OUT)
