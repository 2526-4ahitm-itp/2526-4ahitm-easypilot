"""Lern-Prozess neben dem Spiel: das Netz lernt aus seinen eigenen Flügen im Sim (und übt nebenbei ohne Fenster).

  python -m autopilot.freefly.nn_learn                 # startet das Spiel selbst (nn_show.start_learner)
  python -m autopilot.freefly.nn_learn --dauer --minutes 60    # von Hand: ohne Spiel, 60 min
  python -m autopilot.freefly.nn_learn --nur-episoden          # nur aus aufgezeichneten Flügen lernen

Ablauf (niedrige Priorität: nice 10, Rechen-Prozesse 13, höchstens --workers davon):
  1. bestes Modell (best.pt) laden und mit der Physik des Spiels prüfen (FREEFLY_PHYSIK, Standard liftoff):
     --eval-runs Läufe ohne Fenster wie in train_nn (gleiche Startlage, kein Rauschen) -> Vergleichswert.
  2. Schleife: PPO wie train_nn.Trainer.ppo, jede Aktualisierung aus
       - eigenen Übungsflügen (train_nn.VecEnv mit Domain-Randomisierung), mit kleinem Lehrer-Rest,
       - aufgezeichneten Flügen aus dem Spiel (models/freefly_nn/episodes/*.npz, nn_show.Recorder):
         jeder neue Flug einmal ganz (bis --ep-steps Schritte), dazu ein älterer zur Wiederholung.
         Die Flüge wurden von einer älteren Version geflogen: das PPO-Verhältnis zur damaligen
         Wahrscheinlichkeit (gespeichert) und das Abschneiden bei 0,8/1,2 halten das stabil.
  3. alle --eval-every Minuten Prüfung. Nur wenn die neue Version mindestens so viele Tore schafft wie
     die aktuelle, wird sie als vNNN.pt + best.pt gespeichert (das Spiel lädt sie zwischen zwei Versuchen).
     Zweimal hintereinander schlechter: zurück auf die aktuelle Version.
Ende: ohne --dauer, sobald 5 min kein Spiel mehr „Netz lernt mit“ meldet (learn.want) oder sich die Physik
ändert (das Spiel startet dann einen neuen). Stand für OSD/Studio: learn.json.
"""
import argparse
import csv
import json
import math
import os
import random
import shutil
import sys
import time

import numpy as np

from .nn import MODEL_DIR, N_PRIV, N_STATE, camera
from .nn_show import EP_DIR, LEARN, PIDFILE, WANT, read_json


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class Learner:
    def __init__(self, a):
        from . import train_nn as TN
        self.TN, self.a = TN, a
        self.physics = os.environ.get("FREEFLY_PHYSIK", "classic")
        ns = argparse.Namespace(resume=True)
        self.tr = TN.Trainer(ns)                     # lädt best.pt, Zähler aus status.json
        self.torch = self.tr.torch
        self.state = read_json(LEARN, {}) or {}
        st = self.state
        st.setdefault("days", {})
        st.setdefault("used", [])
        st["physics"] = self.physics
        st["published"] = self._best_meta().get("version")
        st["own_flights"] = max(int(st.get("own_flights", 0)), int(self._best_meta().get("own_flights", 0)))
        self.used = set(st["used"])
        self.t_save = 0.0
        self.minutes = 0.0
        self.t0 = time.time()
        self.updates = 0
        self.fails = 0
        self.base_runs = []
        cam = camera()
        self.H, self.W = cam.height, cam.width
        self.published_sd = {k: v.detach().clone() for k, v in self.tr.net.state_dict().items()}

    def _best_meta(self):
        try:
            ck = self.torch.load(MODEL_DIR / "best.pt", map_location="cpu", weights_only=False)
            return ck.get("meta", {}) or {}
        except Exception:
            return {}

    # ------------------------------------------------------------------ Zustand
    def save_state(self, phase, text, force=False):
        st = self.state
        now = time.time()
        if not force and now - self.t_save < 3.0:
            return
        self.t_save = now
        st.update(running=True, pid=os.getpid(), phase=phase, phase_text=text, updates=self.updates,
                  base=round(float(np.mean(self.base_runs)), 2) if self.base_runs else None,
                  updated=time.strftime("%Y-%m-%d %H:%M:%S"), used=sorted(self.used)[-5000:],
                  episodes_total=len(list(EP_DIR.glob("*.npz"))) if EP_DIR.exists() else 0)
        tmp = LEARN.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1))
        os.replace(tmp, LEARN)

    def add_minutes(self, dt):
        day = time.strftime("%Y-%m-%d")
        d = self.state["days"]
        d[day] = round(d.get(day, 0.0) + dt / 60.0, 2)
        self.minutes += dt / 60.0

    def keep_going(self):
        if self.a.dauer:
            return not self.a.minutes or (time.time() - self.t0) / 60 < self.a.minutes
        w = read_json(WANT, None)
        if not w or time.time() - w.get("t", 0) > 300:
            log("kein Spiel meldet mehr „Netz lernt mit“: Ende")
            return False
        if w.get("physics") != self.physics:
            log(f"Spiel nutzt jetzt Physik {w.get('physics')}: Ende (das Spiel startet einen neuen Lern-Prozess)")
            return False
        return not self.a.minutes or (time.time() - self.t0) / 60 < self.a.minutes

    # ------------------------------------------------------------------ Prüfung
    def evaluate(self, env):
        tr = self.tr
        obs = env.reset("eval", None)
        res = [None] * env.n
        t0 = time.time()
        while any(r is None for r in res) and time.time() - t0 < 300:
            a, _, _ = tr.act(obs)
            obs, _, done, infos = env.step(a)
            for i, inf in enumerate(infos):
                if inf and res[i] is None:
                    res[i] = inf
        env.reset("train", None)
        res = [r for r in res if r]
        gates = [min(r["gates"], 24) for r in res]
        return (float(np.mean(gates)) if gates else 0.0), res

    def publish(self, score, res):
        tr, torch = self.tr, self.torch
        have = [int(p.stem[1:]) for p in MODEL_DIR.glob("v[0-9][0-9][0-9].pt")]
        tr.version = max([tr.version] + have) + 1
        gates = [min(r["gates"], 24) for r in res]
        meta = {"version": tr.version, "phase": "online", "eval_gates": round(score, 2),
                "eval_lap1": round(float(np.mean([min(g, 12) for g in gates])), 2), "eval_max": max(gates),
                "eval_runs": [(r["gates"], r["crash"]) for r in res], "steps_total": tr.steps, "episodes": tr.episodes,
                "minutes": round(self.minutes, 1), "date": time.strftime("%Y-%m-%d %H:%M"), "physics": self.physics,
                "own_flights": self.state["own_flights"], "base_before": round(float(np.mean(self.base_runs)), 2)}
        ck = {"state_dict": {k: v.cpu() for k, v in tr.net.state_dict().items()}, "meta": meta}
        path = MODEL_DIR / f"v{tr.version:03d}.pt"
        torch.save(ck, path)
        tmp = MODEL_DIR / "best.tmp"
        shutil.copy(path, tmp)
        os.replace(tmp, MODEL_DIR / "best.pt")
        self.published_sd = {k: v.detach().clone() for k, v in tr.net.state_dict().items()}
        self.state["published"] = tr.version
        # Lernkurve (curve.csv/png) und status.json wie train_nn
        f = MODEL_DIR / "curve.csv"
        with f.open("a", newline="") as fh:
            csv.writer(fh).writerow([tr.version, "online", meta["minutes"], tr.steps, tr.episodes, meta["eval_gates"],
                                     meta["eval_lap1"], meta["eval_max"],
                                     round(float(np.mean(tr.recent)), 2) if tr.recent else "", ""])
        st = read_json(MODEL_DIR / "status.json", {}) or {}
        st.update(version=tr.version, phase="online", steps_total=tr.steps, episodes=tr.episodes, best_gates=score,
                  best_version=tr.version, last_gates=score, running=False, updated=meta["date"], physics=self.physics)
        (MODEL_DIR / "status.json").write_text(json.dumps(st, indent=1))
        try:
            self.TN.plot_curve()
        except Exception as e:
            log("Grafik:", e)
        log(f"v{tr.version} übernommen: {score:.1f} Tore (vorher {meta['base_before']:.1f}), "
            f"{self.state['own_flights']} eigene Flüge")

    # ------------------------------------------------------------------ Spiel-Flüge
    def game_episodes(self):
        """-> (neue, alte) Dateien passender Physik, neueste zuerst."""
        if not EP_DIR.exists():
            return [], []
        files = sorted((f for f in EP_DIR.glob("*.npz") if not f.name.endswith(".tmp.npz")), reverse=True)
        new = [f for f in files if f.name not in self.used]
        old = [f for f in files[:300] if f.name in self.used]
        return new, old

    def load_episode(self, f):
        try:
            z = np.load(f, allow_pickle=False)
            meta = json.loads(str(z["meta"]))
            if meta.get("physics") != self.physics:
                return None, meta
            pub = self.state.get("published") or 0
            if meta.get("version", 0) < pub - self.a.max_age:   # zu alte Version (z. B. Zeitraffer v1): passt nicht mehr
                return None, meta
            ep = {k: z[k] for k in ("img", "st", "priv", "act", "logp", "rew")}
            ep["terminal"] = bool(z["terminal"])
            return ep, meta
        except Exception as exc:
            log("Flug nicht lesbar:", f.name, repr(exc))
            return None, None

    def episode_batch(self, ep, n_max):
        """GAE mit dem aktuellen Kritiker über den ganzen Flug, dann bis n_max Schritte zufällig."""
        torch, net, dev = self.torch, self.tr.net, self.tr.dev
        T = len(ep["rew"])
        vals = np.zeros(T, np.float32)
        with torch.no_grad():
            for k in range(0, T, 256):
                img = torch.from_numpy(ep["img"][k:k + 256]).to(dev)
                st = torch.from_numpy(ep["st"][k:k + 256]).to(dev)
                feat = net.features(img, st)
                vals[k:k + 256] = net.value(feat, st, torch.from_numpy(ep["priv"][k:k + 256]).to(dev)).cpu().numpy()
        adv = np.zeros(T, np.float32)
        gae = 0.0
        for t in reversed(range(T)):
            last = t == T - 1
            nv = 0.0 if last and ep["terminal"] else (vals[t] if last else vals[t + 1])
            delta = ep["rew"][t] + 0.99 * nv - vals[t]
            gae = delta + 0.99 * 0.95 * gae
            adv[t] = gae
        idx = np.sort(np.random.choice(T, min(T, n_max), replace=False))
        return {"img": ep["img"][idx], "st": ep["st"][idx], "priv": ep["priv"][idx], "act": ep["act"][idx],
                "logp": ep["logp"][idx], "adv": adv[idx], "ret": (adv + vals)[idx],
                "exp": np.zeros((len(idx), 4), np.float32), "bcm": np.zeros(len(idx), np.float32)}

    # ------------------------------------------------------------------ eigene Übungsflüge
    def rollout(self, env, obs):
        tr, torch, T, N = self.tr, self.torch, self.a.rollout, env.n
        bi = np.zeros((T, N, 4, self.H, self.W), np.uint8)
        b = {k: np.zeros((T, N) + s, np.float32) for k, s in
             (("st", (N_STATE,)), ("priv", (N_PRIV,)), ("act", (4,)), ("exp", (4,)), ("logp", ()), ("val", ()),
              ("rew", ()), ("done", ()))}
        for t in range(T):
            act, logp, val = tr.act(obs, sample=True)
            bi[t] = obs["img"]
            b["st"][t], b["priv"][t], b["exp"][t] = obs["st"], obs["priv"], obs["exp"]
            b["act"][t], b["logp"][t], b["val"][t] = act, logp, val
            obs, r, done, infos = env.step(act)
            b["rew"][t], b["done"][t] = r, done
            tr.note_infos(infos)
            tr.steps += N
        with torch.no_grad():
            feat = tr.net.features(torch.from_numpy(obs["img"]).to(tr.dev), torch.from_numpy(obs["st"]).to(tr.dev))
            last_v = tr.net.value(feat, torch.from_numpy(obs["st"]).to(tr.dev),
                                  torch.from_numpy(obs["priv"]).to(tr.dev)).cpu().numpy()
        adv = np.zeros((T, N), np.float32)
        gae = np.zeros(N, np.float32)
        for t in reversed(range(T)):
            nv = last_v if t == T - 1 else b["val"][t + 1]
            nonterm = 1.0 - b["done"][t]
            delta = b["rew"][t] + 0.99 * nv * nonterm - b["val"][t]
            gae = delta + 0.99 * 0.95 * nonterm * gae
            adv[t] = gae
        fl = lambda x: x.reshape((T * N,) + x.shape[2:])
        out = {"img": fl(bi), "st": fl(b["st"]), "priv": fl(b["priv"]), "act": fl(b["act"]), "logp": fl(b["logp"]),
               "adv": fl(adv), "ret": fl(adv + b["val"]), "exp": fl(b["exp"]), "bcm": np.ones(T * N, np.float32)}
        return obs, out, float(b["rew"].mean())

    # ------------------------------------------------------------------ PPO-Schritt (wie train_nn.Trainer.ppo)
    def update(self, B):
        torch, net, dev, a = self.torch, self.tr.net, self.tr.dev, self.a
        F = torch.nn.functional
        if not hasattr(self, "opt"):
            actor = [p for k, p in net.named_parameters() if not k.startswith("critic")]
            self.opt = torch.optim.Adam([{"params": actor, "lr": a.lr}, {"params": net.critic.parameters(), "lr": 3e-4}])
            with torch.no_grad():
                net.log_std.fill_(math.log(a.std))
        n = len(B["adv"])
        adv = (B["adv"] - B["adv"].mean()) / (B["adv"].std() + 1e-8)
        bc_w = torch.tensor([0.1, 1.0, 1.0, 1.0], device=dev)
        warm = self.updates < a.critic_warmup
        stats = []
        net.train()
        for _ in range(a.epochs):
            perm = np.random.permutation(n)
            for k in range(0, n, a.batch):
                idx = perm[k:k + a.batch]
                t = lambda key: torch.from_numpy(np.ascontiguousarray(B[key][idx])).to(dev)
                img, st = t("img"), t("st")
                feat = net.features(img, st)
                mu = net.mu(feat)
                std = net.log_std.exp()
                act = t("act")
                logp = (-((act - mu) ** 2) / (2 * std ** 2) - std.log() - 0.5 * math.log(2 * math.pi)).sum(1)
                ratio = (logp - t("logp")).exp()
                adv_t = torch.from_numpy(adv[idx]).to(dev)
                pg = -torch.min(ratio * adv_t, ratio.clamp(0.8, 1.2) * adv_t).mean()
                v = net.value(feat, st, t("priv"))
                vl = F.mse_loss(v, t("ret"))
                bcm = t("bcm")
                bc = ((F.smooth_l1_loss(mu, t("exp"), beta=0.1, reduction="none") * bc_w).mean(1) * bcm).sum() \
                    / bcm.sum().clamp(min=1.0)
                loss = (0.0 if warm else 1.0) * (pg + a.bc * bc) + 0.5 * vl
                self.opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5)
                self.opt.step()
                with torch.no_grad():
                    net.log_std.clamp_(-3.5, -1.2)
                stats.append((pg.item(), vl.item(), bc.item()))
        net.eval()
        self.updates += 1
        return np.mean(stats, axis=0)

    # ------------------------------------------------------------------ Hauptschleife
    def run(self):
        a, tr = self.a, self.tr
        env = None
        if not a.nur_episoden:
            self.save_state("startet", "startet Übungsflüge", force=True)
            env = self.TN.VecEnv(a.workers, a.envs, a.variants, seed=random.randrange(1, 10000))
        try:
            if env is not None:
                self.save_state("prüft", "prüft die aktuelle Version", force=True)
                score, res = self.evaluate(env)
                self.base_runs = [score]
                log(f"Physik {self.physics}: aktuelle Version v{self.state['published']} schafft {score:.1f} Tore "
                    f"{[r['gates'] for r in res]}")
                self.state["evals"] = (self.state.get("evals") or [])[-30:] + [
                    {"t": time.strftime("%H:%M"), "version": self.state["published"], "gates": round(score, 2), "ok": True,
                     "kind": "Start"}]
                obs = env.reset("train", None)
            last_eval = time.time()
            while self.keep_going():
                t_up = time.time()
                parts, info = [], []
                if env is not None:
                    obs, B, rmean = self.rollout(env, obs)
                    parts.append(B)
                    info.append(f"Übung Belohnung {rmean:.3f}")
                new, old = self.game_episodes()
                took_new = 0
                for f in new[:a.new_per_update]:
                    ep, meta = self.load_episode(f)
                    self.used.add(f.name)
                    if ep is None:
                        continue
                    parts.append(self.episode_batch(ep, a.ep_steps))
                    took_new += 1
                    self.state["own_flights"] = int(self.state.get("own_flights", 0)) + 1
                    info.append(f"eigener Flug {meta.get('source')} v{meta.get('version')}: {meta.get('gates')} Tore")
                if old and (parts or took_new):
                    for f in random.sample(old, min(a.replay, len(old))):
                        ep, _ = self.load_episode(f)
                        if ep is not None:
                            parts.append(self.episode_batch(ep, a.ep_steps // 3))
                if not parts:
                    self.save_state("wartet", "wartet auf neue Flüge")
                    time.sleep(5.0)
                    continue
                B = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
                s = self.update(B)
                self.add_minutes(time.time() - t_up)
                if self.updates % 5 == 1 or took_new:
                    log(f"Lernschritt {self.updates}: {len(B['adv'])} Schritte, pg {s[0]:.3f} v {s[1]:.3f} "
                        f"bc {s[2]:.3f} · " + " · ".join(info))
                self.save_state("lernt", f"übt ({self.state['own_flights']} eigene Flüge)")
                if env is not None and time.time() - last_eval > a.eval_every * 60:
                    self.save_state("prüft", "prüft eine neue Version", force=True)
                    score, res = self.evaluate(env)
                    obs = env.reset("train", None)
                    base = float(np.mean(self.base_runs))
                    ok = score >= base
                    self.state["evals"] = (self.state.get("evals") or [])[-30:] + [
                        {"t": time.strftime("%H:%M"), "version": tr.version + 1 if ok else None, "gates": round(score, 2),
                         "ok": ok, "base": round(base, 2)}]
                    if ok:
                        self.publish(score, res)
                        self.base_runs = [score]
                        self.fails = 0
                    else:
                        self.fails += 1
                        log(f"Prüfung: {score:.1f} Tore < {base:.1f} (aktuelle v{self.state['published']}): nicht übernommen"
                            f"{', zurück auf die aktuelle Version' if self.fails >= 2 else ''}")
                        if self.fails >= 2:
                            tr.net.load_state_dict(self.published_sd)
                            self.fails = 0
                            # aktuelle Version noch einmal messen: der Vergleichswert soll kein Glückstreffer sein
                            sc, _ = self.evaluate(env)
                            obs = env.reset("train", None)
                            self.base_runs = (self.base_runs + [sc])[-4:]
                    last_eval = time.time()
                    self.save_state("lernt", "übt weiter", force=True)
        finally:
            if env is not None:
                env.close()
            self.state["running"] = False
            self.state["phase"], self.state["phase_text"] = "aus", "aus"
            self.state["used"] = sorted(self.used)[-5000:]
            try:
                tmp = LEARN.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1))
                os.replace(tmp, LEARN)
            except OSError:
                pass


def main(argv):
    p = argparse.ArgumentParser(prog="python -m autopilot.freefly.nn_learn")
    p.add_argument("--workers", type=int, default=2, help="Rechen-Prozesse für Übungsflüge")
    p.add_argument("--envs", type=int, default=3)
    p.add_argument("--variants", type=int, default=3)
    p.add_argument("--rollout", type=int, default=96)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch", type=int, default=288)
    p.add_argument("--lr", type=float, default=3e-5)
    p.add_argument("--std", type=float, default=0.1)
    p.add_argument("--bc", type=float, default=0.1, help="Lehrer-Rest bei den Übungsflügen")
    p.add_argument("--critic-warmup", type=int, default=15, help="so viele Schritte erst nur den Kritiker anpassen")
    p.add_argument("--eval-every", type=float, default=8.0, help="Minuten zwischen Prüfungen")
    p.add_argument("--new-per-update", type=int, default=1, help="neue eigene Flüge je Lernschritt")
    p.add_argument("--replay", type=int, default=1, help="ältere eigene Flüge je Lernschritt")
    p.add_argument("--ep-steps", type=int, default=900, help="höchstens so viele Schritte je Flug und Lernschritt")
    p.add_argument("--max-age", type=int, default=8, help="Flüge von Versionen, die so viel älter sind, auslassen")
    p.add_argument("--minutes", type=float, default=0.0, help="0 = so lange ein Spiel es will")
    p.add_argument("--dauer", action="store_true", help="ohne Spiel weiterlernen (bis --minutes)")
    p.add_argument("--nur-episoden", action="store_true", help="keine eigenen Übungsflüge, keine Prüfung")
    a = p.parse_args(argv)
    import signal
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))      # kill: trotzdem sauber beenden (finally)
    try:
        os.nice(10)
    except OSError:
        pass
    os.environ.setdefault("FREEFLY_PHYSIK", "liftoff")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        other = int(PIDFILE.read_text().strip())
        if other != os.getpid():
            os.kill(other, 0)
            log(f"Lern-Prozess läuft schon (pid {other})")
            return
    except (OSError, ValueError):
        pass
    PIDFILE.write_text(str(os.getpid()))
    try:
        L = Learner(a)
        log(f"Lern-Prozess: Physik {L.physics}, Modell v{L.state['published']}, Gerät {L.tr.dev}, "
            f"{0 if a.nur_episoden else a.workers} Rechen-Prozesse")
        L.run()
    finally:
        try:
            if PIDFILE.read_text().strip() == str(os.getpid()):
                PIDFILE.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main(sys.argv[1:])
