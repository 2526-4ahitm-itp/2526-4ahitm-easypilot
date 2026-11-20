"""Showcase für den Netz-Piloten (nn.py): „Lernen zuschauen“, „Zeitraffer“, Einblendungen für Zuschauer.

Autopilot-Modi (Menü „Autopilot-Modus“, Studio):
  nn        Neuronales Netz: bestes Modell, fliegt ohne Rauschen.
  nn_learn  KI: Lernen zuschauen. Das Netz probiert mit etwas Rauschen (wie im PPO-Training), jeder Versuch
            wird aufgezeichnet, daneben lernt nn_learn.py daraus. Nach Absturz / „kein Tor mehr“ startet der
            nächste Versuch von selbst; neue Versionen kommen nur zwischen zwei Versuchen ins Spiel.
  nn_replay KI: Zeitraffer. Gespeicherte Versionen der Reihe nach (v1, v3, v5 … beste), jede mit großer
            Beschriftung „nach 8 min Training“.

Aufzeichnung (Recorder): bei jeder Netz-Entscheidung (15 Hz) Eingabebild (uint8 4x71x128), Flugzustand,
Kritiker-Wissen (Torlage, nur fürs Training), Ausgabe, log-Wahrscheinlichkeit, Belohnung wie in train_nn.Env
(Tor +2, Annäherung, Absturz -3). Ein Versuch wird im Hintergrund-Thread als .npz nach
models/freefly_nn/episodes/ geschrieben (Spiel-Thread kopiert nur Zeiger). Schalter „Netz lernt mit“
(settings["nn_learn"]): aus = nichts speichern, kein Lern-Prozess.

Lern-Prozess: nn_learn.py, wird vom Spiel gestartet (nice, eigene Sitzung), solange ein Sim mit Netz und
„Netz lernt mit“ läuft (Datei learn.want, alle 10 s erneuert). Stand: learn.json; Versuche: show.json.

Einblendungen (settings["nnshow"], Menü „KI-Showcase …“, Taste K = Zuschauer/aus):
  sieht   „Das sieht die KI“: das echte Eingabebild (Farbe + Nähe)
  will    „Das will die KI“: Pfeile/Balken für vor, links/rechts, hoch/runter, drehen
  kurve   Lernkurve: Tore pro Versuch (Zeitraffer: je Version)
  zahlen  Versuch, Bester, heute gelernt, Modell und eigene Flüge
  text    kurze Erklärtexte, wechseln alle paar Sekunden
  geister Zeitraffer: frühere Versionen fliegen als halbdurchsichtige Punkte mit (ihre aufgezeichnete Bahn)
  technik Zahlen für Fachleute (m/s, Rechenzeit, Prüfung)
"""
import csv
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

from .nn import MODEL_DIR, YAW_RATE, heading_axes

EP_DIR = MODEL_DIR / "episodes"
LEARN = MODEL_DIR / "learn.json"
SHOW = MODEL_DIR / "show.json"
WANT = MODEL_DIR / "learn.want"
PIDFILE = MODEL_DIR / "learn.pid"
NOMINAL_STD = 0.1           # Rauschen, mit dem train_nn PPO fliegt (für log p, wenn ohne Rauschen geflogen wird)
LEARN_STD = float(os.environ.get("FREEFLY_NN_RAUSCHEN", 0.1))   # Lernen zuschauen: so viel probiert das Netz aus
NO_GATE_S = 12.0            # wie train_nn: so lange ohne neues Tor -> Versuch zu Ende
MAX_S = 90.0
MAX_GATES = 25
MIN_STEPS = 10              # kürzere Versuche werden nicht gespeichert
MAX_STEPS = int(MAX_S * 15) + 30
MAX_EPISODES = 3000         # älteste Aufzeichnungen darüber werden gelöscht
MAX_BYTES = 6e9             # … und wenn alle zusammen mehr als 6 GB brauchen (ein Flug: ~0,3 MB pro Sekunde)
GAMMA = 0.99

SHOW_MODES = ("nn", "nn_learn", "nn_replay")
ELEMENTS = [("sieht", "Das sieht die KI"), ("will", "Das will die KI"), ("kurve", "Lernkurve"),
            ("zahlen", "Versuch / Bester / gelernt"), ("text", "Erklärtexte"), ("geister", "Geister früherer Versionen"),
            ("technik", "Technik-Zahlen")]
PRESETS = {"zuschauer": {"sieht": True, "will": True, "kurve": True, "zahlen": True, "text": True, "geister": True,
                         "technik": False},
           "technik": {k: True for k, _ in ELEMENTS},
           "klein": {"sieht": True, "will": False, "kurve": False, "zahlen": True, "text": False, "geister": True,
                     "technik": False},
           "aus": {k: False for k, _ in ELEMENTS}}
PRESET_LABEL = {"zuschauer": "Zuschauer", "technik": "Technik", "klein": "Klein", "aus": "Aus"}
MENU = [{"label": "Voreinstellung (K)", "kind": "value", "key": "nns_preset"},
        {"label": "Netz lernt mit", "kind": "toggle", "key": "nn_learn"}] + \
       [{"label": label, "kind": "toggle", "key": "nns:" + k} for k, label in ELEMENTS] + \
       [{"label": "Zurück", "kind": "action", "key": "back"}]

TEXTS = {
    "nn_learn": ["Die KI kennt die Strecke nicht. Sie sieht nur das Kamerabild und lernt aus Fehlern.",
                 "Für jedes Tor gibt es Punkte, für einen Absturz Abzug. So merkt sie, was gut war.",
                 "Jeder Versuch wird gespeichert. Daneben übt ein Lern-Programm damit weiter.",
                 "Eine neue Version fliegt erst, wenn sie in einer Prüfung mindestens so gut war.",
                 "Sie probiert bei jedem Versuch ein wenig anders zu fliegen – daher die Abweichungen."],
    "nn_replay": ["Zeitraffer: dieselbe KI nach unterschiedlich langem Training.",
                  "Am Anfang schaut sie einem Lehrer-Programm zu, danach übt sie ganz allein.",
                  "Die KI kennt die Strecke nicht. Sie sieht nur das Kamerabild."],
    "nn": ["Die KI kennt die Strecke nicht. Sie sieht nur das Kamerabild und lernt aus Fehlern.",
           "Links: genau dieses kleine Bild bekommt das Netz – Farbe und wie nah etwas ist."],
}
PHASE_WORDS = {"imitation": "schaut beim Lehrer ab", "ppo": "übt allein", "online": "lernt aus eigenen Flügen"}


# ============================================================================ Einstellungen / Menü
def ensure(s):
    s.setdefault("nn_learn", True)
    o = s.get("nnshow")
    if not isinstance(o, dict):
        o = dict(PRESETS["zuschauer"])
    for k, _ in ELEMENTS:
        o[k] = bool(o.get(k, PRESETS["zuschauer"][k]))
    s["nnshow"] = o


def preset_of(s):
    for name, p in PRESETS.items():
        if all(s["nnshow"][k] == p[k] for k, _ in ELEMENTS):
            return name
    return None


def menu_values(s):
    p = preset_of(s)
    v = {"nns_preset": PRESET_LABEL[p] if p else "Eigene", "nn_learn": "an" if s.get("nn_learn") else "aus"}
    v.update({"nns:" + k: "an" if s["nnshow"][k] else "aus" for k, _ in ELEMENTS})
    return v


def change(s, key, direction):
    """Menü-Änderung; True, wenn es ein Showcase-Schalter war."""
    if key == "nns_preset":
        order = list(PRESETS)
        p = preset_of(s)
        i = order.index(p) if p else -1
        s["nnshow"] = dict(PRESETS[order[(i + (direction or 1)) % len(order)]])
        return True
    if key.startswith("nns:"):
        k = key[4:]
        s["nnshow"][k] = not s["nnshow"][k]
        return True
    if key == "nn_learn":
        s["nn_learn"] = not s.get("nn_learn")
        return True
    return False


def toggle(s):
    """Taste K: Zuschauer <-> aus."""
    s["nnshow"] = dict(PRESETS["aus" if any(s["nnshow"].values()) else "zuschauer"])


# ============================================================================ Belohnung wie train_nn.Env
def gate_dist(world, next_gate, p):
    g = world.gates[next_gate]
    lx, ly, lz = g.local(p)
    if lz > 0:
        return math.hypot(lx, ly) + lz + 8.0
    return math.dist(p, g.center)


def priv_features(world, next_gate, state, since_gate):
    g = world.gates[next_gate]
    fwd, right = heading_axes(state.quat)
    d = np.subtract(g.center, state.pos)
    n = (math.sin(g.yaw), math.cos(g.yaw))
    lx, ly, lz = g.local(state.pos)
    return np.array([(d[0] * fwd[0] + d[2] * fwd[2]) / 30, (d[0] * right[0] + d[2] * right[2]) / 30, d[1] / 10,
                     n[0] * fwd[0] + n[1] * fwd[2], n[0] * right[0] + n[1] * right[2], lz / 30,
                     next_gate / 12, since_gate / NO_GATE_S], np.float32)


# ============================================================================ Aufzeichnung
class Recorder:
    """Puffert einen Versuch im Speicher, schreibt ihn im Hintergrund als .npz (kein fps-Verlust)."""

    def __init__(self, source, physics):
        self.source, self.physics = source, physics
        self.enabled = True
        self.ep = None
        self.last = None              # Zusammenfassung des letzten Versuchs (für Show)
        self.saved = 0
        self.busy = False
        self.q = queue.Queue(maxsize=6)
        threading.Thread(target=self._writer, daemon=True).start()

    # ------------------------------------------------------------------ Spiel-Thread
    def begin(self, version, explore):
        self.ep = {"version": version, "std": float(explore) if explore > 0 else NOMINAL_STD, "explore": explore,
                   "img": [], "st": [], "priv": [], "act": [], "logp": [], "rew": [], "gates": 0,
                   "t_gate": None, "t0": None, "gate": None, "dprev": None, "keep": self.enabled,
                   "date": time.strftime("%Y-%m-%d %H:%M:%S")}

    def _reward(self, ep, flight):
        r = 0.0
        if flight.next_gate != ep["gate"]:
            ep["gate"] = flight.next_gate
            ep["gates"] += 1
            ep["t_gate"] = flight.flight_time
            r += 2.0
            ep["dprev"] = gate_dist(flight.world, flight.next_gate, flight.drone.pos)
        else:
            dn = gate_dist(flight.world, flight.next_gate, flight.drone.pos)
            r += 0.1 * max(-2.0, min(2.0, ep["dprev"] - dn))
            ep["dprev"] = dn
        return r

    def decision(self, img, st, a, mu, flight, state):
        ep = self.ep
        if ep is None:
            return
        if ep["t0"] is None:
            ep["t0"] = ep["t_gate"] = flight.flight_time
            ep["gate"] = flight.next_gate
            ep["track"] = getattr(flight.world, "track", "dorfrunde")      # Strecke (tracks.py)
            ep["dprev"] = gate_dist(flight.world, flight.next_gate, flight.drone.pos)
        elif ep["img"] or not ep["keep"]:
            r = self._reward(ep, flight)
            if ep["keep"]:
                ep["rew"].append(r)
        if not ep["keep"] or len(ep["img"]) >= MAX_STEPS:
            return
        std = ep["std"]
        d = np.asarray(a, np.float32) - np.asarray(mu, np.float32)
        logp = float(-(d * d).sum() / (2 * std * std) - 4 * (math.log(std) + 0.5 * math.log(2 * math.pi)))
        ep["img"].append(img)
        ep["st"].append(np.asarray(st, np.float32).copy())
        ep["priv"].append(priv_features(flight.world, flight.next_gate, state, flight.flight_time - ep["t_gate"]))
        ep["act"].append(np.asarray(a, np.float32).copy())
        ep["logp"].append(logp)

    def gates(self):
        return self.ep["gates"] if self.ep else 0

    def since_gate(self, flight):
        ep = self.ep
        if ep is None or ep["t_gate"] is None:
            return 0.0
        return flight.flight_time - ep["t_gate"]

    def end(self, flight, reason, crashed=False):
        """Versuch zu Ende. flight=None: abgebrochen (Neustart), keine letzte Belohnung."""
        ep, self.ep = self.ep, None
        if ep is None:
            return None
        if flight is not None and ep["t0"] is not None:
            r = self._reward(ep, flight) - (3.0 if crashed else 0.0)
            if ep["keep"] and ep["img"]:
                ep["rew"].append(r)
        secs = (flight.flight_time - ep["t0"]) if (flight is not None and ep["t0"] is not None) else 0.0
        summary = {"gates": ep["gates"], "reason": reason, "crashed": crashed, "version": ep["version"],
                   "seconds": round(secs, 1), "lap": getattr(flight, "last_lap", None) if flight else None}
        if ep["t0"] is not None and flight is not None:
            self.last = summary
        n = len(ep["img"])
        if not ep["keep"] or n < MIN_STEPS or flight is None and n < 3 * MIN_STEPS:
            return summary if flight is not None else None
        while len(ep["rew"]) < n:
            ep["rew"].append(0.0)
        ep["rew"] = ep["rew"][:n]
        meta = {**summary, "source": self.source, "physics": self.physics, "track": ep.get("track", "dorfrunde"),
                "std": ep["std"], "terminal": flight is not None,
                "explore": ep["explore"], "date": ep["date"], "steps": n}
        try:
            self.q.put_nowait((ep, meta))
        except queue.Full:                # Platte zu langsam: lieber einen Versuch verwerfen als ruckeln
            pass
        return summary if flight is not None else None

    # ------------------------------------------------------------------ Hintergrund
    def _writer(self):
        try:
            os.nice(5)
        except OSError:
            pass
        while True:
            ep, meta = self.q.get()
            self.busy = True
            try:
                EP_DIR.mkdir(parents=True, exist_ok=True)
                name = f"{time.strftime('%Y%m%d-%H%M%S')}-{self.source}-{os.getpid()}-{self.saved:04d}"
                tmp = EP_DIR / (name + ".tmp.npz")
                np.savez_compressed(tmp, img=np.stack(ep["img"]), st=np.stack(ep["st"]), priv=np.stack(ep["priv"]),
                                    act=np.stack(ep["act"]), logp=np.asarray(ep["logp"], np.float32),
                                    rew=np.asarray(ep["rew"], np.float32), terminal=np.array(bool(meta["terminal"])),
                                    meta=np.array(json.dumps(meta, ensure_ascii=False)))
                os.replace(tmp, EP_DIR / (name + ".npz"))
                self.saved += 1
                files = sorted(EP_DIR.glob("*.npz"))
                files = [f for f in files if not f.name.endswith(".tmp.npz")]
                sizes = [f.stat().st_size for f in files]
                total, drop = sum(sizes), max(0, len(files) - MAX_EPISODES)
                while drop < len(files) - 1 and total - sum(sizes[:drop]) > MAX_BYTES:
                    drop += 1
                for f in files[:drop]:
                    f.unlink(missing_ok=True)
            except Exception as exc:                   # Aufzeichnung ist Beiwerk: nie das Spiel stören
                print("Aufzeichnung:", repr(exc), flush=True)
            finally:
                self.busy = False

    def flush(self, timeout=10.0):
        end = time.time() + timeout
        time.sleep(0.05)
        while (not self.q.empty() or self.busy) and time.time() < end:
            time.sleep(0.05)


# ============================================================================ Lern-Prozess (nn_learn.py)
def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def learner_alive():
    try:
        pid = int(PIDFILE.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None


def want_learner(physics):
    """Heartbeat: der Lern-Prozess läuft weiter, solange das hier regelmäßig geschrieben wird."""
    try:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        tmp = WANT.with_suffix(".tmp")
        tmp.write_text(json.dumps({"t": time.time(), "physics": physics, "pid": os.getpid()}))
        os.replace(tmp, WANT)
    except OSError:
        pass


def start_learner(physics):
    if learner_alive():
        return False
    root = Path(__file__).resolve().parents[2]                 # simulator/
    log = open(MODEL_DIR / "learn.log", "a", encoding="utf-8")
    env = dict(os.environ, FREEFLY_PHYSIK=physics, PYTHONUNBUFFERED="1")
    env.pop("SDL_VIDEO_WINDOW_POS", None)
    subprocess.Popen([sys.executable, "-m", "autopilot.freefly.nn_learn"], cwd=str(root), env=env, stdout=log,
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    print("Lern-Prozess gestartet (nn_learn.py, Log models/freefly_nn/learn.log)", flush=True)
    return True


# ============================================================================ Zeitraffer: welche Versionen
def version_minutes():
    """Version -> (Trainingsminuten gesamt, Phase, Tore in der Prüfung) aus curve.csv."""
    out = {}
    try:
        rows = list(csv.DictReader((MODEL_DIR / "curve.csv").open()))
    except OSError:
        return out
    off, prev = 0.0, 0.0
    for r in rows:
        try:
            m = float(r["minutes"])
            v = int(r["version"])
        except (KeyError, ValueError):
            continue
        if m <= prev:
            off += prev
        prev = m
        out[v] = (off + m, r.get("phase", ""), float(r.get("eval_gates") or 0))
    return out


def replay_list():
    """Versionen für den Zeitraffer: früh, dann immer längeres Training, zuletzt das beste Modell."""
    vm = version_minutes()
    have = {int(p.stem[1:]): p for p in MODEL_DIR.glob("v[0-9][0-9][0-9].pt")}
    best = read_json(MODEL_DIR / "status.json", {}).get("best_version")
    learn = read_json(LEARN, {}) or {}
    best = learn.get("published") or best
    cand = sorted(v for v in have if v in vm and (best is None or v <= best))
    if not cand:
        return [(None, "bestes Modell", "", None)]
    picks = []
    for target in (2, 5, 8, 10, 15, 25, 40, 60, 90, 130, 200, 300, 500, 800, 1200):
        v = min(cand, key=lambda x: abs(vm[x][0] - target))
        if v not in picks and (not picks or vm[v][0] > vm[picks[-1]][0]):
            picks.append(v)
    if best in have and best not in picks:
        picks.append(best)
    out = []
    for v in picks:
        m, ph, g = vm.get(v, (0, "", 0))
        out.append((have[v], f"Version {v}", f"nach {fmt_minutes(m)} Training", PHASE_WORDS.get(ph, ph)))
    return out


def fmt_minutes(m):
    if m < 90:
        return f"{max(1, round(m))} min"
    h = m / 60
    return f"{h:.1f} h".replace(".", ",")


# ============================================================================ Showcase im Spiel
class Show:
    def __init__(self, renderer, source="spiel", physics="liftoff"):
        self.r = renderer
        self.recorder = Recorder(source, physics)
        self.physics = physics
        self.data = read_json(SHOW, None) or {"attempts": 0, "best": 0, "curve": []}
        self.tex = None
        self.tex_img = None
        self.learn, self.status, self.t_status = None, None, -1e9
        self.t_beat = -1e9
        self.t_spawn = -1e9
        self.mode = "nn"
        self.replay = []
        self.replay_i = -1
        self.replay_runs = []            # Zeitraffer: (Version, Tore) dieser Runde
        self.ghosts = []                 # Zeitraffer: (Version, [(t, x, y, z)]) der früheren Versionen dieser Runde
        self.path = []
        self.t_att = None                # s seit Beginn des Versuchs (für die Geister)
        self.banner = None               # (Titel, Untertitel, bis wann)
        self.notice = None
        self.text_i, self.t_text = 0, 0.0
        self.last_end = None
        self.today = time.strftime("%Y-%m-%d")

    # ------------------------------------------------------------------ Ablauf
    def prepare(self, pilot, flight, settings, now):
        """Vor pilot.reset() (Neustart): Modus, Rauschen, Modell (Zeitraffer: nächste Version)."""
        mode = settings.get("ap_mode", "nn")
        mode = mode if mode in SHOW_MODES else "nn"
        if mode != self.mode:
            self.replay_i = -1
            self.replay_runs = []
            self.ghosts = []
        self.path = []
        self.t_att = None
        self.mode = mode
        pilot.flight = flight
        pilot.recorder = self.recorder
        self.recorder.enabled = bool(settings.get("nn_learn", True))
        self.recorder.physics = self.physics = settings.get("physik", self.physics)
        pilot.explore = LEARN_STD if mode == "nn_learn" else 0.0
        if mode == "nn_replay":
            if not self.replay or self.replay_i + 1 >= len(self.replay):
                self.replay = replay_list()
                self.replay_i = -1
                self.replay_runs = []
                self.ghosts = []
            self.replay_i += 1
            path, title, sub, phase = self.replay[self.replay_i]
            pilot.set_model(path)
            self.banner = (title, sub + (f" · {phase}" if phase else ""), now + 6.0)
        else:
            pilot.set_model(None)
            if mode == "nn_learn":
                self.banner = (f"Versuch {self.data['attempts'] + 1}", None, now + 2.2)

    def after_reset(self, pilot, now):
        if pilot.just_loaded and self.mode != "nn_replay":
            old, new = pilot.just_loaded
            self.notice = (f"Neue Version v{new} fliegt jetzt", "war in der Prüfung mindestens so gut wie v%s" % old,
                           now + 4.0)
        pilot.just_loaded = None

    def frame(self, flight, pilot, settings, now):
        """Pro Frame (nach der Physik). -> None oder (kind, Titel, Untertitel): Versuch beenden (kein Tor mehr)."""
        if now - self.t_beat > 10.0:
            self.t_beat = now
            if settings.get("nn_learn", True):
                want_learner(self.physics)
                if now - self.t_spawn > 60.0 and not learner_alive():
                    self.t_spawn = now
                    try:
                        start_learner(self.physics)
                    except OSError as exc:
                        print("Lern-Prozess:", repr(exc), flush=True)
        if now - self.t_status > 2.0:
            self.t_status = now
            self.learn = read_json(LEARN, None)
            self.status = read_json(MODEL_DIR / "status.json", None)
        rec = self.recorder
        if rec.ep is None or rec.ep["t0"] is None:
            return None
        self.t_att = flight.flight_time - rec.ep["t0"]
        if self.mode == "nn_replay" and (not self.path or self.t_att - self.path[-1][0] >= 0.05):
            self.path.append((self.t_att, *flight.drone.pos))
        if flight.crashed_at is not None:
            self._done(rec.end(flight, flight.crash_reason, crashed=True))
            return None
        why = None
        if rec.since_gate(flight) > NO_GATE_S:
            why = "findet kein Tor mehr"
        elif rec.gates() >= MAX_GATES:
            why = "zwei Runden geschafft"
        elif flight.flight_time - rec.ep["t0"] > MAX_S:
            why = "Zeit um"
        if why is None:
            return None
        res = rec.end(flight, why)
        self._done(res)
        title = "GESCHAFFT!" if res and res["gates"] >= MAX_GATES else "VERSUCH ZU ENDE"
        return "done", title, why

    def _done(self, res):
        if not res:
            return
        self.last_end = res
        d = self.data
        if self.mode == "nn_replay":
            label = self.replay[self.replay_i][1] if self.replay else "?"
            self.replay_runs.append((label, res["gates"]))
            if len(self.path) > 5:
                self.ghosts = (self.ghosts + [(label.replace("Version ", "v"), self.path)])[-4:]
            self.path = []
        else:
            d["attempts"] += 1
            d["best"] = max(d.get("best", 0), res["gates"])
            d["curve"] = (d["curve"] + [[d["attempts"], res["gates"], res["version"], self.mode]])[-400:]
            day = time.strftime("%Y-%m-%d")
            if d.get("day") != day:
                d["day"], d["best_today"], d["attempts_today"] = day, 0, 0
            d["best_today"] = max(d.get("best_today", 0), res["gates"])
            d["attempts_today"] = d.get("attempts_today", 0) + 1
            d["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            d["last"] = res
            try:
                tmp = SHOW.with_suffix(".tmp")
                tmp.write_text(json.dumps(d, ensure_ascii=False))
                os.replace(tmp, SHOW)
            except OSError:
                pass

    def end_text(self, kind, title, sub):
        """Text für die Neustart-Karte (restart.py)."""
        if self.mode == "nn_learn":
            g = self.last_end["gates"] if self.last_end else 0
            return f"VERSUCH {self.data['attempts']}: {g} TORE", (sub or "") + " – die KI lernt daraus"
        if self.mode == "nn_replay" and self.replay:
            g = self.last_end["gates"] if self.last_end else 0
            return f"{self.replay[self.replay_i][1].upper()}: {g} TORE", self.replay[self.replay_i][2]
        return title, sub

    def label(self, pilot):
        if self.mode == "nn_learn":
            return f"KI lernt · Versuch {self.data['attempts'] + 1} · {pilot.label() if pilot else ''}"
        if self.mode == "nn_replay" and self.replay:
            return f"KI Zeitraffer · {self.replay[self.replay_i][1]}"
        return "Netz · " + (pilot.label() if pilot else "lädt")

    def learned_today(self):
        L = self.learn or {}
        return float((L.get("days") or {}).get(time.strftime("%Y-%m-%d"), 0.0))

    def own_flights(self, pilot):
        m = pilot.meta if pilot is not None else {}
        return int(m.get("own_flights", 0))

    # ------------------------------------------------------------------ Zeichnen
    def draw(self, hud, pilot, settings, now):
        o = settings["nnshow"]
        if not settings.get("hud", True):
            return
        r, T = self.r, hud.text
        W, H = r.size
        s = hud.scale()
        r.begin_2d()
        if o["sieht"]:
            self._draw_sees(hud, pilot, s)
        if o["will"]:
            self._draw_wants(hud, pilot, s, W, H)
        if o["geister"] and self.mode == "nn_replay" and self.ghosts and self.t_att is not None:
            self._draw_ghosts(hud, s, now)
        if o["zahlen"]:
            self._draw_numbers(hud, pilot, s, W, H, 300 * s if o["sieht"] else 150 * s)
        if o["kurve"]:
            self._draw_curve(hud, s, W, H)
        if o["text"]:
            texts = TEXTS.get(self.mode, TEXTS["nn"])
            if now - self.t_text > 7.0:
                self.t_text = now
                self.text_i = (self.text_i + 1) % len(texts)
            t = texts[self.text_i % len(texts)]
            tex, tw, th = T.get(t, int(21 * s), bold=False)
            y = 236 * s                                  # oben, unter Zeit und Kompass-Band
            hud.rect(W / 2, y, tw + 34 * s, th + 12 * s, (0.02, 0.03, 0.06, 0.45))
            r.sprite(tex, W / 2, y, tw, th, tint=(1, 1, 1, 0.88))
        if o["technik"] and pilot is not None and pilot.ok:
            vf, vr, vu, yr = pilot.ctl.set
            L = self.learn or {}
            lines = [f"will: {vf:4.1f} m/s vor  {vr:+.1f} seitl.  {vu:+.1f} hoch  Gier {math.degrees(yr):+4.0f}°/s",
                     f"Bild+Netz {pilot.ms:.1f} ms · Rauschen {pilot.explore:.2f} · gespeichert {self.recorder.saved}"]
            if L.get("running"):
                lines.append(f"Lern-Prozess: {L.get('phase', '')}, {L.get('updates', 0)} Lernschritte, "
                             f"Prüfung v{L.get('published')}: {L.get('base', 0):.1f} Tore")
            for i, t in enumerate(lines):
                T.draw(t, W / 2, H - 150 * s + i * 22 * s, int(15 * s), bold=False, tint=(0.75, 0.95, 1, 0.9))
        # große Beschriftung (Zeitraffer: Version, Lernen: Versuch), Hinweis auf neue Version
        for item, big in ((self.banner, True), (self.notice, False)):
            if item and now < item[2]:
                a = min(1.0, (item[2] - now) / 0.6)
                y = H * (0.36 if big else 0.62)
                T.draw(item[0], W / 2, y, int((92 if big else 40) * s), tint=(0.35, 0.95, 1, a))
                if item[1]:
                    T.draw(item[1], W / 2, y + (70 if big else 38) * s, int((32 if big else 22) * s),
                           tint=(1, 1, 1, 0.9 * a), bold=False)

    def _draw_ghosts(self, hud, s, now):
        """Frühere Versionen an ihrer Stelle zur selben Zeit nach dem Start (halbdurchsichtig, mit Name)."""
        import bisect
        r, T, S = self.r, hud.text, hud.shapes
        W, H = r.size
        for k, (label, path) in enumerate(self.ghosts):
            i = bisect.bisect_left(path, (self.t_att,))
            ended = i >= len(path)
            if ended:
                fade = max(0.5, 1.0 - (self.t_att - path[-1][0]) / 3.0)   # Ende der Bahn: bleibt als „v1 ✕“ stehen
                p = path[-1][1:]
            else:
                fade = 1.0
                a, b = path[max(0, i - 1)], path[i]
                f = 0.0 if b[0] == a[0] else (self.t_att - a[0]) / (b[0] - a[0])
                p = tuple(a[j] + (b[j] - a[j]) * f for j in (1, 2, 3))
            scr, cam = r.project(p)
            if scr is None or not (0 < scr[0] < W and 0 < scr[1] < H):
                continue
            dist = math.dist(p, getattr(r, "cam_pos", p))
            if dist < 2.5:                                         # steckt in der eigenen Drohne: nicht zeigen
                continue
            size = max(14 * s, min(70 * s, 900 * s / dist))
            hue = (1.0, 0.55 + 0.1 * k, 0.25 + 0.15 * k)
            r.sprite(S.dot, scr[0], scr[1], size, size, tint=(*hue, 0.45 * fade))
            T.draw(label + (" ✕" if ended else ""), scr[0], scr[1] - size / 2 - 12 * s, int(16 * s),
                   tint=(*hue, 0.8 * fade))

    def _draw_sees(self, hud, pilot, s):
        import moderngl
        r, T = self.r, hud.text
        x0, y0 = 30 * s, 132 * s
        img = pilot.preview(scale=1) if pilot is not None else None
        dw = 300 * s
        T.draw("DAS SIEHT DIE KI", x0, y0, int(20 * s), "left", tint=(0.3, 0.95, 1, 1))
        if img is None:
            return
        if pilot.last_img is not self.tex_img:          # nur bei neuem Bild (15 Hz) hochladen
            self.tex_img = pilot.last_img
            h, w = img.shape[:2]
            rgba = np.concatenate([img, np.full((h, w, 1), 255, np.uint8)], axis=2)
            if self.tex is None or self.tex.size != (w, h):
                if self.tex is not None:
                    self.tex.release()
                self.tex = r.ctx.texture((w, h), 4)
                self.tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
            self.tex.write(np.ascontiguousarray(rgba).tobytes())
        if self.tex is None:
            return
        w, h = self.tex.size
        dh = dw * h / w
        cy = y0 + 18 * s + dh / 2
        hud.rect(x0 + dw / 2, cy, dw + 8 * s, dh + 8 * s, (0, 0, 0, 0.5))
        r.sprite(self.tex, x0 + dw / 2, cy, dw, dh)
        T.draw("Kamera", x0 + 6 * s, y0 + 32 * s, int(14 * s), "left", bold=False)
        T.draw("Nähe (hell = nah)", x0 + dw / 2 + 6 * s, y0 + 32 * s, int(14 * s), "left", bold=False)
        T.draw(f"nur {w // 2} × {h} Bildpunkte, 15-mal pro Sekunde", x0, cy + dh / 2 + 16 * s, int(14 * s), "left",
               bold=False, tint=(1, 1, 1, 0.75))

    def _draw_wants(self, hud, pilot, s, W, H):
        """Pfeile: vor (Balken), links/rechts, hoch/runter, drehen. Länge = wie stark."""
        if pilot is None or not pilot.ok:
            return
        r, T, S = self.r, hud.text, hud.shapes
        vf, vr, vu, yr = pilot.ctl.set
        cx, cy = 190 * s, H - 240 * s
        R = 85 * s
        hud.rect(cx, cy, 2 * R + 130 * s, 2 * R + 130 * s, (0.02, 0.03, 0.06, 0.45))
        T.draw("DAS WILL DIE KI", cx, cy - R - 46 * s, int(20 * s), tint=(0.3, 0.95, 1, 1))
        hud.rect(cx, cy, 6 * s, 6 * s, (1, 1, 1, 0.8))
        col = (1.0, 0.75, 0.2, 0.95)

        def arrow(dx, dy, mag, label, lx, ly):
            if mag < 0.06:
                return
            L = R * min(1.0, mag)
            ang = math.atan2(dx, -dy)
            mx, my = cx + dx * L / 2, cy + dy * L / 2
            hud.r.sprite(S.white, mx, my, 9 * s, L, angle=ang, tint=col)
            r.sprite(S.arrow, cx + dx * L, cy + dy * L, 34 * s, 34 * s, angle=ang, tint=col)
            T.draw(label, cx + dx * (L + 28 * s) + lx, cy + dy * (L + 22 * s) + ly, int(15 * s), bold=False)

        arrow(0, -1, vf / 14.0, "vor", 0, 0)
        arrow(1 if vr > 0 else -1, 0, abs(vr) / 5.0, "rechts" if vr > 0 else "links", 0, -14 * s)
        # hoch/runter: Balken rechts daneben
        bx = cx + R + 36 * s
        hud.rect(bx, cy, 10 * s, 2 * R * 0.8, (1, 1, 1, 0.18))
        k = max(-1.0, min(1.0, vu / 4.0))
        if abs(k) > 0.04:
            hud.rect(bx, cy - k * R * 0.4, 10 * s, abs(k) * R * 0.8, (0.4, 1, 0.6, 0.95))
        T.draw("hoch", bx, cy - R * 0.8 - 12 * s, int(14 * s), bold=False)
        T.draw("runter", bx, cy + R * 0.8 + 12 * s, int(14 * s), bold=False)
        # drehen: Balken unten
        q = max(-1.0, min(1.0, yr / YAW_RATE * 1.5))
        by = cy + R + 34 * s
        hud.rect(cx, by, 2 * R, 10 * s, (1, 1, 1, 0.18))
        if abs(q) > 0.04:
            hud.rect(cx + q * R / 2, by, abs(q) * R, 10 * s, (0.5, 0.8, 1, 0.95))
        T.draw("dreht links", cx - R, by + 18 * s, int(14 * s), bold=False)
        T.draw("dreht rechts", cx + R, by + 18 * s, int(14 * s), bold=False)

    def _draw_numbers(self, hud, pilot, s, W, H, y):
        T = hud.text
        x = 30 * s
        d = self.data
        lines = []
        if self.mode == "nn_replay" and self.replay:
            _, title, sub, phase = self.replay[self.replay_i]
            lines.append((title, 46, (0.35, 0.95, 1, 1)))
            lines.append((sub, 26, (1, 1, 1, 0.95)))
            if phase:
                lines.append((phase, 20, (1, 1, 1, 0.75)))
            lines.append((f"{self.replay_i + 1} von {len(self.replay)} Versionen", 18, (1, 1, 1, 0.65)))
        else:
            lines.append((f"Versuch {d['attempts'] + 1}", 46, (0.35, 0.95, 1, 1)))
            lines.append((f"Bester: Tor {d.get('best', 0)}", 28, (1, 0.85, 0.3, 1)))
            mins = self.learned_today()
            if mins >= 0.5:
                lines.append((f"Heute gelernt: {fmt_minutes(mins)}", 24, (1, 1, 1, 0.95)))
            if pilot is not None and pilot.ok:
                own = self.own_flights(pilot)
                lines.append((f"Modell v{pilot.version}" + (f" · gelernt aus {own} eigenen Flügen" if own else ""),
                              19, (1, 1, 1, 0.8)))
            L = self.learn or {}
            if L.get("running") and learner_alive():
                lines.append(("Lern-Programm läuft · " + (L.get("phase_text") or "übt"), 17, (0.6, 1, 0.7, 0.85)))
        for t, size, tint in lines:
            _, h = T.draw(t, x, y, int(size * s), "left", tint=tint, bold=size >= 26)
            y += h * 0.95 + 4 * s

    def _draw_curve(self, hud, s, W, H):
        T = hud.text
        w, h = 400 * s, 160 * s                          # rechts in der Mitte, links neben der Höhen-Leiste
        x0, y1 = W - 110 * s - w, 580 * s
        y0 = y1 - h
        hud.rect(x0 + w / 2, y0 + h / 2 - 12 * s, w + 24 * s, h + 64 * s, (0.02, 0.03, 0.06, 0.5))
        if self.mode == "nn_replay":
            title = "SO WEIT KAM JEDE VERSION"
            pts = [(lbl.replace("Version ", "v"), g, i) for i, (lbl, g) in enumerate(self.replay_runs)]
            slots = max(len(self.replay), 1)
        else:
            title = "LERNKURVE: TORE PRO VERSUCH"
            curve = self.data["curve"][-40:]
            pts = [(str(a), g, v) for a, g, v, *_ in curve]
            slots = max(16, len(pts))
        T.draw(title, x0, y0 - 22 * s, int(17 * s), "left", tint=(0.3, 0.95, 1, 1))
        top = max(12, max((p[1] for p in pts), default=0))
        hud.rect(x0 + w / 2, y1, w, 2 * s, (1, 1, 1, 0.5))
        for gy in (6, 12, 18, 24):
            if gy <= top:
                yy = y1 - h * gy / top
                hud.rect(x0 + w / 2, yy, w, 1 * s, (1, 1, 1, 0.14))
                T.draw(str(gy), x0 - 6 * s, yy, int(12 * s), "right", bold=False, tint=(1, 1, 1, 0.6))
        bw = w / slots
        prev_v = None
        for i, (lbl, g, v) in enumerate(pts):
            bh = max(2 * s, h * g / top)
            cx = x0 + bw * (i + 0.5)
            if self.mode == "nn_replay":
                col = (0.35 + 0.5 * i / max(1, slots - 1), 0.95 - 0.3 * i / max(1, slots - 1), 1, 0.9)
            else:
                col = (0.3, 0.9, 1, 0.85) if (v or 0) % 2 == 0 else (0.45, 1, 0.6, 0.85)
            hud.rect(cx, y1 - bh / 2, bw * 0.78, bh, col)
            if self.mode == "nn_replay":
                T.draw(lbl, cx, y1 + 13 * s, int(13 * s), bold=False)
                T.draw(str(g), cx, y1 - bh - 11 * s, int(14 * s))
            elif prev_v is not None and v != prev_v:
                hud.rect(cx - bw / 2, y1 - h / 2, 2 * s, h, (1, 0.85, 0.3, 0.8))
                T.draw(f"v{v}", cx - bw / 2 + 3 * s, y0 + 8 * s, int(12 * s), "left", bold=False, tint=(1, 0.85, 0.3, 1))
            prev_v = v
        if self.mode != "nn_replay":
            T.draw("Versuche →", x0 + w, y1 + 14 * s, int(13 * s), "right", bold=False, tint=(1, 1, 1, 0.6))
            if not pts:
                T.draw("noch kein Versuch", x0 + w / 2, y1 - h / 2, int(16 * s), bold=False, tint=(1, 1, 1, 0.6))


def studio_status():
    """Für studio_sim: Trainings-, Lern- und Versuchs-Stand zusammen (klein, json-fähig)."""
    st = read_json(MODEL_DIR / "status.json", {}) or {}
    L = read_json(LEARN, {}) or {}
    sh = read_json(SHOW, {}) or {}
    alive = bool(learner_alive())
    return {**st, "learn": {k: L.get(k) for k in ("published", "base", "own_flights", "phase", "phase_text", "updates",
                                                  "physics", "evals", "updated", "episodes_total")}
            | {"running": alive and bool(L.get("running")),
               "today_min": round(float((L.get("days") or {}).get(time.strftime("%Y-%m-%d"), 0.0)), 1)},
            "show": {"attempts": sh.get("attempts", 0), "best": sh.get("best", 0), "best_today": sh.get("best_today", 0),
                     "curve": (sh.get("curve") or [])[-60:], "last": sh.get("last")}}
