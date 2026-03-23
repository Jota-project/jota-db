# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git workflow (estricto)

- **`main` tiene push bloqueado** — ningún cambio va directo, todo pasa por PR.
- Flujo obligatorio: crear rama → desarrollar → PR → merge → borrar rama.
- Usar **Conventional Commits** con **Semantic Release**:
  - `feat:` → minor bump
  - `fix:` → patch bump
  - `feat!:` / `BREAKING CHANGE:` → major bump
  - `chore:`, `docs:`, `refactor:`, `test:` → no release
- Ramas de trabajo con prefijo semántico: `feat/`, `fix/`, `chore/`, `refactor/`.
- Al mergear una PR, borrar la rama inmediatamente (local y remoto).

## Levantar el proyecto

```bash
docker compose up --build -d      # Arranca API + PostgreSQL
docker compose logs -f api-server # Ver logs
docker compose down               # Parar
docker compose down -v            # Parar y borrar DB (destructivo)
```

La API queda en `http://localhost:8002`. Docs en `/docs`.

No hay migraciones (Alembic eliminado). Las tablas se crean con `SQLModel.metadata.create_all()` en cada arranque. El bootstrap de servicios y clientes también corre en startup.

## Variables de entorno

Copiar `.env.example` a `.env`. Las críticas:

| Variable | Uso |
|---|---|
| `API_SECRET_KEY` | Bearer token global requerido en todos los endpoints |
| `INTERNAL_*_ID` / `INTERNAL_*_KEY` | Bootstrap de servicios internos (Orchestrator, InferenceCenter, Transcriptor) |
| `JOTA_CLIENTS` | JSON array con clientes externos: `[{"name":"...", "key":"...", "type":"CHAT\|QUICK"}]` |
| `MODELS_DIR` | Path dentro del contenedor para escanear modelos `.gguf` |
| `HOST_MODELS_DIR` | Path en el host (para persistir file_path en la DB) |

## Arquitectura

### Capas del modelo de datos (`src/core/models.py`)

```
InternalService      — servicios del sistema (Orchestrator, InferenceCenter, Transcriptor)
AIModel              — catálogo de modelos .gguf disponibles
Client               — aplicaciones de usuario (jota-desktop=CHAT, jota-pill=QUICK)
  └── Conversation   — sesión de chat de un cliente, con modelo de IA activo
        └── Message  — mensajes individuales (roles: user/assistant/system/tool)
```

`ClientType` es un enum `CHAT | QUICK`: CHAT para conversación completa con historial, QUICK para queries sin contexto.

### Autenticación (dos capas)

Todos los endpoints requieren `Authorization: Bearer <API_SECRET_KEY>` (verificado por `verify_api_key`).

Los endpoints de `/chat` además requieren identificar quién hace la llamada vía `X-API-Key`:

- **Acceso directo**: `X-API-Key` es la `client_key` del Client.
- **Acceso de servicio**: `X-API-Key` es la `api_key` de un InternalService + `X-Client-ID` con el ID del cliente objetivo. El Orchestrator usa esta vía para actuar en nombre de un cliente.

Dependencias relevantes en `src/api/dependencies.py`:
- `get_current_client` — resuelve el Client independientemente del tipo de llamada
- `get_internal_service` — solo servicios internos
- `get_any_authenticated_caller` — cualquiera de los dos (usado en endpoints globales como `/chat/models`)

### Bootstrap en startup

`init_db()` en `src/core/database.py`:
1. Espera a que PostgreSQL esté listo (retry con backoff)
2. Crea tablas con `SQLModel.metadata.create_all()`
3. `bootstrap_system_clients()` — crea/verifica InternalServices desde env
4. `bootstrap_clients()` — crea/actualiza Clients desde `JOTA_CLIENTS`, incluyendo `client_type`
5. `sync_local_models()` — registra ficheros `.gguf` nuevos en `MODELS_DIR`

## Issues abiertas

- **#4** — `POST /auth/validate` requerido por jota-speaker (eliminado de PR #5 por ser incorrecto, pendiente reimplementar)
- **#6** — `HOST_MODELS_DIR` tiene fallback hardcodeado, hay que añadirlo al `.env.example` y eliminar el path fijo
