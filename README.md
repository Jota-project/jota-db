# jota-db

![Status: Deprecated](https://img.shields.io/badge/status-Deprecated-red)

> ⚠️ **Deprecated as identity/config source.** As of `jota-gateway` v1.9.0, the gateway maintains its own SQLite database for client identity and configuration. `jota-db` is kept for compatibility with setups that still use it as a centralized auth backend for `jota-transcriber` and `jota-speaker`.
>
> See [org ARCHITECTURE.md](https://github.com/Jota-project/.github/blob/main/ARCHITECTURE.md) §10 for the full deprecation context.

---

## Current role

`jota-db` provides:

- **Centralized auth API** for legacy service setups (transcriber, speaker, others) via `AUTH_API_URL` + `AUTH_API_SECRET`.
- **Admin REST API** (`/admin/services`, `/admin/clients`, `/admin/providers`, `/admin/config`) for managing `ServiceConfig`, `InferenceProvider`, `AdminUser`, and `Client`/`ClientConfig`.
- **Internal REST API** (`/internal/`) for service-to-service configuration and provider queries.

## Migration direction

The dependency on `jota-db` for client identity is removed in `jota-gateway`. The remaining dependencies (`jota-transcriber` and `jota-speaker` using it as external auth) are tracked in [`Jota-project/jota-gateway` issues](https://github.com/Jota-project/jota-gateway/issues) under the deprecation effort.

If you maintain a fresh deployment:
- **Don't** use `jota-db` as identity source.
- For local auth per service, use `AUTH_TOKEN` static.
- For centralized auth, you can still use `jota-db` until the migration is complete.

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
