"""Keeps one OpenJoystickDriver virtual gamepad alive for the autopilot (macOS).

Run once and leave it running, like the vJoy driver on Windows:
    simulator/.venv/bin/python simulator/mac/ojdpad.py
Listens on UDP 127.0.0.1:9101 (protocol in autopilot/vjoy.py, MacVJoy). No packet for 0.5 s:
throttle off, sticks centred, no buttons.
"""
import socket
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autopilot.vjoy import MAC_PORT, OjdGamepad  # noqa: E402

FAILSAFE = 0.5


def main():
    pad = OjdGamepad()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", MAC_PORT))
    sock.settimeout(0.1)
    print(f"ojdpad: gamepad up, listening on 127.0.0.1:{MAC_PORT} (Ctrl-C to stop)", flush=True)
    last, idle = time.monotonic(), True
    try:
        while True:
            try:
                data, addr = sock.recvfrom(64)
            except socket.timeout:
                if not idle and time.monotonic() - last > FAILSAFE:
                    pad.idle()
                    idle = True
                if pad.proc.poll() is not None:
                    sys.exit("ojdpad: ojd virtual feed ended - is OpenJoystickDriver running?")
                continue
            if data == b"PING":
                sock.sendto(b"PONG", addr)
                continue
            if len(data) != 20:
                continue
            *axes, buttons = struct.unpack("<8hI", data)
            with pad.lock:
                pad.axes = [a / 32767 for a in axes]
                pad.buttons = buttons
            last, idle = time.monotonic(), False
    except KeyboardInterrupt:
        pass
    finally:
        pad.close()


if __name__ == "__main__":
    main()
