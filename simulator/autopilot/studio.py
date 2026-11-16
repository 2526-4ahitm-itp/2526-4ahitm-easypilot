"""EasyPilot Studio: one app to show the autopilot - any map, any speed, human vs. autopilot.

  python -m autopilot.studio                  # http://localhost:8765/  (opens the browser)
  python -m autopilot.studio --no-browser --key geheim

What it does
  - Map: every official Liftoff race and every race built in Liftoff's editor (custom maps).
    Changing the map restarts Liftoff with that race (session.py, ~1 min).
  - Autopilot run: speed as stage 1-5 or free 10-100 %, 1-3 laps, optional camera correction.
    Every run is timed through the real gates; the best run per map/stage becomes the reference
    (time, splits, path for the ghost, FPV video for the split screen).
  - Human run: the visitor's controller is passed through to vJoy (pilot.py; via Parsec a remote
    gamepad works the same way). Split screen: left the live Liftoff image, right the autopilot's
    reference run of the same map and stage, started at the same GO.
  - Layout: puts the Liftoff window in the top-left quarter (borderless, always on top), the
    browser page leaves exactly that area free - works on 1080p and 4K screens.
"""
import json
import math
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import window
from .liftoff import RUNS, Session, key_down, VK_F9
from .race import course
from .envdb import for_track
from .recorder import Recorder, keep_as_reference, video_path
from .session import catalog, flush_laps, lap_counted, lap_record, load as load_liftoff, race_info
from .tdot import STAGES, LapTimer, Leaderboard
from .telemetry import Telemetry
from .track import race_gates

WEB = Path(__file__).resolve().parent / "dashboard"
DATA = RUNS / "studio"
SETTINGS = DATA / "settings.json"
DEFAULTS = {"race": "StrawBaleRace01", "laps": 1, "stage": 3, "custom_speed": None, "vision": False,
            "liftoff_mode": "race", "timeout": 180}


def board_path(race, laps):
    return RUNS / "tdot" / f"{race}-{laps}lap.json"


class Studio:
    def __init__(self):
        DATA.mkdir(parents=True, exist_ok=True)
        self.settings = dict(DEFAULTS)
        if SETTINGS.exists():
            self.settings.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
        self.catalog = catalog()
        self.timer = LapTimer([])
        self.tel = Telemetry(on_state=self._on_state)
        self.tel.start()
        self.commands = queue.Queue()
        self.abort = threading.Event()
        self.live = {"phase": "idle", "pilot": None, "kind": None, "stage": None, "speed_pct": None, "countdown": 0,
                     "message": "", "pos": None, "speed": 0.0, "loaded_race": None}
        self.last_result = None
        self.queue_list = []
        self.spawn = None
        self.frames = None
        self._select(self.settings["race"], self.settings["laps"])
        threading.Thread(target=self._worker, daemon=True).start()

    # ---------------------------------------------------------------- map
    def _select(self, race, laps):
        info = race_info(race)
        self.race, self.info = race, info
        self.gates = race_gates(info["race"], info["track"])
        self.colliders = for_track(info["track"])
        self.laps = int(laps)
        self.seq = course(self.gates, self.laps)
        self.timer.seq = self.seq
        self.timer.reset()
        self.board = Leaderboard(board_path(race, self.laps))

    def save_settings(self):
        SETTINGS.write_text(json.dumps(self.settings, indent=1), encoding="utf-8")

    def _on_state(self, s):
        self.timer.feed(s)
        self.live["pos"] = (round(s.pos[0], 2), round(s.pos[2], 2))
        self.live["speed"] = round(s.speed * 3.6, 1)

    # ---------------------------------------------------------------- state for the page
    def state(self):
        t = self.timer
        st = self.live["stage"]
        bot = self.board.bot(st) if st else None
        delta = None
        if bot and t.splits and len(t.splits) <= len(bot["splits"]):
            delta = round(t.splits[-1] - bot["splits"][len(t.splits) - 1], 2)
        s = self.tel.latest(1.0)
        return {**self.live, "race": self.race, "title": self.info["name"], "env": self.info["env"],
                "laps": self.laps, "settings": self.settings,
                "elapsed": round(t.t_now, 2) if (t.running or t.finished) else 0.0,
                "gate": t.next, "gates_total": len(self.seq), "splits": t.splits, "delta": delta,
                "bot_time": bot["time"] if bot else None,
                "video": (f"/api/video/{self.race}/{st}" if st and video_path(self.race, st).exists() else None),
                "last_result": self.last_result, "waiting": self.queue_list, "board": self.board.summary(),
                "liftoff": {"running": window.find_window() is not None, "telemetry": s is not None,
                            "in_level": bool(s and max(abs(v) for v in s.pos) > 1e-3)},
                "controllers": self.controllers()}

    def controllers(self):
        try:
            from .pilot import CONFIG, controllers
            return {"connected": [n for _, n in controllers()], "calibrated": CONFIG.exists()}
        except Exception as exc:
            return {"connected": [], "calibrated": False, "error": repr(exc)}

    def track_info(self):
        pts = [g.center for g in self.gates]
        xs, zs = [p[0] for p in pts], [p[2] for p in pts]
        return {"race": self.race, "title": self.info["name"], "env": self.info["env"],
                "gates": [{"x": g.center[0], "z": g.center[2], "nx": g.normal[0], "nz": g.normal[2], "w": g.width}
                          for g in self.gates],
                "sequence": [self.gates.index(g) for g in self.seq],
                "bounds": [min(xs) - 15, min(zs) - 15, max(xs) + 15, max(zs) + 15],
                "stages": [s.__dict__ for s in STAGES],
                "ghosts": {str(s.level): (self.board.bot(s.level) or {}).get("path") for s in STAGES}}

    def maps(self):
        """Catalog with the stages that already have an autopilot reference on this map."""
        out = []
        for m in self.catalog:
            b = Leaderboard(board_path(m["key"], 1)) if board_path(m["key"], 1).exists() else None
            refs = {s.level: (b.bot(s.level) or {}).get("time") if b else None for s in STAGES}
            out.append({**m, "refs": refs})
        return out

    # ---------------------------------------------------------------- commands from the page
    def submit(self, cmd):
        a = cmd.get("action")
        if a == "abort":
            self.abort.set()
            self.queue_list.clear()
            return {"ok": True}
        if a == "delete":
            self.board.delete(cmd.get("id", ""))
            return {"ok": True}
        if a == "settings":
            for k in ("laps", "stage", "custom_speed", "vision", "timeout"):
                if k in cmd:
                    self.settings[k] = cmd[k]
            self.save_settings()
            if int(self.settings["laps"]) != self.laps:
                self._select(self.race, self.settings["laps"])
            return {"ok": True}
        if a == "layout":
            return {"ok": arrange_liftoff(cmd.get("mode", "quarter"))}
        if a not in ("bot", "human", "map"):
            return {"ok": False, "error": "unknown action"}
        if a == "map" and not any(m["key"] == cmd.get("race") for m in self.catalog):
            return {"ok": False, "error": "unknown map"}
        cmd["id"] = uuid.uuid4().hex[:6]
        if a == "human":
            cmd["name"] = (cmd.get("name") or "").strip()[:24] or "Gast"
        label = {"bot": "Autopilot", "human": cmd.get("name"), "map": "Strecke laden"}[a]
        self.queue_list.append({"id": cmd["id"], "kind": a, "name": label, "stage": cmd.get("stage")})
        self.commands.put(cmd)
        return {"ok": True, "id": cmd["id"]}

    def _worker(self):
        while True:
            cmd = self.commands.get()
            if not any(q["id"] == cmd["id"] for q in self.queue_list):
                continue
            self.queue_list = [q for q in self.queue_list if q["id"] != cmd["id"]]
            self.abort.clear()
            try:
                if cmd["action"] == "map":
                    self.load_map(cmd["race"])
                elif cmd["action"] == "bot":
                    self.run_bot(cmd.get("stage"), cmd.get("speed"))
                else:
                    self.run_human(cmd["name"], int(cmd.get("stage") or 1))
            except Exception as exc:
                import traceback
                traceback.print_exc()
                self.live.update(phase="error", message=repr(exc)[:200])

    def load_map(self, race):
        self.live.update(phase="loading", message=f"Liftoff lädt {race} …", pilot=None, stage=None)
        self._select(race, self.settings["laps"])
        self.settings["race"] = race
        self.save_settings()
        ok, _ = load_liftoff(race, tel=self.tel, mode=self.settings.get("liftoff_mode", "race"))
        if ok:
            arrange_liftoff("quarter")
        self.live.update(phase="idle" if ok else "error", loaded_race=race if ok else None,
                         message="" if ok else "Liftoff hat die Strecke nicht geladen")

    # ---------------------------------------------------------------- runs
    def _reset(self, joy, settle):
        from .vjoy import BTN_RESET
        for attempt in range(3):
            if attempt:
                # Liftoff in front is not enough: after the Studio page had the focus (click on
                # Start) Unity ignored the vJoy reset until it got a real activation (16.11.)
                try:
                    window.focus_liftoff(hard=True)
                    arrange_liftoff(self.settings.get("layout", "quarter"))
                except RuntimeError:
                    pass
            joy.idle()
            before = self.tel.resets
            joy.tap(BTN_RESET, 0.15)
            end = time.perf_counter() + 2.0
            while time.perf_counter() < end and self.tel.resets == before:
                time.sleep(0.02)
            if self.tel.resets != before:
                time.sleep(settle)
                s = self.tel.wait(1.0)
                if s is not None:
                    self.spawn = s.pos
                return True
            s = self.tel.latest(0.5)
            if s is not None and self.spawn is not None and math.dist(s.pos, self.spawn) < 1.0:
                return True
            time.sleep(0.5)
        return False

    def _settle(self):
        return 4.5 if self.settings.get("liftoff_mode", "race") == "race" else 1.5

    def _prepare(self, kind, name, level, pct, joy):
        self.timer.reset()
        self.live.update(phase="ready", pilot=name, kind=kind, stage=level, speed_pct=pct, countdown=0, message="")
        window.focus_liftoff(hard=False)
        if not self._reset(joy, self._settle()):
            self.live.update(message="Reset kommt nicht an - ist Liftoff im Rennen?")
            return None
        for n in (3, 2, 1):
            self.live.update(phase="countdown", countdown=n)
            if self.abort.wait(1.0):
                return None
        s = self.tel.wait(2.0)
        if s is None or max(abs(v) for v in s.pos) < 1e-3:
            self.live.update(message="Keine Telemetrie - Liftoff im Menü?")
            return None
        self.timer.go(s.t)
        self.live.update(phase="racing", countdown=0)
        return s

    def _finish(self, kind, name, level, why, extra=None):
        t = self.timer
        t.running = False
        result = {"kind": kind, "name": name, "stage": level, "time": t.time, "gates": t.next,
                  "gates_total": len(self.seq), "reason": why, "race": self.race, **(extra or {})}
        bot = self.board.bot(level) if level else None
        if kind == "human":
            entry = self.board.add_run(name, level, t.time, t.splits)
            result.update(beat_bot=entry["beat_bot"], bot_time=bot["time"] if bot else None, id=entry["id"])
        self.last_result = result
        self.live.update(phase="finished" if t.time is not None else "dnf", message=why)
        print("result:", json.dumps(result, ensure_ascii=False), flush=True)
        return result

    def run_bot(self, stage=None, speed=None):
        from .race import fly
        if speed:                                      # free speed in percent
            k, level = max(0.1, min(1.0, float(speed) / 100.0)), None
            name = f"Autopilot {int(float(speed))} %"
        else:
            level = int(stage or self.settings["stage"])
            st = next(s for s in STAGES if s.level == level)
            k, name = st.aggressiveness, f"Autopilot – {st.name}"
        sess = Session(f"studio-{self.race}-{level or int(k * 100)}", tel=self.tel)
        time.sleep(0.5)
        before = lap_record(self.info["race_id"])
        rec = Recorder(self.tel, self.race, level or 0, k) if level and self.laps == 1 else None
        if rec:
            rec.start()
        s = self._prepare("bot", name, level, int(k * 100), sess.joy)
        if s is None:
            sess.close()
            if rec:
                rec.finish(keep_video=False)
            return self._finish("bot", name, level, self.live["message"] or "abgebrochen")
        if rec:
            rec.go()

        def on_step(state, racer):
            if self.abort.is_set() or self.timer.finished:
                racer.progress.finished = True          # brake and land (race.fly)
        res = fly(sess, self.gates, self.laps, k, vision=bool(self.settings.get("vision")), on_step=on_step,
                  colliders=self.colliders)
        time.sleep(1.0)
        counted = lap_counted(before, flush_laps(self.info["race_id"]))
        why = "abgebrochen" if self.abort.is_set() else ("im Ziel" if self.timer.finished else res.get("reason", ""))
        mp4 = rec.finish(keep_video=self.timer.finished) if rec else None
        extra = {"liftoff_counted": counted}
        if level and self.timer.time is not None:
            if self.board.add_bot(level, self.timer.time, self.timer.splits, self.timer.path):
                extra["new_reference"] = True
                if mp4:
                    keep_as_reference(mp4, self.race, level)
        if mp4 and mp4.exists():
            mp4.unlink()
        return self._finish("bot", name, level, why, extra)

    def run_human(self, name, level):
        from .pilot import Controller
        from .vjoy import VJoy
        try:
            ctl = Controller()
        except Exception as exc:
            self.live.update(phase="error", pilot=name, message=f"Kein Controller: {exc}")
            return None
        joy = VJoy()
        time.sleep(0.5)
        try:
            s = self._prepare("human", name, level, None, joy)
            if s is None:
                return self._finish("human", name, level, self.live["message"] or "abgebrochen")
            resets0 = self.tel.resets
            end = time.perf_counter() + float(self.settings.get("timeout", 180))
            why = "im Ziel"
            while not self.timer.finished:
                if self.abort.is_set() or key_down(VK_F9):
                    why = "abgebrochen"
                    break
                if time.perf_counter() > end:
                    why = "Zeitlimit"
                    break
                if self.tel.resets != resets0:
                    why = "Reset / Absturz"
                    break
                joy.sticks(*ctl.read())
                time.sleep(0.004)
            return self._finish("human", name, level, why)
        finally:
            joy.close()

    # ---------------------------------------------------------------- live picture
    def mjpeg_frames(self):
        from .capture import COLORONCOLOR, FrameStream
        import cv2
        if self.frames is None or not self.frames.is_alive():
            self.frames = FrameStream(960, fps=25, mode=COLORONCOLOR)
            self.frames.start()
        last = 0.0
        while True:
            stamp, img = self.frames.latest()
            if img is None or stamp == last:
                time.sleep(0.01)
                continue
            last = stamp
            ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                yield jpg.tobytes()


def arrange_liftoff(mode="quarter"):
    """Borderless Liftoff window in the top-left quarter of the main screen, always on top."""
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = window.find_window()
    if hwnd is None:
        return False
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    if mode == "full":
        w, h = sw, sh
    else:
        w = sw // 2
        h = w * 9 // 16
    GWL_STYLE, WS_POPUP, WS_VISIBLE = -16, 0x80000000, 0x10000000
    user32.SetWindowLongW(hwnd, GWL_STYLE, WS_POPUP | WS_VISIBLE)
    HWND_TOPMOST, SWP_FRAMECHANGED, SWP_SHOWWINDOW = -1, 0x0020, 0x0040
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, w, h, SWP_FRAMECHANGED | SWP_SHOWWINDOW)
    return True


def make_handler(studio, admin_key):
    pages = {"/": "studio.html", "/studio": "studio.html", "/dashboard": "index.html", "/overlay": "overlay.html",
             "/admin": "admin.html"}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _file(self, path, ctype):
            """Static file with HTTP range support (the browser seeks in the video)."""
            size = path.stat().st_size
            rng = self.headers.get("Range")
            start, end = 0, size - 1
            if rng:
                m = re.match(r"bytes=(\d*)-(\d*)", rng)
                if m:
                    start = int(m.group(1) or 0)
                    end = int(m.group(2)) if m.group(2) else size - 1
            end = min(end, size - 1)
            with path.open("rb") as f:
                f.seek(start)
                data = f.read(end - start + 1)
            self.send_response(206 if rng else 200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(data)))
            if rng:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            p = url.path
            if p in pages:
                return self._send(200, (WEB / pages[p]).read_bytes(), "text/html; charset=utf-8")
            if p.startswith("/static/"):
                f = (WEB / p[len("/static/"):]).resolve()
                if WEB.resolve() in f.parents and f.exists():
                    ctype = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
                             ".png": "image/png"}.get(f.suffix, "application/octet-stream")
                    return self._send(200, f.read_bytes(), ctype + "; charset=utf-8")
            if p == "/api/state":
                return self._send(200, json.dumps(studio.state(), ensure_ascii=False))
            if p == "/api/track":
                return self._send(200, json.dumps(studio.track_info(), ensure_ascii=False))
            if p == "/api/maps":
                return self._send(200, json.dumps(studio.maps(), ensure_ascii=False))
            m = re.match(r"/api/video/([^/]+)/(\d+)$", p)
            if m:
                f = video_path(unquote(m.group(1)), int(m.group(2)))
                if f.exists():
                    return self._file(f, "video/mp4")
            if p == "/api/live.mjpg":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    for jpg in studio.mjpeg_frames():
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                         + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                return
            self._send(404, '{"error": "not found"}')

        def do_POST(self):
            url = urlparse(self.path)
            if url.path != "/api/command":
                return self._send(404, '{"error": "not found"}')
            if admin_key and parse_qs(url.query).get("key", [""])[0] != admin_key:
                return self._send(403, '{"ok": false, "error": "falscher Schlüssel"}')
            n = int(self.headers.get("Content-Length", 0))
            try:
                cmd = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._send(400, '{"ok": false, "error": "bad json"}')
            self._send(200, json.dumps(studio.submit(cmd), ensure_ascii=False))

    return Handler


def open_browser(url):
    """Edge/Chrome as an app window in fullscreen (kiosk-like), else the default browser."""
    for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if Path(exe).exists():
            subprocess.Popen([exe, f"--app={url}", "--start-fullscreen", "--new-window"])
            return
    import webbrowser
    webbrowser.open(url)


def main(argv):
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
    key = argv[argv.index("--key") + 1] if "--key" in argv else ""
    studio = Studio()
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(studio, key))
    server.daemon_threads = True
    url = f"http://localhost:{port}/" + (f"?key={key}" if key else "")
    print(f"EasyPilot Studio: {url}  ({len(studio.catalog)} Strecken)", flush=True)
    if "--no-browser" not in argv:
        open_browser(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main(sys.argv[1:])
