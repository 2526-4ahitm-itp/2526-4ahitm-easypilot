#!/usr/bin/env python3
"""Builds the 4-slide 'EasyPilot iOS' deck (clean light style, blue accent).

Slides:
  1. Title      - big "EasyPilot iOS" + one-line description + creator
  2. Was ist..  - heading, a full-width accent line through the section,
                  bullets + iPhone<->ESP32 diagram
  3. Tech Stack - icon grid of understandable technologies (with icons)
  4. Live Demo  - full navy slide, big serif title
"""
import os
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn

HERE  = os.path.dirname(os.path.abspath(__file__))
LOGOS = os.path.join(HERE, "logos")
OUT   = os.path.join(HERE, "EasyPilot-iOS.pptx")

# ---- palette (blue accent instead of tan) ----
NAVY   = RGBColor(0x2C, 0x36, 0x49)
TEAL   = RGBColor(0x10, 0x3A, 0x50)
ACCENT = RGBColor(0x2F, 0x80, 0xED)   # iOS-ish blue
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
INK    = RGBColor(0x33, 0x3B, 0x47)
MUTED  = RGBColor(0x6B, 0x74, 0x82)
LIGHT  = RGBColor(0xD7, 0xDC, 0xE3)
CARD   = RGBColor(0xF6, 0xF8, 0xFB)
BORDER = RGBColor(0xDD, 0xE1, 0xE7)

SERIF = "Georgia"
SANS  = "Calibri"

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
blank = prs.slide_layouts[6]


def slide(bg=WHITE):
    s = prs.slides.add_slide(blank)
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    r.fill.solid(); r.fill.fore_color.rgb = bg
    r.line.fill.background(); r.shadow.inherit = False
    s.shapes._spTree.remove(r._element); s.shapes._spTree.insert(2, r._element)
    return s


def textbox(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
            sp_after=8, line=1.0):
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    first = True
    for para in runs:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align; p.space_after = Pt(sp_after); p.space_before = Pt(0)
        if line:
            p.line_spacing = line
        for txt, size, color, bold, fname in para:
            run = p.add_run(); run.text = txt
            run.font.size = Pt(size); run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = fname
    return tb


def rect(s, x, y, w, h, fill, shape=MSO_SHAPE.RECTANGLE, border=None, bw=1.0, rad=None):
    c = s.shapes.add_shape(shape, x, y, w, h)
    if fill is None:
        c.fill.background()
    else:
        c.fill.solid(); c.fill.fore_color.rgb = fill
    if border is None:
        c.line.fill.background()
    else:
        c.line.color.rgb = border; c.line.width = Pt(bw)
    c.shadow.inherit = False
    if rad is not None:
        try: c.adjustments[0] = rad
        except Exception: pass
    return c


def freeform(s, pts, fill):
    fb = s.shapes.build_freeform(Emu(pts[0][0]), Emu(pts[0][1]), scale=1)
    fb.add_line_segments([(Emu(p[0]), Emu(p[1])) for p in pts[1:]], close=True)
    shp = fb.convert_to_shape()
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    shp.line.fill.background(); shp.shadow.inherit = False
    return shp


def hline(s, x, y, w, col, pt=2.0):
    ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x, y, Emu(int(x) + int(w)), y)
    ln.line.color.rgb = col; ln.line.width = Pt(pt); ln.shadow.inherit = False
    return ln


def fit(path, maxw_in, maxh_in):
    iw, ih = Image.open(path).size
    ar = iw / ih
    w, h = maxw_in, maxw_in / ar
    if h > maxh_in:
        h, w = maxh_in, maxh_in * ar
    return w, h


def icon(s, path, cx_in, top_in, box_w, box_h):
    """Place an icon, fit into box, horizontally centered around cx_in."""
    w, h = fit(os.path.join(LOGOS, path), box_w, box_h)
    x = Inches(cx_in - w / 2)
    y = Inches(top_in + (box_h - h) / 2)
    s.shapes.add_picture(os.path.join(LOGOS, path), x, y, width=Inches(w), height=Inches(h))


# =====================================================================
# Slide 1 — Title
# =====================================================================
s = slide(WHITE)
freeform(s, [(0, int(SH*0.80)), (int(SW), int(SH*0.42)),
             (int(SW), int(SH)), (0, int(SH))], NAVY)
textbox(s, Inches(0.9), Inches(0.85), Inches(11), Inches(1.6),
        [[("EasyPilot ", 60, TEAL, False, SERIF), ("iOS", 60, ACCENT, False, SERIF)]])
rect(s, Inches(0.95), Inches(2.12), Inches(2.3), Pt(3.5), ACCENT)
textbox(s, Inches(0.95), Inches(2.45), Inches(10.6), Inches(0.9),
        [[("SwiftUI-Companion-App für die EasyPilot-Drohne – findet die Drohne",
           21, MUTED, False, SANS)],
         [("selbst im WLAN, zeigt Live-Telemetrie und fliegt einen 3D-Simulator.",
           21, MUTED, False, SANS)]], sp_after=3)
textbox(s, Inches(0.95), Inches(3.85), Inches(8), Inches(0.9),
        [[("Simon Eder", 18, INK, False, SANS)],
         [("Creator", 14, MUTED, False, SANS)]], sp_after=2)

# =====================================================================
# Slide 2 — Was ist EasyPilot iOS
# =====================================================================
s = slide(WHITE)
textbox(s, Inches(0.85), Inches(0.7), Inches(11.6), Inches(1.0),
        [[("Was ist EasyPilot iOS", 36, TEAL, False, SERIF)]])
# the line that runs through the section
hline(s, Inches(0.85), Inches(1.75), Inches(11.63), ACCENT, pt=2.25)

bullets = [
    "EasyPilot ist unser 4AHITM-Drohnenprojekt: eine selbstgebaute Drohne mit ESP32-Steuerung.",
    "Die iOS-App ist der mobile Co-Pilot – komplett in SwiftUI, nur mit Apple-Frameworks.",
    "Sie findet die Drohne automatisch im WLAN – ohne Eintippen einer IP-Adresse.",
    "Live-Telemetrie mit 10 Hz, ein 3D-Flugsimulator und das Senden von Flugbefehlen – alles auf dem iPhone.",
]
runs = []
for b in bullets:
    runs.append([("●  ", 14, ACCENT, True, SANS), (b, 16.5, INK, False, SANS)])
textbox(s, Inches(0.85), Inches(2.25), Inches(6.4), Inches(4.6), runs, sp_after=16, line=1.08)

# right device diagram
def devbox(label, sub, x, y, w, h, accent):
    rect(s, x, y, w, h, WHITE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, border=accent, bw=2, rad=0.12)
    textbox(s, x, y, w, h, [[(label, 18, TEAL, True, SANS)], [(sub, 12, MUTED, False, SANS)]],
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, sp_after=2)

def arrow(x1, y1, x2, y2):
    a = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    a.line.color.rgb = NAVY; a.line.width = Pt(2.25); a.shadow.inherit = False
    ln = a.line._get_or_add_ln()
    ln.append(ln.makeelement(qn('a:tailEnd'), {'type': 'triangle', 'w': 'med', 'len': 'med'}))

devbox("iPhone", "EasyPilot App (SwiftUI)", Inches(8.0), Inches(2.45), Inches(4.4), Inches(1.25), ACCENT)
devbox("ESP32-C3", "Drohne · WLAN", Inches(8.0), Inches(5.45), Inches(4.4), Inches(1.25), NAVY)
arrow(Inches(8.75), Inches(3.7), Inches(8.75), Inches(5.45))
arrow(Inches(11.65), Inches(5.45), Inches(11.65), Inches(3.7))
textbox(s, Inches(8.0), Inches(4.1), Inches(4.4), Inches(1.2),
        [[("WLAN-Discovery · 10 Hz", 12.5, MUTED, False, SANS)],
         [("Befehle ↑ · Telemetrie ↓", 12.5, MUTED, False, SANS)]],
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, sp_after=2)

# =====================================================================
# Slide 3 — Tech Stack (icon grid)
# =====================================================================
s = slide(WHITE)
rect(s, 0, 0, SW, Inches(1.6), NAVY)
textbox(s, Inches(0.85), 0, Inches(11), Inches(1.6),
        [[("EasyPilot iOS – Tech Stack", 34, WHITE, False, SERIF)]],
        anchor=MSO_ANCHOR.MIDDLE)

tech = [
    ("swift.png",     "Swift",        "Sprache der App"),
    ("swiftui.png",   "SwiftUI",      "Benutzeroberfläche"),
    ("wifi.png",      "WLAN",         "Findet die Drohne automatisch"),
    ("websocket.png", "WebSocket",    "Live-Verbindung zur Drohne"),
    ("cube3d.png",    "3D-Simulator", "Flugsimulator am iPhone"),
    ("chip.png",      "ESP32",        "Mikrocontroller der Drohne"),
]
cols, rows = 3, 2
mx, top0 = 0.85, 2.0
gx, gy = 0.45, 0.28
cw = (13.333 - 2*mx - (cols-1)*gx) / cols
chh = 2.35
for i, (img, name, sub) in enumerate(tech):
    c, r = i % cols, i // cols
    x = mx + c*(cw + gx)
    y = top0 + r*(chh + gy)
    rect(s, Inches(x), Inches(y), Inches(cw), Inches(chh), CARD,
         shape=MSO_SHAPE.ROUNDED_RECTANGLE, border=BORDER, bw=1, rad=0.06)
    icon(s, img, x + cw/2, y + 0.32, 1.5, 1.0)
    textbox(s, Inches(x), Inches(y + 1.5), Inches(cw), Inches(0.5),
            [[(name, 18, TEAL, True, SANS)]], align=PP_ALIGN.CENTER)
    textbox(s, Inches(x), Inches(y + 1.92), Inches(cw), Inches(0.4),
            [[(sub, 12.5, MUTED, False, SANS)]], align=PP_ALIGN.CENTER)

# =====================================================================
# Slide 4 — Live Demo
# =====================================================================
s = slide(NAVY)
textbox(s, Inches(0.95), 0, Inches(9), SH,
        [[("Live Demo", 64, WHITE, False, SERIF)]], anchor=MSO_ANCHOR.MIDDLE)
rect(s, Inches(1.0), Inches(4.55), Inches(2.2), Pt(3.5), ACCENT)

prs.save(OUT)
print("saved", OUT)
