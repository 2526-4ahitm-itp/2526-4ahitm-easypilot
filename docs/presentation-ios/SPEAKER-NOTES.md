# EasyPilot iOS — Speaker Notes

Personal talking script for the iOS overview deck (`EasyPilot-iOS-Overview.pptx`
/ `index.html`). Five slides. For each slide: **what's on screen**, **what to
say**, and **likely questions** with answers. Times are rough — the whole talk
fits in ~8–10 minutes.

---

## Slide 1 — Title: "The EasyPilot iOS App"  (~30 s)

**On screen:** Title, one-line summary, tech tags (SwiftUI, Network.framework,
SceneKit, CoreMotion, Combine).

**Say:**
> "This is the iOS side of EasyPilot. It's a SwiftUI companion app for our
> drone. It does four things: it finds the drone on the WiFi by itself,
> it streams live telemetry at 10 times a second, it has a full 3D flight
> simulator you can fly on the phone, and it sends flight commands to the
> drone over a WebSocket. I built it with Apple's own frameworks — no
> third-party libraries."

**If asked "why iOS / SwiftUI?":** SwiftUI is declarative, so the UI updates
automatically when the data changes — perfect for live telemetry. And using
only Apple frameworks keeps it lightweight and dependency-free.

---

## Slide 2 — "The iOS stack"  (~75 s)

**On screen:** Cards for Swift, SwiftUI, Network.framework, SceneKit,
CoreMotion, Espressif ESP32 — each with a logo, a name, and one line.

**Say:**
> "These are the building blocks. **Swift** is the language. **SwiftUI** is the
> entire user interface — declarative, with live bindings, so when telemetry
> changes the screen redraws itself. **Network.framework** does the networking:
> an NWListener for the UDP discovery, and a WebSocket task for the data link.
> **SceneKit** powers the 3D flight simulator — it renders a real .usdz drone
> model with animated propellers. **CoreMotion** reads the phone's gyro and
> accelerometer at 10 Hz for tilt-based interaction. And on the drone itself,
> the **ESP32** firmware provides the WiFi, the WebSocket server, and the
> discovery beacon."

**If asked "what's a .usdz file?":** Apple's 3D model format — like a 3D
equivalent of a JPEG. We use it for the drone model in the simulator.

---

## Slide 3 — Code: "Phone tilt → drone command"  (~75 s)

**On screen:** Left: CoreMotion device-motion handler converting radians to
degrees. Right: a type-safe JSON command builder (`startBalanceCommand`).

**Say:**
> "Two halves here. On the left, CoreMotion gives me the phone's attitude — its
> pitch and roll — 10 times a second. I convert from radians to degrees and
> store it. On the right is how commands go out: instead of hand-writing JSON
> strings everywhere, I have builder functions that produce the exact command
> the firmware expects — here, START_BALANCE with the throttle and the two PID
> gains. Keeping it in one typed place means I can't typo a command."

**If asked "what's the tilt used for?":** Tilt-based interactions like the
sound-mode demo and simulator input — it is deliberately not direct flight
control of the real drone, for safety.

**If asked "what are kPRoll / kPPitch?":** Proportional gains for the drone's
balance controller — how hard it corrects when it tilts off level.

---

## Slide 4 — Code: "Two threads, one drone"  (~75 s)

**On screen:** `DroneSimulator` class — `@Published` vars (main thread) vs.
`_`-prefixed raw physics vars (render thread), plus `tick()` and
`syncPublished()`.

**Say:**
> "One of the trickiest problems was thread safety. The simulator's physics runs
> on the graphics render thread, but SwiftUI only allows updates on the main
> thread — touching the UI from the wrong thread crashes the app. Here's the
> solution. The class keeps two sets of state. The
> `@Published` variables at the top are touched only on the main thread — those
> drive SwiftUI. The underscore variables are the raw physics — position,
> velocity, angles — and those are touched only on the render thread inside
> `tick()`, which runs every frame. Then `syncPublished()` copies the physics
> state into the published state on the main thread at a fixed rate. The two
> worlds never touch each other's data directly, so there are no race
> conditions and no crashes."

**If asked "why not just lock it?":** Locks on a 60-fps render loop hurt
performance and risk stalls. Separating the state and syncing once per frame is
simpler and faster.

---

## Slide 5 — "Where we are & what's next"  (~45 s)

**On screen:** Done column (discovery + telemetry, Dashboard with 3D view, full
simulator with Rate/Balance/PosHold, joysticks + profiles) and Next/Sprint 6.

**Say:**
> "To wrap up — what's done: the app discovers the drone and streams telemetry,
> there's a live Dashboard with the 3D view, a complete flight simulator with
> three modes, Mode-2 virtual joysticks, and savable control profiles. Next, in
> Sprint 6, comes Live mode — flying the real drone directly from those
> joysticks — real MSP telemetry from the Betaflight flight controller, and more
> landscape-UI polish. Thanks — happy to take questions."

**Likely closing questions**
- *"Does it fly a real drone yet?"* — Telemetry and commands work; full
  joystick-to-real-drone "Live mode" is the Sprint 6 goal. The simulator already
  proves the control path.
- *"What are the three simulator modes?"* — Rate (raw, like acro), Balance
  (auto-levels to horizontal), and PosHold (holds position — a GPS-loiter feel).
- *"How accurate is the simulator?"* — It integrates real rigid-body physics
  (thrust, drag, gravity) frame by frame, not a canned animation.

---

### 15-second elevator version (if you're cut short)
> "It's a SwiftUI iPhone app that auto-finds our drone on WiFi, streams live
> telemetry at 10 Hz over a WebSocket, lets you fly a real-physics 3D simulator,
> and sends flight commands — built entirely with Apple frameworks, with real
> engineering around networking, threading, and flight safety."
