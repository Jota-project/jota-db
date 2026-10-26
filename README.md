# jota-db

![Status: Legacy · Archived](https://img.shields.io/badge/status-Legacy%20%C2%B7%20Archived-lightgrey)

> ⚠️ **Legacy · Archived.** Sustituido por la BD local de jota-gateway (desde v1.9.0) dentro de la arquitectura actual de Jota: https://github.com/jota-project/.github/blob/main/ARCHITECTURE.md

---

## Former role

`jota-db` used to provide:

- **Centralized auth API** for service setups (transcriber, speaker, others) via `AUTH_API_URL` + `AUTH_API_SECRET`.
- **Admin REST API** (`/admin/services`, `/admin/clients`, `/admin/providers`, `/admin/config`) for managing `ServiceConfig`, `InferenceProvider`, `AdminUser`, and `Client`/`ClientConfig`.
- **Internal REST API** (`/internal/`) for service-to-service configuration and provider queries.

## Replacement

`jota-db` is no longer part of the Jota architecture and should not be used in new or existing deployments:

- Client identity and configuration live in jota-gateway's own local database (since v1.9.0).
- `jota-transcriber` uses a per-service static `AUTH_TOKEN`; its `AUTH_API_URL` option (which pointed here) is legacy.
- `jota-speaker`'s `jota_db` auth mode is legacy; see the jota-speaker README for its current auth options.

## Components

| Component | Path |
| :--- | :--- |
| All data models | `src/core/models.py` |
| Bearer security | `src/api/security.py` |
| Auth endpoints (`/auth/client`, `/auth/validate`) | `src/api/routers/auth.py` |
| Config endpoints (`/config/me`) | `src/api/routers/config.py` |
| Chat (conversations, messages) | `src/api/routers/chat.py` |
| Admin routers (`/admin/services`, `/admin/clients`, `/admin/providers`, `/admin/config`) | `src/api/routers/admin/` |
| Internal routers (`/internal/`) | `src/api/routers/internal/` |

## Historical

The Tasks/Events API documented in early iterations of this repo is no longer part of the active system. See [`docs/legacy-tasks-api.md`](docs/legacy-tasks-api.md) for the historical surface, kept only for reference.
