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
  └── ClientConfig   — preferencias por cliente (STT, TTS, modelo, barge-in, etc.)
  └── Conversation   — sesión de chat de un cliente, con modelo de IA activo
        └── Message  — mensajes individuales (roles: user/assistant/system/tool)
```

`ClientType` es un enum `CHAT | QUICK`: CHAT para conversación completa con historial, QUICK para queries sin contexto.

`ClientConfig` tiene relación 1:1 con `Client`. Se auto-crea con defaults en el bootstrap. Campos clave: `stt_language`, `stt_vad_thold`, `tts_voice`, `tts_speed`, `preferred_model_id`, `barge_in_enabled`, `conversation_memory_limit`.

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
4. `bootstrap_clients()` — crea/actualiza Clients desde `JOTA_CLIENTS`, incluyendo `client_type` y auto-crea `ClientConfig` si falta
5. `sync_local_models()` — registra ficheros `.gguf` nuevos en `MODELS_DIR`

## Endpoints relevantes para servicios consumidores

### `GET /auth/session` — handshake del gateway (PR #11)

Endpoint principal para jota-gateway. Resuelve `client_key → Client + ClientConfig` en una sola llamada.

```
GET /auth/session
Authorization: Bearer <API_SECRET_KEY>
X-API-Key: <client_key>

→ { "client": { "id": "...", "name": "...", "is_active": true, ... },
    "config": { "stt_language": "es", "tts_voice": "af_heart", ... } }
```

Auto-crea `ClientConfig` con defaults si el cliente no tiene uno. 401 si key inválida, 403 si inactivo.

### `GET|PUT /config/me` y `POST /config/me/reset` — configuración por cliente (PR #11)

Auth: Bearer + `X-API-Key` (client_key directa o service key + `X-Client-ID`).

- `GET /config/me` — devuelve ClientConfig del cliente autenticado
- `PUT /config/me` — actualización parcial (solo campos enviados); 422 si campo desconocido
- `POST /config/me/reset` — restaura todos los campos a defaults

## Issues abiertas

No hay issues abiertas en este repo. Fase 0 completada. Fase 1 Paso 1 completada (PR #11).

## Cambios de API relevantes para servicios consumidores

### `Message.extra_data` (antes `metadata`)

El campo `metadata` fue renombrado a `extra_data` en el modelo `Message` y en el DTO `MessageCreate` (`src/api/routers/chat.py`).

**Afecta a**: jota-orchestrator al llamar a `POST /chat/{conversation_id}/messages`.
Enviar `metadata` en el body será ignorado silenciosamente — usar `extra_data`.

### Historial de issues cerradas

| # | Título | Resolución |
|---|---|---|
| #1 | client_type ausente en Client | ✅ PR #5 |
| #2 | MessageRole sin tool + Message sin metadata | ✅ PR #5 (campo renombrado a extra_data) |
| #3 | model_id vs ai_model_id | ✅ PR #5 |
| #4 | /auth/validate no existe | ✅ Cerrada — error de diseño en jota-speaker, no en jota-db |
| #6 | HOST_MODELS_DIR hardcodeado | ✅ PR #9 |
| #11 | ClientConfig + GET /auth/session + /config/me | ✅ PR #11 (Fase 1 Paso 1) |
