"""Präsentationsmodus am Mac: das Studio ohne Fensterrahmen, ohne Menüleiste und ohne Dock.

Liftoff lässt sich von außen nicht randlos machen. Die Studio-Fenster liegen deshalb randlos
über allem (Fensterebene über Dock und Menüleiste) und decken auch die Titelleiste von Liftoff ab:

  +------------------+------------------+
  | Leiste (schwarz) |                  |   y 0 .. Unterkante Liftoff-Titelleiste
  +------------------+  Autopilot       |
  | Liftoff-Bild     |  (?view=right)   |
  +------------------+------------------+
  | Bedienung (?view=panel), bis zum unteren Rand, über dem Dock |
  +-------------------------------------+

Systemeinstellungen werden nicht geändert. Beenden: Esc in einem Studio-Fenster, oder
mac/Stop-EasyPilot.command.

  .venv/bin/python mac/kiosk.py [http://localhost:8765/]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import AppKit  # noqa: E402
import Foundation  # noqa: E402
import objc  # noqa: E402

from autopilot.window_mac import TITLE_BAR  # noqa: E402

_wk = {}
objc.loadBundle("WebKit", _wk, bundle_path="/System/Library/Frameworks/WebKit.framework")
WKWebView = objc.lookUpClass("WKWebView")
WKWebViewConfiguration = objc.lookUpClass("WKWebViewConfiguration")

LEVEL = AppKit.NSStatusWindowLevel          # 25: über Dock (20) und Menüleiste (24)
MENU_BAR = 25                               # Liftoff liegt bei y = 25 (studio.arrange_liftoff_mac)


class KioskWindow(AppKit.NSWindow):
    """Randlose Fenster bekommen sonst keine Tastatur (Name des Piloten eintippen)."""

    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return True

    def keyDown_(self, event):
        if event.keyCode() == 53:            # Esc
            AppKit.NSApp().terminate_(None)
        else:
            objc.super(KioskWindow, self).keyDown_(event)


def make_window(x, y, w, h, sh):
    """Rechteck in Bildschirmpunkten von oben links (wie Quartz), Cocoa zählt von unten."""
    rect = Foundation.NSMakeRect(x, sh - y - h, w, h)
    win = KioskWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        rect, AppKit.NSWindowStyleMaskBorderless, AppKit.NSBackingStoreBuffered, False)
    win.setLevel_(LEVEL)
    win.setHidesOnDeactivate_(False)
    win.setReleasedWhenClosed_(False)
    win.setBackgroundColor_(AppKit.NSColor.blackColor())
    win.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                               | AppKit.NSWindowCollectionBehaviorStationary)
    return win


def web(win, url):
    view = WKWebView.alloc().initWithFrame_configuration_(win.contentView().bounds(),
                                                          WKWebViewConfiguration.alloc().init())
    view.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
    view.loadRequest_(Foundation.NSURLRequest.requestWithURL_(Foundation.NSURL.URLWithString_(url)))
    win.contentView().addSubview_(view)
    return view


def main(url):
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)   # kein Dock-Symbol
    frame = AppKit.NSScreen.mainScreen().frame()
    sw, sh = int(frame.size.width), int(frame.size.height)
    half = sw // 2
    top = MENU_BAR + TITLE_BAR                     # Oberkante des Liftoff-Bildes
    split = top + half * 9 // 16                   # Unterkante des Liftoff-Bildes
    sep = "&" if "?" in url else "?"

    bar = make_window(0, 0, half, top, sh)
    label = AppKit.NSTextField.labelWithString_("EasyPilot")
    label.setTextColor_(AppKit.NSColor.whiteColor())
    label.setFont_(AppKit.NSFont.boldSystemFontOfSize_(18))
    label.sizeToFit()
    label.setFrameOrigin_(Foundation.NSMakePoint(14, (top - 22) / 2))
    bar.contentView().addSubview_(label)

    right = make_window(half, 0, sw - half, split, sh)
    web(right, f"{url}{sep}view=right")
    panel = make_window(0, split, sw, sh - split, sh)
    web(panel, f"{url}{sep}view=panel")

    wins = (bar, right, panel)                     # Referenzen halten
    for w in wins:
        w.orderFrontRegardless()
    panel.makeKeyWindow()
    print(f"Präsentationsmodus: {sw}x{sh}, Liftoff-Bild 0,{top} - {half},{split}", flush=True)
    app.run()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/")
