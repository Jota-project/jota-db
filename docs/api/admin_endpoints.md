# Admin Endpoints

Endpoints de gestión administrativa del sistema. Permiten gestionar toda la configuración, los providers de inferencia, los clientes y los servicios internos.

**URL Base**: `/admin`

**Auth requerida en todos los endpoints**:
- `Authorization: Bearer <API_SECRET_KEY>`
- `X-API-Key: <ADMIN_KEY>` — la clave de administrador definida en la variable de entorno `ADMIN_KEY`

---

## Config — `/admin/config`

Gestión de `ServiceConfig`: configuración operativa clave-valor por servicio.

### `GET /admin/config`

Lista todas las entradas de configuración de todos los servicios.

**Respuesta exitosa (200)**: array de entradas `ServiceConfig`.

---

### `GET /admin/config/{service_name}`

Lista todas las claves de configuración de un servicio concreto.

**Path params**:
- `service_name` — nombre del servicio (ej: `transcriber`, `speaker`, `orchestrator`)

**Respuesta exitosa (200)**: array de entradas. Lista vacía si el servicio no tiene entradas.

---

### `PUT /admin/config/{service_name}/{key}`

Crea o actualiza una entrada de configuración.

**Path params**:
- `service_name` — nombre del servicio propietario
- `key` — nombre de la clave (soporta notación punto, ej: `audio.chunk_ms`)

**Body**:
```json
{
  "value": "whisper-large-v3",
  "description": "Descripción opcional"
}
```

El campo `value` acepta cualquier tipo JSON. El campo `description` solo se actualiza si se incluye.

**Respuesta exitosa (200)**: la entrada creada o actualizada.

---

### `DELETE /admin/config/{service_name}/{key}`

Elimina una entrada de configuración.

**Respuesta exitosa**: `204 No Content`

**Errores**:
- `404` — la clave no existe

---

### `POST /admin/config/{service_name}/reset`

Restaura la configuración de un servicio a los valores por defecto definidos en las variables de entorno `SEED_*`. Borra las entradas actuales y las regenera.

**Path params**:
- `service_name` — `transcriber`, `speaker` u `orchestrator`

**Variables de entorno usadas**:
| Variable | Servicio | Clave |
|---|---|---|
| `SEED_TRANSCRIBER_MODEL` | transcriber | model |
| `SEED_TRANSCRIBER_AUDIO_CHUNK_MS` | transcriber | audio.chunk_ms |
| `SEED_SPEAKER_MODEL` | speaker | model |

El servicio `orchestrator` toma el `default_provider_id` del primer `InferenceProvider` de tipo `local` en la DB.

**Respuesta exitosa (200)**: array con las entradas regeneradas. Lista vacía si el nombre de servicio no es reconocido.

---

## Providers — `/admin/providers`

Gestión de `InferenceProvider`: los backends de inferencia disponibles (local, OpenAI, Anthropic…).

### `GET /admin/providers`

Lista todos los providers, activos e inactivos.

**Respuesta exitosa (200)**
```json
[
  {
    "id": "uuid",
    "name": "Local LLM",
    "type": "local",
    "base_url": "ws://jota-inference:8002",
    "api_key": null,
    "default_model_id": "llama-3.2-3b",
    "extra_config": null,
    "is_active": true,
    "created_at": "...",
    "updated_at": "..."
  }
]
```

---

### `POST /admin/providers`

Crea un nuevo `InferenceProvider`. El ID se genera automáticamente (UUID). El provider se crea activo por defecto.

**Body**:
```json
{
  "name": "OpenAI",
  "type": "openai",
  "api_key": "sk-...",
  "default_model_id": "gpt-4o"
}
```

Tipos válidos: `local`, `openai`, `anthropic`.

**Respuesta exitosa**: `201 Created` con el provider creado.

---

### `GET /admin/providers/{provider_id}`

Detalle de un provider por UUID.

**Errores**:
- `404` — provider no encontrado

---

### `PUT /admin/providers/{provider_id}`

Actualización parcial de un provider. Solo se actualizan los campos enviados.

**Casos de uso comunes**:
```json
{ "api_key": "sk-nueva-key" }
```
```json
{ "is_active": true }
```

**Errores**:
- `404` — provider no encontrado

---

### `DELETE /admin/providers/{provider_id}`

Desactiva un provider (soft-delete). Marca `is_active=false`. El registro se conserva en DB y deja de aparecer en `/internal/providers`.

**Respuesta exitosa (200)**: el provider con `is_active=false`.

**Errores**:
- `404` — provider no encontrado

---

## Clients — `/admin/clients`

Gestión de `Client` (aplicaciones de usuario) y su `ClientConfig` asociada.

### `GET /admin/clients`

Lista todos los clientes, activos e inactivos.

---

### `POST /admin/clients`

Crea un nuevo cliente y su `ClientConfig` con valores por defecto automáticamente.

**Body**:
```json
{
  "name": "jota-desktop",
  "client_key": "clave-secreta",
  "client_type": "CHAT"
}
```

Tipos: `CHAT` (conversación con historial) o `QUICK` (queries sin contexto). El campo `name` se usa también como `id`.

**Respuesta exitosa**: `201 Created`

---

### `GET /admin/clients/{client_id}`

Detalle de un cliente por ID.

**Errores**:
- `404` — cliente no encontrado

---

### `PUT /admin/clients/{client_id}`

Actualización parcial de un cliente.

**Body** (todos los campos opcionales):
```json
{
  "name": "nuevo-nombre",
  "is_active": false,
  "client_type": "QUICK"
}
```

---

### `DELETE /admin/clients/{client_id}`

Desactiva un cliente (soft-delete). El cliente no podrá autenticarse pero su historial y configuración se conservan.

**Respuesta exitosa (200)**: el cliente con `is_active=false`.

---

### `GET /admin/clients/{client_id}/config`

Devuelve la `ClientConfig` del cliente.

**Errores**:
- `404` — cliente o `ClientConfig` no encontrado

---

### `PUT /admin/clients/{client_id}/config`

Actualización parcial de la `ClientConfig` de un cliente. Mismo comportamiento que `PUT /internal/client-config/{client_id}`.

Campos permitidos: `stt_language`, `stt_model`, `stt_vad_thold`, `tts_voice`, `tts_speed`, `preferred_model_id`, `system_prompt_extra`, `barge_in_enabled`, `barge_in_min_chars`, `conversation_memory_limit`.

**Errores**:
- `422` — campo no permitido

---

### `POST /admin/clients/{client_id}/config/reset`

Restaura la `ClientConfig` a los valores por defecto:

| Campo | Default |
|---|---|
| `stt_language` | `es` |
| `tts_voice` | `af_heart` |
| `tts_speed` | `1.0` |
| `barge_in_enabled` | `true` |
| `barge_in_min_chars` | `5` |
| `conversation_memory_limit` | `20` |
| `stt_model`, `preferred_model_id`, `system_prompt_extra` | `null` |

---

## Services — `/admin/services`

Gestión de `InternalService`: los servicios internos del sistema (Orchestrator, InferenceCenter, Transcriptor…).

### `GET /admin/services`

Lista todos los servicios internos, activos e inactivos.

**Respuesta exitosa (200)**
```json
[
  {
    "id": "JotaOrchestrator",
    "api_key": "...",
    "is_active": true,
    "created_at": "...",
    "updated_at": "..."
  }
]
```

---

### `POST /admin/services`

Registra un nuevo servicio interno. El servicio se crea activo por defecto.

**Body**:
```json
{
  "id": "JotaOrchestrator",
  "api_key": "clave-secreta"
}
```

El `id` debe coincidir con `INTERNAL_*_ID` en el entorno del servicio.

**Respuesta exitosa**: `201 Created`

**Errores**:
- `409` — ya existe un servicio con ese ID

---

### `GET /admin/services/{service_id}`

Detalle de un servicio por ID.

**Errores**:
- `404` — servicio no encontrado

---

### `PUT /admin/services/{service_id}`

Actualiza un servicio interno. Útil para rotación de key o activar/desactivar.

**Casos de uso comunes**:
```json
{ "api_key": "nueva-clave" }
```
```json
{ "is_active": false }
```

**Errores**:
- `404` — servicio no encontrado

---

### `DELETE /admin/services/{service_id}`

Desactiva un servicio interno (soft-delete). El servicio no podrá autenticarse en `/internal/`. El registro se conserva en DB.

**Respuesta exitosa (200)**: el servicio con `is_active=false`.

**Errores**:
- `404` — servicio no encontrado
