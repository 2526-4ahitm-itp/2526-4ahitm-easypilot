"""Load any Liftoff race without clicking through the menus, and read Liftoff's own lap judgement.

Liftoff stores the last played session in Saves/Player/UserData.xml (written when a session starts)
and offers it under Quick Play > Last Session. So: close Liftoff, put the wanted race into
`lastPlaySession`, start Liftoff, click Last Session.

Liftoff counts a lap only if every checkpoint was hit, and then appends it to
LapTimes/lapTimes.xml at once (best five times + running average per race) - an independent
check of our own gate model.

  python -m autopilot.session load StrawBaleRace02
  python -m autopilot.session laps StrawBaleRace02
"""
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from . import window
from .paths import IS_MAC, LIFTOFF_USER
from .track import find, load_race, load_race_with_track, load_track, TRACK_DIR, USER_DIR

LIFTOFF_DIR = LIFTOFF_USER
USER_DATA = LIFTOFF_DIR / "Saves/Player/UserData.xml"
LAP_TIMES = LIFTOFF_DIR / "LapTimes/lapTimes.xml"
# point-to-point races (start and finish apart) end at the finish: Liftoff stores the race time here,
# not as a lap, and respawns the drone (ThePit01, Surtur01/02 looked failed in test series 9, 16.11.)
RACE_TIMES = LIFTOFF_DIR / "RaceTimes/raceTimes.xml"
STEAM_APP = "steam://rungameid/410340"

RACE_SESSION = """<lastPlaySession xsi:type="RaceSessionData">
    <environment>{env}</environment>
    <environmentVariant>Default</environmentVariant>
    <includeSlipstream>false</includeSlipstream>
    <IncludeSlipstreamAssets>false</IncludeSlipstreamAssets>
    <track>
      <str>{track_id}</str>
      <version>1</version>
      <type>TRACK</type>
    </track>
    <race>
      <str>{race_id}</str>
      <version>1</version>
      <type>RACE</type>
    </race>
    <isInfinite>false</isInfinite>
  </lastPlaySession>"""

FREE_SESSION = """<lastPlaySession xsi:type="FreeFlightSessionData">
    <environment>{env}</environment>
    <environmentVariant>Default</environmentVariant>
    <includeSlipstream>false</includeSlipstream>
    <IncludeSlipstreamAssets>false</IncludeSlipstreamAssets>
    <track>
      <str>{track_id}</str>
      <version>1</version>
      <type>TRACK</type>
    </track>
  </lastPlaySession>"""


def race_info(race_name):
    path = find(race_name)
    root_id = re.search(r"<localID>\s*<str>([^<]+)</str>", path.read_text(encoding="utf-8", errors="ignore"))
    race, track = load_race_with_track(race_name)
    return {"race_id": root_id.group(1), "race": race, "track": track, "env": track["environment"],
            "track_id": track["id"], "name": race["name"]}


def catalog():
    """All races that can be flown: official ones (extracted) and custom ones from Liftoff's editor."""
    out = []
    skip = unavailable()
    for d, custom in ((TRACK_DIR, False), (USER_DIR / "Races", True)):
        if not d.exists():
            continue
        for p in sorted(d.glob("*.xml")):
            head = p.read_text(encoding="utf-8", errors="ignore")[:3000]
            if "<Race" not in head[:400]:
                continue
            key = p.name.split("_")[0] if not custom else p.stem
            if key in skip:
                continue
            name = re.search(r"<name>([^<]*)</name>", head)
            env = None
            try:
                info = race_info(key)
                env, title, gates = info["env"], info["name"], len(info["race"]["passages"])
            except Exception:
                continue                      # race without its track file
            out.append({"key": key, "title": title, "env": env, "custom": custom, "gates": gates})
    return out


def liftoff_running():
    if IS_MAC:
        return subprocess.run(["pgrep", "-x", "Liftoff"], capture_output=True).returncode == 0
    out = subprocess.run(["tasklist", "/fi", "imagename eq Liftoff.exe"], capture_output=True, text=True).stdout
    return "Liftoff.exe" in out


def quit_liftoff():
    """Kill, not quit: a clean quit would write UserData.xml again and undo our edit."""
    if liftoff_running():
        if IS_MAC:
            subprocess.run(["pkill", "-9", "-x", "Liftoff"], capture_output=True)
        else:
            subprocess.run(["taskkill", "/im", "Liftoff.exe", "/f"], capture_output=True)
        for _ in range(50):
            if not liftoff_running():
                break
            time.sleep(0.2)
        time.sleep(1.0)


def set_last_session(fragment):
    text = USER_DATA.read_text(encoding="utf-8-sig")
    new, n = re.subn(r"<lastPlaySession[\s\S]*?</lastPlaySession>", fragment, text, count=1)
    if n == 0:
        new = text.replace("</UserData>", "  " + fragment + "\n</UserData>")
    backup = USER_DATA.with_suffix(".xml.easypilot-backup")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    USER_DATA.write_text(new, encoding="utf-8")


def start_and_open_last_session(tel=None, timeout=600.0):
    """Start Liftoff (if needed), Quick Play > Last Session, wait until the drone is in the level."""
    from .ui import click_capture
    if not liftoff_running():
        if IS_MAC:
            subprocess.run(["open", STEAM_APP])
        else:
            subprocess.run(["cmd", "/c", "start", "", STEAM_APP])
    end = time.time() + timeout         # Steam may update Liftoff first
    while True:
        try:
            if window.find_window() is not None and window.client_rect()[2] > 400:
                break
        except Exception:
            pass
        if time.time() > end:
            return False
        time.sleep(2)
    time.sleep(25)                      # splash screen and main menu
    for _ in range(3):
        window.focus_liftoff(hard=True)
        click_capture(630, 100)         # QUICK PLAY
        time.sleep(1.2)
        click_capture(805, 275)         # LAST SESSION
        t_click = time.time()
        while time.time() - t_click < 40:
            s = tel.latest(0.5) if tel is not None else None
            if s is not None and max(abs(v) for v in s.pos) > 1e-3:
                remember_scene()
                return True
            if tel is None and time.time() - t_click > 30:
                return True
            time.sleep(0.5)
    return False


def remember_scene():
    """Liftoff logs which scene (bundle hash) it loaded for an environment: keep it for envdb.py."""
    log = LIFTOFF_DIR / "Player.log"
    try:
        text = log.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    pairs, start = [], None
    for line in text.splitlines():
        m = re.search(r"SCENE LOAD (START|END): (\w+)", line)
        if not m:
            continue
        if m.group(1) == "START":
            start = m.group(2)
        elif start and re.fullmatch(r"[0-9a-f]{32}", m.group(2)):
            pairs.append((start, m.group(2)))
            start = None
        else:
            start = None
    if not pairs:
        return
    f = TRACK_DIR / "env" / "scenes.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    known = json.loads(f.read_text()) if f.exists() else {}
    known.update({env: h for env, h in pairs})
    f.write_text(json.dumps(known, indent=1))


def _unavailable_file():
    from .liftoff import RUNS
    return RUNS / "unavailable_races.json"


def unavailable():
    """Races whose level Liftoff did not start: content missing on this PC ("Missing data - did you
    remove or unsubscribe from content?", PineValley05 and ShortCircuit03 on 16.11.)."""
    f = _unavailable_file()
    try:
        return set(json.loads(f.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _mark(race_name, missing):
    races = unavailable()
    if (race_name in races) == missing:
        return
    (races.add if missing else races.discard)(race_name)
    f = _unavailable_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(sorted(races)), encoding="utf-8")


def load(race_name, tel=None, mode="race"):
    info = race_info(race_name)
    quit_liftoff()
    if mode == "race":
        set_last_session(RACE_SESSION.format(env=info["env"], race_id=info["race_id"], track_id=info["track_id"]))
    else:
        set_last_session(FREE_SESSION.format(env=info["env"], track_id=info["track_id"]))
    ok = start_and_open_last_session(tel)
    if ok:
        warmup_reset(tel)
    if tel is not None:              # only with telemetry is "no drone in the level" a reliable answer
        _mark(race_name, not ok)
    return ok, info


def warmup_reset(tel=None, joy=None):
    """One reset right after loading. The first reset after a fresh level load leaves the drone
    frozen at the spawn in some races (MarinaBay01, Rustline02, Permafrost03/05 ...: 240 s without
    moving, test 16.11.); every later reset works. Burn that first one here."""
    from .vjoy import BTN_RESET, VJoy
    own = joy is None
    if own:
        joy = VJoy()
        time.sleep(0.5)
    try:
        before = tel.resets if tel is not None else None
        joy.idle()
        joy.tap(BTN_RESET, 0.15)
        end = time.time() + 3.0
        while tel is not None and time.time() < end and tel.resets == before:
            time.sleep(0.02)
        time.sleep(1.0)
    finally:
        if own:
            joy.close()


def _times(path, tag, race_id):
    """(best times, average) of one race in a Liftoff times file, or None if it has no entry."""
    if not path.exists():
        return None
    root = ET.fromstring(path.read_text(encoding="utf-8-sig").split("?>", 1)[-1])
    for lt in root.iter(tag):
        if lt.findtext("ID/str") == race_id:
            avg = lt.findtext("average")
            return [float(t.text) for t in lt.iter("Time")], float(avg) if avg else None
    return None


def _mtime():
    return max((f.stat().st_mtime for f in (LAP_TIMES, RACE_TIMES) if f.exists()), default=0)


def lap_record(race_id):
    """(average, best times, file mtime) for a race: laps (lapTimes.xml) and point-to-point race times
    (raceTimes.xml) together, or None when Liftoff has written neither file yet."""
    if not LAP_TIMES.exists() and not RACE_TIMES.exists():
        return None
    best, avgs = [], []
    for path, tag in ((LAP_TIMES, "lapTime"), (RACE_TIMES, "raceTime")):
        got = _times(path, tag, race_id)
        if got:
            best += got[0]
            avgs.append(got[1])
    avg = next((a for a in avgs if a is not None), None)
    return {"average": avg, "averages": avgs, "best": sorted(best), "mtime": _mtime()}


def flush_laps(race_id, joy=None, timeout=4.0):
    """Liftoff writes finished laps to lapTimes.xml only when the race is reset or left: press Reset
    and return the record afterwards."""
    from .vjoy import BTN_RESET, VJoy
    own = joy is None
    if own:
        joy = VJoy()
        time.sleep(0.5)
    m0 = _mtime()
    try:
        joy.tap(BTN_RESET, 0.15)
        end = time.time() + timeout
        while time.time() < end and _mtime() == m0:
            time.sleep(0.1)
        time.sleep(0.2)
    finally:
        if own:
            joy.close()
    return lap_record(race_id)


def lap_counted(before, after):
    """Liftoff accepted at least one new lap between the two records."""
    if after is None:
        return False
    if before is None or before["average"] is None:
        return after["average"] is not None
    return after["mtime"] != before["mtime"] and (after.get("averages") != before.get("averages")
                                                  or after["best"] != before["best"])


if __name__ == "__main__":
    cmd, name = sys.argv[1], sys.argv[2]
    if cmd == "load":
        print(load(name, mode=sys.argv[3] if len(sys.argv) > 3 else "race")[0])
    elif cmd == "laps":
        print(lap_record(race_info(name)["race_id"]))
