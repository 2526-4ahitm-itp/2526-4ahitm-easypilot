"""Was die Drohne im Freiflug-Sim *sieht*: Kamerabild und Tiefenbild aus dem Renderer.

ColorGateDetector findet die orange-weißen Tore nur im Bild (Farbe + Form, keine Torliste):
orange Pixel -> Streifen-Lücken schließen -> Rahmen mit Loch -> die 4 Ecken der Öffnung.
Das gibt dieselben Detection-Objekte wie das YOLO-Modell (detector.py), also passen GateTracker
und VisionPilot aus visionfly.py unverändert. Das Liftoff-Modell gates.pt kennt diese Tore nicht
(getestet 20.11.: 0 Treffer), darum der eigene Detektor.

DepthGuard schaut ins Tiefenbild derselben Kamera: liegt in Flugrichtung etwas näher als ein paar
Meter in einem schmalen Schlauch um die Flugbahn, lenkt er nach oben / zur freien Seite. Hindernisse
kennt der Kamera-Autopilot also nur, solange er sie sieht.
"""
import math

import cv2
import moderngl
import numpy as np

from ..detector import Detection
from ..geometry import qrot


class CameraView:
    """Offscreen-FPV-Kamera mit denselben Daten wie load_camera(640) (für PnP)."""

    def __init__(self, ctx, world, cam):
        from .gfx import Renderer
        self.ctx, self.cam = ctx, cam
        self.size = (cam.width, cam.height)
        prev = ctx.fbo
        self.fbo = ctx.framebuffer(color_attachments=[ctx.texture(self.size, 3)],
                                   depth_attachment=ctx.depth_texture(self.size))
        self.r = Renderer(ctx, world, self.size, cam.hfov_deg, cam.tilt_deg, target=self.fbo)
        self.near, self.far = 0.05, 1500.0
        self._restore(prev)

    def _restore(self, prev):
        """Vorher gebundenen Puffer (im Spiel: den Bildschirm) wieder binden. Bleibt der Kamera-FBO
        gebunden, stürzt das Vollbild am Mac beim nächsten flip() im Treiber ab
        (gldPresentFramebufferData, 20.11.: Menü + Kamera-Autopilot, 1920x1200)."""
        if prev is not None and prev is not self.fbo:
            prev.use()

    def grab(self, pos, quat, craters=None):
        """(BGR-Bild, Tiefe in Metern) aus Sicht der Drohne. Tore ohne Markierung."""
        if craters is not None and craters != self.r.craters:
            self.r.set_craters(craters)
        prev = self.ctx.fbo
        self.fbo.use()
        self.ctx.viewport = (0, 0, *self.size)
        self.r.draw(pos, quat, 0, False, 0.0)
        rgb = np.frombuffer(self.fbo.read(components=3), np.uint8).reshape(self.size[1], self.size[0], 3)[::-1]
        z = np.frombuffer(self.fbo.read(components=1, attachment=-1, dtype="f4"), np.float32).reshape(self.size[1], self.size[0])[::-1]
        self._restore(prev)
        n, f = self.near, self.far
        depth = 2 * n * f / (f + n - (2 * z - 1) * (f - n))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), depth


class ColorGateDetector:
    def __init__(self, min_area=30):
        self.min_area = min_area

    def __call__(self, bgr, state=None):
        return self.detect(bgr)

    def detect(self, bgr):
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        orange = cv2.inRange(hsv, (4, 140, 45), (22, 255, 255))      # auch im Schatten
        white = cv2.inRange(hsv, (0, 0, 95), (180, 95, 255))
        # weiße Streifen zählen nur direkt neben orangen
        near = cv2.dilate(orange, np.ones((7, 7), np.uint8))
        frame = cv2.bitwise_or(orange, cv2.bitwise_and(white, near))
        frame = cv2.morphologyEx(frame, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        contours, hier = cv2.findContours(frame, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        if hier is None:
            return out
        H, W = frame.shape
        for i, h in enumerate(hier[0]):
            parent = h[3]
            if parent < 0:
                continue                                    # nur Löcher (Öffnungen) interessieren
            hole = contours[i]
            area = cv2.contourArea(hole)
            if area < self.min_area:
                continue
            outer = contours[parent]
            if cv2.contourArea(outer) < area * 1.08:
                continue
            peri = cv2.arcLength(hole, True)
            quad = cv2.approxPolyDP(hole, 0.06 * peri, True)
            if len(quad) != 4 or not cv2.isContourConvex(quad):
                continue
            pts = quad.reshape(4, 2).astype(np.float64)
            if (pts[:, 0].min() < 2 or pts[:, 1].min() < 2 or pts[:, 0].max() > W - 3 or pts[:, 1].max() > H - 3):
                continue                                    # vom Bildrand abgeschnitten
            # Rahmen muss ringsum orange sein: Anteil Rahmenpixel in einem Band um das Loch
            ring = np.zeros_like(frame)
            cv2.drawContours(ring, [quad], -1, 255, thickness=max(3, int(math.sqrt(area) * 0.12)))
            share = cv2.countNonZero(cv2.bitwise_and(ring, frame)) / max(1, cv2.countNonZero(ring))
            if share < 0.35:
                continue
            kps = order_corners(pts)
            x0, y0 = kps.min(axis=0)
            x1, y1 = kps.max(axis=0)
            out.append(Detection((float(x0), float(y0), float(x1), float(y1)), min(0.99, 0.5 + share / 2),
                                 kps, np.ones(4)))
        return out


def order_corners(pts):
    """-> unten-links, oben-links, oben-rechts, unten-rechts (Bild: y nach unten)."""
    c = pts.mean(axis=0)
    ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    p = pts[np.argsort(ang)]                                # beginnend oben-links, im Uhrzeigersinn
    # die Ecke mit kleinstem x+y ist oben-links
    k = int(np.argmin(p[:, 0] + p[:, 1]))
    p = np.roll(p, -k, axis=0)                              # TL, TR, BR, BL
    return np.array([p[3], p[0], p[1], p[2]])


class DepthGuard:
    """Reaktives Ausweichen aus dem Tiefenbild: Punkte vor der Drohne in einem Schlauch um die Flugbahn.

    Liegt etwas im Schlauch entlang der gewünschten Richtung, sucht der Wächter unter den Richtungen,
    die die Kamera gerade sieht (seitlich bis 60°, nach oben bis 30°), die mit der meisten freien
    Strecke bei möglichst wenig Abweichung. Früher wurde nur vom Mittel der Hindernispunkte weg
    geschoben: vor einer Wand oder unter Dach/Traktorkabine ging das nach unten in die Wand
    (20.11.: Torhaus nach Tor 11, Traktor in der Halle nach Tor 10)."""

    YAWS = (0, 12, -12, 25, -25, 40, -40, 60, -60)
    PITCHES = (0, 15, 30, -12)

    def __init__(self, cam, radius=0.75, reach=7.0, stride=6):
        self.cam, self.radius, self.reach = cam, radius, reach
        h, w = cam.height, cam.width
        ys, xs = np.mgrid[0:h:stride, 0:w:stride]
        self.ys, self.xs = ys, xs
        f = cam.f
        self.rx = (xs - w / 2) / f                          # Strahl je Pixel (Kamera: x rechts, y oben, z vorn)
        self.ry = -(ys - h / 2) / f
        self.stride = stride
        self.push = (0.0, 0.0, 0.0)
        self.blocked = False
        self.closest = None
        self.dir = None
        self.pts = np.zeros((0, 3))                         # nahe Punkte (Welt, relativ zu self.origin)
        self.origin = np.zeros(3)
        self.axes = None
        self.speed = 0.0
        self._cache = None
        self.vel_clear = reach

    def update(self, depth, pos, quat, vel):
        """depth: lineare Tiefe entlang der Kamera-z-Achse. Merkt sich die nahen Punkte (Welt)."""
        d = depth[::self.stride, ::self.stride][:self.rx.shape[0], :self.rx.shape[1]]
        cq = self.cam.cam_quat(quat)
        right, up, fwd = (np.array(qrot(cq, v)) for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        self.axes = (right, up, fwd)
        self.speed = float(np.linalg.norm(vel))
        reach = self.reach_for(self.speed)
        m = d < reach + self.radius + 1.0
        P = (self.rx[m][:, None] * right + self.ry[m][:, None] * up + fwd) * d[m][:, None]
        P = P[P[:, 1] + pos[1] > 0.3]                       # Wiese/Straße zählen nicht (sonst „steckt fest“ beim Start)
        self.pts, self.origin = P, np.asarray(pos, float)
        self._cache = None
        # Anzeige/Kompatibilität: Lage entlang der aktuellen Flugrichtung
        v = np.asarray(vel, float)
        self.blocked, self.dir, self.push = False, None, (0.0, 0.0, 0.0)
        self.vel_clear = reach
        if self.speed > 0.8:
            self.check(pos, v / self.speed)
            self.vel_clear = self._clear(self.pts, v / self.speed, reach)

    def speed_limit(self):
        """Höchsttempo, mit dem die Drohne vor dem nächsten Hindernis in Flugrichtung noch anhält
        (die Ausweichrichtung kann frei sein, aber mit 10 m/s kommt die Drohne nicht schnell genug herum)."""
        if self.vel_clear >= self.reach_for(self.speed):
            return None
        return max(1.5, math.sqrt(2 * 4.0 * max(0.0, self.vel_clear - 1.2)))

    def sweep_limit(self, pos, u, w):
        """Höchsttempo für die Kurve von der Flugrichtung w zur Wunschrichtung u: die Drohne fliegt einen
        Bogen, der auch Richtungen dazwischen überstreicht. Gerade frei und Ziel frei reicht nicht: nach
        Tor 10 lag der Traktor genau im Bogen (20.11., 10 m/s). None = keine Begrenzung."""
        if self.axes is None or float(u @ w) > 0.97:
            return None
        P = self.pts - (np.asarray(pos, float) - self.origin)
        reach = self.reach_for(self.speed)
        clear = reach
        for k in (0.25, 0.5, 0.75):
            c = w * (1 - k) + u * k
            n = np.linalg.norm(c)
            if n > 1e-6:
                clear = min(clear, self._clear(P, c / n, reach))
        if clear >= reach:
            return None
        return max(1.5, math.sqrt(2 * 4.0 * max(0.0, clear - 1.2)))

    def reach_for(self, speed):
        return max(self.reach, speed * 1.2)

    def _clear(self, P, c, reach):
        if not len(P):
            return reach
        along = P @ c
        lat2 = np.einsum("ij,ij->i", P, P) - along * along
        m = (along > 0.3) & (along < reach) & (lat2 < self.radius * self.radius)
        return float(along[m].min()) if m.any() else reach

    def _visible(self, c):
        right, up, fwd = self.axes
        z = float(c @ fwd)
        if z < 0.2:
            return False
        x, y = float(c @ right) / z * self.cam.f, float(c @ up) / z * self.cam.f
        return abs(x) < self.cam.width * 0.45 and abs(y) < self.cam.height * 0.45

    def check(self, pos, u):
        """Gewünschte Richtung u (Welt, Einheitsvektor) -> (frei?, Ausweichrichtung oder None)."""
        if self.axes is None:
            return True, None
        key = (tuple(np.round(u, 1)), tuple(np.round(np.asarray(pos) - self.origin, 0)))
        if self._cache is not None and self._cache[0] == key:
            return self._cache[1]
        P = self.pts - (np.asarray(pos, float) - self.origin)
        reach = self.reach_for(self.speed)
        c0 = self._clear(P, u, reach)
        if c0 >= reach:
            res = (True, None)
        else:
            self.blocked, self.closest = True, c0
            yaw0 = math.atan2(u[0], u[2])
            el0 = math.asin(max(-1.0, min(1.0, u[1])))
            low = pos[1] < 2.5
            best, best_score = None, c0 - 0.5
            for dy in self.YAWS:
                for de in self.PITCHES:
                    if dy == 0 and de == 0:
                        continue
                    el = el0 + math.radians(de)
                    if de < 0 and low:
                        continue                            # tief unten nie nach unten ausweichen
                    el = max(-0.6, min(0.9, el))
                    yw = yaw0 + math.radians(dy)
                    c = np.array((math.cos(el) * math.sin(yw), math.sin(el), math.cos(el) * math.cos(yw)))
                    if not self._visible(c):
                        continue                            # was die Kamera nicht sieht, gilt nicht als frei
                    score = self._clear(P, c, reach) - 0.05 * (abs(dy) + abs(de))
                    if score > best_score:
                        best, best_score = c, score
            self.dir = best
            if best is not None:
                self.push = tuple((best - u) * 2.0)
            res = (False, best)
        self._cache = (key, res)
        return res


class GuardedController:
    """Steht zwischen VisionPilot und FlightController: lenkt die Soll-Richtung um ein Hindernis herum,
    das die Kamera vor sich sieht."""

    def __init__(self, ctl, guard):
        self.ctl, self.guard = ctl, guard

    def __getattr__(self, name):
        return getattr(self.ctl, name)

    def track(self, state, p_ref, v_ref, a_ref, yaw_dir):
        v = np.asarray(v_ref, float)
        sp = float(np.linalg.norm(v))
        if sp > 0.5:
            pos = np.asarray(state.pos, float)
            free, d = self.guard.check(pos, v / sp)
            cap = self.guard.speed_limit()
            vel = np.asarray(state.vel, float)
            vs = float(np.linalg.norm(vel))
            if vs > 2.0:
                cap2 = self.guard.sweep_limit(pos, v / sp, vel / vs)
                if cap2 is not None:
                    cap = cap2 if cap is None else min(cap, cap2)
            if not free:
                slow = max(0.35, min(1.0, (self.guard.closest or 0.0) / 6.0))
                if d is None:                               # nichts frei, das man sieht: anhalten
                    p_ref, v_ref = tuple(pos), (0.0, 0.0, 0.0)
                else:
                    p_ref = tuple(pos + d * 1.5)
                    v_ref = tuple(d * min(sp * slow, cap or sp))
            elif cap is not None and cap < sp:
                v_ref = tuple(v / sp * cap)
        return self.ctl.track(state, p_ref, v_ref, a_ref, yaw_dir)
