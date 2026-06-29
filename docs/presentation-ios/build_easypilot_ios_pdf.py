#!/usr/bin/env python3
"""Builds the 'EasyPilot iOS' PDFs — same modern style as the PPTX.

Produces two files from the same slide definitions:
  EasyPilot-iOS.pdf           4 slides
  EasyPilot-iOS-Extended.pdf  5 slides (adds a "Das Projekt EasyPilot" slide)
Segoe UI is registered for visual parity with the pptx.
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

HERE    = os.path.dirname(os.path.abspath(__file__))
LOGOS   = os.path.join(HERE, "logos")
OUT     = os.path.join(HERE, "EasyPilot-iOS.pdf")
OUT_EXT = os.path.join(HERE, "EasyPilot-iOS-Extended.pdf")
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

SANS, SANSB = "Helvetica", "Helvetica-Bold"
try:
    pdfmetrics.registerFont(TTFont("Segoe", r"C:\Windows\Fonts\segoeui.ttf"))
    pdfmetrics.registerFont(TTFont("Segoe-Bold", r"C:\Windows\Fonts\segoeuib.ttf"))
    SANS, SANSB = "Segoe", "Segoe-Bold"
except Exception:
    pass

SH_IN, SW_IN = 7.5, 13.333
c = None  # current canvas (set by build())


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
        c.setFillColor(col); d = 7
        p = c.beginPath(); p.moveTo(X2, Y2)
        if abs(X2 - X1) >= abs(Y2 - Y1):
            sx = 1 if X2 > X1 else -1
            p.lineTo(X2 - sx*2*d, Y2 - d); p.lineTo(X2 - sx*2*d, Y2 + d)
        else:
            sy = 1 if Y2 > Y1 else -1
            p.lineTo(X2 - d, Y2 - sy*2*d); p.lineTo(X2 + d, Y2 - sy*2*d)
        p.close(); c.drawPath(p, fill=1, stroke=0)


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
    c.drawImage(path, IN(cx_in - w/2), H - IN(top_in + (box_h - h)/2) - IN(h),
                IN(w), IN(h), mask='auto')


def header_band(title, num):
    rect(0, 0, SW_IN, 1.35, NAVY)
    rect(0.85, 0.5, 0.34, 0.34, ACCENT)
    text(1.4, 0.46, title, SANSB, 30, white)
    text(12.9, 0.52, num, SANSB, 16, ACCENT, align=TA_RIGHT)


def statement_block(statement, paras):
    para(0.95, 1.85, 8.2, 1.4, statement, 27, TEAL, leading=31, font=SANSB)
    rect(0.97, 3.12, 1.6, 0.055, ACCENT)
    for y, barh, body in paras:
        rect(0.95, y + 0.03, 0.06, barh, ACCENT)
        para(1.3, y, 7.4, 1.5, body, 16.5, INK, leading=23)


# --------------------------------------------------------------------- slides
def title_slide():
    rect(0, 0, SW_IN, SH_IN, NAVY)
    rect(0, 0, 0.16, SH_IN, ACCENT)
    text(0.95, 1.5, "EASYPILOT  ·  4AHITM DROHNENPROJEKT", SANSB, 14, ACCENT)
    c.setFont(SANSB, 62); ty = H - IN(2.25) - 62
    c.setFillColor(white); c.drawString(IN(0.9), ty, "EasyPilot ")
    c.setFillColor(ACCENT); c.drawString(IN(0.9) + c.stringWidth("EasyPilot ", SANSB, 62), ty, "iOS")
    rect(0.95, 3.62, 1.5, 0.055, ACCENT)
    para(0.95, 3.95, 11.0, 1.2,
         "SwiftUI-Companion-App für die EasyPilot-Drohne – findet die Drohne "
         "selbst im WLAN, zeigt Live-Telemetrie und einen 3D-Flugsimulator.",
         20, LIGHT, leading=27)
    text(0.95, 6.1, "Simon Eder", SANSB, 19, white)
    text(0.95, 6.5, "Creator", SANS, 14, LIGHT)


def purpose_slide(num):
    rect(0, 0, SW_IN, SH_IN, white)
    header_band("Das Projekt EasyPilot", num)
    statement_block(
        "Eine gewöhnliche Drohne wird zur vernetzten Telemetrie- und Steuerplattform.",
        [
            (3.55, 0.62, "Ein ESP32-C3 an Bord macht die Drohne über WLAN ansprechbar – "
                         "er sendet Telemetrie und nimmt Flugbefehle entgegen."),
            (4.62, 0.62, "Mehrere Clients sind live dabei: eine iOS-App und ein 3D-Web-Viewer "
                         "zeigen Lage und Daten der Drohne in Echtzeit."),
            (5.69, 0.62, "Ein Schulprojekt der 4AHITM (HTL Leonding) – es verbindet "
                         "Embedded-Firmware, Echtzeit-Netzwerk sowie App- und Web-Entwicklung."),
        ],
    )


def wasist_slide(num):
    rect(0, 0, SW_IN, SH_IN, white)
    header_band("Was ist EasyPilot iOS", num)
    statement_block(
        "Das iPhone wird zur Anzeige- und Steuerzentrale für unsere Drohne.",
        [
            (3.55, 0.62, "EasyPilot ist unser Drohnenprojekt der 4AHITM – eine handelsübliche Drohne, "
                         "die wir mit einem ESP32 erweitert haben."),
            (4.62, 0.85, "Die iOS-App ist der mobile Co-Pilot: Sie verbindet sich von selbst über das "
                         "WLAN mit der Drohne, ganz ohne Eingabe einer IP-Adresse."),
            (5.85, 0.95, "Sobald die Verbindung steht, zeigt sie die Telemetrie zehnmal pro Sekunde in "
                         "Echtzeit an und bringt einen eigenen 3D-Flugsimulator direkt aufs Handy. "
                         "Gebaut ist alles in SwiftUI – nur mit Apple-eigenen Frameworks."),
        ],
    )


def arch_slide(num):
    rect(0, 0, SW_IN, SH_IN, white)
    header_band("Architektur & Tech-Stack", num)

    # LEFT — the drone
    rect(0.85, 2.45, 2.95, 3.0, CARD, stroke=BORDER, sw=1, rad=0.05)
    text(2.325, 2.62, "DROHNE", SANSB, 13, MUTED, align=TA_CENTER)
    icon("chip.png", 2.325, 3.05, 1.25, 0.9)
    text(2.325, 4.1, "ESP32-C3", SANSB, 18, TEAL, align=TA_CENTER)
    text(2.325, 4.58, "WebSocket-Server", SANS, 12.5, MUTED, align=TA_CENTER)
    text(2.325, 4.82, "UDP-Beacon (Discovery)", SANS, 12.5, MUTED, align=TA_CENTER)

    # ARROW drone -> app
    line(3.8, 3.62, 5.35, 3.62, NAVY, 2.25, arrow=True)
    text(4.575, 2.98, "WLAN · WebSocket", SANSB, 11.5, MUTED, align=TA_CENTER)
    text(4.575, 3.82, "Telemetrie · 10 Hz", SANS, 11.5, MUTED, align=TA_CENTER)

    # RIGHT — the iPhone app
    APP_X, APP_W = 5.35, 7.05
    rect(APP_X, 1.95, APP_W, 4.95, white, stroke=ACCENT, sw=1.75, rad=0.04)
    text(APP_X + 0.3, 2.12, "iPhone-App", SANSB, 18, TEAL)
    text(APP_X + 0.3, 2.6, "gebaut mit Swift & SwiftUI", SANS, 12.5, MUTED)
    icon("swift.png",   APP_X + APP_W - 1.65, 2.18, 1.25, 0.55)
    icon("swiftui.png", APP_X + APP_W - 0.55, 2.12, 0.62, 0.62)

    comps = [
        ("wifi.png",  "Network.framework", "Verbindung & Auto-Discovery zur Drohne"),
        ("cube3d.png", "SceneKit",         "Rendert den 3D-Flugsimulator"),
        ("gyro.png",  "CoreMotion",        "Liest das Gyroskop des Handys"),
    ]
    cx, cw, chh, cy = APP_X + 0.3, APP_W - 0.6, 1.05, 3.15
    for img, name, sub in comps:
        rect(cx, cy, cw, chh, CARD, stroke=BORDER, sw=1, rad=0.08)
        icon(img, cx + 0.7, cy + 0.12, 0.95, chh - 0.24)
        text(cx + 1.4, cy + 0.2, name, SANSB, 17, TEAL)
        text(cx + 1.4, cy + 0.62, sub, SANS, 12.5, MUTED)
        cy += chh + 0.13


def demo_slide(num):
    rect(0, 0, SW_IN, SH_IN, NAVY)
    rect(0, 0, 0.16, SH_IN, ACCENT)
    text(0.95, 2.7, f"{num}  ·  DEMO", SANSB, 14, ACCENT)
    text(0.9, 3.2, "Live Demo", SANSB, 66, white)
    rect(0.95, 4.75, 1.6, 0.055, ACCENT)


def build(out, extended):
    global c
    c = canvas.Canvas(out, pagesize=(W, H))
    title_slide(); c.showPage()
    if extended:
        purpose_slide("02"); c.showPage()
        wasist_slide("03"); c.showPage()
        arch_slide("04"); c.showPage()
        demo_slide("05"); c.showPage()
    else:
        wasist_slide("02"); c.showPage()
        arch_slide("03"); c.showPage()
        demo_slide("04"); c.showPage()
    c.save()
    print("saved", out)


build(OUT, False)
build(OUT_EXT, True)
