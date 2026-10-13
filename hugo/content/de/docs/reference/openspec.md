---
title: Spec-Übersicht
weight: 1
---

Die Anforderungen stehen in [`openspec/specs/`](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/tree/main/openspec/specs),
eine Capability pro Ordner. Jede Requirement trägt einen Status, gegen den Code geprüft am
13.10.2026, Deployment am 14.10.2026. Fachliche Grundlage ist das Pflichtenheft
[`spec/fsd.md`](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/blob/main/spec/fsd.md).

| Capability | FSD | <span class="status-implemented">umgesetzt</span> | <span class="status-partial">teilweise</span> | <span class="status-not-implemented">offen</span> |
|---|---|---|---|---|
| `hardware-platform` | §3.1, §4 | 4 | 0 | 1 |
| `drone-discovery` | §5.1 | 2 | 1 | 0 |
| `command-protocol` | §5.2 | 3 | 1 | 0 |
| `telemetry-stream` | §5.3 | 4 | 2 | 0 |
| `fc-msp-bridge` | §5.4 | 3 | 0 | 1 |
| `flight-modes` | §6 | 5 | 0 | 0 |
| `safety-failsafe` | §7 | 6 | 0 | 0 |
| `ios-dashboard` | §8.1 | 5 | 0 | 0 |
| `ios-algorithms` | §8.2 | 3 | 1 | 0 |
| `ios-flight-simulator` | §8.3 | 5 | 0 | 0 |
| `ios-live-control` | §8.4 | 2 | 0 | 1 |
| `standalone-web-firmware` | §9 | 5 | 0 | 0 |
| `telemetry-relay` | §5.5 | 3 | 0 | 2 |
| `web-viewer` | §10.1 | 2 | 1 | 0 |
| `web-simulator` | §10.2 | 0 | 1 | 4 |
| `liftoff-hover` | §11 | 6 | 0 | 0 |
| `backend-api` | §12.1 | 2 | 0 | 1 |
| `cloud-deployment` | §12.2 | 4 | 0 | 0 |
| `ci-testing` | §13 | 3 | 0 | 2 |
| `project-documentation` | §14 | 3 | 2 | 0 |
| `openspec-project-config` | – | 4 | 0 | 0 |
| **Summe (95 Requirements)** | | **74** | **9** | **12** |

## Die wichtigsten Lücken

- **Web-Simulator** (Phase 2): Physik, Steuerung, Flugmodi und HUD fehlen →
  [Change `2026-10-13-phase2-web-simulator`](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/tree/main/openspec/changes/2026-10-13-phase2-web-simulator)
- **RC-Modus in der App** wird als IDLE angezeigt →
  [Change `2026-10-13-fix-ios-rc-mode`](https://github.com/2526-4ahitm-itp/2526-4ahitm-easypilot/tree/main/openspec/changes/2026-10-13-fix-ios-rc-mode)
- **Tests** für Firmware und Python-Relay fehlen
- **Hardware:** Air Unit defekt, LIVE-Modus nie im Flug getestet

Selbst nachzählen:

```bash
grep -rn "status: \(partial\|not-implemented\)" openspec/specs
```
