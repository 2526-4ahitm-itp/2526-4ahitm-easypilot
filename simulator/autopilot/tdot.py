"""TDOT race: visitors against the autopilot in several difficulty stages, with live dashboard.

  python -m autopilot.tdot                       # Field Day, 1 lap, dashboard on port 8765
  python -m autopilot.tdot StrawBaleRace02 --laps 2 --port 8765 --key geheim
  python -m autopilot.tdot --direct              # visitors fly with Liftoff's own controller setting

Pages (also from a phone / second PC in the same network):
  http://<pc>:8765/          dashboard for the beamer: live timer, minimap with the bot ghost,
                             stage ladder, leaderboard
  http://<pc>:8765/overlay   compact live overlay (transparent, e.g. OBS browser source)
  http://<pc>:8765/admin     operator: next pilot, stage, start/abort, bot reference runs

Liftoff: Free Flight with the race's track loaded (e.g. Quick Play > Freeflight > 01 - Field Day).
Every run - human or bot - is timed the same way: reset to the spawn, 3-2-1 countdown on the
dashboard (sticks held at zero), GO, then every gate of the race in order through its opening;
the time ends in the finish gate. Liftoff's own timer is not used.
"""
import json
import math
import queue
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .liftoff import RUNS, Session, key_down, VK_F9
from .race import course
from .telemetry import Telemetry
from .track import load_race_with_track, race_gates

WEB = Path(__file__).resolve().parent / "dashboard"
DATA = RUNS / "tdot"


@dataclass
class Stage:
    level: int
    name: str
    aggressiveness: float
    color: str


STAGES = [
    Stage(1, "Einsteiger", 0.25, "#4caf50"),
    Stage(2, "Fortgeschritten", 0.40, "#8bc34a"),
    Stage(3, "Profi", 0.60, "#ffc107"),
    Stage(4, "Champion", 0.80, "#ff7043"),
    Stage(5, "Maschine", 1.00, "#e53935"),
]


def stage(level):
    return next(s for s in STAGES if s.level == int(level))


class LapTimer:
    """Times a run through a gate sequence from telemetry states (simulator clock)."""

    def __init__(self, sequence):
        self.seq = sequence
        self.reset()

    def reset(self):
        self.running = False
        self.finished = False
        self.t0 = None
        self.t_now = 0.0
        self.next = 0
        self.splits = []
        self.prev = None
        self.path = []          # (t, x, z) every 50 ms for the ghost / minimap

    def go(self, sim_t):
        self.reset()
        self.running = True
        self.t0 = sim_t

    def feed(self, s):
        if not self.running:
            return
        self.t_now = s.t - self.t0
        if self.prev is not None and self.next < len(self.seq):
            p0, t_prev = self.prev
            g = self.seq[self.next]
            if g.crossed(p0, s.pos):
                a = sum((p - c) * n for p, c, n in zip(p0, g.center, g.normal))
                b = sum((p - c) * n for p, c, n in zip(s.pos, g.center, g.normal))
                frac = a / (a - b) if a != b else 1.0
                self.splits.append(round(t_prev + (s.t - t_prev) * frac - self.t0, 3))
                self.next += 1
                if self.next == len(self.seq):
                    self.finished = True
                    self.running = False
        if not self.path or self.t_now - self.path[-1][0] >= 0.05:
            self.path.append((round(self.t_now, 2), round(s.pos[0], 2), round(s.pos[2], 2)))
        self.prev = (s.pos, s.t)

    @property
    def time(self):
        return self.splits[-1] if self.finished else None


class Leaderboard:
    """Persistent results: best bot run per stage (with splits and path for the ghost) + all human runs."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.data = {"bot": {}, "runs": []}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def bot(self, level):
        return self.data["bot"].get(str(level))

    def add_bot(self, level, time_s, splits, path):
        with self.lock:
            best = self.bot(level)
            if best is None or time_s < best["time"]:
                self.data["bot"][str(level)] = {"time": time_s, "splits": splits, "path": path,
                                                "date": time.strftime("%Y-%m-%d %H:%M")}
                self.save()
                return True
            return False

    def add_run(self, name, level, time_s, splits):
        bot = self.bot(level)
        entry = {"id": uuid.uuid4().hex[:8], "name": name, "stage": int(level), "time": time_s, "splits": splits,
                 "beat_bot": bool(bot and time_s is not None and time_s < bot["time"]),
                 "date": time.strftime("%Y-%m-%d %H:%M")}
        with self.lock:
            self.data["runs"].append(entry)
            self.save()
        return entry

    def delete(self, run_id):
        with self.lock:
            self.data["runs"] = [r for r in self.data["runs"] if r["id"] != run_id]
            self.save()

    def summary(self, top=10):
        runs = [r for r in self.data["runs"] if r["time"] is not None]
        best = {}
        for r in sorted(runs, key=lambda r: r["time"]):        # one line per pilot: their best time
            best.setdefault(r["name"].strip().lower(), r)
        ranking = sorted(best.values(), key=lambda r: r["time"])[:top]
        stages = []
        for st in STAGES:
            b = self.bot(st.level)
            beaten = sorted({r["name"] for r in runs if b and r["time"] < b["time"]})
            stages.append({"level": st.level, "name": st.name, "color": st.color, "aggressiveness": st.aggressiveness,
                           "bot_time": b["time"] if b else None, "beaten_by": beaten,
                           "attempts": sum(1 for r in self.data["runs"] if r["stage"] == st.level)})
        return {"ranking": ranking, "stages": stages,
                "recent": list(reversed(self.data["runs"][-8:])), "runs_total": len(self.data["runs"])}


class Event:
    def __init__(self, race_name="StrawBaleRace01", laps=1, direct=False, settle=1.5, timeout=180.0):
        race, track = load_race_with_track(race_name)
        self.race_name, self.title = race_name, race["name"]
        self.gates = race_gates(race, track)
        self.seq = course(self.gates, laps)
        self.laps, self.direct, self.settle, self.timeout = laps, direct, settle, timeout
        self.board = Leaderboard(DATA / f"{race_name}-{laps}lap.json")
        self.timer = LapTimer(self.seq)
        self.tel = Telemetry(on_state=self._on_state)
        self.tel.start()
        self.lock = threading.Lock()
        self.commands = queue.Queue()
        self.abort = threading.Event()
        self.live = {"phase": "idle", "pilot": None, "kind": None, "stage": None, "countdown": 0, "message": "",
                     "pos": None, "speed": 0.0}
        self.last_result = None
        self.spawn = None
        self.queue_list = []          # waiting pilots (name, stage) shown on the dashboard
        threading.Thread(target=self._worker, daemon=True).start()

    # ---------------------------------------------------------------- telemetry
    def _on_state(self, s):
        self.timer.feed(s)
        self.live["pos"] = (round(s.pos[0], 2), round(s.pos[2], 2))
        self.live["speed"] = round(s.speed * 3.6, 1)

    # ---------------------------------------------------------------- state for the web pages
    def state(self):
        t = self.timer
        st = self.live["stage"]
        bot = self.board.bot(st) if st else None
        delta = None
        if bot and t.splits:
            i = len(t.splits) - 1
            if i < len(bot["splits"]):
                delta = round(t.splits[i] - bot["splits"][i], 2)
        return {**self.live, "track": self.title, "laps": self.laps,
                "elapsed": round(t.t_now, 2) if (t.running or t.finished) else 0.0,
                "gate": t.next, "gates_total": len(self.seq), "splits": t.splits, "delta": delta,
                "bot_time": bot["time"] if bot else None, "last_result": self.last_result,
                "waiting": self.queue_list, "board": self.board.summary()}

    def track_info(self):
        pts = [g.center for g in self.gates]
        xs, zs = [p[0] for p in pts], [p[2] for p in pts]
        return {"title": self.title, "gates": [{"x": g.center[0], "z": g.center[2], "nx": g.normal[0], "nz": g.normal[2],
                                                "w": g.width} for g in self.gates],
                "sequence": [self.gates.index(g) for g in self.seq],
                "bounds": [min(xs) - 15, min(zs) - 15, max(xs) + 15, max(zs) + 15],
                "stages": [s.__dict__ for s in STAGES],
                "ghosts": {str(s.level): (self.board.bot(s.level) or {}).get("path") for s in STAGES}}

    # ---------------------------------------------------------------- commands
    def submit(self, cmd):
        if cmd.get("action") == "abort":
            self.abort.set()
            return {"ok": True}
        if cmd.get("action") == "delete":
            self.board.delete(cmd.get("id", ""))
            return {"ok": True}
        if cmd.get("action") == "dequeue":
            self.queue_list = [q for q in self.queue_list if q["id"] != cmd.get("id")]
            return {"ok": True}
        if cmd.get("action") not in ("human", "bot"):
            return {"ok": False, "error": "unknown action"}
        try:
            stage(cmd.get("stage", 1))
        except StopIteration:
            return {"ok": False, "error": "unknown stage"}
        cmd["id"] = uuid.uuid4().hex[:6]
        if cmd["action"] == "human":
            cmd["name"] = (cmd.get("name") or "").strip()[:24] or "Gast"
        self.queue_list.append({"id": cmd["id"], "name": cmd.get("name", "Autopilot"), "stage": int(cmd["stage"]),
                                "kind": cmd["action"]})
        self.commands.put(cmd)
        return {"ok": True, "id": cmd["id"]}

    def _worker(self):
        while True:
            cmd = self.commands.get()
            if not any(q["id"] == cmd["id"] for q in self.queue_list):
                continue                                  # removed from the queue meanwhile
            self.queue_list = [q for q in self.queue_list if q["id"] != cmd["id"]]
            self.abort.clear()
            try:
                if cmd["action"] == "bot":
                    self.run_bot(int(cmd["stage"]))
                else:
                    self.run_human(cmd["name"], int(cmd["stage"]))
            except Exception as exc:          # keep the event running whatever happens
                self.live.update(phase="error", message=repr(exc))
                print("run failed:", repr(exc))

    # ---------------------------------------------------------------- runs
    def _reset(self, joy):
        """Respawn with the Liftoff reset button; vJoy taps get lost now and then, so check and retry."""
        from .vjoy import BTN_RESET
        for _ in range(3):
            joy.idle()
            before = self.tel.resets
            joy.tap(BTN_RESET, 0.15)
            end = time.perf_counter() + 2.0
            while time.perf_counter() < end and self.tel.resets == before:
                time.sleep(0.02)
            if self.tel.resets != before:
                time.sleep(self.settle)
                s = self.tel.wait(1.0)
                if s is not None:
                    self.spawn = s.pos
                return True
            s = self.tel.latest(0.5)
            if s is not None and self.spawn is not None and math.dist(s.pos, self.spawn) < 1.0:
                return True                       # already standing at the spawn point
            time.sleep(0.5)
        return False

    def _prepare(self, kind, name, level, joy):
        self.timer.reset()
        self.live.update(phase="ready", pilot=name, kind=kind, stage=level, countdown=0, message="")
        if joy is not None and not self._reset(joy):
            self.live.update(phase="error", message="Reset kommt nicht an - Liftoff im Vordergrund?")
            return None
        for n in (3, 2, 1):
            self.live.update(phase="countdown", countdown=n)
            if self.abort.wait(1.0):
                return None
        s = self.tel.wait(2.0)
        if s is None or max(abs(v) for v in s.pos) < 1e-3:
            self.live.update(phase="error", message="Keine Telemetrie - ist Liftoff im Free Flight?")
            return None
        self.timer.go(s.t)
        self.live.update(phase="racing", countdown=0)
        return s

    def _finish(self, kind, name, level, why):
        t = self.timer
        t.running = False
        result = {"kind": kind, "name": name, "stage": level, "time": t.time, "gates": t.next,
                  "gates_total": len(self.seq), "reason": why}
        bot = self.board.bot(level)
        if kind == "bot" and t.time is not None:
            result["new_reference"] = self.board.add_bot(level, t.time, t.splits, t.path)
        elif kind == "human":
            entry = self.board.add_run(name, level, t.time, t.splits)
            result["beat_bot"] = entry["beat_bot"]
            result["bot_time"] = bot["time"] if bot else None
            result["id"] = entry["id"]
        self.last_result = result
        self.live.update(phase="finished" if t.time is not None else "dnf", message=why)
        print("result:", json.dumps(result))
        return result

    def run_bot(self, level):
        from .race import fly
        st = stage(level)
        sess = Session(f"tdot-bot{level}", tel=self.tel)
        time.sleep(0.5)
        s = self._prepare("bot", f"Autopilot – {st.name}", level, sess.joy)
        if s is None:
            sess.close()
            return self._finish("bot", f"Autopilot – {st.name}", level, self.live["message"] or "abgebrochen")
        done = {"why": ""}

        def on_step(state, racer):
            if self.abort.is_set() or self.timer.finished:
                racer.progress.finished = True        # ends sess.loop through racer.done
                done["why"] = "abgebrochen" if self.abort.is_set() else ""
        res = fly(sess, self.gates, self.laps, st.aggressiveness, on_step=on_step)
        why = done["why"] or ("" if self.timer.finished else res.get("reason", ""))
        return self._finish("bot", f"Autopilot – {st.name}", level, why or "im Ziel")

    def run_human(self, name, level):
        if self.direct:
            return self._run_human_direct(name, level)
        from .pilot import Controller
        from .vjoy import VJoy
        ctl = Controller()
        joy = VJoy()
        time.sleep(0.5)
        try:
            s = self._prepare("human", name, level, joy)
            if s is None:
                return self._finish("human", name, level, self.live["message"] or "abgebrochen")
            resets0 = self.tel.resets
            end = time.perf_counter() + self.timeout
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

    def _run_human_direct(self, name, level):
        """Visitor flies with Liftoff's own controller setting: start = leaving the spawn after a reset."""
        self.timer.reset()
        self.live.update(phase="ready", pilot=name, kind="human", stage=level, countdown=0,
                         message="Reset drücken, dann losfliegen")
        resets0 = self.tel.resets
        spawn = None
        end = time.perf_counter() + self.timeout
        while True:
            if self.abort.is_set() or time.perf_counter() > end:
                return self._finish("human", name, level, "abgebrochen")
            s = self.tel.latest(0.5)
            if s is not None:
                if self.tel.resets != resets0 or spawn is None:
                    spawn, resets0 = s.pos, self.tel.resets
                elif math.dist(s.pos, spawn) > 0.3:
                    self.timer.go(s.t)
                    break
            time.sleep(0.005)
        self.live.update(phase="racing", message="")
        resets0 = self.tel.resets
        while not self.timer.finished:
            if self.abort.is_set() or time.perf_counter() > end:
                return self._finish("human", name, level, "abgebrochen")
            if self.tel.resets != resets0:
                return self._finish("human", name, level, "Reset / Absturz")
            time.sleep(0.01)
        return self._finish("human", name, level, "im Ziel")


def make_handler(event, admin_key):
    pages = {"/": "index.html", "/overlay": "overlay.html", "/admin": "admin.html"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in pages:
                return self._send(200, (WEB / pages[url.path]).read_bytes(), "text/html; charset=utf-8")
            if url.path.startswith("/static/"):
                f = (WEB / url.path[len("/static/"):]).resolve()
                if WEB.resolve() in f.parents and f.exists():
                    ctype = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}.get(f.suffix,
                                                                                                    "application/octet-stream")
                    return self._send(200, f.read_bytes(), ctype + "; charset=utf-8")
            if url.path == "/api/state":
                return self._send(200, json.dumps(event.state(), ensure_ascii=False))
            if url.path == "/api/track":
                return self._send(200, json.dumps(event.track_info(), ensure_ascii=False))
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
            self._send(200, json.dumps(event.submit(cmd), ensure_ascii=False))

    return Handler


def main(argv):
    opts = {"--laps": "1", "--port": "8765", "--key": "", "--settle": "1.5"}
    args, i = [], 0
    while i < len(argv):
        if argv[i] in opts:
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            args.append(argv[i])
            i += 1
    direct = "--direct" in args
    args = [a for a in args if not a.startswith("--")]
    event = Event(args[0] if args else "StrawBaleRace01", laps=int(opts["--laps"]), direct=direct,
                  settle=float(opts["--settle"]))
    server = ThreadingHTTPServer(("0.0.0.0", int(opts["--port"])), make_handler(event, opts["--key"]))
    print(f"{event.title}: {len(event.seq)} Tore, {event.laps} Runde(n)")
    print(f"Dashboard  http://localhost:{opts['--port']}/")
    print(f"Overlay    http://localhost:{opts['--port']}/overlay")
    print(f"Bedienung  http://localhost:{opts['--port']}/admin" + (f"?key={opts['--key']}" if opts["--key"] else ""))
    print("Konsole: 'bot <stufe>', 'mensch <stufe> <name>', 'stop', 'quit'")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for line in sys.stdin:
            parts = line.split()
            if not parts:
                continue
            if parts[0] == "quit":
                break
            if parts[0] == "stop":
                print(event.submit({"action": "abort"}))
            elif parts[0] == "bot" and len(parts) > 1:
                print(event.submit({"action": "bot", "stage": parts[1]}))
            elif parts[0] == "mensch" and len(parts) > 2:
                print(event.submit({"action": "human", "stage": parts[1], "name": " ".join(parts[2:])}))
            else:
                print("?")
        else:
            while True:            # no console (started in the background): keep serving
                time.sleep(3600)
    except KeyboardInterrupt:
        pass
    server.shutdown()


if __name__ == "__main__":
    main(sys.argv[1:])
