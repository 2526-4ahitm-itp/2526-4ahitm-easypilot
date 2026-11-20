"""Training des Netz-Piloten (nn.py) ohne Fenster.

  python -m autopilot.freefly.train_nn [--minutes 80] [--dagger-min 25] [--workers 3] [--envs 3]
  python -m autopilot.freefly.train_nn --resume --minutes 60        # weiter trainieren (PPO ab best.pt)
  python -m autopilot.freefly.train_nn eval [Läufe]                 # bestes Modell mit dem Spiel-Piloten testen
  python -m autopilot.freefly.train_nn lehrer                       # nur den Lehrer fliegen lassen (Kontrolle)

Ablauf:
 1. Imitation (Behavior Cloning + DAgger). Lehrer ist die Rennlinie (auto.Autopilot plant sie, mit allen
    Hindernissen), übersetzt in dieselben Soll-Werte, die das Netz ausgibt. Erst fliegt der Lehrer (mit
    Störungen, damit auch schiefe Lagen vorkommen), dann immer mehr das Netz; der Lehrer sagt in jedem
    Zustand, was richtig gewesen wäre. Das Netz sieht dabei nur Kamerabild + Flugzustand.
 2. Selbstverbesserung mit PPO (Reinforcement Learning): kein Lehrer am Steuer. Belohnung kommt aus dem
    Sim: Tor in Reihenfolge durchflogen, Annäherung ans nächste Tor, Strafe für Absturz. Der Kritiker
    (schätzt nur den Wert, fliegt nie) darf die Torlage kennen, der Pilot nicht. Ein kleiner Rest
    Lehrer-Verlust hält das Netz anfangs in der Spur und wird ausgeblendet.
Domain-Randomisierung: pro Prozess Welt-Varianten mit leicht verschobenen Toren und anderem Dorf,
Helligkeit/Farbe/Rauschen im Bild, Sonnenrichtung, Startlage, Luftwiderstand; die Hälfte der Episoden
beginnt mitten auf der Strecke.

Modelle, Lernkurve (curve.csv, curve.png) und status.json: autopilot/models/freefly_nn/.
Höchstens --workers Rechenprozesse (Standard 3) + der Lernprozess, alle mit niedriger Priorität.
"""
import argparse
import csv
import dataclasses
import json
import math
import multiprocessing as mp
import os
import random
import shutil
import sys
import time

import numpy as np

from .gfx import SUN
from .nn import (DECISION_HZ, MODEL_DIR, N_PRIV, N_STATE, SetpointController, action_to_setpoint, build_net,
                 camera, heading_axes, image_input, setpoint_to_action, state_features)

DT = 0.004                       # Physik im Training (Spiel: 0.002); Regler alle 2 Schritte = 125 Hz
SUB = round(1.0 / DECISION_HZ / DT)
EXPERT_VMAX = 8.0                # m/s: so schnell fliegt der Lehrer höchstens (Kamera-Pilot: 6-10)
NO_GATE_S = 12.0                 # s ohne neues Tor -> Episode zu Ende
TRAIN_MAX_S = 90.0
EVAL_MAX_S = 70.0


# ============================================================================ Lehrer
class LineExpert:
    """Folgt der Rennlinie (kennt also die Tore!) und gibt dieselben Soll-Werte aus wie das Netz."""

    def __init__(self, line):
        self.line = line
        self.step_len = line.length / max(1, len(line.points) - 1)
        self.idx = 0

    def reset(self, idx=0):
        self.idx = idx

    def off(self, pos):
        return math.dist(pos, self.line.points[self.idx])

    def action(self, state):
        L = self.line
        sp = math.sqrt(sum(v * v for v in state.vel))
        self.idx = L.closest(state.pos, self.idx, window=int((sp * 0.25 + 5.0) / max(self.step_len, 0.05)) + 2)
        s = L.project(state.pos, self.idx)
        v_line = max(4.0, min(L.speed[self.idx], EXPERT_VMAX))
        look = max(2.5, 0.35 * v_line)
        p, _, _, _ = L.reference_s(s + look)
        d = np.subtract(p, state.pos)
        n = float(np.linalg.norm(d))
        v = d / max(n, 1e-6) * v_line * min(1.0, 0.5 + n / look / 2)
        q, _, _, _ = L.reference_s(s + max(4.0, 0.7 * v_line))
        fwd, right = heading_axes(state.quat)
        to = (q[0] - state.pos[0], q[2] - state.pos[2])
        err = math.atan2(to[0] * right[0] + to[1] * right[2], to[0] * fwd[0] + to[1] * fwd[2])
        yr = max(-2.5, min(2.5, 3.0 * err))
        vf = v[0] * fwd[0] + v[2] * fwd[2]
        vr = v[0] * right[0] + v[2] * right[2]
        off = math.dist(state.pos, L.points[self.idx])
        return setpoint_to_action(vf, vr, v[1], yr), off, s


# ============================================================================ Umgebung (läuft im Arbeits-Prozess)
def yaw_quat(dx, dz):
    from ..geometry import axis_angle, qrot
    for sgn in (1, -1):
        q = axis_angle((0.0, 1.0, 0.0), sgn * math.atan2(dx, dz))
        f = qrot(q, (0.0, 0.0, 1.0))
        if f[0] * dx + f[2] * dz > 0.99 * math.hypot(dx, dz):
            return q
    return axis_angle((0.0, 1.0, 0.0), math.atan2(dx, dz))


class Variant:
    def __init__(self, ctx, rates, thrust, seed, shift, rng):
        from . import world as W
        from .auto import Autopilot
        from .vision import CameraView
        orig = W.COURSE
        if shift:
            W.COURSE = [(x + rng.uniform(-0.7, 0.7), z + rng.uniform(-0.7, 0.7),
                         lift + rng.uniform(-0.4, 0.4) if lift > 0.5 else lift) for x, z, lift in orig]
        try:
            self.world = W.World(seed=seed)
        finally:
            W.COURSE = orig
        self.line = Autopilot(self.world, rates, thrust, 0.6, laps=3).line
        self.gate_s = self.line.gate_positions()
        self.view = CameraView(ctx, self.world, camera())
        self.base_sun = None


class Env:
    def __init__(self, variants, rates, thrust, rng):
        from .game import Flight
        self.variants, self.rates, self.thrust, self.rng = variants, rates, thrust, rng
        self.v = variants[0]
        self.flight = Flight(self.v.world, rates, thrust)
        self.ctl = SetpointController(rates, thrust)
        self.mode = "train"
        self.max_off = None              # Imitation: Episode endet, wenn so weit (m) neben der Rennlinie
        self.ctx = variants[0].view.ctx
        self.size = variants[0].view.size
        self.fbo = self.ctx.framebuffer(color_attachments=[self.ctx.texture(self.size, 3)],
                                        depth_attachment=self.ctx.depth_texture(self.size))
        self.reset()

    # -- Zustand
    def reset(self, observe=True):
        from .game import DRAG, Flight
        rng = self.rng
        self.v = self.variants[0] if self.mode == "eval" else rng.choice(self.variants)
        f = self.flight
        if f.world is not self.v.world:
            self.flight = f = Flight(self.v.world, self.rates, self.thrust)
        f.respawn()
        f.armed = True
        d = f.drone
        if self.mode == "train":
            d.p = dataclasses.replace(d.p, drag=DRAG * rng.uniform(0.8, 1.25),
                                      hover_throttle=d.p.hover_throttle * rng.uniform(0.95, 1.05))
        self.expert = LineExpert(self.v.line)
        L = self.v.line
        if self.mode == "train" and rng.random() < 0.5:           # mitten auf der Strecke starten
            gi = rng.randrange(1, 13)
            s = self.v.gate_s[gi] - rng.uniform(6.0, 0.8 * (self.v.gate_s[gi] - self.v.gate_s[gi - 1]))
            p, vref, _, t = L.reference_s(s)
            sp = min(math.sqrt(sum(x * x for x in vref)), EXPERT_VMAX) * rng.uniform(0.4, 1.0)
            jit = [rng.uniform(-0.8, 0.8) for _ in range(3)]
            d.pos = (p[0] + jit[0], max(0.6, p[1] + jit[1]), p[2] + jit[2])
            d.vel = (t[0] * sp, t[1] * sp, t[2] * sp)
            a = rng.uniform(-0.3, 0.3)
            c, si = math.cos(a), math.sin(a)
            d.quat = yaw_quat(t[0] * c + t[2] * si, -t[0] * si + t[2] * c)
            f.next_gate = gi % 12
            self.expert.reset(L.index_at(s))
            prev = setpoint_to_action(sp, 0, 0, 0)
        else:
            a = rng.uniform(-0.25, 0.25)
            d.pos = (rng.uniform(-0.6, 0.6), d.pos[1], rng.uniform(-0.6, 0.6))
            d.quat = yaw_quat(math.sin(a), math.cos(a))
            prev = np.array([-1.0, 0, 0, 0], np.float32)
        self.ctl.reset()
        self.prev = prev.astype(np.float32)
        self.t = 0.0
        self.gates = 0
        self.last_gate_t = 0.0
        self.dprev = self._gate_dist()
        # Bild-Störungen dieser Episode
        if self.mode == "train":
            self.gain = np.array([rng.uniform(0.85, 1.15) for _ in range(3)]) * rng.uniform(0.7, 1.25)
            self.noise = rng.uniform(0.0, 6.0)
            sun = np.array(SUN) + np.array([rng.uniform(-0.25, 0.25), rng.uniform(-0.15, 0.1), rng.uniform(-0.25, 0.25)])
            self.sun = tuple(sun / np.linalg.norm(sun))
        else:
            self.gain, self.noise = None, 0.0
            self.sun = tuple(SUN)
        self.world_focus()
        return self.observe() if observe else None

    def world_focus(self):
        self.v.world.focus(self.flight.drone.pos)

    def _gate_dist(self):
        g = self.v.world.gates[self.flight.next_gate]
        p = self.flight.drone.pos
        lx, ly, lz = g.local(p)
        c = g.center
        if lz > 0:                                  # schon hinter dem Tor (nicht durch): erst wieder davor
            return math.hypot(lx, ly) + lz + 8.0
        return math.dist(p, c)

    def priv(self):
        g = self.v.world.gates[self.flight.next_gate]
        s = self.flight.drone.state()
        fwd, right = heading_axes(s.quat)
        d = np.subtract(g.center, s.pos)
        n = (math.sin(g.yaw), math.cos(g.yaw))
        lx, ly, lz = g.local(s.pos)
        return np.array([(d[0] * fwd[0] + d[2] * fwd[2]) / 30, (d[0] * right[0] + d[2] * right[2]) / 30, d[1] / 10,
                         n[0] * fwd[0] + n[1] * fwd[2], n[0] * right[0] + n[1] * right[2], lz / 30,
                         self.flight.next_gate / 12, (self.t - self.last_gate_t) / NO_GATE_S], np.float32)

    def draw(self):
        """Kamerabild in den eigenen Puffer zeichnen (noch nicht lesen: die GPU arbeitet, während die
        anderen Umgebungen zeichnen; gelesen wird danach in einem Rutsch)."""
        s = self.flight.drone.state()
        r = self.v.view.r
        for prog in (r.obj, r.ground, r.inst, r.sky):
            prog["sun"].value = self.sun
        r.target = self.fbo
        self.fbo.use()
        self.ctx.viewport = (0, 0, *self.size)
        r.draw(s.pos, s.quat, 0, False, 0.0)
        self._s = s

    def observe(self, drawn=False):
        if not drawn:
            self.draw()
        s = self._s
        W, H = self.size
        rgb = np.frombuffer(self.fbo.read(components=3), np.uint8).reshape(H, W, 3)[::-1]
        z = np.frombuffer(self.fbo.read(components=1, attachment=-1, dtype="f4"), np.float32).reshape(H, W)[::-1]
        n, f = self.v.view.near, self.v.view.far
        depth = 2 * n * f / (f + n - (2 * z - 1) * (f - n))
        img = image_input(rgb[:, :, ::-1], depth)
        if self.gain is not None:
            x = img[:3].astype(np.float32) * self.gain[::-1, None, None]
            if self.noise > 0:
                x += np.random.normal(0, self.noise, x.shape).astype(np.float32)
            img[:3] = np.clip(x, 0, 255).astype(np.uint8)
        exp, off, _ = self.expert.action(s)
        return img, state_features(s, self.prev), exp, self.priv(), off

    def step(self, a):
        a = np.clip(np.asarray(a, np.float32), -1, 1)
        self.ctl.set = action_to_setpoint(a)
        self.prev = a
        f = self.flight
        before = f.next_gate
        passed = 0
        cmd = None
        for i in range(SUB):
            if i % 2 == 0:
                cmd = self.ctl.command(f.drone.state())
            f.step(cmd, DT)
            if f.next_gate != before:
                passed += 1
                before = f.next_gate
            if f.crashed_at is not None:
                break
        self.t += SUB * DT
        self.world_focus()
        r = 0.0
        if passed:
            self.gates += passed
            self.last_gate_t = self.t
            r += 2.0 * passed
            self.dprev = self._gate_dist()
        else:
            dn = self._gate_dist()
            r += 0.1 * max(-2.0, min(2.0, self.dprev - dn))
            self.dprev = dn
        crashed = f.crashed_at is not None or f.drone.pos[1] > 35.0
        if crashed:
            r -= 3.0
        limit = TRAIN_MAX_S if self.mode == "train" else EVAL_MAX_S
        stalled = self.t - self.last_gate_t > NO_GATE_S
        done = crashed or stalled or self.t > limit or self.gates >= 25
        info = None
        if done:
            info = {"gates": self.gates, "t": round(self.t, 1), "crash": f.crash_reason if f.crashed_at else
                    ("zu hoch" if crashed else ("kein Tor" if stalled else "Zeit"))}
        return r, done, info


def fast_sticks():
    """Nur in den Trainings-Prozessen: Umkehrung der Rate-Kurve per Tabelle statt 40-mal Halbieren
    (der Regler rechnet sie 375-mal pro Sekunde; Abweichung < 0,001 Stick)."""
    from ..rates import AxisRate
    tables = {}

    def stick(self, deg_per_s):
        t = tables.get(self)
        if t is None:
            xs = np.linspace(-1.0, 1.0, 8193)
            t = tables[self] = (np.array([self.rate(x) for x in xs]), xs)
        return float(np.interp(deg_per_s, t[0], t[1]))
    AxisRate.stick = stick


def worker(conn, wid, n_envs, n_variants, seed):
    try:
        os.nice(3)                     # etwas unter normal: Simons Spiel und der Mac bleiben flüssig
    except OSError:
        pass
    import moderngl
    from ..sysid import load_model
    rng = random.Random(seed)
    np.random.seed(seed)
    rates, thrust = load_model()
    fast_sticks()
    ctx = moderngl.create_standalone_context(require=330)
    variants = [Variant(ctx, rates, thrust, 11, False, rng)]
    for k in range(1, n_variants):
        variants.append(Variant(ctx, rates, thrust, 11 if k == 1 else 100 + seed + k, True, rng))
    envs = [Env(variants, rates, thrust, random.Random(seed * 100 + i)) for i in range(n_envs)]
    conn.send(("ready", [v.line.length for v in variants]))
    while True:
        cmd, data = conn.recv()
        if cmd == "close":
            break
        if cmd == "mode":
            for e in envs:
                e.mode, e.max_off = data
            cmd = "reset"
        if cmd == "reset":
            conn.send([e.reset() + (0.0, False, None) for e in envs])
        elif cmd == "step":
            res = []
            for e, a in zip(envs, data):
                r, done, info = e.step(a)
                if not done and e.max_off and e.expert.off(e.flight.drone.pos) > e.max_off:
                    done, info = True, {"gates": e.gates, "t": round(e.t, 1), "crash": "weg von der Strecke"}
                if done:
                    e.reset(observe=False)
                e.draw()
                res.append((r, done, info))
            conn.send([e.observe(drawn=True) + x for e, x in zip(envs, res)])


class VecEnv:
    def __init__(self, n_workers, n_envs, n_variants=3, seed=0):
        ctx = mp.get_context("spawn")
        self.pipes, self.procs = [], []
        for w in range(n_workers):
            a, b = ctx.Pipe()
            p = ctx.Process(target=worker, args=(b, w, n_envs, n_variants, seed * 1000 + w + 1), daemon=True)
            p.start()
            self.pipes.append(a)
            self.procs.append(p)
        for a in self.pipes:
            msg = a.recv()
            print(f"  Arbeits-Prozess bereit, Rennlinien {[round(x) for x in msg[1]]} m", flush=True)
        self.n = n_workers * n_envs
        self.k = n_envs

    def _gather(self):
        out = []
        for a in self.pipes:
            out += a.recv()
        return self._stack(out)

    @staticmethod
    def _stack(out):
        img = np.stack([o[0] for o in out])
        st = np.stack([o[1] for o in out])
        exp = np.stack([o[2] for o in out])
        priv = np.stack([o[3] for o in out])
        off = np.array([o[4] for o in out], np.float32)
        r = np.array([o[5] for o in out], np.float32)
        done = np.array([o[6] for o in out], bool)
        infos = [o[7] for o in out]
        return dict(img=img, st=st, exp=exp, priv=priv, off=off), r, done, infos

    def reset(self, mode=None, max_off=None):
        for a in self.pipes:
            a.send(("mode", (mode, max_off)) if mode else ("reset", None))
        return self._gather()[0]

    def step(self, actions):
        for i, a in enumerate(self.pipes):
            a.send(("step", actions[i * self.k:(i + 1) * self.k]))
        return self._gather()

    def close(self):
        for a in self.pipes:
            try:
                a.send(("close", None))
            except OSError:
                pass
        for p in self.procs:
            p.join(timeout=5)


# ============================================================================ Lernen
class Trainer:
    def __init__(self, args):
        import torch
        torch.set_num_threads(2)
        self.torch = torch
        self.args = args
        self.dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.net = build_net().to(self.dev)
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        self.status = self._load_status()
        if args.resume and (MODEL_DIR / "best.pt").exists():
            ck = torch.load(MODEL_DIR / "best.pt", map_location="cpu", weights_only=False)
            self.net.load_state_dict(ck["state_dict"])
            print(f"weiter ab v{ck['meta'].get('version')} ({ck['meta'].get('eval_gates')} Tore)")
        self.t0 = time.time()
        self.steps = self.status.get("steps_total", 0)
        self.episodes = self.status.get("episodes", 0)
        self.version = self.status.get("version", 0)
        self.best = self.status.get("best_gates", -1.0) if args.resume else -1.0
        self.recent = []

    def _load_status(self):
        try:
            return json.loads((MODEL_DIR / "status.json").read_text())
        except (OSError, ValueError):
            return {}

    # ---------------------------------------------------------------- Netz-Auswertung
    def act(self, obs, sample=False):
        torch = self.torch
        with torch.no_grad():
            img = torch.from_numpy(obs["img"]).to(self.dev)
            st = torch.from_numpy(obs["st"]).to(self.dev)
            feat = self.net.features(img, st)
            mu = self.net.mu(feat)
            if not sample:
                return mu.clamp(-1, 1).cpu().numpy(), None, None
            std = self.net.log_std.exp()
            a = mu + std * torch.randn_like(mu)
            logp = (-((a - mu) ** 2) / (2 * std ** 2) - std.log() - 0.5 * math.log(2 * math.pi)).sum(1)
            v = self.net.value(feat, st, torch.from_numpy(obs["priv"]).to(self.dev))
            return a.cpu().numpy(), logp.cpu().numpy(), v.cpu().numpy()

    def note_infos(self, infos):
        for inf in infos:
            if inf:
                self.episodes += 1
                self.recent.append(inf["gates"])
                self.recent = self.recent[-60:]

    # ---------------------------------------------------------------- Bewertung + Speichern
    def evaluate(self, env, phase, extra=None):
        obs = env.reset("eval", None)
        results = [None] * env.n
        t0 = time.time()
        while any(r is None for r in results) and time.time() - t0 < 300:
            a, _, _ = self.act(obs)
            obs, _, done, infos = env.step(a)
            for i, inf in enumerate(infos):
                if inf and results[i] is None:
                    results[i] = inf
        res = [r for r in results if r]
        gates = [min(r["gates"], 24) for r in res]
        lap1 = [min(g, 12) for g in gates]
        score = float(np.mean(gates)) if gates else 0.0
        self.version += 1
        meta = {"version": self.version, "phase": phase, "eval_gates": round(score, 2),
                "eval_lap1": round(float(np.mean(lap1)), 2) if lap1 else 0, "eval_max": max(gates) if gates else 0,
                "eval_runs": [(r["gates"], r["crash"]) for r in res], "steps_total": self.steps,
                "episodes": self.episodes, "minutes": round((time.time() - self.t0) / 60, 1),
                "date": time.strftime("%Y-%m-%d %H:%M")}
        if extra:
            meta.update(extra)
        ck = {"state_dict": {k: v.cpu() for k, v in self.net.state_dict().items()}, "meta": meta}
        self.torch.save(ck, MODEL_DIR / f"v{self.version:03d}.pt")
        better = score > self.best
        if better:
            self.best = score
            tmp = MODEL_DIR / "best.tmp"
            shutil.copy(MODEL_DIR / f"v{self.version:03d}.pt", tmp)
            os.replace(tmp, MODEL_DIR / "best.pt")
        print(f"[{meta['minutes']:5.1f} min] v{self.version} {phase}: Tore {score:.1f} (Runde 1: {meta['eval_lap1']}, "
              f"max {meta['eval_max']}) {[r['gates'] for r in res]} {'** bestes **' if better else ''}", flush=True)
        self._log(meta, better)
        return score

    def _log(self, meta, better):
        f = MODEL_DIR / "curve.csv"
        new = not f.exists()
        with f.open("a", newline="") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["version", "phase", "minutes", "steps_total", "episodes", "eval_gates", "eval_lap1",
                            "eval_max", "train_gates", "loss"])
            w.writerow([meta["version"], meta["phase"], meta["minutes"], meta["steps_total"], meta["episodes"],
                        meta["eval_gates"], meta["eval_lap1"], meta["eval_max"],
                        round(float(np.mean(self.recent)), 2) if self.recent else "", meta.get("loss", "")])
        best = json.loads((MODEL_DIR / "status.json").read_text()) if (MODEL_DIR / "status.json").exists() else {}
        st = {"version": meta["version"], "phase": meta["phase"], "steps_total": self.steps, "episodes": self.episodes,
              "best_gates": self.best, "best_version": meta["version"] if better else best.get("best_version"),
              "last_gates": meta["eval_gates"], "running": True, "updated": meta["date"]}
        (MODEL_DIR / "status.json").write_text(json.dumps(st, indent=1))
        try:
            plot_curve()
        except Exception as e:                                   # Grafik ist nur Beiwerk
            print("Grafik:", e)

    # ---------------------------------------------------------------- 1. Imitation + DAgger
    def dagger(self, env, minutes):
        torch = self.torch
        cap = self.args.data
        H, W = env_obs_shape(env)
        D_img = np.zeros((cap, 4, H, W), np.uint8)
        D_st = np.zeros((cap, N_STATE), np.float32)
        D_y = np.zeros((cap, 4), np.float32)
        n = 0
        opt = torch.optim.Adam([p for k, p in self.net.named_parameters() if not k.startswith("critic")
                                and k != "log_std"], lr=3e-4)
        obs = env.reset("train", self.args.max_off)
        end = time.time() + minutes * 60
        it = 0
        use_exp = np.ones(env.n, bool)
        while time.time() < end:
            beta = (1.0, 0.6, 0.45, 0.35)[it] if it < 4 else 0.25     # Lehrer lenkt anteilig mit (je Schritt)
            collect = self.args.collect * (3 if it == 0 else 2) // 2
            got = 0
            while got < collect:
                a_net, _, _ = self.act(obs)
                use_exp[:] = np.random.rand(env.n) < beta
                noise = np.random.normal(0, 0.25, obs["exp"].shape).astype(np.float32)
                a = np.where(use_exp[:, None], obs["exp"] + noise, a_net)
                for i in range(env.n):                    # Daten speichern (voll: zufällig ersetzen)
                    j = n if n < cap else random.randrange(cap)
                    D_img[j], D_st[j], D_y[j] = obs["img"][i], obs["st"][i], obs["exp"][i]
                    n = min(n + 1, cap) if n < cap else n
                obs, r, done, infos = env.step(a)
                # weit weg von der Linie (> 10 m): Lehrer-Etikett nicht mehr sinnvoll -> trotzdem weiter,
                # die Episode endet über "kein Tor"
                self.note_infos(infos)
                got += env.n
                self.steps += env.n
            # Lernen
            self.net.train()
            losses = []
            iters = self.args.bc_iters if it else self.args.bc_iters * 2
            for _ in range(iters):
                idx = np.random.randint(0, n, 192)
                img = torch.from_numpy(D_img[idx]).to(self.dev)
                st = torch.from_numpy(D_st[idx]).to(self.dev)
                y = torch.from_numpy(D_y[idx]).to(self.dev)
                loss = torch.nn.functional.smooth_l1_loss(self.net(img, st), y, beta=0.1)
                opt.zero_grad()
                loss.backward()
                opt.step()
                losses.append(loss.item())
            self.net.eval()
            it += 1
            print(f"  DAgger {it}: Lehrer-Anteil {beta:.2f}, Daten {n}, Verlust {np.mean(losses[-100:]):.4f}, "
                  f"Netz-Episoden Tore Ø {np.mean(self.recent[-20:]) if self.recent else float('nan'):.1f}", flush=True)
            if it >= 3 and it % 2 == 1 or time.time() >= end:
                self.evaluate(env, "imitation", {"loss": round(float(np.mean(losses[-100:])), 4)})
                obs = env.reset("train", self.args.max_off)
        return D_img, D_st, D_y, n

    # ---------------------------------------------------------------- 2. PPO
    def ppo(self, env, minutes, data=None):
        torch = self.torch
        F = torch.nn.functional
        a = self.args
        T = a.rollout
        N = env.n
        H, W = env_obs_shape(env)
        actor = [p for k, p in self.net.named_parameters() if not k.startswith("critic")]
        opt = torch.optim.Adam([{"params": actor, "lr": a.lr},
                                {"params": self.net.critic.parameters(), "lr": 3e-4}])
        with torch.no_grad():                    # wenig Rauschen: std 0,3 zerstörte das nachgeahmte Fliegen
            self.net.log_std.fill_(math.log(a.std))   # (20.11.: v17 nach 5 min PPO 8 statt 15 Tore)
        obs = env.reset("train", None)
        end = time.time() + minutes * 60
        upd = 0
        last_eval = time.time()
        buf_img = np.zeros((T, N, 4, H, W), np.uint8)
        buf = {k: np.zeros((T, N) + s, np.float32) for k, s in
               (("st", (N_STATE,)), ("priv", (N_PRIV,)), ("act", (4,)), ("exp", (4,)), ("logp", ()), ("val", ()),
                ("rew", ()), ("done", ()))}
        while time.time() < end:
            for t in range(T):
                act, logp, val = self.act(obs, sample=True)
                buf_img[t] = obs["img"]
                buf["st"][t], buf["priv"][t], buf["exp"][t] = obs["st"], obs["priv"], obs["exp"]
                buf["act"][t], buf["logp"][t], buf["val"][t] = act, logp, val
                obs, r, done, infos = env.step(act)
                buf["rew"][t], buf["done"][t] = r, done
                self.note_infos(infos)
                self.steps += N
            with torch.no_grad():
                feat = self.net.features(torch.from_numpy(obs["img"]).to(self.dev), torch.from_numpy(obs["st"]).to(self.dev))
                last_v = self.net.value(feat, torch.from_numpy(obs["st"]).to(self.dev),
                                        torch.from_numpy(obs["priv"]).to(self.dev)).cpu().numpy()
            adv = np.zeros((T, N), np.float32)
            gae = np.zeros(N, np.float32)
            for t in reversed(range(T)):
                nv = last_v if t == T - 1 else buf["val"][t + 1]
                nonterm = 1.0 - buf["done"][t]
                delta = buf["rew"][t] + 0.99 * nv * nonterm - buf["val"][t]
                gae = delta + 0.99 * 0.95 * nonterm * gae
                adv[t] = gae
            ret = adv + buf["val"]
            flat = lambda x: x.reshape((T * N,) + x.shape[2:])
            B_img = flat(buf_img)
            B = {k: flat(v) for k, v in buf.items()}
            B_adv, B_ret = flat(adv), flat(ret)
            B_adv = (B_adv - B_adv.mean()) / (B_adv.std() + 1e-8)
            warm = upd < a.critic_warmup
            bc_w = torch.tensor([0.1, 1.0, 1.0, 1.0], device=self.dev)
            bc_coef = a.bc_coef * max(0.1, 1.0 - upd / max(1, a.bc_decay))
            stats = []
            self.net.train()
            for ep in range(a.epochs):
                perm = np.random.permutation(T * N)
                for k in range(0, T * N, a.batch):
                    idx = perm[k:k + a.batch]
                    img = torch.from_numpy(B_img[idx]).to(self.dev)
                    st = torch.from_numpy(B["st"][idx]).to(self.dev)
                    feat = self.net.features(img, st)
                    mu = self.net.mu(feat)
                    std = self.net.log_std.exp()
                    act_t = torch.from_numpy(B["act"][idx]).to(self.dev)
                    logp = (-((act_t - mu) ** 2) / (2 * std ** 2) - std.log() - 0.5 * math.log(2 * math.pi)).sum(1)
                    ratio = (logp - torch.from_numpy(B["logp"][idx]).to(self.dev)).exp()
                    adv_t = torch.from_numpy(B_adv[idx]).to(self.dev)
                    pg = -torch.min(ratio * adv_t, ratio.clamp(0.8, 1.2) * adv_t).mean()
                    v = self.net.value(feat, st, torch.from_numpy(B["priv"][idx]).to(self.dev))
                    vl = F.mse_loss(v, torch.from_numpy(B_ret[idx]).to(self.dev))
                    # Lehrer-Rest nur für seitlich/hoch/Gieren: das Tempo (Spalte 0) soll PPO selbst finden
                    bc = (F.smooth_l1_loss(mu, torch.from_numpy(B["exp"][idx]).to(self.dev), beta=0.1,
                                           reduction="none") * bc_w).mean()
                    loss = (0.0 if warm else 1.0) * (pg + bc_coef * bc) + 0.5 * vl
                    opt.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(self.net.parameters(), 0.5)
                    opt.step()
                    with torch.no_grad():
                        self.net.log_std.clamp_(-3.5, -1.2)
                    stats.append((pg.item(), vl.item(), bc.item(), ((ratio - 1).abs().mean()).item()))
            self.net.eval()
            upd += 1
            s = np.mean(stats, axis=0)
            print(f"  PPO {upd}{' (Kritiker warm)' if warm else ''}: Belohnung/Schritt {buf['rew'].mean():.3f}, "
                  f"Tore Ø {np.mean(self.recent[-30:]) if self.recent else float('nan'):.1f}, pg {s[0]:.3f} "
                  f"v {s[1]:.3f} bc {s[2]:.4f} (x{bc_coef:.2f}) std {self.net.log_std.exp().mean().item():.2f}",
                  flush=True)
            if time.time() - last_eval > a.eval_every * 60 or time.time() >= end:
                self.evaluate(env, "ppo", {"loss": round(float(s[2]), 4)})
                obs = env.reset("train", None)
                last_eval = time.time()


def env_obs_shape(env):
    cam = camera()
    return cam.height, cam.width


def plot_curve():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = list(csv.DictReader((MODEL_DIR / "curve.csv").open()))
    if not rows:
        return
    x, off, prev = [], 0.0, 0.0
    for r in rows:                       # fortgesetzte Trainings zählen ab 0: aufaddieren
        m = float(r["minutes"])
        if m <= prev:
            off += prev
        prev = m
        x.append(off + m)
    y = [float(r["eval_gates"]) for r in rows]
    y1 = [float(r["eval_lap1"]) for r in rows]
    fig, ax = plt.subplots(figsize=(6.4, 3.2), dpi=110)
    ph = [r["phase"] for r in rows]
    for i in range(1, len(rows)):
        if ph[i] != ph[i - 1]:
            ax.axvline(x[i], color="#999", lw=0.8, ls="--")
    ax.plot(x, y, "-o", color="#e8730c", ms=3, label="Tore (bis 2 Runden)")
    ax.plot(x, y1, "-", color="#3b6fb6", lw=1.2, label="davon Runde 1")
    ax.axhline(12, color="#bbb", lw=0.6)
    ax.set_xlabel("Trainingszeit [min]")
    ax.set_ylabel("Tore ohne Lehrer")
    ax.set_title("EasyPilot Netz-Pilot: Lernkurve")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(MODEL_DIR / "curve.png")
    plt.close(fig)


# ============================================================================ Tests mit dem Spiel-Piloten
def eval_game(runs=5, path=None, expert=False):
    """Wie im Spiel: Physik 500 Hz, NNPilot aus nn.py (bzw. der Lehrer), Welt wie im Spiel."""
    from ..sysid import load_model
    from .game import Flight
    from .nn import NNPilot
    from .world import World
    rates, thrust = load_model()
    world = World()
    pilot = None
    if expert:
        from .auto import Autopilot
        line = Autopilot(world, rates, thrust, 0.6, laps=3).line
    else:
        pilot = NNPilot(world, rates, thrust, path=path)
        if not pilot.ok:
            print("kein Modell in", MODEL_DIR)
            return
        print("Modell:", pilot.label(), pilot.meta.get("date"))
    rng = random.Random(7)
    totals = []
    for run in range(runs):
        f = Flight(world, rates, thrust)
        f.armed = True
        a = rng.uniform(-0.25, 0.25)
        f.drone.pos = (rng.uniform(-0.6, 0.6), f.drone.pos[1], rng.uniform(-0.6, 0.6))
        f.drone.quat = yaw_quat(math.sin(a), math.cos(a))
        if expert:
            ex, ctl = LineExpert(line), SetpointController(rates, thrust)
            n = 0
        else:
            pilot.reset()
        t, gates, last_gate, nxt = 0.0, 0, 0.0, f.next_gate
        t0 = time.perf_counter()
        while t < EVAL_MAX_S and f.crashed_at is None and t - last_gate < NO_GATE_S and gates < 24:
            if int(round(t / 0.002)) % 25 == 0:
                world.focus(f.drone.pos)
            s = f.drone.state()
            if expert:
                if n % 33 == 0:
                    ctl.set = action_to_setpoint(ex.action(s)[0])
                if n % 4 == 0:
                    cmd = ctl.command(s)
                n += 1
            else:
                cmd = pilot.step(s)
            f.step(cmd, 0.002)
            t += 0.002
            if f.next_gate != nxt:
                gates += 1
                last_gate = t
                nxt = f.next_gate
        why = f.crash_reason or ("kein Tor mehr" if t - last_gate >= NO_GATE_S else "fertig/Zeit")
        totals.append(gates)
        extra = "" if expert else f", Bild+Netz {pilot.ms:.1f} ms"
        lap = f" (Rundenzeit {f.last_lap:.1f} s)" if f.last_lap else ""
        print(f"Lauf {run + 1}: {gates} Tore in Reihenfolge (Runde 1: {min(gates, 12)}/12){lap}, {t:.1f} s, Ende: {why} "
              f"bei {tuple(round(v, 1) for v in f.drone.pos)}{extra}, Rechenzeit {time.perf_counter() - t0:.0f} s",
              flush=True)
    print(f"Mittel {np.mean(totals):.1f} Tore, Runde 1 im Mittel {np.mean([min(g, 12) for g in totals]):.1f}/12")


def main(argv):
    if argv and argv[0] in ("eval", "lehrer"):
        runs = int(argv[1]) if len(argv) > 1 else (5 if argv[0] == "eval" else 2)
        return eval_game(runs, path=argv[2] if len(argv) > 2 else None, expert=argv[0] == "lehrer")
    p = argparse.ArgumentParser(prog="python -m autopilot.freefly.train_nn")
    p.add_argument("--minutes", type=float, default=80.0, help="Gesamtzeit")
    p.add_argument("--dagger-min", type=float, default=25.0, help="davon Imitation/DAgger (0 = gleich PPO)")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--envs", type=int, default=3, help="Umgebungen je Arbeits-Prozess")
    p.add_argument("--variants", type=int, default=3, help="Welt-Varianten je Arbeits-Prozess")
    p.add_argument("--resume", action="store_true", help="ab best.pt weiter (Versionen zählen weiter)")
    p.add_argument("--data", type=int, default=60000, help="max. Bilder im Imitations-Speicher")
    p.add_argument("--bc-iters", type=int, default=600)
    p.add_argument("--max-off", type=float, default=5.0, help="Imitation: Episode endet so weit (m) neben der Linie")
    p.add_argument("--collect", type=int, default=3000, help="Imitation: neue Schritte je DAgger-Runde")
    p.add_argument("--rollout", type=int, default=96)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch", type=int, default=288)
    p.add_argument("--lr", type=float, default=3e-5)
    p.add_argument("--std", type=float, default=0.1, help="PPO: Anfangs-Rauschen der Ausgabe (Einheiten von [-1, 1])")
    p.add_argument("--bc-coef", type=float, default=1.0)
    p.add_argument("--bc-decay", type=int, default=600, help="PPO-Updates bis der Lehrer-Verlust auf 10 %% ist")
    p.add_argument("--critic-warmup", type=int, default=30)
    p.add_argument("--eval-every", type=float, default=6.0, help="Minuten zwischen Bewertungen (PPO)")
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args(argv)
    tr = Trainer(a)
    print(f"Lernen auf {tr.dev}, {a.workers} Prozesse x {a.envs} Umgebungen, Ziel {a.minutes:.0f} min", flush=True)
    env = VecEnv(a.workers, a.envs, a.variants, a.seed)
    try:
        if a.dagger_min > 0 and not a.resume:
            tr.dagger(env, a.dagger_min)
            # mit dem besten Imitations-Modell in PPO
            if (MODEL_DIR / "best.pt").exists():
                ck = tr.torch.load(MODEL_DIR / "best.pt", map_location="cpu", weights_only=False)
                tr.net.load_state_dict(ck["state_dict"])
        rest = a.minutes - (time.time() - tr.t0) / 60
        if rest > 1:
            tr.ppo(env, rest)
    finally:
        env.close()
        try:
            st = json.loads((MODEL_DIR / "status.json").read_text())
            st["running"] = False
            (MODEL_DIR / "status.json").write_text(json.dumps(st, indent=1))
        except (OSError, ValueError):
            pass
    print(f"fertig: bestes Modell {tr.best:.1f} Tore -> {MODEL_DIR / 'best.pt'}")


if __name__ == "__main__":
    main(sys.argv[1:])
