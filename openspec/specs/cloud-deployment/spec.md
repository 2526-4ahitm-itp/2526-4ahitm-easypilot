## Purpose

How backend and web simulator get to the LeoCloud (Kubernetes of HTL Leonding): images built by GitHub Actions, manifests in `k8s/`, one host with one ingress (FSD §3.3, §12.2). Documentation and slides are served from GitHub Pages instead.

## Requirements

### Requirement: Container images on ghcr.io

On every push to `main` that changes `webinterface/`, GitHub Actions SHALL build `easypilot-backend` and `easypilot-web` and push them to `ghcr.io/2526-4ahitm-itp/` tagged `latest` and with the commit SHA (§12.2).

`status: implemented`

#### Scenario: Merge to main
- **WHEN** a change to `webinterface/` is merged
- **THEN** both images are pushed with the new commit tag

### Requirement: Kubernetes manifests

`k8s/` SHALL contain deployments and services for backend (port 8080, readiness `GET /api/status`) and web (port 80) and one ingress that routes `/api` to the backend and `/` to the web container on `LEOCLOUD_HOST` (§12.2).

`status: implemented`

#### Scenario: Apply manifests
- **WHEN** the manifests are applied with `LEOCLOUD_HOST=it220270.cloud.htl-leonding.ac.at`
- **THEN** both deployments become ready behind one ingress

### Requirement: Running production deployment

Backend and web simulator SHALL be deployed and reachable at `https://it220270.cloud.htl-leonding.ac.at/` (§3.3, US-08, US-09).

`status: implemented`

#### Scenario: Status from outside
- **WHEN** `curl https://it220270.cloud.htl-leonding.ac.at/api/status` is run
- **THEN** it returns 200 with `"status":"UP"` (deployed 2026-10-14 to namespace `student-it220270`)

### Requirement: Relay stays in the LAN

The Python relay SHALL NOT be deployed to the cloud, because its UDP broadcasts only reach devices in the same network (§3.3, §5.5).

`status: implemented`

#### Scenario: Manifests
- **WHEN** `k8s/` is listed
- **THEN** there is no relay deployment
