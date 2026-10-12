# Deployment: LeoCloud (Kubernetes)

## Zielsystem

| | |
|---|---|
| Cluster | LeoCloud der HTL Leonding (Kubernetes, Ingress-Klasse `nginx`) |
| Namespace | `student-it220234` |
| Host | `it220234.cloud.htl-leonding.ac.at` (der Namespace erlaubt genau diesen einen Host) |

Ein Host, ein Ingress:

| URL | Ziel |
|---|---|
| `https://it220234.cloud.htl-leonding.ac.at/` | Web-Simulator (`easypilot-web`, nginx mit dem Vite-Build) |
| `https://it220234.cloud.htl-leonding.ac.at/api/status` | Backend (`easypilot-backend`, Quarkus) |

Doku und Präsentationen liegen auf GitHub Pages:
https://2526-4ahitm-itp.github.io/2526-4ahitm-easypilot/

**Nicht in der Cloud:** der Python-Relay (`webinterface/backend/src/main/python/relay_server.py`).
Er schickt UDP-Broadcasts ins lokale Netz, damit die iOS-App den ESP32 findet. Broadcasts
erreichen nur Geräte im selben LAN, deshalb läuft er auf einem Laptop im Drohnen-WLAN.

## Dateien

| Datei | Inhalt |
|---|---|
| `backend.yaml` | Deployment + Service `easypilot-backend` (Port 8080, Readiness `GET /api/status`) |
| `web.yaml` | Deployment + Service `easypilot-web` (Port 80, Readiness `GET /`) |
| `ingress.yaml` | Ingress `easypilot`: `/api` → Backend, `/` → Web-Simulator; Host aus `LEOCLOUD_HOST` |
| `postgres.yaml`, `volume-claim.yaml` | alte Demo, wird nicht deployt (das Backend nutzt keine Datenbank) |

## Images

GitHub Actions (`.github/workflows/images.yml`) baut bei jedem Push auf `main`, der
`webinterface/` ändert, zwei Images und pusht sie nach GitHub Container Registry:

- `ghcr.io/2526-4ahitm-itp/easypilot-backend:latest` und `:<commit>`
- `ghcr.io/2526-4ahitm-itp/easypilot-web:latest` und `:<commit>`

Neue Pakete auf ghcr.io sind zuerst **privat**. Nach dem ersten Lauf unter
GitHub → Organisation → Packages die Sichtbarkeit beider Pakete auf *public* stellen,
sonst kann die LeoCloud sie nicht ohne `imagePullSecret` laden.

## Konfiguration

| Variable | Wert | Wofür |
|---|---|---|
| `LEOCLOUD_HOST` | `it220234.cloud.htl-leonding.ac.at` | Host im Ingress (per `envsubst`) |

`envsubst` gehört zu gettext (`brew install gettext` auf macOS).

## Ablauf

```bash
# 1. Build & Auslieferung: automatisch durch .github/workflows/images.yml bei Push auf main

# 2. Deploy (lokal, kubectl mit LeoCloud-kubeconfig, Kontext leocloud)
export LEOCLOUD_HOST=it220234.cloud.htl-leonding.ac.at
kubectl apply -f k8s/backend.yaml -f k8s/web.yaml
envsubst < k8s/ingress.yaml | kubectl apply -f -

# 3. Neue Version ausrollen (Images mit Tag latest neu ziehen)
kubectl rollout restart deployment/easypilot-backend deployment/easypilot-web

# 4. Prüfen
kubectl get pods
curl -s https://$LEOCLOUD_HOST/api/status
# erwartet: {"name":"easypilot-backend","status":"UP","version":"1.0-SNAPSHOT"}
```

Vor einem echten Deploy lässt sich alles gegen den Cluster prüfen, ohne etwas anzulegen:

```bash
kubectl apply --dry-run=server -f k8s/backend.yaml -f k8s/web.yaml
envsubst < k8s/ingress.yaml | kubectl apply --dry-run=server -f -
```

## Stand

Vorbereitet, noch **nicht** deployt. Manifeste sind mit `--dry-run=server` gegen die
LeoCloud geprüft, beide Images lokal gebaut und gestartet.

## Bekannte Grenze

Der Web-Viewer verbindet sich fest auf `ws://localhost:8765` (`websocket_sender.py`).
In der Cloud gibt es diesen Telemetrie-Stream nicht; das betrifft die Umsetzung des
Web-Simulators in Phase 2.
