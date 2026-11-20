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
import os
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
from .studio_sim import SimStudio

WEB = Path(__file__).resolve().parent / "dashboard"
DATA = RUNS / "studio"
SETTINGS = DATA / "settings.json"
DEFAULTS = {"race": "StrawBaleRace01", "laps": 1, "stage": 3, "custom_speed": None, "vision": False,
            "liftoff_mode": "race", "timeout": 180, "autopilot_mode": "karte",
            "simulator": "liftoff"}   # "liftoff" or "sim" (own simulator, studio_sim.py)
# Autopilot modes: "karte" = gates from the track file, "karte_kamera" = plus camera correction (old
# "vision" switch), "erkunden" = camera-only scouting lap, then race on its own map, "nur_kamera" =
# camera only, no map (visionfly.py). The track file then only scores the run (lap timer).
AUTOPILOT_MODES = {"karte": "Karte", "karte_kamera": "Karte + Kamera", "erkunden": "Erkunden + Rennen",
                   "nur_kamera": "Nur Kamera"}
VISION_SPEED = {1: 2.0, 2: 3.0, 3: 4.0, 4: 5.0, 5: 6.0}     # m/s in "nur_kamera" per stage


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
        self.dbg_racer, self.dbg_state, self.dbg_plan = None, None, None
        self.dets = None              # (stamp, [[x0, y0, x1, y1, conf, 4 corners...]] normalised) of the live image
        self.det_thread = None
        self.sim = SimStudio(DATA)       # second simulator choice: EasyPilot-Sim (autopilot/freefly)
        self._select(self.settings["race"], self.settings["laps"])
        threading.Thread(target=self._worker, daemon=True).start()

    # ---------------------------------------------------------------- map
    def _select(self, race, laps):
        info = race_info(race)
        self.race, self.info = race, info
        gates = race_gates(info["race"], info["track"])
        colliders = for_track(info["track"])
        # gates and their sequence change together: /api/track polled in between failed (16.11.)
        self.gates, self.seq, self.colliders, self.laps = gates, course(gates, int(laps)), colliders, int(laps)
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
                "laps": self.laps, "settings": self.settings, "detector": self.detector_status(),
                "elapsed": round(t.t_now, 2) if (t.running or t.finished) else 0.0,
                "gate": t.next, "gates_total": len(self.seq), "splits": t.splits, "delta": delta,
                "bot_time": bot["time"] if bot else None,
                "video": (f"/api/video/{self.race}/{st}" if st and video_path(self.race, st).exists() else None),
                "last_result": self.last_result, "waiting": self.queue_list, "board": self.board.summary(),
                "liftoff": {"running": window.find_window() is not None, "telemetry": s is not None,
                            "in_level": bool(s and max(abs(v) for v in s.pos) > 1e-3)},
                "controllers": self.controllers(), "debug": self.debug_state()}

    # ---------------------------------------------------------------- live debug view
    def debug_state(self):
        """What the autopilot does right now: pose, plan reference, sticks, AI detections of the live image."""
        r, s = self.dbg_racer, self.dbg_state
        out = {"plan": id(r.line) if r is not None else None}
        if r is not None and s is not None and getattr(r, "last_cmd", None) is not None:
            c, d = r.last_cmd, r.ctl.debug
            out.update(t=round(s.t, 3), p=[round(v, 2) for v in s.pos], q=[round(v, 4) for v in s.quat],
                       v=round(s.speed, 2), vr=round(r.last_v_ref, 2), xt=round(math.dist(s.pos, r.line.points[r.idx]), 3),
                       st=[round(c.throttle, 3), round(c.yaw, 3), round(c.pitch, 3), round(c.roll, 3)],
                       ref=[round(v, 2) for v in r.last_ref], g=r.progress.gate_index,
                       tilt=round(d.get("tilt_err_deg", 0.0), 1))
        if self.dets is not None and time.time() - self.dets[0] < 1.0:
            out["dets"] = self.dets[1]
        return out

    def debug_plan(self):
        """The racing line of the running flight with what the planner knew (cached per line)."""
        r = self.dbg_racer
        if r is None:
            return {}
        if self.dbg_plan and self.dbg_plan[0] == id(r.line):
            return self.dbg_plan[1]
        from . import gatedb
        from .geometry import cross, unit
        from .sysid import load_camera
        line = r.line
        pts, last = [], -1e9
        for i, p in enumerate(line.points):
            if line.s[i] - last >= 0.5 or i == len(line.points) - 1:
                pts.append([round(p[0], 2), round(p[1], 2), round(p[2], 2), round(line.speed[i], 2)])
                last = line.s[i]
        gates = []
        for g in self.gates:
            n = unit(g.normal)
            side = unit(cross((0.0, 1.0, 0.0), n), (1.0, 0.0, 0.0))
            up = cross(n, side)
            gates.append({"c": [round(v, 2) for v in g.center], "o": [[round(g.center[k] + sx * g.width / 2 * side[k] + sy * g.height / 2 * up[k], 2)
                          for k in range(3)] for sx, sy in ((-1, -1), (-1, 1), (1, 1), (1, -1))]})
        boxes, seen = [], set()
        for p in line.points[::8]:
            for name, pp in self.colliders.near(p, 3.0):
                if id(pp) in seen or gatedb.pp_distance(pp, p) > 3.0:
                    continue
                cs = gatedb.pp_corners(pp)
                if max(math.dist(a, b) for a in cs for b in cs) < 60:
                    seen.add(id(pp))
                    boxes.append([[round(v, 2) for v in c] for c in cs])
        cam = load_camera()
        plan = {"id": id(line), "line": pts, "vias": [[round(v, 2) for v in g.center] for g in line.gates if getattr(g, "via", False)],
                "gates": gates, "boxes": boxes[:400], "cam": {"hfov": cam.hfov_deg, "tilt": cam.tilt_deg},
                "length": round(line.length, 1), "planned": round(line.lap_time_estimate, 2)}
        self.dbg_plan = (id(line), plan)
        return plan

    def _start_detector(self):
        """YOLO on the live image during runs (debug view): ~15 Hz, a few ms on the GPU."""
        if not self.settings.get("debug_vision", True) or (self.det_thread and self.det_thread.is_alive()):
            return
        def loop():
            from .capture import COLORONCOLOR, FrameStream
            from .detector import GateDetector
            try:
                det = GateDetector()
            except Exception as exc:
                print("debug detector off:", exc, flush=True)
                return
            if self.frames is None or not self.frames.is_alive():
                self.frames = FrameStream(960, fps=25, mode=COLORONCOLOR)
                self.frames.start()
            last = 0.0
            while True:
                if self.live["phase"] not in ("ready", "countdown", "racing"):
                    time.sleep(0.2)
                    continue
                stamp, img = self.frames.latest()
                if img is None or stamp == last:
                    time.sleep(0.01)
                    continue
                last = stamp
                h, w = img.shape[:2]
                out = []
                for d in det.detect(img):
                    kp = [round(float(v), 4) for xy, c in zip(d.kps, d.kp_conf)
                          for v in ((xy[0] / w, xy[1] / h) if c > 0.5 else (-1, -1))]
                    out.append([round(d.box[0] / w, 4), round(d.box[1] / h, 4), round(d.box[2] / w, 4),
                                round(d.box[3] / h, 4), round(d.conf, 2)] + kp)
                self.dets = (time.time(), out)
                time.sleep(0.05)
        self.det_thread = threading.Thread(target=loop, daemon=True)
        self.det_thread.start()

    def controllers(self):
        try:
            from .pilot import calibrated, controllers
            return {"connected": [n for _, n in controllers()], "calibrated": calibrated()}
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
        if a == "simulator":
            self.settings["simulator"] = "sim" if cmd.get("which") == "sim" else "liftoff"
            self.save_settings()
            return {"ok": True}
        if a == "sim_layout":
            ok = self.sim.arrange()
            if sys.platform == "darwin" and cmd.get("url"):
                ok = arrange_studio_windows_mac(cmd["url"]) and ok
            return {"ok": ok} if ok else {"ok": False, "error": "Sim läuft nicht oder Safari-Fenster gehen nicht"}
        if str(a).startswith("sim_"):
            return self.sim.submit(cmd)
        if a == "abort":
            self.abort.set()
            self.queue_list.clear()
            return {"ok": True}
        if a == "delete":
            self.board.delete(cmd.get("id", ""))
            return {"ok": True}
        if a == "settings":
            for k in ("laps", "stage", "custom_speed", "vision", "timeout", "autopilot_mode"):
                if k in cmd:
                    self.settings[k] = cmd[k]
            if "autopilot_mode" in cmd:          # the old checkbox follows the mode
                self.settings["vision"] = cmd["autopilot_mode"] == "karte_kamera"
            elif "vision" in cmd and self.settings.get("autopilot_mode") in ("karte", "karte_kamera"):
                self.settings["autopilot_mode"] = "karte_kamera" if cmd["vision"] else "karte"
            self.save_settings()
            if int(self.settings["laps"]) != self.laps:
                self._select(self.race, self.settings["laps"])
            return {"ok": True}
        if a == "layout":
            mode = cmd.get("mode", "quarter")
            self.settings["layout"] = mode
            self.save_settings()
            ok = arrange_liftoff(mode)
            if sys.platform == "darwin" and mode == "quarter" and cmd.get("url"):
                ok = arrange_studio_windows_mac(cmd["url"]) and ok
            if not ok and sys.platform == "darwin":
                return {"ok": False, "error": "Liftoff-Fenster lässt sich nicht verschieben: Liftoff läuft nicht, oder "
                        "das Terminal braucht Bedienungshilfen (Systemeinstellungen > Datenschutz & Sicherheit)."}
            return {"ok": ok}
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
                    self.run_human(cmd["name"], int(cmd.get("stage") or 1), bool(cmd.get("practice")),
                                   bool(cmd.get("infinite")))
            except (Exception, SystemExit) as exc:   # SystemExit: vjoy/ojdpad missing - must not kill the worker
                import traceback
                traceback.print_exc()
                self.live.update(phase="error", message=(str(exc) if isinstance(exc, SystemExit) else repr(exc))[:200])

    def load_map(self, race):
        self.live.update(phase="loading", message=f"Liftoff lädt {race} …", pilot=None, stage=None)
        self._select(race, self.settings["laps"])
        self.settings["race"] = race
        self.save_settings()
        ok, _ = load_liftoff(race, tel=self.tel, mode=self.settings.get("liftoff_mode", "race"))
        if ok:
            arrange_liftoff("quarter")
            self._unpause()
        self.live.update(phase="idle" if ok else "error", loaded_race=race if ok else None,
                         message="" if ok else "Liftoff hat die Strecke nicht geladen")

    # ---------------------------------------------------------------- runs
    def _unpause(self):
        """macOS: after a track load Liftoff sometimes sits in its pause menu (19.11., twice in a row
        on AutumnFieldsRace01 and StrawBaleRace01), so no telemetry comes and the reset does nothing.
        Without telemetry click "Resume" once. Windows is left as it was (never seen there)."""
        if sys.platform != "darwin" or self.tel.latest(0.5) is not None:
            return
        try:
            from . import ui
            window.focus_liftoff(hard=False)
            ui.click_capture(648, 243)          # "Resume" in the pause menu, capture coordinates
        except Exception as exc:
            print("unpause:", repr(exc), flush=True)
            return
        time.sleep(1.5)
        print("unpause:", "ok" if self.tel.latest(1.0) is not None else "still no telemetry", flush=True)

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
        self._unpause()
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

    def detector_status(self):
        if os.environ.get("EASYPILOT_TEST_DETECTOR"):
            return "TEST-DETEKTOR aus der Streckendatei (nur Entwicklung, kein echter Kameratest)"
        from .detector import detector_status
        return detector_status()

    def _vision_detect(self):
        """Detector for the camera-only modes: YOLO, or (development only) the test detector."""
        from . import visionfly
        if os.environ.get("EASYPILOT_TEST_DETECTOR"):
            from .sysid import load_camera
            return visionfly.TestDetector(self.gates, load_camera(640))
        return visionfly.yolo_detect()

    def run_vision(self, mode, stage):
        """Camera-only modes (visionfly.py). The track file is not used for flying, only the lap timer
        (= the referee, like Liftoff's own checkpoints) and the map check afterwards."""
        from . import visionfly
        from .race import fly
        level = int(stage or self.settings["stage"])
        st = next(s for s in STAGES if s.level == level)
        name = f"Autopilot – {AUTOPILOT_MODES[mode]}"
        self.dbg_racer, self.dbg_plan = None, None
        why = None if os.environ.get("EASYPILOT_TEST_DETECTOR") else self.detector_status()
        if why:
            self.live.update(phase="error", pilot=name, message=f"{AUTOPILOT_MODES[mode]} geht nicht: {why}")
            return None
        try:
            detect = self._vision_detect()
        except Exception as exc:
            self.live.update(phase="error", pilot=name, message=f"Torerkennung: {exc}"[:200])
            return None
        stop = lambda: self.abort.is_set() or self.timer.finished      # noqa: E731
        extra = {"mode": mode, "test_detector": bool(os.environ.get("EASYPILOT_TEST_DETECTOR"))}

        def show(s, pilot):
            self.dbg_state = s
            t = pilot.target
            self.live["message"] = (f"Ziel: Tor V{t.id} ({'trianguliert' if t.triangulated else 'geschätzt'})"
                                    if t else "sucht ein Tor …")

        if mode == "nur_kamera":
            sess = Session(f"studio-vision-{self.race}-{level}", tel=self.tel)
            time.sleep(0.5)
            if self._prepare("bot", name, None, None, sess.joy) is None:
                sess.close()
                return self._finish("bot", name, None, self.live["message"] or "abgebrochen", extra)
            res = visionfly.fly_by_camera(sess, VISION_SPEED[level], detect, on_step=show,
                                          max_time=float(self.settings.get("timeout", 180)) + 60, stop=stop)
            sess.close()
            extra["vision"] = {k: res[k] for k in ("reason", "passages", "gates_seen", "detections", "fps")}
            why = "abgebrochen" if self.abort.is_set() else ("im Ziel" if self.timer.finished else res["reason"])
            return self._finish("bot", name, None, why, extra)

        # erkunden: scouting lap by camera, then race on the own map
        sess = Session(f"studio-explore-{self.race}", tel=self.tel)
        time.sleep(0.5)
        if self._prepare("bot", f"{name}: Erkundungsrunde", None, None, sess.joy) is None:
            sess.close()
            return self._finish("bot", name, None, self.live["message"] or "abgebrochen", extra)
        res = visionfly.fly_by_camera(sess, 3.0, detect, explore=True, on_step=show,
                                      max_time=float(self.settings.get("timeout", 180)) + 120,
                                      stop=self.abort.is_set)
        sess.close()
        gmap = res.pop("map")
        scout = {"time": self.timer.time, "gates": self.timer.next, "gates_total": len(self.seq),
                 "reason": res["reason"], "mapped": len(gmap), "map_vs_track": visionfly.map_error(gmap, self.gates)}
        extra["explore"] = scout
        print("explore:", json.dumps(scout, ensure_ascii=False), flush=True)
        if self.abort.is_set() or len(gmap) < 2:
            return self._finish("bot", name, None, "abgebrochen" if self.abort.is_set() else
                                f"Erkundung: nur {len(gmap)} Tor(e) gefunden ({res['reason']})", extra)
        sess = Session(f"studio-explorerace-{self.race}-{level}", tel=self.tel)
        time.sleep(0.5)
        if self._prepare("bot", f"{name}: Rennen ({len(gmap)} Tore kartiert)", None, int(st.aggressiveness * 100),
                         sess.joy) is None:
            sess.close()
            return self._finish("bot", name, None, self.live["message"] or "abgebrochen", extra)

        def on_step(state, racer):
            self.dbg_racer, self.dbg_state = racer, state
            if self.abort.is_set() or self.timer.finished:
                racer.progress.finished = True
        r = fly(sess, gmap, 1, st.aggressiveness, vision=False, on_step=on_step, colliders=None)
        extra["race_on_own_map"] = {k: r[k] for k in ("reason", "gates_passed", "gates_total", "planned_s")}
        why = "abgebrochen" if self.abort.is_set() else ("im Ziel" if self.timer.finished else r.get("reason", ""))
        return self._finish("bot", name, None, why, extra)

    def run_bot(self, stage=None, speed=None):
        from .race import fly
        mode = self.settings.get("autopilot_mode") or ("karte_kamera" if self.settings.get("vision") else "karte")
        if mode in ("erkunden", "nur_kamera") and not speed:
            return self.run_vision(mode, stage)
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

        self.dbg_racer, self.dbg_plan = None, None
        self._start_detector()

        def on_step(state, racer):
            self.dbg_racer, self.dbg_state = racer, state
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

    def run_human(self, name, level, practice=False, infinite=False):
        """practice: a crash does not end the run. Liftoff respawns the drone at the start, the
        timer starts again and the pilot keeps flying (Versuch 2, 3, ...) until the finish, Stop/F9
        or practice_minutes (default 5) are over. infinite: practice without time limit, and after
        the finish the drone is reset for the next lap too - it only ends with Stop/F9."""
        practice = practice or infinite
        self.dbg_racer, self.dbg_plan = None, None     # the debug view belongs to autopilot runs
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
            limit = float(self.settings.get("practice_minutes", 5)) * 60 if practice else float(self.settings.get("timeout", 180))
            end = float("inf") if infinite else time.perf_counter() + limit
            why = "im Ziel"
            attempt = 1
            if practice:
                self.live.update(message="Übung: Versuch 1")
            best = None
            while infinite or not self.timer.finished:
                if infinite and self.timer.finished:     # lap done: show it, back to the start
                    best = self.timer.time if best is None else min(best, self.timer.time)
                    joy.idle()
                    self.live.update(message=f"Übung: Versuch {attempt} im Ziel {self.timer.time:.2f} s (Bestzeit {best:.2f} s)")
                    if not self._reset(joy, self._settle()):
                        why = "Reset kommt nicht an"
                        break
                    s = self.tel.wait(1.0)
                    resets0 = self.tel.resets
                    attempt += 1
                    self.timer.reset()
                    if s is not None:
                        self.timer.go(s.t)
                    self.live.update(phase="racing", message=f"Übung: Versuch {attempt} (Bestzeit {best:.2f} s)")
                    continue
                if self.abort.is_set() or key_down(VK_F9):
                    why = "abgebrochen"
                    break
                if time.perf_counter() > end:
                    why = "Zeitlimit"
                    break
                if self.tel.resets != resets0:
                    if not practice:
                        why = "Reset / Absturz"
                        break
                    joy.idle()                      # respawned: new attempt from the start
                    time.sleep(self._settle())
                    s = self.tel.wait(1.0)
                    resets0 = self.tel.resets
                    attempt += 1
                    self.timer.reset()
                    if s is not None:
                        self.timer.go(s.t)
                    tail = f" (Bestzeit {best:.2f} s)" if best is not None else ""
                    self.live.update(phase="racing", message=f"Übung: Versuch {attempt}{tail}")
                    continue
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
    if sys.platform == "darwin":
        return arrange_liftoff_mac(mode)
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


def arrange_liftoff_mac(mode="quarter"):
    """macOS: move/resize the window (no borderless/always-on-top from outside the app)."""
    from . import window_mac
    if window_mac.find_window() is None:
        return False
    sw, sh = window_mac._screen_size()
    if mode == "full":
        return window_mac.arrange(0, 0, int(sw), int(sh))
    w = int(sw) // 2
    target = (0, 25, w, w * 9 // 16 + window_mac.TITLE_BAR)
    if window_mac.arrange(*target):
        return True
    # without the Accessibility permission macOS refuses the move; fine if Liftoff is already there
    # (1920x1080 windowed in Liftoff's prefs gives exactly this window, mac/README.md)
    b = window_mac.find_window()["kCGWindowBounds"]
    return all(abs(a - t) <= 2 for a, t in zip((b["X"], b["Y"], b["Width"], b["Height"]), target))


# macOS: Liftoff cannot be kept on top from outside, so one full-screen page would cover it.
# Like on the Windows screen the three areas are separate windows instead: Liftoff top left,
# the autopilot half top right (?view=right), the race control below (?view=panel).
_SAFARI_WINDOW = """
on run {u, x1, y1, x2, y2}
  tell application "Safari"
    set found to missing value
    repeat with w in windows
      try
        if URL of current tab of w is u then set found to w
      end try
    end repeat
    if found is missing value then
      make new document with properties {URL:u}
      set found to front window
    end if
    set bounds of found to {x1 as integer, y1 as integer, x2 as integer, y2 as integer}
  end tell
end run
"""


def arrange_studio_windows_mac(url):
    """Open (or move back) the two Studio windows in Safari around the Liftoff quarter."""
    from . import window_mac
    import AppKit
    sw, sh = (int(v) for v in window_mac._screen_size())
    sh -= int(AppKit.NSScreen.mainScreen().visibleFrame().origin.y)   # stop above the Dock
    split = 25 + (sw // 2) * 9 // 16 + window_mac.TITLE_BAR      # bottom edge of the Liftoff window
    sep = "&" if "?" in url else "?"
    ok = True
    for view, box in (("right", (sw // 2, 25, sw, split)), ("panel", (0, split, sw, sh))):
        r = subprocess.run(["osascript", "-e", _SAFARI_WINDOW, f"{url}{sep}view={view}", *map(str, box)],
                           capture_output=True, text=True)
        if r.returncode:
            print("Safari-Fenster:", r.stderr.strip(), flush=True)
            ok = False
    return ok


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
            if p == "/api/plan":
                return self._send(200, json.dumps(studio.debug_plan()))
            if p == "/api/sim":
                return self._send(200, json.dumps({**studio.sim.state(), "selected": studio.settings.get("simulator")},
                                                  ensure_ascii=False))
            if p == "/api/sim/ghost":
                return self._send(200, json.dumps(studio.sim.ghost()))
            if p == "/api/sim/nn_curve.png":                  # Lernkurve des Netz-Piloten (freefly/train_nn.py)
                from .freefly.nn import MODEL_DIR
                if (MODEL_DIR / "curve.png").exists():
                    return self._send(200, (MODEL_DIR / "curve.png").read_bytes(), "image/png")
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
    if sys.platform == "darwin":
        if Path("/Applications/Safari.app").exists() and arrange_studio_windows_mac(url):
            return
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
