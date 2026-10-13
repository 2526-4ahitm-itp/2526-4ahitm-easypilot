---
title: Web und Backend lokal starten
weight: 3
---

## Backend (Quarkus)

```bash
cd webinterface/backend
./mvnw quarkus:dev
curl -s http://localhost:8080/api/status
```

Erwartet: `{"name":"easypilot-backend","status":"UP",…}`.

## Web-Viewer (React + Vite)

```bash
cd webinterface/frontend
npm ci
npm run dev
```

Vite zeigt die URL an (meist `http://localhost:5173`). Die 3D-Ansicht liegt unter `/model`.
Damit sich das Modell bewegt, muss `websocket_sender.py` laufen, der den Flight Controller per USB
liest und auf `ws://localhost:8765` sendet (siehe [Relay starten](../relay-starten)).

## Beides als Container

```bash
docker build -t easypilot-web webinterface/frontend
docker run --rm -p 8081:80 easypilot-web
```

Das Backend-Image baut GitHub Actions aus `webinterface/backend/src/main/docker/Dockerfile.jvm`.
