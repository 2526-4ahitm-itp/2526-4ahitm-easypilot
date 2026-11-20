"""Physik gegen echte Liftoff-Flüge prüfen: gleiche Stickfolge, Liftoff-Aufnahme vs. Modell.

  python -m autopilot.freefly.fit_physics [sekunden] [max_fenster]

Liest die Telemetrie-Logs aus ~/EasyPilot/runs (Session.log von race/studio/hover: Lage, Geschwindigkeit,
Gyro und die gesendeten Sticks cmd_*), schneidet Fenster von `sekunden` Länge heraus (ohne Crashes,
Resets und Bodenkontakt) und rechnet sie mit sim.SimDrone („Klassisch“) und physics.LiftoffDrone
(„Liftoff-nah“) nach: Startzustand aus der Aufnahme, danach nur noch die Sticks (Liftoff reagiert
10 ms nach dem Senden, so wird auch hier eingespeist). Ausgabe: mittlerer Fehler von Geschwindigkeit,
Höhe, Lage und Drehrate am Fensterende und über das Fenster gemittelt, alt gegen neu.

Die Parameter in physics.LiftoffParams kommen aus einem Nelder-Mead-Fit auf der Hälfte der Log-Dateien
(is_test() falsch); diese Auswertung nutzt nur die andere Hälfte.
"""
import csv
import glob
import math
import os
import sys
import zlib
from pathlib import Path

from ..geometry import qconj, qmul
from ..sim import SimDrone, SimParams
from ..sysid import load_model
from .game import DRAG
from .physics import LiftoffDrone, LiftoffParams

RUNS = Path(os.environ.get("EASYPILOT_RUNS") or Path.home() / "EasyPilot" / "runs")
COLS = ["t", "x", "y", "z", "qx", "qy", "qz", "qw", "vx", "vy", "vz", "gx", "gy", "gz",
        "cmd_t", "cmd_y", "cmd_p", "cmd_r"]


def is_test(path):
    """Feste Aufteilung nach Datei: die Hälfte der Logs (crc32 ungerade) wird nie zum Fitten benutzt."""
    return zlib.crc32(os.path.basename(path).encode()) % 2 == 1


def load_runs(root=RUNS, test=None):
    """Zusammenhängende Stücke (Zeitschritt 7-25 ms, kein Sprung) aus allen Logs mit gesendeten Sticks.
    test=True/False: nur Test- bzw. nur Trainingsdateien."""
    out = []
    for f in sorted(glob.glob(str(root / "*.csv"))):
        with open(f) as fh:
            rd = csv.reader(fh)
            try:
                head = next(rd)
            except StopIteration:
                continue
            if not all(c in head for c in COLS) or (test is not None and is_test(f) != test):
                continue
            idx = [head.index(c) for c in COLS]
            rows = []
            for r in rd:
                try:
                    rows.append([float(r[i]) for i in idx])
                except (ValueError, IndexError):
                    pass
        seg = []
        for r in rows:
            if seg:
                p = seg[-1]
                dt = r[0] - p[0]
                if not (0.007 < dt < 0.025) or math.dist(r[1:4], p[1:4]) > 1.5:
                    if len(seg) > 50:
                        out.append(seg)
                    seg = []
            seg.append(r)
        if len(seg) > 50:
            out.append(seg)
    return out


def windows(segs, steps, every=20):
    w = []
    for s in segs:
        for i in range(1, len(s) - steps - 1, every):
            part = s[i - 1:i + steps + 1]
            ok = all(r[2] > 0.5 for r in part)
            for a, b in zip(part, part[1:]):
                dt = b[0] - a[0]
                if math.dist(a[8:11], b[8:11]) / max(dt, 1e-3) > 60.0:      # Aufprall
                    ok = False
                    break
            if ok:
                w.append(part)
    return w


def angle_between(a, b):
    d = qmul(qconj(a), b)
    return math.degrees(2.0 * math.acos(min(1.0, abs(d[3]))))


def make(kind, row, prev, rates, thrust, params=None):
    pos, quat, vel = tuple(row[1:4]), tuple(row[4:8]), tuple(row[8:11])
    omega = tuple(math.radians(v) for v in (row[11], row[13], row[12]))     # Liftoff-Gyro (Nick, Roll, Gier)
    if kind == "classic":
        p = SimParams(hover_throttle=thrust.hover_throttle, thrust_exponent=thrust.exponent,
                      drag=DRAG, inflow=thrust.inflow, airmode=thrust.airmode)
        d = SimDrone(pos, quat, vel, p, rates)
        d.thrust = thrust.k * max(0.0, prev[14]) ** thrust.exponent
    else:
        d = LiftoffDrone(pos, quat, vel, params or LiftoffParams(), rates)
        d.motor = max(0.0, prev[14])
        dt = row[0] - prev[0]
        prev_om = tuple(math.radians(v) for v in (prev[11], prev[13], prev[12]))
        d.domega = [(a - b) / dt for a, b in zip(omega, prev_om)]
        d.ground_level = -1e9                   # Höhe der Liftoff-Wiese unbekannt: Bodeneffekt aus
    d.omega = omega
    d.ground = -1e9
    return d


def run(kind, ws, rates, thrust, sub=5, params=None):
    """Fehler je Fenster: (v am Ende, v Mittel, Höhe am Ende, Lage am Ende, Drehrate Mittel)."""
    res = []
    for w in ws:
        d = make(kind, w[1], w[0], rates, thrust, params)
        ev, eg = [], []
        for k in range(1, len(w) - 1):
            cmd = w[k - 1]                          # 10 ms Eingabeverzögerung wie in Liftoff
            dt = (w[k + 1][0] - w[k][0]) / sub
            for _ in range(sub):
                d.step(cmd[14], cmd[15], cmd[16], cmd[17], dt)
            ref = w[k + 1]
            ev.append(math.dist(d.vel, ref[8:11]))
            om = tuple(math.degrees(v) for v in d.omega)
            eg.append(math.dist(om, (ref[11], ref[13], ref[12])))
        end = w[-1]
        res.append((ev[-1], sum(ev) / len(ev), abs(d.pos[1] - end[2]), angle_between(d.quat, tuple(end[4:8])),
                    sum(eg) / len(eg)))
    return res


def summary(res):
    n = len(res)
    return [sum(r[i] for r in res) / n for i in range(5)]


def main(argv):
    nums = [a for a in argv if not a.startswith('--')]
    secs = float(nums[0]) if nums else 1.0
    limit = int(nums[1]) if len(nums) > 1 else 800
    rates, thrust = load_model()
    segs = load_runs(test=True)
    steps = int(round(secs / 0.01))
    ws = windows(segs, steps)
    test = ws[::max(1, len(ws) // limit)][:limit]
    print(f"Liftoff-Aufnahmen (Testdateien, nie gefittet): {len(segs)} Stücke, {sum(len(s) for s in segs)} Zeilen, "
          f"{len(ws)} Fenster à {secs:.1f} s, geprüft {len(test)}")
    hdr = f"{'':12s} {'v Ende':>8s} {'v Mittel':>9s} {'Höhe Ende':>10s} {'Lage Ende':>10s} {'Drehrate':>9s}"
    print(hdr)
    out = {}
    for kind, name in (("classic", "Klassisch"), ("liftoff", "Liftoff-nah")):
        s = summary(run(kind, test, rates, thrust))
        out[kind] = s
        print(f"{name:12s} {s[0]:6.2f} m/s {s[1]:6.2f} m/s {s[2]:8.2f} m {s[3]:8.1f} ° {s[4]:6.1f} °/s")
    a, b = out["classic"], out["liftoff"]
    print("Verbesserung: " + ", ".join(f"{n} {100 * (1 - y / x):.0f} %" for n, x, y in
                                       zip(("v Ende", "v Mittel", "Höhe", "Lage", "Drehrate"), a, b)))
    if "--ablation" in argv:
        import dataclasses
        base = LiftoffParams()
        for name, ch in (("ohne Widerstand je Achse", dict(cx=DRAG, cy=DRAG, cz=DRAG, lin=0.0, lin_y=0.0)),
                         ("ohne Inflow-Fit (1.37)", dict(inflow=1.37, vsat=1e6)),
                         ("ohne Motor-Fit (30 ms)", dict(tau_up=0.03, tau_down=0.03)),
                         ("Raten-Regler weich", dict(rate_wn=25.0, rate_zeta=1.0)),
                         ("ohne Propwash", dict(propwash=0.0))):
            s = summary(run("liftoff", test, rates, thrust, params=dataclasses.replace(base, **ch)))
            print(f"  {name:26s} {s[0]:6.2f} m/s {s[1]:6.2f} m/s {s[2]:8.2f} m {s[3]:8.1f} ° {s[4]:6.1f} °/s")
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
