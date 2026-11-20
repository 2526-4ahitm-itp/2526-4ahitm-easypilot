"""Freies Fliegen im eigenen Mini-Simulator: Acro wie in Liftoff, ohne Liftoff und ohne Autopilot.

FPV-Kamera mit Uptilt, Flugmodell aus sim.py (gleiche Raten, Schubkurve und Airmode wie die
vermessene Liftoff-Drohne in drone.json), Dorf mit Häusern und Straßen, Bäume, 12 Tore als
Rundkurs (das nächste Tor leuchtet magenta, Pfeil am Rand zeigt hin). Gesteuert wird mit der
kalibrierten Fernsteuerung (pilot.Controller, am Mac die DJI FPV RC 3 über hid_mac), ohne
Controller mit der Tastatur (W/S Gas, A/D Gieren, Pfeile Nicken/Rollen).

  python -m autopilot.freefly              # Vollbild, startet im Menü
  python -m autopilot.freefly --window     # Fenster 1280x800
  python -m autopilot.freefly --physik klassisch   # alte Physik (sim.py); Standard ist Liftoff-nah (physics.py)
  python -m autopilot.freefly --physik real --wind leicht   # echte 5"-Drohne mit Betaflight (physics_real.py)
  python -m autopilot.freefly --strecke profi      # Strecke (tracks.py: anfaenger, dorfrunde, scheunen, turm, profi)
  python -m autopilot.freefly --bench 10   # sofort fliegen, nach 10 s Latenz/Frame-Rate ausgeben
  python -m autopilot.freefly --window --bench 25 --autopilot --bomb     # Auto-Bomben
  python -m autopilot.freefly --window --bench 25 --autopilot --camera   # Autopilot nur aus dem Kamerabild

Autopilot (P oder Menü): im Rennen wahlweise Rennlinie oder nur Kamera (Menü „Autopilot-Modus“),
im Bomben-Modus fliegt immer BombAutopilot. Pro Bomben-Ziel 30 s (Zeit im Menü zählt nicht), dann neues Ziel.

Esc = Menü, R / Leertaste / Knopf an der Fernsteuerung = Neustart, H = Anzeige, O = Lageanzeige (attitude.py),
T = Steuerung umschalten (Automatisch / RC 3 / Tastatur, controls.py; Fernsteuerung darf später angesteckt werden).
Nach Absturz, Treffer oder Runden-Ende: Blick auf die Stelle, abblenden, Countdown (restart.py), R überspringt.
Nach Start und Absturz ist die Drohne erst scharf, wenn das Gas ganz unten war.

Latenz: jeder Frame liest die Sticks (IOKit-Callback, +0,5 ms laut hid_mac), rechnet die Physik
bis "jetzt" in 2-ms-Schritten, zeichnet und wartet, bis die GPU fertig ist. Gemessen wird
Stick lesen -> Bild fertig (ctx.finish + flip); dazu kommt im Mittel ein halber Frame Abtastung.
"""
import argparse
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

if sys.platform == "darwin":
    os.environ["SDL_VIDEODRIVER"] = "cocoa"       # pilot.py stellt sonst "dummy" ein
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import moderngl
import pygame

from ..geometry import axis_angle, qmul
from ..sysid import load_camera, load_model
from . import fx
from .game import Flight
from .gfx import Renderer
from .physics import PHYSICS as PHYSICS_NAMES
from .physics_real import WIND_LABEL, WIND_ORDER, ap_thrust   # Wind/Böen, Regler-Schubmodell für „Realistisch“
from .entities import Entities, bus_mesh, car_mesh, person_mesh
from .controls import CTL_LABEL, CTL_MODES, Controls, open_controller
from .restart import RestartSeq
from .ui import Hud, Menu
from . import osd as osd_ui                   # Liftoff-OSD, Elemente und Presets (Menü „Anzeige / OSD …“)
from . import nn_show                         # KI-Showcase: Lernen zuschauen, Zeitraffer, Aufzeichnung (Menü „KI-Showcase …“)
from .world import World
from . import tracks                          # Strecken (Menü „Strecke“, --strecke), Bestzeit je Strecke

DT = 0.002              # s, Physik-Schritt (500 Hz)
SETTINGS = Path(__file__).resolve().parent.parent / "freefly.local.json"


KB_GAS = 0.8            # Gas pro Sekunde (W/S) bei „Gas-Tempo“ 1.0x
# Tastatur, Fernsteuerung und das Umschalten im Spiel (Taste T, Menü „Steuerung“): controls.py
# Neustart mit Blick auf die Absturzstelle, Abblenden, Countdown: restart.py


def _user_sim_running():
    """Läuft gerade ein Sim zum Fliegen (ohne --bench)? Dann darf ein Testlauf nicht sichtbar aufgehen."""
    import os
    import subprocess
    try:
        out = subprocess.run(["pgrep", "-fl", "autopilot.freefly"], capture_output=True, text=True).stdout
    except OSError:
        return False
    for line in out.splitlines():
        pid, _, cmd = line.partition(" ")
        if pid.strip() == str(os.getpid()) or "--bench" in cmd or "--remote" in cmd or "freefly." in cmd \
                or "claude" in cmd or "zsh" in cmd:
            continue
        if "-m autopilot.freefly" in cmd:
            return True
    return False


def load_settings(cam_tilt, hfov):
    s = {"tilt": round(cam_tilt), "fov": round(hfov), "mark": True, "hud": True, "best_lap": None,
         "ap_k": 0.6, "show_line": True, "quick": False, "mode": "race", "ap_mode": "line", "kb_sens": 0.6, "kb_gas": 1.0, "ctl": "auto",
         "physik": "liftoff"}            # Liftoff-nah (physics.py); "classic" = sim.py; OSD-Elemente: osd.ensure
    try:
        s.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    s["strecke"] = tracks.key(s.get("strecke") or tracks.DEFAULT)
    if not isinstance(s.get("best_laps"), dict):      # Bestzeit je Strecke; die alte gilt für die Dorfrunde
        s["best_laps"] = {"dorfrunde": s.get("best_lap")} if s.get("best_lap") else {}
    s["best_lap"] = s["best_laps"].get(s["strecke"])
    osd_ui.ensure(s)                   # "osd": Elemente; alte "lage"/"karte" werden übernommen
    nn_show.ensure(s)                  # "nnshow": KI-Einblendungen, "nn_learn": Netz lernt mit (nn_show.py)
    s["auto"] = False                 # Autopilot nie von selbst einschalten
    s["mode"] = "race"                 # Bomben-Modus wählt man im Menü (B)
    return s


def save_settings(s):
    if s.get("no_save"):                 # --bench: Messläufe ändern die Einstellungen nicht
        return
    try:
        SETTINGS.write_text(json.dumps({k: v for k, v in s.items() if k not in ("auto", "mode", "no_save")}, indent=1), encoding="utf-8")
    except OSError:
        pass


MENU = [{"label": "Fliegen", "kind": "action", "key": "resume"},
        {"label": "Neustart am Startplatz", "kind": "action", "key": "restart"},
        {"label": "Zerstörung zurücksetzen (Z)", "kind": "action", "key": "repair"},
        {"label": "Modus", "kind": "value", "key": "mode"},
        {"label": "Strecke", "kind": "value", "key": "strecke"},
        {"label": "Kamera-Uptilt", "kind": "value", "key": "tilt"},
        {"label": "Sichtfeld", "kind": "value", "key": "fov"},
        {"label": "Physik", "kind": "value", "key": "physik"},
        {"label": "Wind", "kind": "value", "key": "wind"},
        {"label": "Autopilot fliegt", "kind": "toggle", "key": "auto"},
        {"label": "Autopilot-Modus", "kind": "value", "key": "ap_mode"},
        {"label": "Autopilot-Tempo (k)", "kind": "value", "key": "ap_k"},
        {"label": "Rennlinie zeigen", "kind": "toggle", "key": "show_line"},
        {"label": "Tore markieren", "kind": "toggle", "key": "mark"},
        {"label": "Anzeige / OSD …", "kind": "action", "key": "osd"},
        {"label": "KI-Showcase …", "kind": "action", "key": "nnshow"},
        {"label": "Schnell-Neustart (ohne Countdown)", "kind": "toggle", "key": "quick"},
        {"label": "Steuerung (T)", "kind": "value", "key": "ctl"},
        {"label": "Tastatur-Empfindlichkeit", "kind": "value", "key": "kb_sens"},
        {"label": "Gas-Tempo (W/S)", "kind": "value", "key": "kb_gas"},
        {"label": "Beenden", "kind": "action", "key": "quit"}]


AP_MODES = {"line": "Rennlinie", "camera": "Nur Kamera", "nn": "Neuronales Netz",
            "nn_learn": "KI: Lernen zuschauen", "nn_replay": "KI: Zeitraffer"}     # nn_show.py
BOMB_TIMEOUT = 30.0     # s: so lange pro Bomben-Ziel, dann kommt ein neues


def menu_values(s):
    onoff = lambda k: "an" if s[k] else "aus"
    return {"tilt": f"{s['tilt']}°", "fov": f"{s['fov']}°", "mark": onoff("mark"), "hud": onoff("hud"),
            "auto": onoff("auto"), "mode": "Bomben" if s["mode"] == "bomb" else "Rennen (Tore)", "ap_k": f"{s['ap_k']:.1f}", "show_line": onoff("show_line"), "quick": onoff("quick"),
            "ap_mode": "Bomben-Ziele" if s["mode"] == "bomb" else AP_MODES[s["ap_mode"]],
            "kb_sens": f"{round(s['kb_sens'] * 100)} %", "kb_gas": f"{s['kb_gas']:.1f}x",
            "ctl": CTL_LABEL.get(s.get("ctl"), "Automatisch"),
            "physik": PHYSICS_NAMES.get(s.get("physik"), "Klassisch"),
            "wind": WIND_LABEL.get(s.get("wind"), "aus") if s.get("physik") == "real" else "nur bei Realistisch",
            "strecke": tracks.label(s.get("strecke")),
            **osd_ui.menu_values(s), **nn_show.menu_values(s)}


def change(s, key, direction):
    if osd_ui.change(s, key, direction) or nn_show.change(s, key, direction):
        pass
    elif key == "tilt":
        s["tilt"] = max(0, min(70, s["tilt"] + 5 * direction))
    elif key == "fov":
        s["fov"] = max(80, min(150, s["fov"] + 5 * direction))
    elif key == "mode":
        s["mode"] = "race" if s["mode"] == "bomb" else "bomb"
    elif key == "strecke":
        order = tracks.ORDER
        i = order.index(s["strecke"]) if s.get("strecke") in order else 0
        s["strecke"] = order[(i + (direction or 1)) % len(order)]
    elif key == "ap_mode":
        order = list(AP_MODES)
        s["ap_mode"] = order[(order.index(s["ap_mode"]) + (direction or 1)) % len(order)] if s["ap_mode"] in order else "line"
        if s["ap_mode"] in ("nn_learn", "nn_replay"):
            s["auto"] = True               # Showcase: gleich losfliegen lassen
    elif key == "kb_sens":
        s["kb_sens"] = round(max(0.1, min(1.0, s["kb_sens"] + 0.1 * direction)), 1)
    elif key == "kb_gas":
        s["kb_gas"] = round(max(0.2, min(3.0, s["kb_gas"] + 0.2 * direction)), 1)
    elif key == "ctl":
        i = CTL_MODES.index(s["ctl"]) if s.get("ctl") in CTL_MODES else 0
        s["ctl"] = CTL_MODES[(i + direction) % len(CTL_MODES)]
    elif key == "physik":                  # Klassisch -> Liftoff-nah -> Realistisch (physics_real.py)
        order = list(PHYSICS_NAMES)
        i = order.index(s["physik"]) if s.get("physik") in order else 0
        s["physik"] = order[(i + (direction or 1)) % len(order)]
    elif key == "wind":
        i = WIND_ORDER.index(s["wind"]) if s.get("wind") in WIND_ORDER else 0
        s["wind"] = WIND_ORDER[(i + (direction or 1)) % len(WIND_ORDER)]
    elif key == "ap_k":
        s["ap_k"] = round(max(0.2, min(1.2, s["ap_k"] + 0.1 * direction)), 1)
    else:
        s[key] = not s[key]


def stats_text(read_to_done, frame_times):
    if len(read_to_done) < 10:
        return "zu wenige Frames"
    lat, ft = sorted(read_to_done), sorted(frame_times)

    def q(xs, p):
        return xs[min(len(xs) - 1, int(p * len(xs)))] * 1000
    fps = 1.0 / statistics.mean(frame_times)
    return (f"Frames {len(lat)}, {fps:.0f} fps (Frame-Zeit Median {q(ft, .5):.2f} ms, 99 % {q(ft, .99):.2f} ms)\n"
            f"Stick lesen -> Bild fertig: Median {q(lat, .5):.2f} ms, 99 % {q(lat, .99):.2f} ms, max {lat[-1] * 1000:.2f} ms\n"
            f"Zusatzlatenz gesamt (+ halber Frame Abtastung): ca. {q(lat, .5) + q(ft, .5) / 2:.2f} ms Median")


def _swap_interval(n):
    """Nicht auf den Bildschirm-Takt warten: Bild sofort zeigen (weniger Latenz)."""
    try:
        import ctypes
        import glob
        lib = glob.glob(os.path.join(os.path.dirname(pygame.__file__), ".dylibs", "libSDL2*.dylib"))
        if lib:
            ctypes.CDLL(lib[0]).SDL_GL_SetSwapInterval(n)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="EasyPilot Freiflug")
    ap.add_argument("--window", action="store_true", help="im Fenster statt Vollbild")
    ap.add_argument("--size", default="1280x800")
    ap.add_argument("--max-fps", type=float, default=240.0, help="Obergrenze der Bildrate (0 = ohne)")
    ap.add_argument("--bench", type=float, default=0.0, help="sofort fliegen, nach so vielen Sekunden enden und messen")
    ap.add_argument("--keyboard", action="store_true", help="Tastatur statt Fernsteuerung")
    ap.add_argument("--shot", help="beim Beenden das letzte Bild als PNG speichern")
    ap.add_argument("--pose", help="x,y,z,gier,nick (Grad): Drohne dort einfrieren (für Bilder)")
    ap.add_argument("--menu", action="store_true", help="mit --bench: Menü zeigen")
    ap.add_argument("--autopilot", action="store_true", help="Autopilot fliegt von Anfang an")
    ap.add_argument("--bomb", action="store_true", help="im Bomben-Modus starten")
    ap.add_argument("--camera", action="store_true", help="Autopilot-Modus 'nur Kamera'")
    ap.add_argument("--line", action="store_true", help="Autopilot-Modus 'Rennlinie' (unabhängig vom gespeicherten Modus)")
    ap.add_argument("--nn", action="store_true", help="Autopilot-Modus 'Neuronales Netz' (nn.py)")
    ap.add_argument("--nn-show", choices=("lernen", "zeitraffer"), help="KI-Showcase: Lernen zuschauen / Zeitraffer (nn_show.py)")
    ap.add_argument("--boom-test", type=float, default=0.0, help="nach so vielen s ins Ziel stürzen (Test)")
    ap.add_argument("--remote", type=int, default=0, help="Fernsteuerung für EasyPilot Studio auf diesem Port (remote.py)")
    ap.add_argument("--physik", choices=("klassisch", "liftoff", "real"),
                    help="Flugphysik: klassisch (sim.py), liftoff (physics.py, Liftoff-nah) oder real "
                         "(physics_real.py, echte 5\"-Drohne mit Betaflight); sonst aus dem Menü / FREEFLY_PHYSIK")
    ap.add_argument("--wind", choices=WIND_ORDER, help="Wind und Böen (nur Physik real); sonst Menü / FREEFLY_WIND")
    ap.add_argument("--strecke", help="Strecke: " + ", ".join(tracks.ORDER) + " (oder 1-5); sonst aus dem Menü")
    args = ap.parse_args()

    rates, thrust = load_model()
    cam = load_camera()
    t0 = time.perf_counter()
    settings = load_settings(rates.camera_angle_deg, cam.hfov_deg)
    if args.strecke:
        settings["strecke"] = tracks.key(args.strecke)
    world = World(track=settings["strecke"])
    print(f"Welt: {len(world.vertices) // 3} Dreiecke, {len(world.boxes)} Kollisionsboxen, "
          f"Strecke {world.track_info['name']}, {len(world.gates)} Tore ({time.perf_counter() - t0:.1f} s)")

    pygame.init()
    for attr, val in ((pygame.GL_CONTEXT_MAJOR_VERSION, 3), (pygame.GL_CONTEXT_MINOR_VERSION, 3),
                      (pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE),
                      (pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, 1), (pygame.GL_MULTISAMPLEBUFFERS, 1),
                      (pygame.GL_MULTISAMPLESAMPLES, 4)):
        pygame.display.gl_set_attribute(attr, val)
    flags = pygame.OPENGL | pygame.DOUBLEBUF
    if args.window:
        size = tuple(int(v) for v in args.size.split("x"))
    else:
        flags |= pygame.FULLSCREEN
        size = (0, 0)
    if _user_sim_running():               # jeder zweite Sim (Test, Studio-Test, --window) bleibt unsichtbar
        # Testlauf, während Simon fliegt: Fenster unsichtbar, damit es ihn nicht aus dem Vollbild holt
        flags |= pygame.HIDDEN
        if not args.window:
            flags &= ~pygame.FULLSCREEN
            size = (1920, 1080)
        print("Testlauf unsichtbar (ein Sim zum Fliegen läuft gerade)")
    pygame.display.set_mode(size, flags, vsync=0)
    pygame.display.set_caption("EasyPilot – Freiflug")
    size = pygame.display.get_window_size()
    ctx = moderngl.create_context()
    _swap_interval(0)
    renderer = Renderer(ctx, world, size, settings["fov"], settings["tilt"])
    hud = Hud(renderer)
    menu = Menu(hud, MENU)
    osd_menu = Menu(hud, osd_ui.MENU)              # Untermenü „Anzeige / OSD“
    nn_menu = Menu(hud, nn_show.MENU)              # Untermenü „KI-Showcase“
    cur_menu = [menu]
    losd = osd_ui.LiftoffOsd(renderer)
    from .attitude import Lage
    lage = Lage(renderer, world)                  # Horizont, Kompass, Leisten, 3D-Drohne, Minikarte (attitude.py)

    if args.keyboard:
        settings["ctl"] = "keyboard"
    pad = Controls(settings["ctl"], settings["kb_sens"], KB_GAS * settings["kb_gas"],
                   None if settings["ctl"] == "keyboard" else open_controller())
    seq = RestartSeq()                            # Neustart-Ablauf (restart.py)
    flight = Flight(world, rates, thrust)
    from .auto import Autopilot, BombAutopilot, CameraAutopilot
    pilot = {"line": None, "camera": None, "bomb": None, "nn": None}
    nn_overlay = []                                # nn_show.Show (Einblendungen, Aufzeichnung), sobald das Netz fliegt

    def ap_kind():
        if settings["mode"] == "bomb":
            return "bomb"
        return "nn" if settings["ap_mode"] in nn_show.SHOW_MODES else settings["ap_mode"]

    def nn_active():
        return bool(settings["auto"] and ap_kind() == "nn" and nn_overlay and pilot["nn"] is not None)

    def line_pilot():
        if pilot["line"] is None or pilot["line"].k != settings["ap_k"]:
            pilot["line"] = Autopilot(world, rates, ap_thrust(thrust, settings["physik"]), settings["ap_k"], laps=3)
            line = pilot["line"].line
            print(f"Autopilot: Rennlinie {line.length:.0f} m, k={settings['ap_k']}, "
                  f"Vias {getattr(line, 'vias', 0)}, geplant in {pilot['line'].plan_time:.2f} s")
        return pilot["line"]

    def autopilot():
        """Der Autopilot für den aktuellen Modus (einmal gebaut, dann nur noch reset())."""
        kind = ap_kind()
        if kind == "line":
            return line_pilot()
        if kind == "camera":
            if pilot["camera"] is None:
                t0 = time.perf_counter()
                pilot["camera"] = CameraAutopilot(world, rates, ap_thrust(thrust, settings["physik"]), ctx=ctx, speed=10 * settings["ap_k"])
                print(f"Kamera-Autopilot: {pilot['camera'].cam.width} px, {time.perf_counter() - t0:.2f} s")
            pilot["camera"].speed = 10 * settings["ap_k"]       # k=0,6 -> 6 m/s (so getestet)
            return pilot["camera"]
        if kind == "nn":                           # Neuronales Netz: nur Kamerabild + Flugzustand (nn.py)
            if pilot["nn"] is None:
                from .nn import NNPilot
                pilot["nn"] = NNPilot(world, rates, thrust, ctx=ctx)
                nn_overlay.append(nn_show.Show(renderer, "studio" if args.remote else "test" if args.bench else "spiel",
                                               settings.get("physik", "classic")))
                print(f"Netz-Pilot: {pilot['nn'].label()}")
            return pilot["nn"]
        if pilot["bomb"] is None:
            pilot["bomb"] = BombAutopilot(world, rates, ap_thrust(thrust, settings["physik"]), entities)
        return pilot["bomb"]

    def ap_label():
        kind = ap_kind()
        if kind == "nn":
            return nn_overlay[0].label(pilot["nn"]) if nn_overlay else "Netz · lädt"
        return {"line": f"Rennlinie k={settings['ap_k']:.1f}", "camera": f"nur Kamera {10 * settings['ap_k']:.0f} m/s",
                "bomb": "Bomben"}[kind] + (f" · {pilot['bomb'].info}" if kind == "bomb" and pilot["bomb"] else "")

    explosions = []
    fxtex = fx.FxTextures(renderer)
    entities = Entities(world)
    flight.entities = entities
    models = {k: renderer.entity_vao(m, 64) for k, m in
              (("person", person_mesh()), ("car", car_mesh()), ("bus", bus_mesh()))}

    def repair():
        """Alles Zerstörte wieder aufbauen: Ziele (Personen, Autos, Busse), Häuser, Krater."""
        entities.revive()
        world.revive()
        renderer.set_craters([])
        if flight.mode == "bomb":
            flight.next_target()
        flight.say("Zerstörung zurückgesetzt", "alles wieder heil", 2.0)

    def switch_track():
        """Andere Strecke: Welt neu bauen (gleiches Dorf, andere Tore) und alles, was an ihr hängt."""
        nonlocal world, entities, lage
        t0 = time.perf_counter()
        world = World(track=settings["strecke"])
        settings["strecke"] = world.track
        renderer.set_world(world)
        lage = Lage(renderer, world)
        entities = Entities(world)
        flight.world, flight.entities = world, entities
        flight.target = None
        for k in pilot:
            pilot[k] = None                         # Autopiloten planen für die neue Strecke neu
        explosions.clear()
        settings["best_lap"] = settings["best_laps"].get(world.track)
        if remote is not None:
            remote.world = world
            remote.send({"hello": remote.hello()})
        print(f"Strecke {world.track_info['name']}: {len(world.gates)} Tore, "
              f"{getattr(world, 'removed_deco', 0)} Bäume/Laternen geräumt ({time.perf_counter() - t0:.1f} s)")
        flight.say(world.track_info["name"], f"Schwierigkeit {world.track_info['stars']}/5", 3.0)

    def restart():
        if settings.get("strecke") != world.track:
            switch_track()
        flight.mode = settings["mode"]
        if flight.mode == "bomb":
            timed_out = flight.target is not None and time.perf_counter() - flight.target_since > BOMB_TIMEOUT
            if flight.target is None or not entities.alive[flight.target] or timed_out:
                if not entities.alive.any():
                    entities.revive()
                    renderer.set_craters([])
                    flight.say("Alle Ziele erwischt!", "alles wieder auf Anfang", 3.0)
                flight.next_target()
        flight.physics = settings.get("physik", "classic")
        if pilot.get("physik", flight.physics) != flight.physics:   # Regler-Schubmodell je Physik (ap_thrust): neu bauen
            pilot.update(line=None, camera=None, bomb=None)
        pilot["physik"] = flight.physics
        flight.wind = settings.get("wind", "aus")          # nur „Realistisch“ (physics_real.WIND)
        flight.respawn()
        pad.kb.throttle = 0.0                    # nach jedem Neustart Gas auf 0 (Fernsteuerung: erst Gas runter = scharf)
        if settings["auto"]:
            ap0 = autopilot()
            if ap0 is pilot["nn"]:                # Modus, Rauschen, Modell (nur zwischen zwei Versuchen) – nn_show
                nn_overlay[0].prepare(ap0, flight, settings, time.perf_counter())
            ap0.reset()
            if ap0 is pilot["nn"]:
                nn_overlay[0].after_reset(ap0, time.perf_counter())
            flight.armed = True
        show = settings["auto"] and settings["show_line"] and ap_kind() == "line"
        renderer.set_line(autopilot().line.points if show else None)

    settings["auto"] = args.autopilot
    if os.environ.get("FREEFLY_LAGE") in ("0", "1"):     # Messung: Lageanzeige aus/an (ohne die Einstellung zu ändern)
        settings["osd"].update({k: os.environ["FREEFLY_LAGE"] == "1" for k in osd_ui.LAGE})
    if os.environ.get("FREEFLY_OSD") in osd_ui.PRESETS:  # Messung/Bild: OSD-Voreinstellung (liftoff/minimal/zuschauer/aus)
        osd_ui.apply_preset(settings, os.environ["FREEFLY_OSD"])
    if os.environ.get("FREEFLY_PHYSIK") in PHYSICS_NAMES:   # wie in den Tests ohne Fenster (game.PHYSICS)
        settings["physik"] = os.environ["FREEFLY_PHYSIK"]
    if os.environ.get("FREEFLY_WIND") in WIND_ORDER:
        settings["wind"] = os.environ["FREEFLY_WIND"]
    if args.physik:
        settings["physik"] = {"liftoff": "liftoff", "real": "real"}.get(args.physik, "classic")
    if args.wind:
        settings["wind"] = args.wind
    settings["no_save"] = bool(args.bench)
    if args.bomb:
        settings["mode"] = "bomb"
    if args.line:
        settings["ap_mode"] = "line"
    if args.camera:
        settings["ap_mode"] = "camera"
    if args.nn:
        settings["ap_mode"] = "nn"
    if args.nn_show:
        settings["ap_mode"] = "nn_learn" if args.nn_show == "lernen" else "nn_replay"
    restart()
    if args.pose:
        x, y, z, yaw, pitch = (float(v) for v in args.pose.split(","))
        flight.drone.pos = (x, y, z)
        flight.drone.quat = qmul(axis_angle((0, 1, 0), math.radians(yaw)), axis_angle((1, 0, 0), math.radians(pitch)))
        flight.frozen = flight.armed = True
        flight.frozen = not os.environ.get("FREEFLY_DROP")      # Test: aus der Pose fallen lassen (Absturz)
    if os.environ.get("FREEFLY_CRATER"):                  # Test: Krater vorab setzen
        renderer.add_crater(tuple(float(v) for v in os.environ["FREEFLY_CRATER"].split(",")), 1.8)
    stats = {"crashes": 0, "laps": 0}
    remote = None
    if args.remote:                                       # EasyPilot Studio steuert den Sim (remote.py)
        from .remote import RemoteServer
        remote = RemoteServer(args.remote, world)
    print(f"Freiflug:{pad.name}, {size[0]}x{size[1]}, Raten {rates.roll}, Uptilt {settings['tilt']}°, "
          f"Sichtfeld {settings['fov']}°, Physik {PHYSICS_NAMES.get(settings.get('physik'), 'Klassisch')} {1 / DT:.0f} Hz")

    in_menu = not args.bench or args.menu
    pygame.mouse.set_visible(in_menu or args.window)
    read_to_done, frame_times, fps_win = [], [], []
    last_buttons = set(pad.buttons())       # schon gedrückte Knöpfe/Schalter zählen nicht
    t_start = t_prev = t_phys = time.perf_counter()
    running = True

    menu_since = [time.perf_counter()]

    def resume():
        nonlocal in_menu, t_phys
        in_menu = False
        t_phys = time.perf_counter()
        flight.target_since = min(t_phys, flight.target_since + t_phys - menu_since[0])  # Menüzeit zählt nicht
        pygame.mouse.set_visible(args.window)
        save_settings(settings)

    def end_run(kind, title, sub, color):
        """Absturz, Treffer oder Runden-Ende: Blick auf die Stelle, abblenden, Start, Countdown."""
        lap = None if flight.lap_start is None else flight.flight_time - flight.lap_start
        best = settings.get("best_lap")
        if flight.mode == "bomb":
            line = f"Treffer {flight.hits}   Daneben {flight.misses}   Flugzeit {flight.flight_time:.1f} s"
        else:
            line = (f"Flugzeit {flight.flight_time:.1f} s" + (f"   Runde {lap:.2f} s" if lap is not None else "")
                    + (f"   Letzte {flight.last_lap:.2f} s" if flight.last_lap else "")
                    + (f"   Bestzeit {best:.2f} s" if best else ""))
        if nn_active():                           # KI-Showcase: „Versuch 37: 9 Tore“
            title, sub = nn_overlay[0].end_text(kind, title, sub)
        if settings.get("quick"):                # Schnell-Neustart: sofort zurück zum Start, kein Countdown
            restart_clean()
            flight.say(title, sub, 1.2)
            return
        seq.begin(time.perf_counter(), kind, title, sub, line, color, restart_clean)

    def restart_clean():
        restart()
        stats["counted"] = False

    def skip_or_restart():
        if not seq.skip(flight):
            restart()
        stats["counted"] = False

    while running:
        events = pygame.event.get()
        pad.poll(events)                          # Fernsteuerung nachträglich angesteckt / abgezogen
        if pad.notice:
            flight.say(*pad.notice, 2.5)
            print(pad.notice[0])
            pad.notice = None
        for ev in events:
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                renderer.resize(pygame.display.get_window_size())
            elif in_menu:
                act = cur_menu[0].handle(ev, settings)
                if act == "osd":
                    cur_menu[0] = osd_menu
                    osd_menu.sel = 0
                elif act == "nnshow":                     # Untermenü „KI-Showcase“ (nn_show.MENU)
                    cur_menu[0] = nn_menu
                    nn_menu.sel = 0
                elif act == "back" or (act == "resume" and cur_menu[0] in (osd_menu, nn_menu)):
                    cur_menu[0] = menu
                    save_settings(settings)
                elif act == "resume":
                    resume()
                elif act == "restart":
                    skip_or_restart()
                    resume()
                elif act == "repair":
                    repair()
                elif act == "quit":
                    running = False
                elif isinstance(act, tuple):
                    change(settings, act[1], act[2])
                    pad.configure(settings["kb_sens"], KB_GAS * settings["kb_gas"])
                    if act[1] == "ctl":
                        pad.set_mode(settings["ctl"])
                        pad.notice = None
                    if act[1] in ("auto", "ap_k", "show_line", "mode", "ap_mode", "physik", "wind", "strecke"):
                        skip_or_restart()
                    renderer.tilt = settings["tilt"]
                    renderer.set_fov(settings["fov"])
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    in_menu = True
                    menu_since[0] = time.perf_counter()
                    menu.sel = 0
                    cur_menu[0] = menu
                    pygame.mouse.set_visible(True)
                elif ev.key in (pygame.K_r, pygame.K_SPACE):
                    skip_or_restart()
                elif ev.key == pygame.K_t:
                    pad.cycle()                   # Steuerung: Automatisch -> RC 3 -> Tastatur
                    settings["ctl"] = pad.mode
                    save_settings(settings)
                elif ev.key == pygame.K_b:
                    change(settings, "mode", 1)
                    skip_or_restart()
                elif ev.key == pygame.K_p:
                    settings["auto"] = not settings["auto"]
                    skip_or_restart()
                elif ev.key == pygame.K_h:
                    settings["hud"] = not settings["hud"]
                elif ev.key == pygame.K_o:
                    osd_ui.toggle_lage(settings)              # Lageanzeige (Horizont, Gradkompass, Leisten, 3D, Karte)
                    save_settings(settings)
                elif ev.key == pygame.K_z:
                    repair()
                elif ev.key == pygame.K_k:
                    nn_show.toggle(settings)                  # KI-Einblendungen: Zuschauer <-> aus
                    save_settings(settings)

        t_read = time.perf_counter()
        sticks = pad.read()
        buttons = set(pad.buttons())
        if buttons - last_buttons:
            if in_menu:
                resume()
            else:
                skip_or_restart()
        last_buttons = buttons
        if remote is not None:
            remote.poll(settings, flight, restart, resume)
            running = running and not remote.quit

        if not in_menu:
            world.focus(flight.drone.pos)
            t_phys = max(t_phys, t_read - 0.1)
            ap = pilot[ap_kind()] if settings["auto"] else None
            if stats.get("boomed"):
                sticks = (0.0, 0.0, 0.0, 0.0)             # Test: Fernsteuerung ignorieren
            seq.update(t_read, flight)
            while t_phys + DT <= t_read:
                if ap is not None and flight.crashed_at is None and flight.armed and not flight.frozen:
                    if ap is pilot["bomb"]:
                        sticks = ap.step(flight.drone.state(), flight.target)
                    else:
                        sticks = ap.step(flight.drone.state())
                flight.step(sticks, DT)
                t_phys += DT
            if ap is not None:
                sticks = ap.cmd or sticks
                if ap is pilot["camera"] and ap.done and flight.crashed_at is None:
                    print(f"Kamera-Autopilot: {ap.pilot.reason}, Tore gesehen {len(ap.per.tracker.found())}, "
                          f"Bild+Erkennung {ap.vision_ms:.1f} ms")
                    if not seq.active:
                        end_run("done", "RUNDE ZU ENDE", f"Kamera-Autopilot: {ap.pilot.reason}", (0.4, 1, 0.6, 1))
                elif ap is pilot["line"] and ap.done and flight.crashed_at is None:
                    if ap.racer.crashed:
                        flight.crash("Autopilot steckt fest")
                    else:
                        if not seq.active:
                            end_run("done", "AUTOPILOT FERTIG", f"{len(ap.racer.progress.gate_times)} Tore geflogen",
                                    (0.4, 1, 0.6, 1))
            if nn_overlay:                                 # KI: Aufzeichnung abschließen, „kein Tor mehr“, Lern-Prozess
                if nn_active():
                    nn_end = nn_overlay[0].frame(flight, pilot["nn"], settings, t_read)
                    if nn_end and not seq.active and flight.crashed_at is None:
                        end_run(nn_end[0], nn_end[1], nn_end[2], (0.4, 1, 0.6, 1))
                else:
                    nn_overlay[0].recorder.end(None, "neu gestartet")
            if (flight.mode == "bomb" and flight.crashed_at is None and flight.target is not None
                    and t_read - flight.target_since > BOMB_TIMEOUT):
                old = entities.name(flight.target)                  # Zeit um: neues Ziel
                flight.misses += 1
                flight.next_target()
                flight.say("Zeit um", f"{old} entkommen, neues Ziel: {entities.name(flight.target)}", 2.5)
                print(f"Zeit um: {old} nach {BOMB_TIMEOUT:.0f} s, neues Ziel {entities.name(flight.target)}")
                if ap is pilot["bomb"] and ap is not None:
                    ap.reset()
            if flight.crashed_at is not None and not stats.get("counted"):
                stats["crashes"] += 1
                stats["counted"] = True
                print(f"Absturz: {flight.crash_reason} bei {tuple(round(v, 1) for v in flight.drone.pos)}"
                      f"{' (Autopilot)' if ap else ''}")
            if args.boom_test and flight.target is not None and not stats.get("boomed") and t_read - t_start > args.boom_test:
                stats["boomed"] = True                     # Test: 12 m vor dem Ziel, 15 m/s drauf zu
                entities.hold = flight.target              # Ziel steht für den Test still
                c = flight.target_info()["center"]
                d0 = math.hypot(c[0], c[2]) or 1.0
                ux, uz = c[0] / d0, c[2] / d0
                if os.environ.get("FREEFLY_TEST_HOUSE"):        # Test: gerade in ein Haus
                    flight.drone.pos = (c[0] - ux * 14, c[1] + 0.6, c[2] - uz * 14)
                    flight.drone.vel = (ux * 18, 0.0, uz * 18)
                else:                                            # Test: senkrecht von oben aufs Ziel
                    flight.drone.pos = (c[0], c[1] + 9.0, c[2])
                    flight.drone.vel = (0.0, -18.0, 0.0)
                flight.drone.quat = axis_angle((0, 1, 0), math.atan2(ux, uz))
                print("Boom-Test: Ziel", entities.name(flight.target), [round(v, 1) for v in c], "armed", flight.armed)
                flight.armed, flight.frozen = True, False
            for kind, pos, big, idx in flight.events:
                big_bus = idx is not None and entities.kind[idx] in ("car", "bus")
                explosions.append(fx.Explosion(pos, size=2.0 if big_bus else 1.3 if big else 1.0))
                world.focus(pos, 10)
                if world.hit(pos, 1.2):                                   # Loch in Haus/Mauer
                    renderer.add_crater(pos, 2.2 if big_bus else 1.6)
                if pos[1] < 2.5:                                          # Brandfleck am Boden
                    renderer.add_crater((pos[0], 0.0, pos[2]), 1.8 if big_bus else 1.2)
                print(f"{'Treffer' if idx is not None else 'Explosion'}: {flight.crash_reason}")
            flight.events.clear()
            if flight.crashed_at is not None and not seq.active and stats.get("counted") is True:
                hit = getattr(flight, "target_hit", False)
                end_run("hit" if hit else "crash", "TREFFER!" if hit else "ABSTURZ", flight.crash_reason,
                        (1, 0.8, 0.2, 1) if hit else (1, 0.35, 0.3, 1))
                stats["counted"] = "seq"
            if flight.new_best is not None:
                stats["laps"] += 1
                print(f"Runde {flight.new_best:.2f} s{' (Autopilot k=%.1f)' % settings['ap_k'] if ap else ''}")
                if not settings["auto"] and (settings["best_lap"] is None or flight.new_best < settings["best_lap"]):
                    settings["best_lap"] = flight.new_best
                    settings["best_laps"][world.track] = flight.new_best       # Bestzeit je Strecke
                    flight.say(f"Runde {flight.new_best:.2f} s", "neuer Rekord!", 3.0)
                    save_settings(settings)
                flight.new_best = None

        d = flight.drone
        dt_frame = min(0.05, t_read - stats.get("t_fx", t_read))
        stats["t_fx"] = t_read
        if not in_menu:
            if flight.mode == "bomb":
                entities.update(dt_frame, d.pos)
            for e in explosions:
                e.update(dt_frame)
            explosions[:] = [e for e in explosions if not e.done]
        axes, eye = None, d.pos
        look = seq.camera(t_read, flight, max((e.shake() for e in explosions), default=0.0))
        if look is not None:                      # Kamera schaut auf die Absturzstelle / Explosion
            eye = look[0]
            axes = renderer.look_axes(eye, look[1])
        renderer.draw(eye, d.quat, flight.next_gate, settings["mark"] and flight.mode == "race", t_read, axes=axes)
        if flight.mode == "bomb":
            renderer.draw_entities([(vao, ibuf, entities.instances(k)) for k, (vao, ibuf) in models.items()])
        if settings["auto"] and settings["show_line"]:
            renderer.draw_line()
        fx.draw(renderer, fxtex, explosions)
        if not in_menu:
            fps = len(fps_win) / max(1e-6, sum(fps_win)) if fps_win else 0.0
            lat = statistics.median(read_to_done[-120:]) * 1000 if read_to_done else 0.0
            hud.draw(flight, sticks, {"fps": fps, "lat": lat, "pad": pad.name,
                                      "auto": ap_label() if settings["auto"] else None}, settings, t_read)
            if settings["hud"] and any(settings["osd"][k] for k in osd_ui.LAGE):
                lage.draw(hud, flight, settings, t_read, dt_frame,
                          left_busy=bool(nn_active() and settings["hud"] and settings["nnshow"]["sieht"]))
            losd.draw(hud, flight, sticks, {"auto": ap_label() if settings["auto"] else None}, settings, t_read, dt_frame)
            if nn_active():                       # KI-Einblendungen: sieht / will / Lernkurve / Zähler / Erklärtexte
                nn_overlay[0].draw(hud, pilot["nn"], settings, t_read)
            hud.flash(max((e.flash() for e in explosions), default=0.0))
            if seq.active or seq.done_at is not None:
                seq.draw(hud, t_read)             # Meldung, Abblenden, Countdown, „LOS!“
            if seq.active or flight.crashed_at is not None:
                pass
            elif not flight.armed:
                hud.message("Gas ganz runter", "dann ist die Drohne scharf", (1, 0.85, 0.3, 1))
            elif flight.msg and t_read < flight.msg[2]:
                hud.message(flight.msg[0], flight.msg[1], (0.6, 1, 0.7, 1))
        else:
            menu.items[0]["label"] = "Weiter fliegen" if flight.flight_time > 0 else "Fliegen"
            if cur_menu[0] is osd_menu:
                osd_menu.draw(menu_values(settings), "Anzeige / OSD",
                              "Voreinstellung: Liftoff · Minimal · Zuschauer · Aus    H schaltet alles, O die Lageanzeige")
            elif cur_menu[0] is nn_menu:
                nn_menu.draw(menu_values(settings), "KI-Showcase",
                             "Autopilot-Modus „KI: Lernen zuschauen“ / „KI: Zeitraffer“    K schaltet die Einblendungen")
            else:
                menu.draw(menu_values(settings), "EasyPilot Freiflug", f"Acro · {pad.name} · {len(world.gates)} Tore · "
                          f"{len(entities.kind)} bewegte Ziele")
                tracks.draw_card(hud, settings["strecke"], menu.items[menu.sel]["key"] == "strecke")
        if remote is not None:
            remote.publish(flight, settings, sticks, {
                "fps": len(fps_win) / max(1e-6, sum(fps_win)), "pad": pad.name, "menu": in_menu, "timeout": BOMB_TIMEOUT,
                "lat": statistics.median(read_to_done[-120:]) * 1000 if read_to_done else 0.0,
                "auto": ap_label() if settings["auto"] else None})
        ctx.finish()
        if args.shot and args.bench and time.perf_counter() - t_start > args.bench:
            break
        pygame.display.flip()
        hud.text.end_frame()                  # alte Schrift-Texturen erst nach dem flip freigeben
        fx.end_frame()                        # dito Rauch/Feuer-Puffer
        t_done = time.perf_counter()

        frame = t_done - t_prev
        t_prev = t_done
        if not in_menu:
            read_to_done.append(t_done - t_read)
            frame_times.append(frame)
        fps_win.append(frame)
        if len(fps_win) > 120:
            fps_win.pop(0)
        if len(read_to_done) > 200000:
            del read_to_done[:100000], frame_times[:100000]
        if args.bench and t_done - t_start > args.bench:
            running = False
        limit = 60.0 if in_menu else args.max_fps
        if limit:
            wait = t_read + 1.0 / limit - time.perf_counter()
            if wait > 0.0005:
                time.sleep(wait - 0.0003)

    if args.shot:
        img = ctx.screen.read(components=3)
        pygame.image.save(pygame.transform.flip(pygame.image.frombytes(img, size, "RGB"), False, True), args.shot)
    save_settings(settings)
    if nn_overlay:                                # laufenden KI-Versuch noch speichern (nn_show.Recorder)
        nn_overlay[0].recorder.end(None, "Sim beendet")
        nn_overlay[0].recorder.flush()
    pygame.quit()
    print(f"Runden {stats['laps']}, Abstürze {stats['crashes']}, Treffer {flight.hits}, daneben {flight.misses}")
    print(stats_text(read_to_done[30:], frame_times[30:]))


if __name__ == "__main__":
    main()
