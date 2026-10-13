---
title: In die LeoCloud deployen
weight: 6
---

Voraussetzung: `kubectl` mit der LeoCloud-kubeconfig (Kontext `leocloud`, Namespace
`student-it220270`, das ist Davids Namespace), `envsubst` (gettext). Unter Windows geht das aus der WSL.

{{% steps %}}

### Images bauen lassen

Passiert automatisch: Jeder Merge nach `main`, der `webinterface/` ändert, baut
`ghcr.io/2526-4ahitm-itp/easypilot-backend` und `…/easypilot-web` (Tags `latest` und Commit).

### Trockenlauf

```bash
export LEOCLOUD_HOST=it220270.cloud.htl-leonding.ac.at
kubectl apply --dry-run=server -f k8s/backend.yaml -f k8s/web.yaml
envsubst < k8s/ingress.yaml | kubectl apply --dry-run=server -f -
```

### Deployen

```bash
kubectl apply -f k8s/backend.yaml -f k8s/web.yaml
envsubst < k8s/ingress.yaml | kubectl apply -f -
```

### Neue Version ausrollen

```bash
kubectl rollout restart deployment/easypilot-backend deployment/easypilot-web
```

### Prüfen

```bash
kubectl get pods
curl -s https://$LEOCLOUD_HOST/api/status
```

{{% /steps %}}

`k8s/postgres.yaml` und `k8s/volume-claim.yaml` sind eine alte Demo und werden nicht deployt.
