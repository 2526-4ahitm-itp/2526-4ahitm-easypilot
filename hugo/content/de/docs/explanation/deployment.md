---
title: Deployment
weight: 9
---

{{< plantuml src="/content/de/diagrams/deployment.puml" />}}

## Was wohin kommt

| Teil | Ziel | Warum |
|---|---|---|
| Web-Simulator | LeoCloud, `https://it220234.cloud.htl-leonding.ac.at/` | soll ohne Installation im Browser laufen |
| Backend | LeoCloud, `…/api` | gleicher Host, ein Ingress |
| Doku, Präsentationen | GitHub Pages | statisch, versioniert mit dem Code |
| Firmware, iOS-App | Drohne / iPhone | Hardware |
| Relay | Laptop im Drohnen-WLAN | UDP-Broadcasts erreichen nur das eigene Netz |
| Liftoff-Hover | Windows-PC mit Liftoff | braucht vJoy und den Simulator |

## Stand

Images und Manifeste sind fertig. `images.yml` baut bei jedem Merge nach `main`, die Pakete auf
ghcr.io sind öffentlich (anonymer Pull am 12.10.2026 geprüft). **Deployt ist noch nichts.** Das
ist Task 6.2 im Phase-2-Change.

Wie man deployt: [LeoCloud-Deployment](../../how-to-guides/leocloud-deployen).
