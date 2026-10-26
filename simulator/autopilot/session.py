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
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from . import window
from .track import find, load_race, load_track, TRACK_DIR

LIFTOFF_DIR = Path.home() / "AppData/LocalLow/LuGus Studios/Liftoff"
USER_DATA = LIFTOFF_DIR / "Saves/Player/UserData.xml"
LAP_TIMES = LIFTOFF_DIR / "LapTimes/lapTimes.xml"
STEAM_APP = "steam://rungameid/410340"

RACE_SESSION = """<lastPlaySession xsi:type="RaceSessionData">
    <environment>{env}</environment>
    <environmentVariant>Default</environmentVariant>
    <includeSlipstream>false</includeSlipstream>
    <IncludeSlipstreamAssets>false</IncludeSlipstreamAssets>
    <race>
      <str>{race_id}</str>
      <version>1</version>
      <type>RACE</type>
    </race>
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
    race = load_race(path)
    track_path = next(p for p in TRACK_DIR.glob("*Track*.xml")
                      if load_track(p)["id"] == race["track"])
    track = load_track(track_path)
    return {"race_id": root_id.group(1), "race": race, "track": track, "env": track["environment"],
            "track_id": track["id"], "name": race["name"]}


def liftoff_running():
    out = subprocess.run(["tasklist", "/fi", "imagename eq Liftoff.exe"], capture_output=True, text=True).stdout
    return "Liftoff.exe" in out


def quit_liftoff():
    """Kill, not quit: a clean quit would write UserData.xml again and undo our edit."""
    if liftoff_running():
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


def start_and_open_last_session(tel=None, timeout=150.0):
    """Start Liftoff (if needed), Quick Play > Last Session, wait until the drone is in the level."""
    from .ui import click_capture
    if not liftoff_running():
        subprocess.run(["cmd", "/c", "start", "", STEAM_APP])
    end = time.time() + timeout
    while time.time() < end:
        try:
            if window.client_rect()[2] > 800:
                break
        except Exception:
            pass
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
                return True
            if tel is None and time.time() - t_click > 30:
                return True
            time.sleep(0.5)
    return False


def load(race_name, tel=None, mode="race"):
    info = race_info(race_name)
    quit_liftoff()
    if mode == "race":
        set_last_session(RACE_SESSION.format(env=info["env"], race_id=info["race_id"]))
    else:
        set_last_session(FREE_SESSION.format(env=info["env"], track_id=info["track_id"]))
    ok = start_and_open_last_session(tel)
    return ok, info


def lap_record(race_id):
    """(average, number of best times, file mtime) for a race in lapTimes.xml, or None."""
    if not LAP_TIMES.exists():
        return None
    root = ET.fromstring(LAP_TIMES.read_text(encoding="utf-8-sig").split("?>", 1)[-1])
    for lt in root.iter("lapTime"):
        if lt.findtext("ID/str") == race_id:
            times = [float(t.text) for t in lt.iter("Time")]
            return {"average": float(lt.findtext("average") or 0), "best": times, "mtime": LAP_TIMES.stat().st_mtime}
    return {"average": None, "best": [], "mtime": LAP_TIMES.stat().st_mtime}


def lap_counted(before, after):
    """Liftoff accepted at least one new lap between the two records."""
    if after is None:
        return False
    if before is None or before["average"] is None:
        return after["average"] is not None
    return after["mtime"] != before["mtime"] and (after["average"] != before["average"] or after["best"] != before["best"])


if __name__ == "__main__":
    cmd, name = sys.argv[1], sys.argv[2]
    if cmd == "load":
        print(load(name, mode=sys.argv[3] if len(sys.argv) > 3 else "race")[0])
    elif cmd == "laps":
        print(lap_record(race_info(name)["race_id"]))
