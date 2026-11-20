"""EasyPilot Studio für den eigenen Simulator (autopilot/freefly): zweite Simulator-Wahl neben Liftoff.

Das Studio startet den Sim als eigenen Prozess (Fenster oben links, --remote PORT) und steuert ihn über
freefly/remote.py: Modus (Rennen / Bomben), Autopilot-Art (Rennlinie / Nur Kamera / Bomben), Tempo k,
Runden bzw. Ziele, Strecke (freefly/tracks.py), Mensch oder Autopilot. Jeder Lauf hat Countdown, Zeit, Torzeiten
und landet in der Bestenliste der Strecke; der beste Autopilot-Lauf je Art und k ist die Referenz (Zeit, Torzeiten,
Geist auf der Karte).
Ein Sim, der schon mit --remote läuft (z. B. von Hand gestartet), wird einfach verbunden.
"""
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from .freefly import tracks
from .freefly.remote import DEFAULT_PORT, SimClient

ROOT = Path(__file__).resolve().parent.parent          # simulator/
DEFAULTS = {"mode": "race", "ap_mode": "line", "ap_k": 0.6, "laps": 1, "targets": 5, "timeout": 180, "strecke": "dorfrunde"}
AP_NAMES = {"line": "Rennlinie", "camera": "Nur Kamera", "nn": "Neuronales Netz", "bomb": "Bomben"}
TITLE_BAR = 28           # macOS-Fenster: Titelleiste über dem Bild (wie window_mac.TITLE_BAR)


def _nn_status():
    """Trainings-, Lern- und Versuchs-Stand des Netz-Piloten (freefly/nn_show.py) fürs Studio."""
    from .freefly.nn_show import studio_status
    return studio_status()


def screen_size():
    if sys.platform == "darwin":
        try:
            import Quartz
            b = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
            return int(b.size.width), int(b.size.height)
        except Exception:
            pass
    return 1920, 1080


def quarter():
    """Sim-Bild oben links, gleiche Fläche wie das Liftoff-Fenster (halbe Breite, 16:9)."""
    sw, _ = screen_size()
    w = sw // 2
    return 0, 25 + TITLE_BAR, w, w * 9 // 16


class SimBoard:
    """Bestenliste je Modus und Länge: beste Autopilot-Läufe je Art/k (Referenz mit Torzeiten und Pfad) + alle Läufe."""

    def __init__(self, path, bomb=False):
        self.path, self.bomb = Path(path), bomb
        self.lock = threading.Lock()
        self.data = {"bot": {}, "runs": []}
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def better(self, a, b):
        """Ist Lauf a besser als b? Rennen: Zeit; Bomben: mehr Treffer, dann Zeit."""
        if b is None:
            return True
        if self.bomb:
            return (a.get("hits", 0), -(a["time"] or 1e9)) > (b.get("hits", 0), -(b["time"] or 1e9))
        return a["time"] < b["time"]

    def bot(self, key):
        return self.data["bot"].get(key)

    def add_bot(self, key, entry):
        with self.lock:
            if self.better(entry, self.bot(key)):
                self.data["bot"][key] = {**entry, "date": time.strftime("%Y-%m-%d %H:%M")}
                self.save()
                return True
        return False

    def add_run(self, entry, key):
        ref = self.bot(key)
        e = {"id": uuid.uuid4().hex[:8], **entry, "vs": key, "date": time.strftime("%Y-%m-%d %H:%M"),
             "beat_bot": bool(ref and entry["time"] is not None and self.better(entry, ref))}
        with self.lock:
            self.data["runs"].append(e)
            self.save()
        return e

    def delete(self, run_id):
        with self.lock:
            self.data["runs"] = [r for r in self.data["runs"] if r["id"] != run_id]
            self.save()

    def summary(self, top=10):
        runs = [r for r in self.data["runs"] if r["time"] is not None and r.get("kind") == "human"]
        key = (lambda r: (-r.get("hits", 0), r["time"])) if self.bomb else (lambda r: r["time"])
        best = {}
        for r in sorted(runs, key=key):
            best.setdefault(r["name"].strip().lower(), r)
        refs = [{"key": k, **{f: v.get(f) for f in ("time", "hits", "name", "ap_mode", "k", "date")}}
                for k, v in sorted(self.data["bot"].items())]
        return {"ranking": sorted(best.values(), key=key)[:top], "refs": refs,
                "recent": list(reversed(self.data["runs"][-8:]))}


class SimStudio:
    def __init__(self, data_dir, port=DEFAULT_PORT):
        self.dir = Path(data_dir) / "sim"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.dir / "settings.json"
        self.settings = dict(DEFAULTS)
        try:
            self.settings.update(json.loads(self.settings_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        self.port = port
        self.proc = None
        self.client = SimClient(port, on_event=self._event)
        self.commands = queue.Queue()
        self.abort = threading.Event()
        self.queue_list = []
        self.live = {"phase": "idle", "pilot": None, "kind": None, "countdown": 0, "message": ""}
        self.run = None
        self.last_result = None
        self.events = []                 # die letzten Ereignisse für die Seite
        self._ctl = (0.0, None)
        self._boards = {}
        self.client.connect(0.2)         # läuft schon ein Sim mit --remote?
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._sampler, daemon=True).start()

    # ---------------------------------------------------------------- settings, boards
    def save_settings(self):
        self.settings_path.write_text(json.dumps(self.settings, indent=1), encoding="utf-8")

    def kind(self):
        """Autopilot-Art für den aktuellen Modus."""
        return "bomb" if self.settings["mode"] == "bomb" else self.settings["ap_mode"]

    def ref_key(self):
        k = self.kind()
        return "bomb" if k == "bomb" else f"{k}-{float(self.settings['ap_k']):.1f}"

    def board(self):
        """Bestenliste je Strecke (Dorfrunde: die bisherige Datei race-Nlap.json) und Rundenzahl."""
        s = self.settings
        tr = tracks.key(s.get("strecke"))
        name = f"bomb-{int(s['targets'])}ziele.json" if s["mode"] == "bomb" else \
            f"race-{int(s['laps'])}lap.json" if tr == "dorfrunde" else f"race-{tr}-{int(s['laps'])}lap.json"
        if name not in self._boards:
            self._boards[name] = SimBoard(self.dir / name, bomb=s["mode"] == "bomb")
        return self._boards[name]

    def gates_total(self):
        if self.settings["mode"] == "bomb":
            return int(self.settings["targets"])
        n = len((self.client.hello or {}).get("gates") or []) or 12
        return n * int(self.settings["laps"]) + 1          # Runden + zurück durchs Starttor

    def sim_settings(self):
        s = self.settings
        return {"mode": s["mode"], "ap_mode": s["ap_mode"], "ap_k": float(s["ap_k"]), "strecke": tracks.key(s.get("strecke"))}

    # ---------------------------------------------------------------- process
    def running(self):
        return self.client.connected

    def start_sim(self):
        if self.client.connect(0.2):
            return {"ok": True}
        if self.proc is not None and self.proc.poll() is None:
            return {"ok": True, "starting": True}
        x, y, w, h = quarter()
        env = dict(os.environ, SDL_VIDEO_WINDOW_POS=f"{x},{y}", PYTHONUNBUFFERED="1")
        log = open(self.dir / "freefly.log", "w", encoding="utf-8")
        self.proc = subprocess.Popen([sys.executable, "-m", "autopilot.freefly", "--window", "--size", f"{w}x{h}",
                                      "--remote", str(self.port)], cwd=str(ROOT), env=env, stdout=log,
                                     stderr=subprocess.STDOUT)
        self.live.update(phase="starting", message="Sim startet …")

        def wait():
            end = time.time() + 40
            while time.time() < end and self.proc is not None and self.proc.poll() is None:
                if self.client.connect(0.3):
                    time.sleep(0.3)
                    self.client.send(cmd="settings", **self.sim_settings())
                    self.live.update(phase="idle", message="")
                    return
                time.sleep(0.3)
            self.live.update(phase="error", message=f"Sim startet nicht (Log: {self.dir / 'freefly.log'})")
        threading.Thread(target=wait, daemon=True).start()
        return {"ok": True, "starting": True}

    def stop_sim(self):
        self.abort.set()
        self.queue_list.clear()
        self.client.send(cmd="quit")
        p, self.proc = self.proc, None
        if p is not None:
            try:
                p.wait(4)
            except subprocess.TimeoutExpired:
                p.terminate()
        self.client.close()
        self.live.update(phase="idle", message="", pilot=None, kind=None)
        return {"ok": True}

    def arrange(self):
        x, y, w, h = quarter()
        return self.client.send(cmd="window", x=x, y=y, w=w, h=h)

    # ---------------------------------------------------------------- commands from the page
    def submit(self, cmd):
        a = cmd.get("action")
        if a == "sim_start":
            return self.start_sim()
        if a == "sim_stop":
            return self.stop_sim()
        if a == "sim_show":                 # KI-Showcase im Sim: Lernen zuschauen / Zeitraffer / aus (nn_show.py)
            if not self.client.connected:
                return {"ok": False, "error": "Der Sim läuft nicht – erst „Sim starten“."}
            mode = {"learn": "nn_learn", "replay": "nn_replay"}.get(cmd.get("show"))
            self.abort.set()
            self.queue_list.clear()
            if mode:
                self.settings.update(mode="race", ap_mode="nn")
                self.save_settings()

            def go():                       # erst den laufenden Studio-Lauf enden lassen (der schickt "stop")
                end = time.time() + 4.0
                while self.live["phase"] in ("ready", "countdown", "racing") and time.time() < end:
                    time.sleep(0.05)
                time.sleep(0.2)
                self.client.send(cmd="settings", mode="race", ap_mode=mode or "nn", auto=bool(mode))
            threading.Thread(target=go, daemon=True).start()
            return {"ok": True}
        if a == "sim_abort":
            self.abort.set()
            self.queue_list.clear()
            return {"ok": True}
        if a == "sim_delete":
            self.board().delete(cmd.get("id", ""))
            return {"ok": True}
        if a == "sim_settings":
            for k in DEFAULTS:
                if k in cmd and cmd[k] is not None:
                    self.settings[k] = cmd[k]
            self.settings["ap_k"] = round(max(0.2, min(1.2, float(self.settings["ap_k"]))), 1)
            self.settings["strecke"] = tracks.key(self.settings.get("strecke"))
            self.save_settings()
            if self.live["phase"] not in ("ready", "countdown", "racing"):
                self.client.send(cmd="settings", **self.sim_settings())
            return {"ok": True}
        if a not in ("sim_bot", "sim_human"):
            return {"ok": False, "error": "unknown action"}
        if not self.client.connected:
            return {"ok": False, "error": "Der Sim läuft nicht – erst „Sim starten“."}
        c = {"id": uuid.uuid4().hex[:6], "kind": "bot" if a == "sim_bot" else "human"}
        c["name"] = ((cmd.get("name") or "").strip()[:24] or "Gast") if c["kind"] == "human" else self.bot_name()
        self.queue_list.append({"id": c["id"], "kind": c["kind"], "name": c["name"]})
        self.commands.put(c)
        return {"ok": True, "id": c["id"]}

    def bot_name(self):
        k = self.kind()
        return f"Autopilot – {AP_NAMES[k]}" + ("" if k == "bomb" else f" k={float(self.settings['ap_k']):.1f}")

    def _worker(self):
        while True:
            c = self.commands.get()
            if not any(q["id"] == c["id"] for q in self.queue_list):
                continue
            self.queue_list = [q for q in self.queue_list if q["id"] != c["id"]]
            self.abort.clear()
            try:
                self.fly(c["kind"], c["name"])
            except Exception as exc:
                import traceback
                traceback.print_exc()
                self.live.update(phase="error", message=repr(exc)[:200])
                self.run = None

    # ---------------------------------------------------------------- runs
    def fly(self, kind, name):
        s = self.settings
        bomb = s["mode"] == "bomb"
        self.live.update(phase="ready", pilot=name, kind=kind, countdown=0, message="")
        self.last_result = None
        self.run = None
        self.client.send(cmd="prepare", auto=kind == "bot", **self.sim_settings())
        if not self._wait_tel(lambda t: t.get("hold"), 30):
            return self._finish(kind, name, "Sim reagiert nicht")
        for n in (3, 2, 1):
            self.live.update(phase="countdown", countdown=n)
            self.client.send(cmd="say", text=str(n), sub=name, s=1.0)
            if self.abort.wait(1.0):
                self.client.send(cmd="stop")
                return self._finish(kind, name, "abgebrochen")
        tel = self.client.latest() or {}
        self.run = {"t0": None, "base": 0.0, "last_t": 0.0, "splits": [], "path": [], "finished": False, "end": None,
                    "bomb": bomb, "hits": 0, "misses": 0, "sim_m": 0, "target": None,
                    "total": self.gates_total(), "key": self.ref_key(), "start_gate": tel.get("next_gate", 0)}
        self.client.send(cmd="go")
        self.client.send(cmd="say", text="Los!", sub=None, s=1.0)
        self.live.update(phase="racing", countdown=0)
        if kind == "human":
            limit = float(s.get("timeout", 180))
        elif bomb:
            limit = 45.0 * int(s["targets"])
        else:                  # Kamera-Pilot fliegt 10*k m/s, eine Runde ist ~1,4 km
            limit = (90.0 if s["ap_mode"] in ("line", "nn") else 1600.0 / (10 * float(s["ap_k"])) + 60) * int(s["laps"])
        start = time.time()
        while True:
            r = self.run
            if r["end"]:
                why = r["end"]
                break
            if self.abort.is_set():
                why = "abgebrochen"
                break
            if not self.client.connected:
                why = "Sim beendet"
                break
            if time.time() - start > limit:
                why = "Zeitlimit"
                break
            time.sleep(0.02)
        self.run["stopped_at"] = self.elapsed()        # Uhr bleibt stehen (auch nach dem Respawn)
        if why != "im Ziel" or kind == "bot":
            self.client.send(cmd="stop")
        return self._finish(kind, name, why)

    def _wait_tel(self, cond, timeout):
        end = time.time() + timeout
        while time.time() < end:
            t = self.client.latest(0.5)
            if t is not None and cond(t):
                return True
            if self.abort.wait(0.05):
                return False
        return False

    def elapsed(self):
        r = self.run
        if r is None or r["t0"] is None:
            return 0.0
        if r.get("time") is not None:
            return r["time"]
        if r.get("stopped_at") is not None:
            return r["stopped_at"]
        tel = self.client.latest()
        t = tel["t"] if tel else r["last_t"]
        return round(r["base"] + max(0.0, t - r["t0"]), 3)

    def _event(self, ev):
        """Ereignisse aus dem Sim (Client-Thread)."""
        e = ev.get("ev")
        self.events = (self.events + [{**ev, "at": round(time.time(), 2)}])[-20:]
        r = self.run
        if r is None or r["end"]:
            return
        if e == "go":
            r["t0"], r["last_t"] = ev.get("t", 0.0), ev.get("t", 0.0)
            r["target"] = ev.get("target")
            r["t_target"] = 0.0
            r["sim_m"] = ev.get("misses", 0)
            return
        if r["t0"] is None:
            return
        t = ev.get("t")
        if t is not None:
            r["last_t"] = t
        now = round(r["base"] + (r["last_t"] - r["t0"]), 3)
        if r["bomb"]:
            if e == "crash":
                took = round(now - r.get("t_target", 0.0), 2)
                if ev.get("hit"):
                    r["hits"] += 1
                else:
                    r["misses"] += 1
                r["splits"].append({"t": now, "took": took, "hit": bool(ev.get("hit")), "what": ev.get("reason", ""),
                                    "target": r["target"]})
                r["sim_m"] = ev.get("misses", r["sim_m"])
            elif e == "respawn":            # nach Treffer/Absturz: weiter vom Startplatz, Flugzeit beginnt bei 0
                r["base"] += r["last_t"] - r["t0"]
                r["t0"] = r["last_t"] = 0.0
            elif e == "target":
                if ev.get("misses", 0) > r["sim_m"] and r["target"] is not None:   # Zeit um (zählt der Sim als daneben)
                    r["misses"] += 1
                    r["splits"].append({"t": now, "took": round(now - r.get("t_target", 0.0), 2), "hit": False,
                                        "what": "Zeit um", "target": r["target"]})
                r["sim_m"] = ev.get("misses", r["sim_m"])
                r["target"] = ev.get("name")
                r["t_target"] = now
            if len(r["splits"]) >= r["total"]:
                r["time"] = r["splits"][-1]["t"]
                r["end"] = "im Ziel"
            return
        if e == "gate":
            r["splits"].append(now)
            if len(r["splits"]) >= r["total"]:
                r["time"] = now
                r["end"] = "im Ziel"
        elif e == "crash":
            r["end"] = f"Absturz: {ev.get('reason', '')}"
        elif e == "respawn":
            r["end"] = r["end"] or "Neustart im Sim"

    def _sampler(self):
        """Pfad des laufenden Laufs (Geist, Karte) alle 50 ms aus der Telemetrie."""
        while True:
            time.sleep(0.05)
            r, tel = self.run, self.client.latest(0.3)
            if r is None or r["end"] or r["t0"] is None or tel is None or self.live["phase"] != "racing":
                continue
            p = tel["pos"]
            if not r["path"] or math.hypot(p[0] - r["path"][-1][1], p[2] - r["path"][-1][2]) > 0.2:
                r["path"].append((round(self.elapsed(), 2), round(p[0], 2), round(p[2], 2)))
                if len(r["path"]) > 20000:
                    del r["path"][::2]

    def _finish(self, kind, name, why):
        r = self.run or {}
        t = r.get("time")
        bomb = self.settings["mode"] == "bomb"
        res = {"kind": kind, "name": name, "time": t, "reason": why, "mode": self.settings["mode"],
               "gates": len(r.get("splits", [])), "gates_total": r.get("total", self.gates_total()),
               "hits": r.get("hits", 0), "misses": r.get("misses", 0), "key": r.get("key", self.ref_key())}
        board = self.board()
        ref = board.bot(res["key"])
        if t is not None:
            entry = {"name": name, "kind": kind, "time": t, "splits": r["splits"], "hits": r.get("hits", 0),
                     "misses": r.get("misses", 0), "ap_mode": self.kind(), "k": float(self.settings["ap_k"])}
            if kind == "bot":
                res["new_reference"] = board.add_bot(res["key"], {**entry, "path": r["path"][::2]})
                board.add_run(entry, res["key"])
            else:
                e = board.add_run(entry, res["key"])
                res.update(beat_bot=e["beat_bot"], id=e["id"])
            res["bot_time"] = ref["time"] if ref else None
            res["bot_hits"] = ref.get("hits") if ref else None
        elif bomb and r.get("splits"):
            res["time_partial"] = r["splits"][-1]["t"]
        self.last_result = res
        self.live.update(phase="finished" if t is not None else "dnf", message=why)
        print("sim result:", json.dumps({k: v for k, v in res.items()}, ensure_ascii=False), flush=True)
        return res

    # ---------------------------------------------------------------- state for the page
    def controllers(self):
        if time.time() - self._ctl[0] > 2.0:
            try:
                from .pilot import calibrated, controllers
                self._ctl = (time.time(), {"connected": [n for _, n in controllers()], "calibrated": calibrated()})
            except Exception as exc:
                self._ctl = (time.time(), {"connected": [], "calibrated": False, "error": repr(exc)})
        return self._ctl[1]

    def ghost(self):
        ref = self.board().bot(self.run["key"] if self.run else self.ref_key())
        return (ref or {}).get("path") or []

    def state(self):
        board = self.board()
        key = self.run["key"] if self.run else self.ref_key()
        ref = board.bot(key)
        r = self.run
        splits = r["splits"] if r else []
        delta = None
        if r and not r["bomb"] and ref and splits and len(splits) <= len(ref.get("splits", [])):
            delta = round(splits[-1] - ref["splits"][len(splits) - 1], 2)
        tel = self.client.latest()
        hello = self.client.hello or {}
        return {**self.live, "settings": self.settings, "kind_ap": self.kind(), "ref_key": key,
                "tracks": tracks.summary(), "track": hello.get("track") or {"key": "dorfrunde", "name": "Dorfrunde", "stars": 2},
                "sim": {"running": self.client.connected, "own": self.proc is not None and self.proc.poll() is None,
                        "starting": self.live["phase"] == "starting", "port": self.port},
                "tel": tel, "gates": (self.client.hello or {}).get("gates", []), "roads": (self.client.hello or {}).get("roads", []),
                "elapsed": self.elapsed(), "splits": splits, "gate": len(splits), "gates_total": r["total"] if r else self.gates_total(),
                "hits": r["hits"] if r else 0, "misses": r["misses"] if r else 0, "target": r["target"] if r else None,
                "delta": delta, "ref": ({k: ref.get(k) for k in ("time", "splits", "hits", "name", "date")} if ref else None),
                "ghost_id": f"{key}|{ref.get('date')}|{ref.get('time')}" if ref and ref.get("path") else None,
                "last_result": self.last_result, "waiting": self.queue_list, "board": board.summary(),
                "controllers": self.controllers(), "events": self.events[-6:],
                "nn": self._nn(tel)}

    def _nn(self, tel):
        """Netz-Stand, wenn das Netz gewählt ist oder im Sim der KI-Showcase läuft (höchstens 2-mal pro Sekunde lesen)."""
        show = tel.get("ap_mode") if tel and tel.get("auto_on") and str(tel.get("ap_mode")).startswith("nn_") else None
        if self.kind() != "nn" and not show:
            return None
        t, cached = getattr(self, "_nn_cache", (0.0, None))
        if time.time() - t > 0.5 or cached is None:
            cached = _nn_status()
            self._nn_cache = (time.time(), cached)
        return {**cached, "show_mode": show}
