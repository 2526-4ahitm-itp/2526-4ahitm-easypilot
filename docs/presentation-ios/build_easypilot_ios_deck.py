#!/usr/bin/env python3
"""Builds the 4-slide 'EasyPilot iOS' deck in the clean Franklyn style.

Slides:
  1. Title      - big "EasyPilot iOS" + one-line description + creator
  2. Was ist..  - left navy panel with bullets, right device diagram
  3. Tech Stack - navy header bar + tech tiles (app side / drone side)
  4. Live Demo  - full navy slide, big serif title
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn

import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "EasyPilot-iOS.pptx")

# ---- Franklyn-inspired palette ----
NAVY   = RGBColor(0x2C, 0x36, 0x49)   # dark slate panels / triangle
TEAL   = RGBColor(0x10, 0x3A, 0x50)   # dark teal serif title on white
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
INK    = RGBColor(0x33, 0x3B, 0x47)   # body text on white
MUTED  = RGBColor(0x6B, 0x74, 0x82)   # secondary text
TAN    = RGBColor(0xC9, 0xB7, 0x9C)   # warm accent line
LIGHT  = RGBColor(0xD7, 0xDC, 0xE3)   # light text on navy
CARD   = RGBColor(0xF3, 0xF5, 0xF8)   # light tile fill on white

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


def freeform(s, pts, fill):
    """Filled polygon from a list of (x_emu, y_emu) points."""
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    left, top = min(xs), min(ys)
    fb = s.shapes.build_freeform(Emu(pts[0][0]), Emu(pts[0][1]), scale=1)
    fb.add_line_segments([(Emu(p[0]), Emu(p[1])) for p in pts[1:]], close=True)
    shp = fb.convert_to_shape()
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    shp.line.fill.background(); shp.shadow.inherit = False
    return shp


def tile(s, x, y, w, h, head, sub, accent=NAVY):
    c = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    c.fill.solid(); c.fill.fore_color.rgb = CARD
    c.line.color.rgb = RGBColor(0xDD, 0xE1, 0xE7); c.line.width = Pt(1)
    c.shadow.inherit = False
    try: c.adjustments[0] = 0.10
    except Exception: pass
    # left accent stripe
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, Inches(0.08), h)
    bar.fill.solid(); bar.fill.fore_color.rgb = accent
    bar.line.fill.background(); bar.shadow.inherit = False
    textbox(s, x + Inches(0.28), y, w - Inches(0.42), h,
            [[(head, 16, TEAL, True, SANS)], [(sub, 11.5, MUTED, False, SANS)]],
            anchor=MSO_ANCHOR.MIDDLE, sp_after=2)


# =====================================================================
# Slide 1 — Title
# =====================================================================
s = slide(WHITE)
# navy diagonal wedge across the bottom
freeform(s, [(0, int(SH*0.78)), (int(SW), int(SH*0.40)),
             (int(SW), int(SH)), (0, int(SH))], NAVY)

textbox(s, Inches(0.9), Inches(0.85), Inches(11), Inches(1.6),
        [[("EasyPilot ", 60, TEAL, False, SERIF), ("iOS", 60, TAN, False, SERIF)]])
textbox(s, Inches(0.95), Inches(2.35), Inches(10.5), Inches(0.8),
        [[("SwiftUI-Companion-App für die EasyPilot-Drohne – findet die Drohne",
           21, MUTED, False, SANS)],
         [("selbst im WLAN, zeigt Live-Telemetrie und fliegt einen 3D-Simulator.",
           21, MUTED, False, SANS)]], sp_after=3)
textbox(s, Inches(0.95), Inches(3.7), Inches(8), Inches(0.9),
        [[("Simon Eder", 18, INK, False, SANS)],
         [("Creator", 14, MUTED, False, SANS)]], sp_after=2)

# =====================================================================
# Slide 2 — Was ist EasyPilot iOS
# =====================================================================
s = slide(WHITE)
PANEL_W = Inches(6.4)
panel = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, PANEL_W, SH)
panel.fill.solid(); panel.fill.fore_color.rgb = NAVY
panel.line.fill.background(); panel.shadow.inherit = False
# tan diagonal accent line across lower-left
ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, 0, int(SH*0.86),
                            int(PANEL_W), int(SH*0.62))
ln.line.color.rgb = TAN; ln.line.width = Pt(2.5); ln.shadow.inherit = False

textbox(s, Inches(0.6), Inches(0.75), Inches(5.4), Inches(1.0),
        [[("Was ist EasyPilot iOS", 34, WHITE, False, SERIF)]])
textbox(s, Inches(0.62), Inches(1.95), Inches(5.4), Inches(4.6),
        [[("●  ", 14, TAN, True, SANS), ("EasyPilot ist unser 4AHITM-Drohnenprojekt: eine "
          "selbstgebaute Drohne mit ESP32-Steuerung.", 16, LIGHT, False, SANS)],
         [("●  ", 14, TAN, True, SANS), ("Die iOS-App ist der mobile Co-Pilot – komplett "
          "in SwiftUI mit reinen Apple-Frameworks, ohne Fremd-Bibliotheken.", 16, LIGHT, False, SANS)],
         [("●  ", 14, TAN, True, SANS), ("Sie findet die Drohne automatisch im WLAN (kein "
          "Eintippen einer IP) und verbindet sich per WebSocket.", 16, LIGHT, False, SANS)],
         [("●  ", 14, TAN, True, SANS), ("Live-Telemetrie mit 10 Hz, ein 3D-Flugsimulator "
          "und das Senden von Flugbefehlen – alles auf dem iPhone.", 16, LIGHT, False, SANS)]],
        sp_after=14, line=1.05)

# right side: simple device-link diagram
def devbox(label, sub, x, y, w, h, accent):
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    b.fill.solid(); b.fill.fore_color.rgb = WHITE
    b.line.color.rgb = accent; b.line.width = Pt(2)
    b.shadow.inherit = False
    try: b.adjustments[0] = 0.12
    except Exception: pass
    textbox(s, x, y, w, h, [[(label, 18, TEAL, True, SANS)], [(sub, 12, MUTED, False, SANS)]],
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, sp_after=2)

def arrow_tail(conn):
    ln = conn.line._get_or_add_ln()
    tail = ln.makeelement(qn('a:tailEnd'), {'type': 'triangle', 'w': 'med', 'len': 'med'})
    ln.append(tail)

devbox("iPhone", "EasyPilot App (SwiftUI)", Inches(7.5), Inches(1.7), Inches(4.6), Inches(1.25), TEAL)
devbox("ESP32-C3", "Drohne · WLAN", Inches(7.5), Inches(4.9), Inches(4.6), Inches(1.25), TAN)
# arrows between
a1 = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(9.4), Inches(2.95), Inches(9.4), Inches(4.9))
a1.line.color.rgb = NAVY; a1.line.width = Pt(2.25); a1.shadow.inherit = False
arrow_tail(a1)
a2 = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(10.2), Inches(4.9), Inches(10.2), Inches(2.95))
a2.line.color.rgb = NAVY; a2.line.width = Pt(2.25); a2.shadow.inherit = False
arrow_tail(a2)
textbox(s, Inches(7.5), Inches(3.35), Inches(4.6), Inches(1.4),
        [[("UDP-Discovery · Port 4242", 12.5, MUTED, False, SANS)],
         [("WebSocket · Port 81 · 10 Hz", 12.5, MUTED, False, SANS)]],
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, sp_after=2)

# =====================================================================
# Slide 3 — Tech Stack
# =====================================================================
s = slide(WHITE)
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, Inches(1.75))
bar.fill.solid(); bar.fill.fore_color.rgb = NAVY
bar.line.fill.background(); bar.shadow.inherit = False
textbox(s, Inches(0.85), 0, Inches(11), Inches(1.75),
        [[("EasyPilot iOS – Tech Stack", 34, WHITE, False, SERIF)]],
        anchor=MSO_ANCHOR.MIDDLE)

# section labels
textbox(s, Inches(0.85), Inches(2.15), Inches(5.5), Inches(0.4),
        [[("APP · iPHONE", 13, TEAL, True, SANS)]])
textbox(s, Inches(7.4), Inches(2.15), Inches(5.5), Inches(0.4),
        [[("DROHNE · ESP32-C3", 13, TAN, True, SANS)]])

# left column (app)
ax, ay, aw, ah, gap = Inches(0.85), Inches(2.65), Inches(5.4), Inches(0.80), Inches(0.13)
app = [
    ("Swift", "Programmiersprache der App"),
    ("SwiftUI", "Deklarative UI, Live-Bindings"),
    ("Network.framework", "UDP-Discovery + WebSocket"),
    ("SceneKit", "3D-Flugsimulator (.usdz-Modell)"),
    ("CoreMotion", "Gyro/Beschleunigung @ 10 Hz"),
]
y = ay
for h, sub in app:
    tile(s, ax, y, aw, ah, h, sub, TEAL)
    y = Emu(int(y) + int(ah) + int(gap))

# right column (drone)
bx = Inches(7.4)
drone = [
    ("ESP32-C3", "WLAN-Mikrocontroller der Drohne"),
    ("WebSocket-Server", "Befehle + Telemetrie, Port 81"),
    ("UDP-Beacon", "\"EASYPILOT:<IP>\" · Port 4242"),
    ("Arduino / C++", "Firmware & Balancing-Algorithmus"),
]
y = ay
for h, sub in drone:
    tile(s, bx, y, aw, ah, h, sub, TAN)
    y = Emu(int(y) + int(ah) + int(gap))

# =====================================================================
# Slide 4 — Live Demo
# =====================================================================
s = slide(NAVY)
textbox(s, Inches(0.95), 0, Inches(8), SH,
        [[("Live Demo", 64, WHITE, False, SERIF)]],
        anchor=MSO_ANCHOR.MIDDLE)
# small tan accent under the title
acc = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(4.55), Inches(2.2), Pt(3))
acc.fill.solid(); acc.fill.fore_color.rgb = TAN
acc.line.fill.background(); acc.shadow.inherit = False

prs.save(OUT)
print("saved", OUT)
