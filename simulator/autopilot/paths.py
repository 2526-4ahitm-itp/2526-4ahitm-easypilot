"""Where Liftoff keeps its files, on Windows and on macOS.

Liftoff is a Unity game, so its user data sits in Unity's persistentDataPath:
  Windows  %USERPROFILE%\\AppData\\LocalLow\\LuGus Studios\\Liftoff
  macOS    ~/Library/Application Support/LuGus Studios/Liftoff
The game data (asset bundles) lives in the Steam install folder.

EASYPILOT_LIFTOFF_USER and EASYPILOT_LIFTOFF_GAME override both (other Steam library,
other drive).
"""
import os
import sys
from pathlib import Path

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

if IS_MAC:
    _USER = Path.home() / "Library/Application Support/LuGus Studios/Liftoff"
    _GAME = Path.home() / "Library/Application Support/Steam/steamapps/common/Liftoff/Liftoff.app/Contents/Resources/Data"
    BUNDLE_PLATFORM = "StandaloneOSX"
else:
    _USER = Path.home() / "AppData/LocalLow/LuGus Studios/Liftoff"
    _GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Liftoff\Liftoff_Data")
    BUNDLE_PLATFORM = "StandaloneWindows64"

LIFTOFF_USER = Path(os.environ.get("EASYPILOT_LIFTOFF_USER") or _USER)
GAME = Path(os.environ.get("EASYPILOT_LIFTOFF_GAME") or _GAME)
BUNDLES = GAME / "StreamingAssets/aa" / BUNDLE_PLATFORM
