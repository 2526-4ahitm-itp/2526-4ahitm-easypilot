#!/usr/bin/env python3
"""Builds the 4-slide 'EasyPilot iOS' deck — own modern style.

Distinct from the Franklyn template: full-navy title slide, sans-serif bold
headings, navy header bands with a blue square mark, blue square bullet marks,
a vertical divider, slide-number chips. Same navy/white/blue colour family.

Slides:
  1. Title      - full navy, big "EasyPilot iOS"
  2. Was ist..  - navy header band, bullets + vertical divider + diagram
  3. Tech Stack - icon grid, real technology names
  4. Live Demo  - full navy
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

NAVY   = RGBColor(0x22, 0x2B, 0x3C)   # title / bands
TEAL   = RGBColor(0x16, 0x21, 0x33)   # heading ink on white
ACCENT = RGBColor(0x2F, 0x80, 0xED)   # blue
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
INK    = RGBColor(0x2B, 0x33, 0x40)
MUTED  = RGBColor(0x6B, 0x74, 0x82)
LIGHT  = RGBColor(0xC4, 0xCE, 0xDE)   # light text on navy
CARD   = RGBColor(0xF4, 0xF7, 0xFB)
BORDER = RGBColor(0xE2, 0xE7, 0xEE)

HEAD = "Segoe UI Semibold"
SANS = "Segoe UI"

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


def vline(s, x, y, h, col, pt=1.5):
    ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x, y, x, Emu(int(y) + int(h)))
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
    w, h = fit(os.path.join(LOGOS, path), box_w, box_h)
    x = Inches(cx_in - w / 2)
    y = Inches(top_in + (box_h - h) / 2)
    s.shapes.add_picture(os.path.join(LOGOS, path), x, y, width=Inches(w), height=Inches(h))


def header_band(s, title, num):
    rect(s, 0, 0, SW, Inches(1.35), NAVY)
    rect(s, Inches(0.85), Inches(0.5), Inches(0.34), Inches(0.34), ACCENT)
    textbox(s, Inches(1.4), 0, Inches(10), Inches(1.35),
            [[(title, 30, WHITE, True, HEAD)]], anchor=MSO_ANCHOR.MIDDLE)
    textbox(s, Inches(12.0), 0, Inches(0.9), Inches(1.35),
            [[(num, 16, ACCENT, True, HEAD)]], align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)


def page_num(s, num):
    textbox(s, Inches(12.1), Inches(6.85), Inches(0.9), Inches(0.4),
            [[(num, 13, MUTED, True, HEAD)]], align=PP_ALIGN.RIGHT)


# =====================================================================
# Slide 1 — Title (full navy)
# =====================================================================
s = slide(NAVY)
rect(s, 0, 0, Inches(0.16), SH, ACCENT)
textbox(s, Inches(0.95), Inches(1.5), Inches(11), Inches(0.5),
        [[("EASYPILOT  ·  4AHITM DROHNENPROJEKT", 14, ACCENT, True, HEAD)]])
textbox(s, Inches(0.9), Inches(2.25), Inches(11.5), Inches(1.5),
        [[("EasyPilot ", 62, WHITE, True, HEAD), ("iOS", 62, ACCENT, True, HEAD)]])
rect(s, Inches(0.95), Inches(3.62), Inches(1.5), Pt(4), ACCENT)
textbox(s, Inches(0.95), Inches(3.95), Inches(10.8), Inches(1.2),
        [[("SwiftUI-Companion-App für die EasyPilot-Drohne – findet die Drohne", 20, LIGHT, False, SANS)],
         [("selbst im WLAN, zeigt Live-Telemetrie und fliegt einen 3D-Flugsimulator.", 20, LIGHT, False, SANS)]],
        sp_after=3)
textbox(s, Inches(0.95), Inches(6.1), Inches(8), Inches(0.9),
        [[("Simon Eder", 19, WHITE, True, HEAD)],
         [("Creator", 14, LIGHT, False, SANS)]], sp_after=2)

# =====================================================================
# Slide 2 — Was ist EasyPilot iOS
# =====================================================================
s = slide(WHITE)
header_band(s, "Was ist EasyPilot iOS", "02")

bullets = [
    "EasyPilot ist unser 4AHITM-Drohnenprojekt: eine selbstgebaute Drohne mit ESP32-Steuerung.",
    "Die iOS-App ist der mobile Co-Pilot – komplett in SwiftUI, nur mit Apple-Frameworks.",
    "Sie findet die Drohne automatisch im WLAN – ohne Eintippen einer IP-Adresse.",
    "Live-Telemetrie mit 10 Hz, ein 3D-Flugsimulator und das Senden von Flugbefehlen – alles auf dem iPhone.",
]
runs = [[("▪  ", 15, ACCENT, True, SANS), (b, 16.5, INK, False, SANS)] for b in bullets]
textbox(s, Inches(0.85), Inches(1.95), Inches(6.3), Inches(4.8), runs, sp_after=16, line=1.1)

# vertical divider between the two halves
vline(s, Inches(7.55), Inches(2.05), Inches(4.6), ACCENT, pt=1.75)

def devbox(label, sub, x, y, w, h, accent):
    rect(s, x, y, w, h, CARD, shape=MSO_SHAPE.ROUNDED_RECTANGLE, border=accent, bw=1.75, rad=0.10)
    textbox(s, x, y, w, h, [[(label, 18, TEAL, True, HEAD)], [(sub, 12, MUTED, False, SANS)]],
            align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, sp_after=2)

def arrow(x1, y1, x2, y2):
    a = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    a.line.color.rgb = NAVY; a.line.width = Pt(2.25); a.shadow.inherit = False
    ln = a.line._get_or_add_ln()
    ln.append(ln.makeelement(qn('a:tailEnd'), {'type': 'triangle', 'w': 'med', 'len': 'med'}))

devbox("iPhone", "EasyPilot App (SwiftUI)", Inches(8.1), Inches(2.35), Inches(4.3), Inches(1.2), ACCENT)
devbox("ESP32-C3", "Drohne · WLAN", Inches(8.1), Inches(5.3), Inches(4.3), Inches(1.2), NAVY)
arrow(Inches(8.9), Inches(3.55), Inches(8.9), Inches(5.3))
arrow(Inches(11.6), Inches(5.3), Inches(11.6), Inches(3.55))
textbox(s, Inches(8.1), Inches(4.0), Inches(4.3), Inches(1.1),
        [[("Auto-Discovery · 10 Hz", 12.5, MUTED, False, SANS)],
         [("Befehle ↑ · Telemetrie ↓", 12.5, MUTED, False, SANS)]],
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, sp_after=2)

# =====================================================================
# Slide 3 — Tech Stack (icon grid, real names)
# =====================================================================
s = slide(WHITE)
header_band(s, "Tech Stack", "03")

tech = [
    ("swift.png",     "Swift",              "Programmiersprache"),
    ("swiftui.png",   "SwiftUI",            "User Interface"),
    ("cube3d.png",    "SceneKit",           "3D-Flugsimulator"),
    ("websocket.png", "WebSocket",          "Live-Telemetrie · 10 Hz"),
    ("wifi.png",      "Network.framework",  "Auto-Discovery im WLAN"),
    ("chip.png",      "ESP32-C3",           "Mikrocontroller der Drohne"),
]
cols = 3
mx, top0 = 0.85, 1.95
gx, gy = 0.45, 0.28
cw = (13.333 - 2*mx - (cols-1)*gx) / cols
chh = 2.3
for i, (img, name, sub) in enumerate(tech):
    cidx, ridx = i % cols, i // cols
    x = mx + cidx*(cw + gx)
    y = top0 + ridx*(chh + gy)
    rect(s, Inches(x), Inches(y), Inches(cw), Inches(chh), CARD,
         shape=MSO_SHAPE.ROUNDED_RECTANGLE, border=BORDER, bw=1, rad=0.05)
    icon(s, img, x + cw/2, y + 0.3, 1.45, 0.95)
    textbox(s, Inches(x), Inches(y + 1.42), Inches(cw), Inches(0.45),
            [[(name, 17, TEAL, True, HEAD)]], align=PP_ALIGN.CENTER)
    # short blue underline under the name
    rect(s, Inches(x + cw/2 - 0.28), Inches(y + 1.86), Inches(0.56), Pt(2.5), ACCENT)
    textbox(s, Inches(x), Inches(y + 1.95), Inches(cw), Inches(0.4),
            [[(sub, 12, MUTED, False, SANS)]], align=PP_ALIGN.CENTER)

# =====================================================================
# Slide 4 — Live Demo (full navy)
# =====================================================================
s = slide(NAVY)
rect(s, 0, 0, Inches(0.16), SH, ACCENT)
textbox(s, Inches(0.95), Inches(2.7), Inches(8), Inches(0.5),
        [[("04  ·  DEMO", 14, ACCENT, True, HEAD)]])
textbox(s, Inches(0.9), Inches(3.2), Inches(10), Inches(1.4),
        [[("Live Demo", 66, WHITE, True, HEAD)]])
rect(s, Inches(0.95), Inches(4.75), Inches(1.6), Pt(4), ACCENT)

prs.save(OUT)
print("saved", OUT)
