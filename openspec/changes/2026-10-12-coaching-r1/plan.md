# Coaching Runde 1 – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alle offenen To-dos aus Coaching Runde 1 (08.10.2026) umsetzen: automatisierte Tests, CI, Doku-Link im README, Projektpräsentation mit Aufgabenstellung/Team/Stand/Terminen/Meilensteinen/C4, dokumentiertes Deployment auf die LeoCloud.

**Architecture:** Die Arbeit ist in Arbeitspakete (AP) geschnitten. Jedes AP hat einen eigenen Branch von `main`, eigene Commits nach Conventional Commits und endet mit einem PR nach `main`. Reihenfolge: AP0 zuerst (bringt den iOS-Code auf `main`), danach sind AP1–AP3 unabhängig, AP4–AP6 bauen auf den Ergebnissen auf.

**Tech Stack:** Swift/SwiftUI + Swift Testing/XCTest, Quarkus 3.28 (Java 21) + JUnit, React 19 + Vite 7 + three.js, GitHub Actions, Kubernetes (LeoCloud), reveal.js 5.1.0 + Mermaid (C4), AsciiDoc, OpenSpec.

**Spec:** `openspec/changes/2026-10-12-coaching-r1/proposal.md` (dieser Ordner) und das Coaching-Feedback Runde 1 (unten zitiert).

## Coaching-Feedback Runde 1 (Ausgangslage)

| Bereich | Kriterium | R1 | Arbeitspaket |
|---|---|---|---|
| Arbeit & Prozess | Commit-Konventionen | ⚪ | AP4 (dokumentieren), alle APs (anwenden) |
| Arbeit & Prozess | Verteilung im Team | ⚪ | erledigt: `.mailmap` (Branch `chore/mailmap`) |
| Tests | Automatisierte Tests vorhanden | 🟡 | AP1 |
| Tests | Tests laufen | 🟢 | AP1 (bleibt grün) |
| Tests | Tests in CI | 🔴 | AP2 |
| Dokumentation | Link zur Doku im README | 🔴 | AP4 |
| Dokumentation | Doku erreichbar | 🟢 | – |
| Präsentation | als reveal.js veröffentlicht | 🟡 | AP5 |
| Präsentation | Aufgabenstellung / aktuell | 🔴/🟡 | AP4 + AP5 |
| Präsentation | Team | 🔴 | AP5 |
| Präsentation | Aktueller Stand | 🟡 | AP5 |
| Präsentation | Projekttermine | 🔴 | AP5 |
| Präsentation | Meilensteine | 🟡 | AP5 |
| Präsentation | C4-Kontext / -Container | 🔴 | AP5 |
| Präsentation | C4-Komponente (Bonus) | ⚪ | AP5 (Task 5.4) |
| Präsentation | C4 zeigt neue Lösung | 🟡 | AP5 |
| Deployment | Zielserver / URLs / Deploy-Ablauf | 🟡 | AP6 |
| Deployment | Konfiguration | 🟢 | – |

## Bestandsaufnahme (12.10.2026)

- `main` hat die neue Pages-Seite (Startseite, Projektdoku `docs/projektdoku.adoc`, iOS-Slides). Der neueste iOS-Code (`DroneCommand`, `FlightMode`, Reconnect-Fix) und weitere Deck-Commits liegen nur auf `origin/ep7-ios-app`.
- Tests: iOS nur leere Xcode-Templates; Backend hat `StatusResourceTest` (2 Tests); Frontend keine. `PlatformIO/.../test_ssl.cpp` und `test_wifi.cpp` sind keine Tests, sondern alte Experimente.
- Lokal ist keine iOS-Plattform installiert („iOS 26.2 is not installed“), ohne sie laufen weder iOS-Build noch -Tests.
- Das Xcode-Schema `EasyPilotIOS` ist **nicht geteilt** (keine `xcshareddata/xcschemes/*.xcscheme`). Auf CI gibt es das Schema dann nicht.
- Keine CI (`.github/workflows/` fehlt).
- `webinterface/frontend` hat kein `package-lock.json`; `ModelPage.jsx` verbindet fest auf `ws://localhost:8765`.
- `PlatformIO/Projects/EasyPilotIOS/include/secrets_auto.h` ist eingecheckt und enthält **echte WLAN-Zugangsdaten** (in `.gitignore`, aber vorher getrackt).
- `k8s/` enthält nur ein Demo-Postgres (vom Backend nicht benutzt). Für Backend/Frontend gibt es keine Manifeste; das Backend hat `src/main/docker/Dockerfile.jvm`.
- Der Python-Relay (`relay_server.py`) schickt UDP-Broadcasts ins lokale Netz, damit die iOS-App ihn findet. Das funktioniert nur im selben LAN, nicht aus einem Kubernetes-Cluster.
- Doku-Lücken: `CLAUDE.md` beschreibt Sprint 3; README verlinkt die Pages-Seite nicht; Simulator-Spec sagt zu LIVE „Available in Sprint 5“; Projektdoku nennt `secrets.ini.example` (existiert nicht) und als Team nur „Team EasyPilot“.
- Bug: Firmware meldet `"mode":"RC"`, die App macht daraus `IDLE` und blendet im Tab „Algorithms“ den STOP-Button aus (`ControlView.swift`, `if droneMode != .idle`).

## Global Constraints

- **Branches:** Ein Branch pro AP, Name `<typ>/<thema>` (siehe Tabelle unten), immer von aktuellem `origin/main`. Nie direkt auf `main` committen.
- **Commits:** Conventional Commits, Betreff auf Deutsch im Imperativ: `<typ>(<scope>): <was>`. Typen: `feat`, `fix`, `test`, `docs`, `ci`, `chore`, `refactor`. Scopes: `ios`, `firmware`, `backend`, `web`, `k8s`, `docs`, `pages`. Body erklärt das *Warum*, wenn es nicht offensichtlich ist. Ein Commit = ein Task.
- **Identität:** Commits nur als `SimonnEder <114646364+SimonnEder@users.noreply.github.com>` (globale Git-Config). **Keine** `Co-Authored-By`- oder `Claude-Session`-Zeilen, kein „Generated with Claude Code“ in PRs.
- **PRs:** Ein PR pro AP nach `main`, Beschreibung auf Deutsch mit „Änderung“, „Warum“, „Wie getestet“ (inkl. Ausgabe-Ausschnitt). Merge erst nach Freigabe durch das Team.
- **Push** nur nach Freigabe durch das Team.
- Code, Kommentare, Log-Texte Englisch; Doku Deutsch.
- Keine neuen Code-Dependencies ohne Rückfrage. GitHub-eigene Actions (`actions/*`) und CDN-Skripte für Pages (reveal.js, Mermaid) gelten als freigegeben, weil sie nicht ins Produkt gehen.
- Xcode lokal immer mit `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`; Test-Destination als `SIM_DEST` (Task 1.1).
- Das Xcode-Projekt nutzt synchronisierte Ordner (`objectVersion = 77`): neue `.swift`-Dateien werden automatisch ins Target aufgenommen; `project.pbxproj` nicht von Hand ändern.
- Wire-Format zur Firmware bleibt unverändert; Tests pinnen das heutige Format.
- Alles, was in Doku oder Folien steht, muss im Repo oder durch das Team belegt sein. Unbelegtes wird als „vom Team zu ergänzen“ markiert, nicht erfunden.

| AP | Branch | Inhalt |
|---|---|---|
| AP0 | `ep7-ios-app` → PR | iOS-Stand nach `main` bringen |
| AP1 | `test/ios-unit-tests` | iOS-Tests, geteiltes Schema |
| AP2 | `ci/github-actions` | CI für Backend, iOS, Frontend |
| AP3 | `chore/firmware-secrets` | Zugangsdaten untracken, Experimente löschen |
| AP4 | `docs/coaching-r1` | README, CLAUDE.md, Specs, Projektdoku, Konventionen |
| – | `chore/mailmap` | erledigt: `.mailmap`, Git-Identität vereinheitlicht |
| AP5 | `docs/project-presentation` | Projektpräsentation mit C4 |
| AP6 | `feat/k8s-leocloud` | Deployment LeoCloud + Doku |
| AP7 (optional) | `fix/ios-rc-mode` | RC-Modus-Bug, RC-Befehle ins Enum |

## Vorbedingungen (vom Team)

1. iOS-Plattform in Xcode installieren (Task 1.1, Step 1).
2. Entscheidung zu den lokalen, uncommitteten Änderungen auf `ep7-ios-app` (pptx, `build_deck*.py`, Logos, `SPEAKER-NOTES.md`): `origin/ep7-ios-app` hat neuere Commits an denselben Dateien. Vor AP0 entweder committen oder verwerfen.
3. LeoCloud: Namespace, Hostname der Produktions-URL, `kubeconfig` und die Ingress-Vorgaben der LeoCloud (für AP6).
4. Künftige Projekttermine und geplante Meilensteine der Phase 2 (für AP5; bis dahin als „vom Team zu ergänzen“ markiert).
5. Formulierung der Aufgabenstellung Phase 2 bestätigen (Task 4.4).

## Review Focus

1. **Dezimaltrennzeichen bei deutschem Gerät:** `startBalance` muss auch mit Region Österreich `10.00` senden, nicht `10,00`, sonst ignoriert ArduinoJson den Befehl. Test: `balancePayloadUsesDotDecimalSeparator` (Task 1.2).
2. **Unbekannter oder fehlender Modus in der Telemetrie:** `"RC"`, `"foo"`, fehlendes Feld → kein Absturz, `.idle`. Tests: `unknownModeFallsBackToIdle`, `rcModeIsCurrentlyReportedAsIdle` (Task 1.2).
3. **Minimale Telemetrie älterer Firmware** (nur `roll/pitch/yaw`) muss dekodieren. Test: `decodesMinimalTelemetry` (Task 1.3).
4. **Sound Mode an den Grenzen:** 60° = noch kein Notstopp, 60,1° = Notstopp; über 45° bleibt PWM bei `maxPWM`; Neigung auf 90° geklemmt. Tests in Task 1.4.
5. **CI läuft auch auf PRs aus Forks/Branches ohne Secrets:** Workflows dürfen für Tests keine Secrets brauchen; nur der Image-Push (AP6) braucht `GITHUB_TOKEN` und läuft nur auf `main`. Prüfung in Task 2.4 und 6.3.

---

## AP0: iOS-Stand nach `main` bringen

### Task 0.1: `main` in `ep7-ios-app` mergen und PR öffnen

**Files:** Merge, Konflikte unter `docs/`, `README.adoc`, `openspec/specs/guidelines.md`

- [ ] **Step 1: Sauberen Worktree vom Remote-Stand anlegen** (sobald Vorbedingung 2 erledigt ist)

```bash
cd /Users/simoneder/2526-4ahitm-easypilot
git fetch origin
git worktree add ../easypilot-ap0 ep7-ios-app
cd ../easypilot-ap0
git pull --ff-only origin ep7-ios-app
git merge origin/main
```

- [ ] **Step 2: Konflikte auflösen**

- `docs/index.html`, `docs/projektdoku.*`, `docs/presentation-ios/index.html`, `docs/presentation-ios/slides.html`: Version von `main` (`git checkout --theirs <datei>`).
- `docs/index.adoc` (auf `main` nach `docs/projektdoku.adoc` umbenannt): Änderungen aus `ep7` per `git diff origin/main...ep7-ios-app -- docs/index.adoc` prüfen und in `docs/projektdoku.adoc` übernehmen, dann `git rm docs/index.adoc`.
- Übrige Dateien in `docs/presentation-ios/` (pptx, `build_deck*.py`, `logos/`, `SPEAKER-NOTES.md`): Version von `ep7` (`git checkout --ours <datei>`).

- [ ] **Step 3: Prüfen**

Run: `git grep -n "docs/index.adoc"` → keine Treffer.
Run: `ls docs/projektdoku.adoc docs/index.html docs/presentation-ios/slides.html EasyPilotIOS/EasyPilotIOS/DroneCommand.swift` → alle vorhanden.

- [ ] **Step 4: Commit, Push, PR** (nach Freigabe)

```bash
git commit -m "chore: main in ep7-ios-app mergen"
git push origin ep7-ios-app
gh pr create --base main --head ep7-ios-app --title "feat(ios): typisierte Befehle, Reconnect-Fix und Deck-Updates nach main"
```

Nach dem Merge: `git worktree remove ../easypilot-ap0`.

---

## AP1: iOS-Tests (`test/ios-unit-tests`)

```bash
git fetch origin && git worktree add -b test/ios-unit-tests ../easypilot-ap1 origin/main && cd ../easypilot-ap1
```

### Task 1.1: Testumgebung herstellen und Schema teilen

**Files:**
- Create: `EasyPilotIOS/EasyPilotIOS.xcodeproj/xcshareddata/xcschemes/EasyPilotIOS.xcscheme`

**Interfaces:**
- Produces: `SIM_DEST`, geteiltes Schema `EasyPilotIOS` (AP2 braucht es auf CI).

- [ ] **Step 1: iOS-Plattform installieren** (Team, manuell): Xcode → Settings → Components → iOS 26.2 inkl. Simulator, oder:

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -downloadPlatform iOS
```

- [ ] **Step 2: Simulator wählen**

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun simctl list devices available | grep -i iphone
export SIM_DEST='platform=iOS Simulator,name=iPhone 17'   # Namen aus der Liste übernehmen
```

- [ ] **Step 3: Schema teilen**

In Xcode: Product → Scheme → Manage Schemes… → bei `EasyPilotIOS` Haken „Shared“ setzen. Kontrolle:

Run: `ls EasyPilotIOS/EasyPilotIOS.xcodeproj/xcshareddata/xcschemes/`
Expected: `EasyPilotIOS.xcscheme`

Run: `grep -c "EasyPilotIOSTests\|EasyPilotIOSUITests" EasyPilotIOS/EasyPilotIOS.xcodeproj/xcshareddata/xcschemes/EasyPilotIOS.xcscheme`
Expected: ≥ 2 (beide Test-Targets im Test-Abschnitt). Fehlen sie: im Schema-Editor unter „Test“ beide Targets hinzufügen.

- [ ] **Step 4: Baseline mit Template-Test**

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild test \
  -project EasyPilotIOS/EasyPilotIOS.xcodeproj -scheme EasyPilotIOS \
  -destination "$SIM_DEST" -only-testing:EasyPilotIOSTests
```

Expected: `** TEST SUCCEEDED **`. Scheitert schon der Build: stoppen und den Fehler melden.

- [ ] **Step 5: Commit**

```bash
git add EasyPilotIOS/EasyPilotIOS.xcodeproj/xcshareddata
git commit -m "chore(ios): Xcode-Schema teilen, damit Tests auf CI laufen"
```

### Task 1.2: Tests für `DroneCommand` und `FlightMode`

**Files:**
- Delete: `EasyPilotIOS/EasyPilotIOSTests/EasyPilotIOSTests.swift`
- Create: `EasyPilotIOS/EasyPilotIOSTests/DroneCommandTests.swift`, `EasyPilotIOS/EasyPilotIOSTests/FlightModeTests.swift`

**Interfaces:**
- Consumes: `DroneCommand.payload: String`, `FlightMode(rawOrIdle: String?)`.

- [ ] **Step 1: Template löschen, Tests schreiben**

```bash
git rm EasyPilotIOS/EasyPilotIOSTests/EasyPilotIOSTests.swift
```

`DroneCommandTests.swift`:

```swift
import Foundation
import Testing
@testable import EasyPilotIOS

/// Pins the exact wire format the ESP32 firmware (main.cpp) parses.
struct DroneCommandTests {

    @Test func simpleCommands() {
        #expect(DroneCommand.arm.payload == #"{"cmd":"ARM"}"#)
        #expect(DroneCommand.disarm.payload == #"{"cmd":"DISARM"}"#)
        #expect(DroneCommand.stop.payload == #"{"cmd":"STOP"}"#)
    }

    @Test func safeTestIsPlainText() {
        #expect(DroneCommand.safeTest.payload == "SAFE_TEST")
    }

    @Test func startBalance() {
        let cmd = DroneCommand.startBalance(baseThrottle: 1200, kPRoll: 10, kPPitch: 12.5)
        #expect(cmd.payload == #"{"cmd":"START_BALANCE","baseThrottle":1200,"kPRoll":10.00,"kPPitch":12.50}"#)
    }

    @Test func balancePayloadUsesDotDecimalSeparator() {
        // ArduinoJson only understands '.', regardless of the phone's region.
        let payload = DroneCommand.startBalance(baseThrottle: 1100, kPRoll: 1.5, kPPitch: 0.25).payload
        #expect(payload.contains("1.50"))
        #expect(!payload.contains("1,50"))
    }

    @Test func startManual() {
        let cmd = DroneCommand.startManual(roll: 1.5, pitch: -2, yaw: 0,
                                           m1: 1000, m2: 1100, m3: 1200, m4: 1300,
                                           voltage: 16.8, batteryPercentage: 100)
        #expect(cmd.payload == #"{"cmd":"START_MANUAL","roll":1.50,"pitch":-2.00,"yaw":0.00,"m1":1000,"m2":1100,"m3":1200,"m4":1300,"voltage":16.80,"batteryPercentage":100}"#)
    }

    @Test func updateManualHasNoCmdKey() {
        let cmd = DroneCommand.updateManual(roll: 0, pitch: 0, yaw: 0,
                                            m1: 1000, m2: 1000, m3: 1000, m4: 1000,
                                            voltage: 16.8, batteryPercentage: 100)
        #expect(!cmd.payload.contains("\"cmd\""))
        #expect(cmd.payload.hasPrefix(#"{"roll":0.00"#))
    }

    @Test func soundCommands() {
        #expect(DroneCommand.startSound(maxPWM: 1400).payload == #"{"cmd":"START_SOUND","maxPWM":1400}"#)
        #expect(DroneCommand.tiltSound(pwm: 1234).payload == #"{"cmd":"TILT_SOUND","pwm":1234}"#)
    }

    @Test(arguments: [
        DroneCommand.arm, .disarm, .stop,
        .startBalance(baseThrottle: 1200, kPRoll: 10, kPPitch: 10),
        .startManual(roll: 0, pitch: 0, yaw: 0, m1: 1000, m2: 1000, m3: 1000, m4: 1000,
                     voltage: 16.8, batteryPercentage: 100),
        .updateManual(roll: 0, pitch: 0, yaw: 0, m1: 1000, m2: 1000, m3: 1000, m4: 1000,
                      voltage: 16.8, batteryPercentage: 100),
        .startSound(maxPWM: 1400), .tiltSound(pwm: 1200),
    ])
    func jsonCommandsAreValidJSON(_ cmd: DroneCommand) throws {
        let object = try JSONSerialization.jsonObject(with: Data(cmd.payload.utf8))
        #expect(object is [String: Any])
    }
}
```

`FlightModeTests.swift`:

```swift
import Testing
@testable import EasyPilotIOS

struct FlightModeTests {

    @Test func parsesFirmwareStrings() {
        #expect(FlightMode(rawOrIdle: "IDLE") == .idle)
        #expect(FlightMode(rawOrIdle: "BALANCE") == .balance)
        #expect(FlightMode(rawOrIdle: "MANUAL") == .manual)
        #expect(FlightMode(rawOrIdle: "SOUND") == .sound)
    }

    @Test func unknownModeFallsBackToIdle() {
        #expect(FlightMode(rawOrIdle: nil) == .idle)
        #expect(FlightMode(rawOrIdle: "") == .idle)
        #expect(FlightMode(rawOrIdle: "balance") == .idle)   // case-sensitive like the firmware
        #expect(FlightMode(rawOrIdle: "foo") == .idle)
    }

    /// Documents the bug fixed in AP7. Flip this test when AP7 lands.
    @Test func rcModeIsCurrentlyReportedAsIdle() {
        #expect(FlightMode(rawOrIdle: "RC") == .idle)
    }

    @Test func rawValuesRoundTrip() {
        for mode in FlightMode.allCases {
            #expect(FlightMode(rawOrIdle: mode.rawValue) == mode)
        }
    }
}
```

- [ ] **Step 2: Laufen lassen**

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild test \
  -project EasyPilotIOS/EasyPilotIOS.xcodeproj -scheme EasyPilotIOS \
  -destination "$SIM_DEST" -only-testing:EasyPilotIOSTests
```

Expected: `** TEST SUCCEEDED **` (Charakterisierungstests, müssen sofort grün sein). Ein roter Test heißt: das Format weicht von der Firmware ab → `main.cpp` prüfen, nicht den Test anpassen.

- [ ] **Step 3: Commit**

```bash
git add -A EasyPilotIOS/EasyPilotIOSTests
git commit -m "test(ios): Wire-Format von DroneCommand und FlightMode absichern"
```

### Task 1.3: Tests für Telemetrie-Decoding

**Files:** Create `EasyPilotIOS/EasyPilotIOSTests/DroneTelemetryTests.swift`

- [ ] **Step 1: Tests schreiben**

```swift
import Foundation
import Testing
@testable import EasyPilotIOS

struct DroneTelemetryTests {

    private func decode(_ json: String) throws -> DroneTelemetry {
        try JSONDecoder().decode(DroneTelemetry.self, from: Data(json.utf8))
    }

    @Test func decodesFullFirmwarePacket() throws {
        let t = try decode(#"""
        {"roll":1.5,"pitch":-2.0,"yaw":90.0,"m1":1000,"m2":1010,"m3":1020,"m4":1030,
         "voltage":16.8,"batteryPercentage":100,"armed":true,"mode":"BALANCE","fc":true}
        """#)
        #expect(t.roll == 1.5)
        #expect(t.pitch == -2.0)
        #expect(t.m4 == 1030)
        #expect(t.armed == true)
        #expect(t.mode == "BALANCE")
        #expect(t.fc == true)
    }

    @Test func decodesMinimalTelemetry() throws {
        let t = try decode(#"{"roll":0,"pitch":0,"yaw":0}"#)
        #expect(t.m1 == nil)
        #expect(t.voltage == nil)
        #expect(t.armed == nil)
        #expect(t.mode == nil)
        #expect(t.fc == nil)
    }

    @Test func rejectsPacketWithoutAttitude() {
        #expect(throws: DecodingError.self) {
            try decode(#"{"m1":1000}"#)
        }
    }

    @Test func ignoresUnknownFields() throws {
        let t = try decode(#"{"roll":0,"pitch":0,"yaw":0,"newField":42}"#)
        #expect(t.roll == 0)
    }
}
```

- [ ] **Step 2: Laufen lassen** (Befehl wie 1.2 Step 2) → `** TEST SUCCEEDED **`.

- [ ] **Step 3: Commit**

```bash
git add EasyPilotIOS/EasyPilotIOSTests/DroneTelemetryTests.swift
git commit -m "test(ios): Decoding der ESP32-Telemetrie absichern"
```

### Task 1.4: Sound-Mode-Rechnung herausziehen und testen

Die Rechnung steckt als `private` Properties in `ControlView` und ist so nicht testbar. Sie wird unverändert in einen reinen Typ verschoben.

**Files:**
- Create: `EasyPilotIOS/EasyPilotIOS/SoundMode.swift`
- Modify: `EasyPilotIOS/EasyPilotIOS/ControlView.swift` (`currentTiltAngle`, `currentSoundPWM`, Notstopp in `startSoundMode()`)
- Test: `EasyPilotIOS/EasyPilotIOSTests/SoundModeTests.swift`

**Interfaces:**
- Produces: `SoundMode.tiltAngle(pitch:roll:) -> Double`, `SoundMode.pwm(forTilt:maxPWM:) -> Int`, `SoundMode.isEmergency(tilt:) -> Bool`, `SoundMode.emergencyTiltDegrees = 60.0`, `SoundMode.fullScaleTiltDegrees = 45.0`.

- [ ] **Step 1: Name frei?** `grep -rnw "SoundMode" EasyPilotIOS/EasyPilotIOS` → keine Treffer.

- [ ] **Step 2: Failing Test**

```swift
import Testing
@testable import EasyPilotIOS

struct SoundModeTests {

    @Test func tiltCombinesPitchAndRoll() {
        #expect(SoundMode.tiltAngle(pitch: 3, roll: 4) == 5)
        #expect(SoundMode.tiltAngle(pitch: -3, roll: -4) == 5)
    }

    @Test func tiltIsClampedTo90() {
        #expect(SoundMode.tiltAngle(pitch: 100, roll: 100) == 90)
    }

    @Test func levelPhoneIsSilent() {
        #expect(SoundMode.pwm(forTilt: 0, maxPWM: 1400) == 1000)
    }

    @Test func pwmScalesLinearlyUpTo45Degrees() {
        #expect(SoundMode.pwm(forTilt: 22.5, maxPWM: 1400) == 1200)
        #expect(SoundMode.pwm(forTilt: 45, maxPWM: 1400) == 1400)
    }

    @Test func pwmStaysAtMaxAbove45Degrees() {
        #expect(SoundMode.pwm(forTilt: 80, maxPWM: 1400) == 1400)
        #expect(SoundMode.pwm(forTilt: 90, maxPWM: 1050) == 1050)
    }

    @Test func emergencyStartsAbove60Degrees() {
        #expect(!SoundMode.isEmergency(tilt: 60))
        #expect(SoundMode.isEmergency(tilt: 60.1))
    }
}
```

- [ ] **Step 3: Laufen lassen** → Build-Fehler `cannot find 'SoundMode' in scope`.

- [ ] **Step 4: Implementierung** – `SoundMode.swift`:

```swift
import Foundation

/// Tilt → PWM math for Sound Mode, kept out of the view so it can be unit-tested.
enum SoundMode {
    /// Tilt (degrees) above which the app sends an emergency STOP.
    static let emergencyTiltDegrees = 60.0
    /// Tilt (degrees) at which the motors reach `maxPWM`.
    static let fullScaleTiltDegrees = 45.0

    /// Combined tilt of the phone in degrees, clamped to 90.
    static func tiltAngle(pitch: Double, roll: Double) -> Double {
        min(sqrt(pitch * pitch + roll * roll), 90)
    }

    /// PWM for a tilt: 1000 when level, `maxPWM` at 45° and beyond.
    static func pwm(forTilt tilt: Double, maxPWM: Double) -> Int {
        1000 + Int((min(tilt, fullScaleTiltDegrees) / fullScaleTiltDegrees) * (maxPWM - 1000))
    }

    static func isEmergency(tilt: Double) -> Bool {
        tilt > emergencyTiltDegrees
    }
}
```

In `ControlView.swift`:

```swift
    private var currentTiltAngle: Double {
        SoundMode.tiltAngle(pitch: motionManager.pitch, roll: motionManager.roll)
    }
    private var currentSoundPWM: Int {
        SoundMode.pwm(forTilt: currentTiltAngle, maxPWM: maxSoundPWM)
    }
```

und in `startSoundMode()` `if self.currentTiltAngle > 60 {` → `if SoundMode.isEmergency(tilt: self.currentTiltAngle) {`.

- [ ] **Step 5: Laufen lassen** → `** TEST SUCCEEDED **`.

- [ ] **Step 6: Commit**

```bash
git add EasyPilotIOS/EasyPilotIOS/SoundMode.swift EasyPilotIOS/EasyPilotIOS/ControlView.swift EasyPilotIOS/EasyPilotIOSTests/SoundModeTests.swift
git commit -m "refactor(ios): Sound-Mode-Rechnung in testbaren Typ auslagern" \
  -m "Die Rechnung lag privat in ControlView. Verhalten unverändert, jetzt mit Tests für 0°, 45°, 60° und 90°."
```

### Task 1.5: `ProfileManager` testbar machen und testen

**Files:**
- Modify: `EasyPilotIOS/EasyPilotIOS/ProfileManager.swift`
- Test: `EasyPilotIOS/EasyPilotIOSTests/ProfileManagerTests.swift`

**Interfaces:**
- Produces: `ProfileManager.init(defaults: UserDefaults = .standard)`; bestehende Aufrufe `ProfileManager()` bleiben gültig.

- [ ] **Step 1: Failing Test**

```swift
import Foundation
import Testing
@testable import EasyPilotIOS

struct ProfileManagerTests {

    /// Isolated defaults per test, so tests never touch real app data.
    private func freshDefaults() -> UserDefaults {
        let suite = "ProfileManagerTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defaults.removePersistentDomain(forName: suite)
        return defaults
    }

    @Test func savedProfileSurvivesRestart() {
        let defaults = freshDefaults()
        let profile = ControlProfile(name: "Hover", mode: "BALANCE", baseThrottle: 1300)
        ProfileManager(defaults: defaults).save(profile)

        #expect(ProfileManager(defaults: defaults).profiles == [profile])
    }

    @Test func savingSameIdReplacesInsteadOfDuplicating() {
        let manager = ProfileManager(defaults: freshDefaults())
        var profile = ControlProfile(name: "A")
        manager.save(profile)
        profile.kPRoll = 20
        manager.save(profile)

        #expect(manager.profiles.count == 1)
        #expect(manager.profiles.first?.kPRoll == 20)
    }

    @Test func renameAndDeletePersist() {
        let defaults = freshDefaults()
        let manager = ProfileManager(defaults: defaults)
        let a = ControlProfile(name: "A")
        let b = ControlProfile(name: "B")
        manager.save(a); manager.save(b)

        manager.rename(a, to: "Renamed")
        manager.delete(b)

        #expect(ProfileManager(defaults: defaults).profiles.map(\.name) == ["Renamed"])
    }

    @Test func corruptStoredDataStartsEmpty() {
        let defaults = freshDefaults()
        defaults.set(Data("not json".utf8), forKey: "easypilot.controlProfiles")
        #expect(ProfileManager(defaults: defaults).profiles.isEmpty)
    }
}
```

- [ ] **Step 2: Laufen lassen** → Build-Fehler `extra argument 'defaults' in call`.

- [ ] **Step 3: Implementierung** in `ProfileManager.swift`:

```swift
    private let storageKey = "easypilot.controlProfiles"
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        load()
    }
```

In `persist()` und `load()` `UserDefaults.standard` durch `defaults` ersetzen.

- [ ] **Step 4: Laufen lassen** → `** TEST SUCCEEDED **`.

- [ ] **Step 5: Commit**

```bash
git add EasyPilotIOS/EasyPilotIOS/ProfileManager.swift EasyPilotIOS/EasyPilotIOSTests/ProfileManagerTests.swift
git commit -m "test(ios): Persistenz der Steuerprofile absichern"
```

### Task 1.6: UI-Templates durch Smoke-Test ersetzen

**Files:**
- Delete: `EasyPilotIOS/EasyPilotIOSUITests/EasyPilotIOSUITestsLaunchTests.swift`
- Modify: `EasyPilotIOS/EasyPilotIOSUITests/EasyPilotIOSUITests.swift` (komplett ersetzen)

- [ ] **Step 1: Test schreiben**

```swift
import XCTest

/// Smoke test: the app launches and all three tabs are reachable.
/// No drone is needed — without an ESP32 the app simply stays offline.
final class EasyPilotIOSUITests: XCTestCase {

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func testAllTabsAreReachable() throws {
        let app = XCUIApplication()
        app.launch()

        for tab in ["Dashboard", "Simulator", "Algorithms"] {
            let button = app.tabBars.buttons[tab]
            XCTAssertTrue(button.waitForExistence(timeout: 5), "Tab \(tab) missing")
            button.tap()
        }
    }
}
```

```bash
git rm EasyPilotIOS/EasyPilotIOSUITests/EasyPilotIOSUITestsLaunchTests.swift
```

- [ ] **Step 2: Laufen lassen**

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild test \
  -project EasyPilotIOS/EasyPilotIOS.xcodeproj -scheme EasyPilotIOS \
  -destination "$SIM_DEST" -only-testing:EasyPilotIOSUITests
```

Expected: `** TEST SUCCEEDED **`. Verdeckt der iOS-Dialog „Lokales Netzwerk“ die Tab-Bar: vor der Schleife einen `addUIInterruptionMonitor` ergänzen, der „Allow“/„Erlauben“ tippt, danach `app.tap()`.

- [ ] **Step 3: Commit**

```bash
git add -A EasyPilotIOS/EasyPilotIOSUITests
git commit -m "test(ios): UI-Templates durch Smoke-Test der drei Tabs ersetzen"
```

### Task 1.7: Gesamtlauf und PR

- [ ] Alle iOS-Tests:

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild test \
  -project EasyPilotIOS/EasyPilotIOS.xcodeproj -scheme EasyPilotIOS -destination "$SIM_DEST" 2>&1 | tail -20
```

Expected: `** TEST SUCCEEDED **`; Ausschnitt mit Testanzahl in die PR-Beschreibung.

- [ ] Push und PR (nach Freigabe): `gh pr create --base main --title "test(ios): Unit- und UI-Tests statt Templates"`.

---

## AP2: CI mit GitHub Actions (`ci/github-actions`)

Nach AP1 (geteiltes Schema). `git worktree add -b ci/github-actions ../easypilot-ap2 origin/main`

### Task 2.1: Backend-Workflow

**Files:** Create `.github/workflows/backend.yml`

- [ ] **Step 1: Lokal grün?**

```bash
cd webinterface/backend && ./mvnw -B test
```

Expected: `Tests run: 2, Failures: 0, Errors: 0`, `BUILD SUCCESS`. Sonst: Ausgabe verbatim festhalten, superpowers:systematic-debugging, nicht den Test aufweichen.

- [ ] **Step 2: Ausführbar?** `git ls-files -s webinterface/backend/mvnw` → Modus `100755`. Wenn `100644`: `git update-index --chmod=+x webinterface/backend/mvnw`.

- [ ] **Step 3: Workflow**

```yaml
name: Backend

on:
  push:
    branches: [main]
    paths: ['webinterface/backend/**', '.github/workflows/backend.yml']
  pull_request:
    paths: ['webinterface/backend/**', '.github/workflows/backend.yml']

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: webinterface/backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '21'
          cache: maven
      - run: ./mvnw -B test
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/backend.yml webinterface/backend/mvnw
git commit -m "ci(backend): Quarkus-Tests bei jedem Push und PR ausführen"
```

### Task 2.2: iOS-Workflow

**Files:** Create `.github/workflows/ios.yml`

- [ ] **Step 1: Runner und Xcode festlegen**

In https://github.com/actions/runner-images nachsehen, welches macOS-Image Xcode 26.x mit iOS-Simulator enthält, und Image (`macos-…`), Xcode-Pfad (`/Applications/Xcode_26.x.app`) und einen vorhandenen Simulator-Namen notieren. Das Projekt verlangt iOS 18.5 als Deployment-Target und `objectVersion = 77`, braucht also mindestens Xcode 16.

- [ ] **Step 2: Workflow** (Werte aus Step 1 einsetzen: `RUNNER_IMAGE`, `XCODE_APP`, `SIM_NAME`)

```yaml
name: iOS

on:
  push:
    branches: [main]
    paths: ['EasyPilotIOS/**', '.github/workflows/ios.yml']
  pull_request:
    paths: ['EasyPilotIOS/**', '.github/workflows/ios.yml']

jobs:
  test:
    runs-on: macos-26            # RUNNER_IMAGE aus Step 1
    env:
      DEVELOPER_DIR: /Applications/Xcode_26.0.app/Contents/Developer   # XCODE_APP aus Step 1
    steps:
      - uses: actions/checkout@v4
      - name: Unit- und UI-Tests
        run: |
          xcodebuild test \
            -project EasyPilotIOS/EasyPilotIOS.xcodeproj \
            -scheme EasyPilotIOS \
            -destination 'platform=iOS Simulator,name=iPhone 17' \
            CODE_SIGNING_ALLOWED=NO
```

`CODE_SIGNING_ALLOWED=NO`: auf CI gibt es kein Signing-Zertifikat, für den Simulator ist keins nötig.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ios.yml
git commit -m "ci(ios): Unit- und UI-Tests im iOS-Simulator ausführen"
```

### Task 2.3: Frontend-Workflow (Lint + Build)

Das Frontend hat keine Tests. Der Workflow prüft Lint und Build. Ein Test-Framework (z. B. Vitest) wäre eine neue Dependency → nur nach Rückfrage, nicht Teil dieses Tasks.

**Files:**
- Create: `webinterface/frontend/package-lock.json`
- Create: `.github/workflows/frontend.yml`

- [ ] **Step 1: Lockfile erzeugen und lokal prüfen**

```bash
cd webinterface/frontend
npm install
npm run lint
npm run build
```

Expected: `package-lock.json` entsteht; Lint ohne Errors; Build erzeugt `dist/`. Lint-Errors: Ausgabe festhalten und mit dem Team klären, ob sie im selben PR (eigener `fix(web)`-Commit) behoben werden.

- [ ] **Step 2: Workflow**

```yaml
name: Frontend

on:
  push:
    branches: [main]
    paths: ['webinterface/frontend/**', '.github/workflows/frontend.yml']
  pull_request:
    paths: ['webinterface/frontend/**', '.github/workflows/frontend.yml']

jobs:
  build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: webinterface/frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: npm
          cache-dependency-path: webinterface/frontend/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run build
```

- [ ] **Step 3: Commit (zwei Commits)**

```bash
git add webinterface/frontend/package-lock.json
git commit -m "chore(web): package-lock.json für reproduzierbare Builds einchecken"
git add .github/workflows/frontend.yml
git commit -m "ci(web): Lint und Build des Frontends prüfen"
```

### Task 2.4: Status-Badges, Push, Prüfen

- [ ] **Step 1: Badges** oben in `README.adoc` ergänzen:

```asciidoc
image:https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/actions/workflows/backend.yml/badge.svg[Backend CI,link=https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/actions/workflows/backend.yml]
image:https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/actions/workflows/ios.yml/badge.svg[iOS CI,link=https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/actions/workflows/ios.yml]
image:https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/actions/workflows/frontend.yml/badge.svg[Frontend CI,link=https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/actions/workflows/frontend.yml]
```

```bash
git add README.adoc && git commit -m "docs: CI-Status-Badges im README anzeigen"
```

- [ ] **Step 2: Push + PR** (nach Freigabe), dann prüfen:

```bash
gh pr checks --watch
```

Expected: `Backend`, `iOS`, `Frontend` grün. Kein Workflow darf Secrets brauchen (Review Focus 5): `grep -n "secrets\." .github/workflows/*.yml` → keine Treffer.

---

## AP3: Zugangsdaten und Experimente (`chore/firmware-secrets`)

Unabhängig. `git worktree add -b chore/firmware-secrets ../easypilot-ap3 origin/main`

### Task 3.1: `secrets_auto.h` untracken, Vorlage anlegen, Experimente löschen

**Files:**
- Untrack: `PlatformIO/Projects/EasyPilotIOS/include/secrets_auto.h`
- Create: `PlatformIO/Projects/EasyPilotIOS/secrets.ini.example`
- Delete: `PlatformIO/Projects/EasyPilotIOS/test_ssl.cpp`, `PlatformIO/Projects/EasyPilotIOS/test_wifi.cpp`

- [ ] **Step 1:** `git grep -n "test_ssl\|test_wifi"` → keine Treffer außer `openspec/changes/archive/`.

- [ ] **Step 2: Untracken + Vorlage** (erster Commit)

```bash
git rm --cached PlatformIO/Projects/EasyPilotIOS/include/secrets_auto.h
```

`PlatformIO/Projects/EasyPilotIOS/secrets.ini.example`:

```ini
; Copy to secrets.ini (gitignored) and fill in your WLAN.
; load_secrets.py turns it into include/secrets_auto.h at build time.
[secrets]
wifi_ssid = YOUR_WIFI_SSID
wifi_pass = YOUR_WIFI_PASSWORD
```

```bash
git add PlatformIO/Projects/EasyPilotIOS/secrets.ini.example
git commit -m "chore(firmware): generierte secrets_auto.h nicht mehr tracken" \
  -m "Die Datei enthielt echte WLAN-Zugangsdaten. Sie bleibt in der Git-History, das WLAN-Passwort muss deshalb geändert werden. secrets.ini.example zeigt das erwartete Format."
```

- [ ] **Step 3: Experimente löschen** (zweiter Commit)

```bash
git rm PlatformIO/Projects/EasyPilotIOS/test_ssl.cpp PlatformIO/Projects/EasyPilotIOS/test_wifi.cpp
git commit -m "chore(firmware): liegengebliebene WLAN/SSL-Experimente entfernen"
```

- [ ] **Step 4: Prüfen**

Run: `git ls-files PlatformIO/Projects/EasyPilotIOS/include` → nur `include/README`.
Run: `git check-ignore PlatformIO/Projects/EasyPilotIOS/include/secrets_auto.h` → Pfad wird ausgegeben.

- [ ] **Step 5:** Team informieren: WLAN-Passwort ändern. Push + PR nach Freigabe.

---

## AP4: Doku nachziehen (`docs/coaching-r1`)

Nach AP0. `git worktree add -b docs/coaching-r1 ../easypilot-ap4 origin/main`

### Task 4.1: README – Doku-Link, Tests, Konventionen

**Files:** Modify `README.adoc`

- [ ] **Step 1: Abschnitt „Documentation“ ersetzen durch**

```asciidoc
== Dokumentation

* Projektseite (GitHub Pages): https://2526-4ahitm-itp.github.io/2526-4ahitm-easypilot/
* Projektdokumentation: https://2526-4ahitm-itp.github.io/2526-4ahitm-easypilot/projektdoku.html (Quelle: `docs/projektdoku.adoc`)
* Präsentation: https://2526-4ahitm-itp.github.io/2526-4ahitm-easypilot/presentation/slides.html
* Specs & Sprint-Workflow: `openspec/`
```

(Die Präsentations-URL entsteht in AP5. Wird AP4 vorher gemergt, zunächst die iOS-Slides `presentation-ios/slides.html` verlinken und in AP5 umstellen.)

- [ ] **Step 2: Abschnitt „Tests“** nach „Build & Run“:

```asciidoc
== Tests

[source,bash]
----
# iOS (Simulator, siehe CLAUDE.md für den Gerätenamen)
xcodebuild test -project EasyPilotIOS/EasyPilotIOS.xcodeproj -scheme EasyPilotIOS \
  -destination 'platform=iOS Simulator,name=iPhone 17'

# Backend
cd webinterface/backend && ./mvnw test

# Frontend (Lint + Build)
cd webinterface/frontend && npm ci && npm run lint && npm run build
----

Alle drei laufen automatisch in GitHub Actions (`.github/workflows/`).
```

- [ ] **Step 3: Abschnitt „Mitarbeit“** vor „Team“:

```asciidoc
== Mitarbeit

* *Branches:* ein Branch pro Thema, `<typ>/<thema>`, z. B. `test/ios-unit-tests`. Nie direkt auf `main`.
* *Commits:* https://www.conventionalcommits.org/de/[Conventional Commits], Betreff auf Deutsch im Imperativ:
  `<typ>(<scope>): <was>` – Typen `feat`, `fix`, `test`, `docs`, `ci`, `chore`, `refactor`;
  Scopes `ios`, `firmware`, `backend`, `web`, `k8s`, `docs`, `pages`.
  Beispiel: `fix(ios): Reconnect nach Verbindungsabbruch`.
* *Pull Requests:* ein PR pro Thema nach `main`, mit „Änderung“, „Warum“, „Wie getestet“.
```

- [ ] **Step 4: Firmware-Abschnitt:** Modi um `RC` ergänzen und als ersten Build-Schritt `cp secrets.ini.example secrets.ini` (nach AP3).

- [ ] **Step 5: Commit**

```bash
git add README.adoc
git commit -m "docs: Doku-Link, Tests und Commit-Konventionen im README"
```

### Task 4.2: `.mailmap` – erledigt

Umgesetzt im Branch `chore/mailmap` (Commit `chore: Git-Identitäten per .mailmap zusammenführen`). `git shortlog -sne` zeigt danach genau zwei Personen: `SimonnEder` und `dwindischbauer`. Die globale Git-Config ist auf `SimonnEder <114646364+SimonnEder@users.noreply.github.com>` gesetzt. Auf anderen Rechnern (Schul-PCs, Mac mini) muss Simon dieselbe Config setzen:

```bash
git config --global user.name SimonnEder
git config --global user.email 114646364+SimonnEder@users.noreply.github.com
```

Hinweis: GitHub selbst wertet `.mailmap` nicht aus. Commits mit Mail-Adressen, die nicht im GitHub-Account hinterlegt sind (`…@Simons-Mac-mini.local`, `…@fritz.box`, `it220234@WS8A…`), zählen dort weiterhin nicht zu `SimonnEder`. Die Schul-Mail-Adressen kann Simon unter GitHub → Settings → Emails hinzufügen; dann werden diese Commits nachträglich zugeordnet.

### Task 4.3: `CLAUDE.md` auf aktuellen Code

**Files:** Modify `CLAUDE.md`

- [ ] **Step 1: Korrigieren** (jede Aussage gegen den Code prüfen):

1. „Project Overview“: Phase 2 (Web-Simulator mit Physik-Engine, `webinterface/frontend`) als aktuellen Fokus; iOS-App und Firmware als bestehende Subsysteme.
2. „Flight modes“: `MODE_RC` – Stick-Werte aus dem LIVE-Modus des Simulator-Tabs; 500 ms ohne `RC`-Paket stoppt die Motoren (`RC_TIMEOUT_MS`).
3. Befehlstabelle: `START_RC` (`kPRoll`, `kPPitch`), `RC` (`thr`, `pit`, `rol`, `yaw`), `SIMULATE` (plain text), JSON ohne `cmd` = Manual-Update.
4. Telemetrie-Beispiel: Feld `"fc"` ergänzen; `"mode"` kann `"RC"` sein.
5. „State ownership“: drei Tabs (Dashboard, Simulator, Algorithms); `ContentView` besitzt auch genau einen `MotionManager`.
6. Dateitabelle: `DroneCommand.swift`, `FlightMode.swift`, `SoundMode.swift`, `SimulatorView.swift`, `DroneSimulator.swift`, `SimulatorScene.swift`, `VirtualJoystick.swift`.
7. Neuer Abschnitt „Tests“ (Befehle wie README) und „Branches & Commits“ (Verweis auf README „Mitarbeit“).
8. „OpenSpec“: Verweis auf `openspec/changes/` statt `sprint-03`.

- [ ] **Step 2: Prüfen**

Run: `grep -n "Sprint 3\|both tabs" CLAUDE.md` → keine Treffer.
Run: `grep -c "START_RC\|SoundMode\|xcodebuild test" CLAUDE.md` → ≥ 3.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md an aktuellen Code und Phase 2 anpassen"
```

### Task 4.4: Projektdoku – Aufgabenstellung, Änderung, Team, Termine, Tests, Probleme

**Files:** Modify `docs/projektdoku.adoc`; Regenerate `docs/projektdoku.html`

- [ ] **Step 1: Neuer Abschnitt nach „Projektbeschreibung“**

```asciidoc
== Aufgabenstellung

=== Aktuell: Phase 2 – Drohnensimulation mit Physik-Engine (seit 14.09.2026)

Ein Web-Simulator im Browser, aufbauend auf dem bestehenden 3D-Viewer
(`webinterface/frontend`, React + three.js), simuliert die Drohne mit einer
Physik-Engine. Ziel ist, Flugverhalten und Steuerung ohne die echte Drohne
entwickeln und vorführen zu können.

=== Änderung der Aufgabenstellung

[cols="1,3", options="header"]
|===
| Datum | Änderung und Grund

| 14.09.2026
| Wechsel von Phase 1 „Drohnensteuerung“ zu Phase 2 „Drohnensimulation mit
  Physik-Engine“. *Grund:* Die DJI O4 Air Unit der Drohne ist defekt. Ohne sie
  gibt es kein Videobild und keine Steuerung über Brille und Fernbedienung,
  Tests mit der echten Drohne sind nicht mehr möglich.
|===

=== Phase 1: Drohnensteuerung (abgeschlossen)

<bisherige Projektbeschreibung hierher verschieben bzw. darauf verweisen>
```

Den letzten Platzhalter beim Umsetzen durch einen echten Verweis auf die bestehenden Abschnitte „Projektbeschreibung“ und „Features“ ersetzen (`<<_projektbeschreibung>>`), nicht stehen lassen. Wortlaut von Phase 2 vom Team bestätigen lassen (Vorbedingung 5).

- [ ] **Step 2: „Team“-Tabelle** – „Team EasyPilot“ durch die Namen ersetzen: Simon Eder, David Windischbauer. Rollen nur eintragen, wenn das Team sie nennt; sonst Spalte „Rolle“ weglassen.

- [ ] **Step 3: Abschnitt „Termine und Meilensteine“** (belegte Daten aus dem Repo, Lücken markiert):

```asciidoc
== Termine und Meilensteine

[cols="1,3", options="header"]
|===
| Datum | Ereignis

| 07.10.2025 | Projektstart (erster Commit)
| 25.11.2025 | Sprintplanung (Protokoll in `minutes-of-meetings/`)
| 23.12.2025 | Sprintplanung / Abschluss Sprint 1
| 24.03.2026 | Sprint 2 und 3 in OpenSpec: MSP-Telemetrie, iPhone-Sensoren, hybride Verbindung
| 07.05.2026 | Sprint 4: Phone-Side-Simulator und Joysticks
| 23.06.2026 | Sprint 5: Landscape-UI, touch-aware Stabilisierung
| 14.09.2026 | Start Phase 2: Drohnensimulation mit Physik-Engine
| 08.10.2026 | Coaching Runde 1
| _vom Team zu ergänzen_ | weitere Termine Phase 2
|===

=== Meilensteine

* *M1* Motoren einzeln ansteuern (Sound-Demo) – Sprint 1 ✓
* *M2* Echtzeit-Telemetrie über MSP – Sprint 2 ✓
* *M3* iPhone-Sensoren und hybride Verbindung – Sprint 3 ✓
* *M4* Simulator in der iOS-App – Sprint 4 ✓
* *M5* Landscape-UI und LIVE-Modus – Sprint 5 ✓ (Abschluss Phase 1)
* *M6* Web-Simulator mit Physik-Engine – Phase 2, offen
* _weitere Meilensteine Phase 2: vom Team zu ergänzen_
```

Jedes Datum vor dem Commit noch einmal gegen das Repo prüfen:

```bash
git log --reverse --format='%ad %s' --date=short | head -1
ls docs/minutes-of-meetings/
git log --reverse --format='%ad' --date=short -- openspec/changes/archive/2026-05-28-sprint-04 | head -1
```

- [ ] **Step 4: Abschnitte „Tests“ und „Bekannte Probleme“** vor „Minutes of Meeting“:

```asciidoc
== Tests

* *iOS:* Unit-Tests (Swift Testing) für Befehls-Format, Telemetrie-Decoding,
  Sound-Mode-Rechnung und Profil-Speicherung; UI-Smoke-Test der drei Tabs.
* *Backend:* Quarkus-Tests für `GET /api/status`.
* *Frontend:* Lint und Build.
* Alle laufen bei jedem Push und Pull Request in GitHub Actions.

== Bekannte Probleme

* Die DJI O4 Air Unit ist defekt (siehe <<_änderung_der_aufgabenstellung>>).
* Firmware-Logik (MSP-Parser, Befehle) hat noch keine Unit-Tests.
```

- [ ] **Step 5: „Aktueller Implementierungsstand“** um Sprint 5 und Phase 2 ergänzen; Quellen `openspec/changes/sprint-05`, `openspec/changes/2026-10-12-coaching-r1`.

- [ ] **Step 6: Quick Start prüfen** – `cp secrets.ini.example secrets.ini` stimmt nach AP3.

- [ ] **Step 7: HTML erzeugen**

`asciidoctor` ist lokal nicht installiert → neue lokale Tool-Abhängigkeit, vorher Team fragen. Dann:

```bash
brew install asciidoctor          # oder: gem install asciidoctor
asciidoctor docs/projektdoku.adoc -o docs/projektdoku.html
grep -c "Änderung der Aufgabenstellung\|Bekannte Probleme\|Termine und Meilensteine" docs/projektdoku.html
```

Expected: ≥ 3.

- [ ] **Step 8: Commit** (Quelle und erzeugtes HTML zusammen, weil Pages das HTML ausliefert)

```bash
git add docs/projektdoku.adoc docs/projektdoku.html
git commit -m "docs(pages): Aufgabenstellung Phase 2, Team, Termine und Tests in der Projektdoku" \
  -m "Antwort auf Coaching Runde 1: Änderung der Aufgabenstellung mit Datum und Grund dokumentiert."
```

### Task 4.5: OpenSpec nachziehen

**Files:**
- Modify: `openspec/specs/simulator-controller/spec.md`
- Modify: `openspec/specs/core/spec.md`

- [ ] **Step 1: Simulator-Spec** – Szenario „Sim / Live mode toggle“ ersetzen:

```markdown
#### Scenario: Sim / Live mode toggle
- **Given** the WebSocket is connected
- **When** the user taps the "LIVE" segment
- **Then** the simulator is disarmed (if armed) and LIVE mode is active
- **Given** the WebSocket is not connected
- **When** the user taps "LIVE"
- **Then** a "not connected" hint is shown and the mode stays SIM
- **When** the user switches from LIVE back to SIM while armed
- **Then** `{"cmd":"DISARM"}` is sent and the simulator disarms

#### Scenario: Arm / Disarm in LIVE mode
- **Given** LIVE mode is active and throttle is at zero
- **When** the user arms
- **Then** `{"cmd":"ARM"}` and `{"cmd":"START_RC","kPRoll":…,"kPPitch":…}` are sent
- **And** an `RC` packet with `thr, pit, rol, yaw` is sent every 100 ms while armed
- **When** the user disarms
- **Then** `{"cmd":"DISARM"}` is sent and RC packets stop
```

Bestehendes „Arm / Disarm“ in „Arm / Disarm in SIM mode“ umbenennen. Jede Zeile gegen `SimulatorView.swift` (`enterLiveMode`, `enterSimMode`, `startRCTimer`, `sendRCPacket`, Arm-Buttons) prüfen.

- [ ] **Step 2: Core-Spec** – im Subsystem-Index „Web-Simulator (`webinterface/frontend`), Phase 2“ und als Deployment-Ziel „LeoCloud (Kubernetes) für Backend und Web-Simulator“ ergänzen.

- [ ] **Step 3: Commit**

```bash
git add openspec/specs
git commit -m "docs(openspec): LIVE-Modus und Phase 2 in den Specs nachziehen"
```

- [ ] **Step 4:** Push + PR nach Freigabe.

---

## AP5: Projektpräsentation (`docs/project-presentation`)

Nach AP4 (gleiche Inhalte). `git worktree add -b docs/project-presentation ../easypilot-ap5 origin/main`

### Task 5.0: Air-Unit-Slide der iOS-Präsentation übernehmen

Der Branch `docs/slides-air-unit` (lokal, Worktree im Scratchpad) enthält den fertigen Slide „Problem: Air Unit kaputt“ für `docs/presentation-ios/slides.html`.

- [ ] Commit dort: `docs(pages): Air-Unit-Problem als Slide in der iOS-Präsentation`; Push + eigener PR nach Freigabe.

### Task 5.1: Gerüst der Projektpräsentation

**Files:**
- Create: `docs/presentation/slides.html`
- Modify: `docs/index.html` (Button + Inhaltsverzeichnis)

**Interfaces:**
- Produces: URL `…/presentation/slides.html` mit Ankern `#/team`, `#/aufgabenstellung`, `#/aenderung`, `#/stand`, `#/termine`, `#/meilensteine`, `#/c4-kontext`, `#/c4-container`, `#/c4-komponenten`, `#/deployment`, `#/tests`.

- [ ] **Step 1: Datei anlegen**

Kopf, Stil und Skripte 1:1 aus `docs/presentation-ios/slides.html` übernehmen (Inter, `--navy`/`--blue`, dunkler Titel- und Schluss-Slide, Fußzeile). Fußzeile: `<a href="../">EasyPilot</a> · Projektpräsentation`.

- [ ] **Step 2: Slides mit Inhalt** (Texte aus AP4 Task 4.4, nichts Neues erfinden):

| Anker | Titel | Inhalt |
|---|---|---|
| `titel` | EasyPilot | „Phase 2: Drohnensimulation mit Physik-Engine“, 4AHITM · HTL Leonding · 2025/26 |
| `team` | Team | Simon Eder, David Windischbauer (Rollen nur, wenn vom Team genannt) |
| `aufgabenstellung` | Aufgabenstellung | Phase 2 laut Projektdoku, 3–4 Stichpunkte |
| `aenderung` | Änderung der Aufgabenstellung | 14.09.2026, Phase 1 → Phase 2, Grund: Air Unit defekt |
| `stand` | Aktueller Stand | Phase 1 fertig (iOS-App, Firmware, Simulator in der App); Phase 2: Web-3D-Viewer vorhanden, Physik offen; Tests + CI |
| `termine` | Projekttermine | Tabelle aus Projektdoku |
| `meilensteine` | Meilensteine | M1–M6 aus Projektdoku |
| `c4-kontext` | C4: Systemkontext | Task 5.2 |
| `c4-container` | C4: Container | Task 5.3 |
| `c4-komponenten` | C4: Komponenten Web-Simulator (Bonus) | Task 5.4 |
| `deployment` | Deployment | aus AP6 (bis dahin: „LeoCloud, in Arbeit“) |
| `tests` | Tests & CI | Liste aus Projektdoku + Hinweis auf GitHub Actions |
| `ende` | Danke! | „Fragen?“ |

- [ ] **Step 3: Mermaid einbinden** (vor `Reveal.initialize`, damit Diagramme vor dem Layout gerendert sind). Version vorher prüfen: `curl -sI https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs | head -1` → `200`.

```html
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs';
  mermaid.initialize({ startOnLoad: false, theme: 'neutral' });
  await mermaid.run({ querySelector: '.mermaid' });
  Reveal.initialize({ hash: true, slideNumber: true, plugins: [RevealHighlight, RevealNotes] });
</script>
```

Den bisherigen `Reveal.initialize(...)`-Block entfernen; reveal.js-Skripte bleiben als normale `<script src>` davor.

### Task 5.2: C4-Systemkontext

- [ ] Slide `c4-kontext`:

```html
<section id="c4-kontext">
  <h2>C4: Systemkontext</h2>
  <pre class="mermaid">
C4Context
  Person(user, "Nutzer:in", "übt und testet das Fliegen im Browser")
  Person(pilot, "Pilot:in", "nutzt die iOS-App mit der echten Drohne")
  System(easypilot, "EasyPilot", "Web-Simulator mit Physik-Engine, iOS-App, Backend")
  System_Ext(drone, "FPV-Drohne", "ESP32-C3 + Betaflight FC; Air Unit defekt")
  System_Ext(github, "GitHub", "Code, CI, Pages")
  System_Ext(leocloud, "LeoCloud", "Kubernetes der HTL Leonding")
  Rel(user, easypilot, "fliegt simuliert", "HTTPS")
  Rel(pilot, easypilot, "steuert und beobachtet")
  Rel(easypilot, drone, "Befehle und Telemetrie", "WebSocket / UDP")
  Rel(easypilot, leocloud, "läuft auf")
  Rel(github, leocloud, "liefert Images", "ghcr.io")
  </pre>
</section>
```

### Task 5.3: C4-Container

- [ ] Slide `c4-container`:

```html
<section id="c4-container">
  <h2>C4: Container</h2>
  <pre class="mermaid">
C4Container
  Person(user, "Nutzer:in")
  Person(pilot, "Pilot:in")
  System_Boundary(ep, "EasyPilot") {
    Container(web, "Web-Simulator", "React 19, three.js, Physik-Engine", "3D-Simulation im Browser (Phase 2)")
    Container(api, "Backend", "Quarkus 3.28, Java 21", "REST /api/status")
    Container(ios, "iOS-App", "SwiftUI, SceneKit", "Dashboard, Simulator, LIVE-Steuerung")
    Container(relay, "Relay", "Python", "WebSocket → UDP im lokalen Netz")
    Container(fw, "Firmware", "ESP32-C3, Arduino", "WebSocket :81, UDP-Beacon :4242, MSP")
  }
  System_Ext(fc, "Betaflight FC", "IMU, Motoren")
  Rel(user, web, "nutzt", "HTTPS")
  Rel(web, api, "Status", "HTTPS/JSON")
  Rel(pilot, ios, "bedient")
  Rel(ios, fw, "Befehle / Telemetrie", "WebSocket :81")
  Rel(fw, ios, "Beacon", "UDP :4242")
  Rel(relay, ios, "Beacon über Tunnel", "UDP :4242")
  Rel(fw, fc, "MSP", "UART 115200")
  </pre>
</section>
```

Die Physik-Engine bleibt neutral benannt, bis das Team eine Bibliothek gewählt hat; dann Label in beiden Diagrammen und in der Projektdoku nachziehen (eigener Commit `docs: Physik-Engine im C4-Diagramm benennen`).

Prüfen, ob `Rel(web, api, …)` stimmt: `grep -rn "fetch(\|axios\|/api/" webinterface/frontend/src`. Gibt es keinen Aufruf, die Beziehung mit „(geplant)“ beschriften.

### Task 5.4 (Bonus): C4-Komponenten Web-Simulator

- [ ] Komponenten aus dem Code ableiten: `ls webinterface/frontend/src webinterface/frontend/src/pages webinterface/frontend/src/components` (heute `App.jsx`, `pages/HomePage.jsx`, `pages/ModelPage.jsx`, `components/Model.jsx`). Slide `c4-komponenten`:

```html
<section id="c4-komponenten">
  <h2>C4: Komponenten Web-Simulator</h2>
  <pre class="mermaid">
C4Component
  Container_Boundary(web, "Web-Simulator") {
    Component(app, "App", "React Router", "Routing zwischen den Seiten")
    Component(home, "HomePage", "React", "Startseite")
    Component(modelPage, "ModelPage", "React", "3D-Ansicht, Telemetrie per WebSocket")
    Component(model, "Model", "react-three-fiber", "Drohnenmodell (three.js)")
    Component(physics, "Physik-Schleife", "Physik-Engine", "Phase 2, geplant")
  }
  Rel(app, home, "rendert")
  Rel(app, modelPage, "rendert")
  Rel(modelPage, model, "rendert")
  Rel(physics, model, "setzt Lage und Position (geplant)")
  </pre>
</section>
```

### Task 5.5: Startseite anpassen, rendern, committen

- [ ] **Step 1:** In `docs/index.html` den Hauptbutton auf `presentation/slides.html` („Zur Projektpräsentation“) setzen, zweiter Button „iOS-App-Präsentation“ (`presentation-ios/slides.html`), dritter „Projektdokumentation“. Inhaltsverzeichnis auf die Anker aus Task 5.1 umstellen.

- [ ] **Step 2: Lokal prüfen**

```bash
cd docs && python3 -m http.server 8770
```

Im Browser jede Folie ansehen, besonders die drei C4-Folien: Diagramm sichtbar, nichts abgeschnitten. Screenshots in die PR-Beschreibung.

- [ ] **Step 3: Commits** (je Task ein Commit)

```bash
git commit -m "docs(pages): Projektpräsentation mit Aufgabenstellung, Team, Terminen und Meilensteinen"
git commit -m "docs(pages): C4-Kontext- und -Containerdiagramm für Phase 2"
git commit -m "docs(pages): C4-Komponentendiagramm des Web-Simulators"
git commit -m "docs(pages): Startseite verlinkt die Projektpräsentation"
```

- [ ] **Step 4:** README-Link aus Task 4.1 prüfen bzw. auf `presentation/slides.html` umstellen. Push + PR nach Freigabe.

---

## AP6: Deployment LeoCloud (`feat/k8s-leocloud`)

Braucht Vorbedingung 3. `git worktree add -b feat/k8s-leocloud ../easypilot-ap6 origin/main`

Zielbild:
- **LeoCloud (Kubernetes):** Backend (Quarkus) und Web-Simulator (statischer Vite-Build hinter nginx), erreichbar unter einem Host per Ingress: `/` → Web-Simulator, `/api` → Backend.
- **Nicht in der Cloud:** Python-Relay. Es sendet UDP-Broadcasts ins lokale Netz, damit die iOS-App den ESP32 findet; das geht nur im selben LAN. Es läuft auf einem Laptop im Drohnen-WLAN (wie heute mit `start_system.sh`).
- **Images:** GitHub Container Registry `ghcr.io/2526-4ahitm-itp/easypilot-backend` und `…/easypilot-web`, gebaut von GitHub Actions bei Push auf `main`.

### Task 6.1: Container-Image für den Web-Simulator

**Files:**
- Create: `webinterface/frontend/Dockerfile`
- Create: `webinterface/frontend/.dockerignore`

- [ ] **Step 1: Dockerfile**

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

`.dockerignore`:

```
node_modules
dist
```

- [ ] **Step 2: Lokal bauen und starten**

```bash
docker build -t easypilot-web webinterface/frontend
docker run --rm -p 8081:80 easypilot-web
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8081/
```

Expected: `200`.

- [ ] **Step 3: Commit** – `git commit -m "feat(web): Container-Image für den Web-Simulator"`

### Task 6.2: Kubernetes-Manifeste

**Files:**
- Create: `k8s/backend.yaml`, `k8s/web.yaml`, `k8s/ingress.yaml`

- [ ] **Step 1: LeoCloud-Vorgaben einholen** (Vorbedingung 3): Namespace, Host, Ingress-Klasse/Annotations, ob `ghcr.io`-Images öffentlich sein müssen oder ein `imagePullSecret` nötig ist. In `k8s/README.md` festhalten (Teil von Task 6.4).

- [ ] **Step 2: `k8s/backend.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: easypilot-backend
spec:
  replicas: 1
  selector:
    matchLabels: { app: easypilot-backend }
  template:
    metadata:
      labels: { app: easypilot-backend }
    spec:
      containers:
        - name: backend
          image: ghcr.io/2526-4ahitm-itp/easypilot-backend:latest
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet: { path: /api/status, port: 8080 }
---
apiVersion: v1
kind: Service
metadata:
  name: easypilot-backend
spec:
  selector: { app: easypilot-backend }
  ports:
    - port: 8080
      targetPort: 8080
```

- [ ] **Step 3: `k8s/web.yaml`** – gleich aufgebaut, Name `easypilot-web`, Image `ghcr.io/2526-4ahitm-itp/easypilot-web:latest`, Port `80`, Readiness `GET /`.

- [ ] **Step 4: `k8s/ingress.yaml`** – Host kommt beim Deploy aus der Umgebungsvariable `LEOCLOUD_HOST` (per `envsubst`), damit kein Host hart im Repo steht:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: easypilot
spec:
  rules:
    - host: ${LEOCLOUD_HOST}
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service: { name: easypilot-backend, port: { number: 8080 } }
          - path: /
            pathType: Prefix
            backend:
              service: { name: easypilot-web, port: { number: 80 } }
```

Ingress-Klasse und Annotations aus Step 1 ergänzen.

- [ ] **Step 5: Syntax prüfen**

```bash
for f in k8s/backend.yaml k8s/web.yaml; do kubectl apply --dry-run=client -f $f; done
LEOCLOUD_HOST=example.invalid envsubst < k8s/ingress.yaml | kubectl apply --dry-run=client -f -
```

Expected: je `… created (dry run)`.

- [ ] **Step 6: Commit** – `git commit -m "feat(k8s): Deployments, Services und Ingress für Backend und Web-Simulator"`

`k8s/postgres.yaml` und `k8s/volume-claim.yaml` bleiben unverändert; das Backend nutzt keine Datenbank. In `k8s/README.md` als „Demo, nicht deployt“ vermerken.

### Task 6.3: Images in CI bauen und pushen

**Files:** Create `.github/workflows/images.yml`

- [ ] **Step 1: Workflow** (läuft nur auf `main`, braucht nur `GITHUB_TOKEN`)

```yaml
name: Images

on:
  push:
    branches: [main]
    paths: ['webinterface/**', '.github/workflows/images.yml']

permissions:
  contents: read
  packages: write

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: '21', cache: maven }
      - run: ./mvnw -B package -DskipTests
        working-directory: webinterface/backend
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - run: |
          docker build -f src/main/docker/Dockerfile.jvm -t ghcr.io/2526-4ahitm-itp/easypilot-backend:latest -t ghcr.io/2526-4ahitm-itp/easypilot-backend:${GITHUB_SHA::7} .
          docker push --all-tags ghcr.io/2526-4ahitm-itp/easypilot-backend
        working-directory: webinterface/backend

  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - run: |
          docker build -t ghcr.io/2526-4ahitm-itp/easypilot-web:latest -t ghcr.io/2526-4ahitm-itp/easypilot-web:${GITHUB_SHA::7} webinterface/frontend
          docker push --all-tags ghcr.io/2526-4ahitm-itp/easypilot-web
```

`docker/login-action` ist eine Action von Docker selbst; vor Einsatz mit dem Team bestätigen (Global Constraints: nur `actions/*` vorab freigegeben). Alternative ohne Fremd-Action: `echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin`.

- [ ] **Step 2: Commit** – `git commit -m "ci(k8s): Backend- und Web-Image bei Push auf main nach ghcr.io pushen"`

### Task 6.4: Deploy-Ablauf dokumentieren und einmal ausführen

**Files:**
- Create: `k8s/README.md`
- Modify: `docs/projektdoku.adoc` (+ HTML neu erzeugen), `README.adoc`

- [ ] **Step 1: `k8s/README.md`** mit: Zielsystem (LeoCloud, Namespace aus Vorbedingung 3), was dort läuft und was nicht (Relay im LAN, Begründung UDP-Broadcast), Images, Konfiguration (`LEOCLOUD_HOST`), Ablauf:

```bash
# 1. Build & Auslieferung: automatisch durch .github/workflows/images.yml bei Push auf main
# 2. Deploy (lokal mit LeoCloud-kubeconfig):
export LEOCLOUD_HOST=<Host aus der LeoCloud>
kubectl apply -f k8s/backend.yaml -f k8s/web.yaml
envsubst < k8s/ingress.yaml | kubectl apply -f -
# 3. Neue Version ausrollen:
kubectl rollout restart deployment/easypilot-backend deployment/easypilot-web
# 4. Prüfen:
kubectl get pods
curl -s https://$LEOCLOUD_HOST/api/status
```

- [ ] **Step 2: Einmal wirklich deployen** (Team, mit LeoCloud-Zugang) und prüfen:

```bash
curl -s https://$LEOCLOUD_HOST/api/status
```

Expected: `{"name":"easypilot-backend","status":"UP","version":"1.0-SNAPSHOT"}`.

- [ ] **Step 3: Projektdoku** – Abschnitt `== Deployment` mit Zielsystem, **Produktions-URLs** (`https://<host>/` Web-Simulator, `https://<host>/api/status` Backend, Pages-URL für Doku/Präsentation) und dem Ablauf aus Step 1 (Kurzfassung + Verweis auf `k8s/README.md`). URLs erst eintragen, wenn Step 2 erfolgreich war. HTML neu erzeugen wie Task 4.4 Step 7.

- [ ] **Step 4: README** – unter „Dokumentation“ die Produktions-URL ergänzen; Präsentation: Slide `deployment` mit denselben Angaben (Task 5.1).

- [ ] **Step 5: Commits**

```bash
git add k8s/README.md && git commit -m "docs(k8s): Zielsystem, Konfiguration und Deploy-Ablauf beschreiben"
git add docs/projektdoku.adoc docs/projektdoku.html README.adoc docs/presentation/slides.html
git commit -m "docs: Produktions-URLs und Deployment in Projektdoku, README und Präsentation"
```

- [ ] **Step 6:** Push + PR nach Freigabe.

**Bekannte Grenze:** `ModelPage.jsx` verbindet fest auf `ws://localhost:8765`. In der Cloud findet der Web-Simulator diesen Telemetrie-Stream nicht. Das betrifft die Implementierung des Simulators (Phase 2), nicht dieses AP; im Projektdoku-Abschnitt „Bekannte Probleme“ vermerken.

---

## AP7 (optional, nach Freigabe): RC-Modus (`fix/ios-rc-mode`)

Nach AP1. `git worktree add -b fix/ios-rc-mode ../easypilot-ap7 origin/main`

### Task 7.1: RC-Modus erkennen, STOP-Button zeigen

**Files:** `EasyPilotIOS/EasyPilotIOS/FlightMode.swift`, `EasyPilotIOS/EasyPilotIOS/ControlView.swift`, `EasyPilotIOS/EasyPilotIOSTests/FlightModeTests.swift`

**Interfaces:** Produces `FlightMode.rc` (`"RC"`), `FlightMode.selectable: [FlightMode]`.

- [ ] **Step 1: Failing Test** – in `FlightModeTests` `rcModeIsCurrentlyReportedAsIdle` ersetzen:

```swift
    @Test func rcModeIsRecognised() {
        #expect(FlightMode(rawOrIdle: "RC") == .rc)
    }

    @Test func rcIsNotSelectableInAlgorithmsTab() {
        #expect(FlightMode.selectable == [.idle, .balance, .manual, .sound])
    }
```

Expected beim Lauf: `type 'FlightMode' has no member 'rc'`.

- [ ] **Step 2: Implementierung** – `FlightMode.swift`:

```swift
enum FlightMode: String, CaseIterable, Codable {
    case idle    = "IDLE"
    case balance = "BALANCE"
    case manual  = "MANUAL"
    case sound   = "SOUND"
    /// Set by the firmware while the Simulator tab flies the drone in LIVE mode.
    /// Reported in telemetry only; not started from the Algorithms tab.
    case rc      = "RC"

    /// Modes the Algorithms tab lets the user start.
    static let selectable: [FlightMode] = [.idle, .balance, .manual, .sound]

    init(rawOrIdle raw: String?) {
        self = raw.flatMap(FlightMode.init(rawValue:)) ?? .idle
    }
}
```

`ControlView.swift`:
- `ForEach(FlightMode.allCases, …)` → `ForEach(FlightMode.selectable, …)`
- `.onChange(of: droneMode) { mode in selectedMode = mode }` → `.onChange(of: droneMode) { mode in if FlightMode.selectable.contains(mode) { selectedMode = mode } }`
- `switch selectedMode` im Konfig-Bereich: `case .rc: EmptyView()`
- `switch selectedMode` beim Senden: `case .sound, .idle:` → `case .sound, .idle, .rc:`
- `modeColor`: `case .rc: return EasyPilotTheme.success`
- `modeIcon`: `case .rc: return "gamecontroller.fill"`

- [ ] **Step 3: Tests** → `** TEST SUCCEEDED **`.

- [ ] **Step 4: Commit**

```bash
git commit -am "fix(ios): RC-Modus der Firmware erkennen und STOP-Button zeigen" \
  -m "Im RC-Modus zeigte die App IDLE und blendete STOP aus, obwohl die Motoren laufen können."
```

### Task 7.2: RC-Befehle ins `DroneCommand`-Enum

**Files:** `EasyPilotIOS/EasyPilotIOS/DroneCommand.swift`, `EasyPilotIOS/EasyPilotIOS/SimulatorView.swift`, `EasyPilotIOS/EasyPilotIOSTests/DroneCommandTests.swift`

**Interfaces:** Produces `DroneCommand.startRC(kPRoll: Double, kPPitch: Double)`, `DroneCommand.rc(thr: Int, pit: Double, rol: Double, yaw: Double)`.

- [ ] **Step 1: Failing Tests** (Format = heute in `SimulatorView`, eine Nachkommastelle)

```swift
    @Test func startRC() {
        #expect(DroneCommand.startRC(kPRoll: 10, kPPitch: 12.5).payload
                == #"{"cmd":"START_RC","kPRoll":10.0,"kPPitch":12.5}"#)
    }

    @Test func rcPacket() {
        #expect(DroneCommand.rc(thr: 1300, pit: -5.3, rol: 3, yaw: 0).payload
                == #"{"cmd":"RC","thr":1300,"pit":-5.3,"rol":3.0,"yaw":0.0}"#)
    }
```

- [ ] **Step 2: Implementierung** – Cases ergänzen:

```swift
    case startRC(kPRoll: Double, kPPitch: Double)
    /// Stick packet, sent at 10 Hz in LIVE mode.
    case rc(thr: Int, pit: Double, rol: Double, yaw: Double)
```

im `switch`:

```swift
        case let .startRC(kpr, kpp):
            return #"{"cmd":"START_RC","kPRoll":\#(f1(kpr)),"kPPitch":\#(f1(kpp))}"#

        case let .rc(thr, pit, rol, yaw):
            return #"{"cmd":"RC","thr":\#(thr),"pit":\#(f1(pit)),"rol":\#(f1(rol)),"yaw":\#(f1(yaw))}"#
```

und:

```swift
    /// One-decimal formatting, used by the RC packets.
    private func f1(_ v: Double) -> String { String(format: "%.1f", v) }
```

In `SimulatorView.swift` alle `wsManager.sendCommand("{\"cmd\":…}")` ersetzen durch `wsManager.send(.arm)`, `.disarm`, `.startRC(kPRoll: kPRoll, kPPitch: kPPitch)` und in `sendRCPacket()` `wsManager.send(.rc(thr: thr, pit: pit, rol: rol, yaw: yaw))`; `kPRStr`, `kPPStr`, `cmd` entfallen.

- [ ] **Step 3: Prüfen** – `grep -n 'sendCommand("' EasyPilotIOS/EasyPilotIOS/SimulatorView.swift` → keine Treffer; Tests grün.

- [ ] **Step 4: Commit** – `git commit -am "refactor(ios): RC-Befehle über DroneCommand senden"`; Push + PR nach Freigabe.

---

## Abschluss

- [ ] Alle PRs gemergt, GitHub Actions auf `main` grün (`gh run list --branch main --limit 5`).
- [ ] Pages: Startseite, Projektdoku, Projektpräsentation und iOS-Präsentation erreichbar (je `curl -s -o /dev/null -w '%{http_code}'` → `200`).
- [ ] `git grep -n "docs/index.adoc\|Available in Sprint 5"` → keine Treffer; `git ls-files | grep secrets_auto.h` → keine Treffer.
- [ ] Delta-Specs aus AP4 sind in `openspec/specs/`; diesen Ordner nach `openspec/changes/archive/2026-10-12-coaching-r1/` verschieben (`docs(openspec): Coaching Runde 1 archivieren`).
- [ ] Coaching-To-do-Liste mit den PR-Links abhaken (`tasks.md`).
