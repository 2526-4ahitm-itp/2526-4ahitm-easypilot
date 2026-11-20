"""Fernsteuerung des Freiflug-Sims für EasyPilot Studio: JSON-Zeilen über einen lokalen TCP-Socket.

  python -m autopilot.freefly --window --remote 8766      # Sim nimmt Befehle auf 127.0.0.1:8766 an

Der Sim ist der Server (RemoteServer, läuft in der Spielschleife), das Studio der Client (SimClient).
Jede Nachricht ist eine Zeile JSON.

Studio -> Sim (Befehle, "cmd"):
  settings  mode ("race"/"bomb"), ap_mode ("line"/"camera"), ap_k, show_line, mark, hud, auto,
            strecke (tracks.py; der Sim baut die Welt neu und schickt danach ein neues "hello")
  prepare   Lauf vorbereiten: Einstellungen wie bei settings, Drohne an den Start, eingefroren,
            Menü zu. auto = ob danach der Autopilot fliegt (er wird hier schon gebaut).
  go        Start: Drohne frei; mit auto fliegt der Autopilot ab dem Startplatz.
  stop      Autopilot aus, Drohne zurück an den Start, danach wieder frei fliegbar.
  say       text, sub, s: Meldung im Sim-Bild (Countdown)
  window    x, y, w, h: Sim-Fenster verschieben/Größe ändern (Studio-Layout)
  quit      Sim beenden

Sim -> Studio:
  {"hello": {...}}   nach dem Verbinden und nach jedem Streckenwechsel: Strecke, Tore (x, y, z, Gier), Straßen
  {"tel": {...}}     Telemetrie mit 20 Hz (Lage, Höhe, Tempo, Sticks, Tor, Modus, Ziel ...)
  {"ev": "..."}      Ereignisse sofort: go, gate (i, t), crash (reason, hit), respawn, target, lap

Zeiten ("t") sind Flugzeit des Sims (flight.flight_time): sie steht im Menü und bis die Drohne scharf ist.
"""
import json
import math
import queue
import socket
import threading
import time

from ..geometry import body_axes, heading

TEL_HZ = 20.0
DEFAULT_PORT = 8766


def attitude(q):
    """(Roll, Nick, Gier) in Grad: Roll + = rechts runter, Nick + = Nase hoch, Gier 0 = +z, + = rechts."""
    right, up, fwd = body_axes(q)
    roll = math.degrees(math.atan2(-right[1], up[1]))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, fwd[1]))))
    yaw = math.degrees(heading(fwd)) % 360.0
    return roll, pitch, yaw


def _r(v, n=2):
    return [round(x, n) for x in v]


class RemoteServer:
    """Im Sim: nimmt Verbindungen an, sammelt Befehle (poll) und schickt Telemetrie (publish).
    poll() und publish() laufen im Hauptthread der Spielschleife, nur Netz-I/O in eigenen Threads."""

    def __init__(self, port=DEFAULT_PORT, world=None, host="127.0.0.1"):
        self.world = world
        self.inbox = queue.Queue()
        self.clients = []
        self.lock = threading.Lock()
        self.quit = False
        self.run_auto = False          # nach "go" fliegt der Autopilot
        self.hold = False              # Drohne bis "go" eingefroren
        self._last = {}
        self._t_tel = 0.0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, int(port)))
        self.sock.listen(4)
        self.port = int(port)
        threading.Thread(target=self._accept, daemon=True).start()
        print(f"Fernsteuerung: 127.0.0.1:{self.port} (EasyPilot Studio)", flush=True)

    # ------------------------------------------------------------ Netz
    def _accept(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self.lock:
                self.clients.append(conn)
            self._send_to(conn, {"hello": self.hello()})
            threading.Thread(target=self._read, args=(conn,), daemon=True).start()

    def _read(self, conn):
        buf = b""
        try:
            while True:
                data = conn.recv(65536)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        try:
                            self.inbox.put(json.loads(line))
                        except ValueError:
                            pass
        except OSError:
            pass
        self._drop(conn)

    def _drop(self, conn):
        with self.lock:
            if conn in self.clients:
                self.clients.remove(conn)
        try:
            conn.close()
        except OSError:
            pass

    def _send_to(self, conn, msg):
        try:
            conn.sendall((json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8"))
        except OSError:
            self._drop(conn)

    def send(self, msg):
        with self.lock:
            conns = list(self.clients)
        for c in conns:
            self._send_to(c, msg)

    def hello(self):
        gates = []
        if self.world is not None:
            for g in self.world.gates:
                c = g.center
                gates.append({"x": round(c[0], 2), "y": round(c[1], 2), "z": round(c[2], 2),
                              "yaw": round(math.degrees(getattr(g, "yaw", 0.0)), 1)})
        from .world import ROADS
        from .tracks import summary
        info = getattr(self.world, "track_info", None) or {"key": "dorfrunde", "name": "Dorfrunde", "stars": 2}
        return {"gates": gates, "roads": [list(r) for r in ROADS], "version": 2,
                "track": {"key": info["key"], "name": info["name"], "stars": info["stars"]}, "tracks": summary()}

    # ------------------------------------------------------------ Befehle
    def poll(self, settings, flight, restart, resume):
        """Befehle anwenden. restart/resume sind die Funktionen aus __main__ (Neustart, Menü zu)."""
        settings["no_save"] = True          # Studio-Läufe ändern freefly.local.json nicht (eigene Bestenliste)
        while True:
            try:
                c = self.inbox.get_nowait()
            except queue.Empty:
                break
            try:
                self._apply(c, settings, flight, restart, resume)
            except Exception as exc:        # ein kaputter Befehl darf den Sim nicht beenden
                print("Fernsteuerung:", repr(exc), flush=True)
                self.send({"ev": "error", "msg": repr(exc)[:200]})
        if self.hold:
            flight.frozen = True

    def _settings(self, c, settings):
        changed = False
        if c.get("strecke"):
            from .tracks import key
            c = {**c, "strecke": key(c["strecke"])}
        for k in ("mode", "ap_mode", "ap_k", "show_line", "mark", "hud", "strecke"):
            if k in c and c[k] is not None and settings.get(k) != c[k]:
                if k == "mode" and c[k] not in ("race", "bomb"):
                    continue
                if k == "ap_mode" and c[k] not in ("line", "camera", "nn", "nn_learn", "nn_replay"):   # nn_*: nn_show.py
                    continue
                settings[k] = round(max(0.2, min(1.2, float(c[k]))), 1) if k == "ap_k" else c[k]
                changed = True
        return changed

    def _apply(self, c, settings, flight, restart, resume):
        cmd = c.get("cmd")
        if cmd == "settings":
            changed = self._settings(c, settings)
            if "auto" in c:
                settings["auto"] = bool(c["auto"])
                changed = True
            if changed and not self.hold:
                restart()
        elif cmd == "prepare":
            self._settings(c, settings)
            self.run_auto = bool(c.get("auto"))
            self.hold = False
            if self.run_auto:               # Autopilot jetzt bauen (Rennlinie planen dauert), nicht erst beim Start
                settings["auto"] = True
                restart()
            settings["auto"] = False
            restart()
            resume()
            self.hold = True
            flight.frozen = True
            self._remember(flight)
            self.send({"ev": "ready", "mode": settings["mode"], "auto": self.run_auto})
        elif cmd == "go":
            self.hold = False
            if self.run_auto:
                settings["auto"] = True
                restart()                   # Autopilot zurückgesetzt, Drohne scharf
            flight.frozen = False
            flight.target_since = time.perf_counter()
            self._remember(flight)          # der Neustart hier ist kein Respawn-Ereignis
            self._last["t_go"] = flight.flight_time
            self.send({"ev": "go", "t": round(flight.flight_time, 3), "next_gate": flight.next_gate,
                       "target": self._target_name(flight), "hits": flight.hits, "misses": flight.misses})
        elif cmd == "stop":
            self.run_auto = False
            settings["auto"] = False
            self.hold = False               # danach frei fliegbar (scharf erst mit Gas ganz unten)
            restart()
            self._remember(flight)
            self.send({"ev": "stopped"})
        elif cmd == "say":
            flight.say(str(c.get("text", ""))[:40], (str(c["sub"])[:60] if c.get("sub") else None), float(c.get("s", 1.0)))
        elif cmd == "window":
            self._move_window(c)
        elif cmd == "quit":
            self.quit = True

    @staticmethod
    def _move_window(c):
        try:
            import pygame
            from pygame._sdl2.video import Window
            w = Window.from_display_module()
            if "w" in c and "h" in c:
                w.size = (int(c["w"]), int(c["h"]))
            if "x" in c and "y" in c:
                w.position = (int(c["x"]), int(c["y"]))
            pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE, size=w.size, w=w.size[0], h=w.size[1]))
        except Exception as exc:
            print("Fenster verschieben:", repr(exc), flush=True)

    # ------------------------------------------------------------ Telemetrie
    @staticmethod
    def _target_name(flight):
        try:
            return flight.entities.name(flight.target) if flight.target is not None else None
        except Exception:
            return None

    def publish(self, flight, settings, sticks, info):
        """Einmal pro Frame nach der Physik: Ereignisse sofort, Telemetrie mit TEL_HZ.
        info: fps, lat (ms), pad, auto (Beschriftung des Autopiloten oder None), menu (bool), timeout (s)."""
        if not self.clients:
            self._remember(flight)
            return
        d = flight.drone
        L = self._last
        if L.get("drone") is not None and L["drone"] is not d:
            self.send({"ev": "respawn"})
        elif L.get("next_gate") is not None and flight.next_gate != L["next_gate"]:
            self.send({"ev": "gate", "i": L["next_gate"], "t": round(flight.flight_time, 3),
                       "lap": flight.last_lap if L["next_gate"] == 0 else None})
        if flight.crashed_at is not None and L.get("crashed_at") != flight.crashed_at:
            self.send({"ev": "crash", "reason": flight.crash_reason, "hit": bool(getattr(flight, "target_hit", False)),
                       "t": round(flight.flight_time, 3), "pos": _r(d.pos), "hits": flight.hits, "misses": flight.misses})
        if flight.target != L.get("target") and L.get("drone") is not None:
            self.send({"ev": "target", "name": self._target_name(flight), "hits": flight.hits, "misses": flight.misses})
        self._remember(flight)
        now = time.perf_counter()
        if now - self._t_tel < 1.0 / TEL_HZ:
            return
        self._t_tel = now
        roll, pitch, yaw = attitude(d.quat)
        v = d.vel
        tgt = None
        if flight.mode == "bomb":
            ti = flight.target_info() if flight.target is not None else None
            if ti:
                tgt = {"name": ti["name"], "pos": _r(ti["center"], 1), "dist": round(math.dist(ti["center"], d.pos), 1),
                       "left": round(max(0.0, info.get("timeout", 30.0) - (now - flight.target_since)), 1)}
        self.send({"tel": {
            "t": round(flight.flight_time, 3), "pos": _r(d.pos), "vel": _r(v),
            "speed": round(math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) * 3.6, 1), "vz": round(v[1], 2),
            "alt": round(d.pos[1], 2), "roll": round(roll, 1), "pitch": round(pitch, 1), "yaw": round(yaw, 1),
            "sticks": _r(sticks, 3), "armed": bool(flight.armed), "frozen": bool(flight.frozen),
            "crashed": flight.crashed_at is not None, "crash_reason": flight.crash_reason if flight.crashed_at else "",
            "next_gate": flight.next_gate, "gates": len(flight.world.gates), "mode": flight.mode,
            "auto": info.get("auto"), "ap_mode": settings.get("ap_mode"), "ap_k": settings.get("ap_k"),
            "auto_on": bool(settings.get("auto")), "last_lap": flight.last_lap, "best_lap": settings.get("best_lap"),
            "strecke": getattr(flight.world, "track", "dorfrunde"),
            "hits": flight.hits, "misses": flight.misses, "target": tgt, "menu": bool(info.get("menu")),
            "fps": round(info.get("fps", 0.0)), "lat": round(info.get("lat", 0.0), 2), "pad": info.get("pad"),
            "hold": self.hold}})

    def _remember(self, flight):
        L = self._last
        L["drone"], L["next_gate"], L["crashed_at"], L["target"] = flight.drone, flight.next_gate, flight.crashed_at, flight.target

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
        with self.lock:
            for c in self.clients:
                try:
                    c.close()
                except OSError:
                    pass
            self.clients.clear()


class SimClient:
    """Im Studio: Verbindung zum Sim, letzte Telemetrie, Ereignisse an einen Callback."""

    def __init__(self, port=DEFAULT_PORT, on_event=None):
        self.port = port
        self.on_event = on_event
        self.tel, self.tel_at, self.hello = None, 0.0, None
        self.sock = None
        self.lock = threading.Lock()

    @property
    def connected(self):
        return self.sock is not None

    def connect(self, timeout=0.5):
        if self.sock is not None:
            return True
        try:
            s = socket.create_connection(("127.0.0.1", self.port), timeout=timeout)
        except OSError:
            return False
        s.settimeout(None)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock = s
        threading.Thread(target=self._read, args=(s,), daemon=True).start()
        return True

    def _read(self, s):
        buf = b""
        try:
            while True:
                data = s.recv(65536)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if "tel" in msg:
                        self.tel, self.tel_at = msg["tel"], time.perf_counter()
                    elif "hello" in msg:
                        self.hello = msg["hello"]
                    elif "ev" in msg and self.on_event:
                        try:
                            self.on_event(msg)
                        except Exception as exc:
                            print("Sim-Ereignis:", repr(exc), flush=True)
        except OSError:
            pass
        if self.sock is s:
            self.sock = None
        try:
            s.close()
        except OSError:
            pass

    def latest(self, max_age=1.0):
        return self.tel if self.tel is not None and time.perf_counter() - self.tel_at < max_age else None

    def send(self, **cmd):
        s = self.sock
        if s is None:
            return False
        try:
            with self.lock:
                s.sendall((json.dumps(cmd) + "\n").encode("utf-8"))
            return True
        except OSError:
            self.sock = None
            return False

    def close(self):
        s, self.sock = self.sock, None
        if s is not None:
            try:
                s.close()
            except OSError:
                pass
