# Internal Endpoints

Endpoints para consumo exclusivo de **servicios internos** del sistema (Orchestrator, InferenceCenter, Transcriptor, Speaker…). Permiten leer y escribir configuración operativa, consultar providers de inferencia disponibles y acceder a la configuración de clientes.

**URL Base**: `/internal`

**Auth requerida en todos los endpoints**:
- `Authorization: Bearer <API_SECRET_KEY>`
- `X-API-Key: <service_api_key>` — la key del servicio interno que hace la llamada

---

## Service Config

Configuración operativa clave-valor de cada servicio. El Orchestrator puede leer la config de cualquier servicio (acceso cross-service intencional).

### `GET /internal/service-config`

Lista todas las entradas de `ServiceConfig` del sistema.

**Respuesta exitosa (200)**
```json
[
  { "service": "transcriber", "key": "model", "value": "whisper-large-v3", "description": "Modelo de Whisper a usar", "updated_at": "..." },
  { "service": "transcriber", "key": "audio.chunk_ms", "value": 200, "description": "Tamaño de chunk de audio en ms", "updated_at": "..." },
  { "service": "speaker", "key": "model", "value": "kokoro-v1", "description": "Modelo TTS a usar", "updated_at": "..." },
  { "service": "orchestrator", "key": "default_provider_id", "value": "uuid-del-provider", "description": "UUID del InferenceProvider por defecto", "updated_at": "..." }
]
```

---

### `GET /internal/service-config/{service_name}`

Devuelve todas las claves de configuración de un servicio concreto.

**Path params**:
- `service_name` — nombre del servicio (ej: `transcriber`, `speaker`, `orchestrator`)

**Respuesta exitosa (200)**: lista de entradas del servicio. Lista vacía si el servicio no tiene entradas registradas.

---

### `PUT /internal/service-config/{service_name}/{key}`

Crea o actualiza una entrada de configuración. Si la clave ya existe la sobreescribe; si no, la crea.

**Path params**:
- `service_name` — nombre del servicio propietario
- `key` — nombre de la clave (soporta notación punto, ej: `audio.chunk_ms`)

**Body**:
```json
{
  "value": "nuevo-valor",
  "description": "Descripción opcional (solo se actualiza si se envía)"
}
```

El campo `value` acepta cualquier tipo JSON: string, número, booleano, objeto o array.

**Respuesta exitosa (200)**: la entrada actualizada.

---

### `DELETE /internal/service-config/{service_name}/{key}`

Elimina una entrada de configuración.

**Path params**:
- `service_name` — nombre del servicio propietario
- `key` — nombre de la clave a eliminar

**Respuesta exitosa**: `204 No Content`

**Errores**:
- `404` — la clave no existe

---

## Inference Providers

Providers de inferencia disponibles para el Orchestrator.

### `GET /internal/providers`

Lista los `InferenceProvider` activos. Solo devuelve providers con `is_active=true`.

**Respuesta exitosa (200)**
```json
[
  {
    "id": "uuid",
    "name": "Local LLM",
    "type": "local",
    "base_url": "ws://jota-inference:8002",
    "default_model_id": "llama-3.2-3b",
    "is_active": true,
    "created_at": "...",
    "updated_at": "..."
  }
]
```

---

### `GET /internal/providers/{provider_id}`

Devuelve el detalle de un `InferenceProvider` por ID, independientemente de si está activo o no.

**Path params**:
- `provider_id` — UUID del provider

**Respuesta exitosa (200)**: objeto `InferenceProvider`

**Errores**:
- `404` — provider no encontrado

---

## Client Config

Acceso a las preferencias de un cliente concreto, para que el Orchestrator (u otros servicios) las lean y actúen en consecuencia.

### `GET /internal/client-config/{client_id}`

Devuelve la `ClientConfig` del cliente indicado.

**Path params**:
- `client_id` — ID del cliente

**Respuesta exitosa (200)**
```json
{
  "client_id": "jota_desktop",
  "stt_language": "es",
  "stt_model": null,
  "stt_vad_thold": 0.0,
  "tts_voice": "af_heart",
  "tts_speed": 1.0,
  "preferred_model_id": null,
  "system_prompt_extra": null,
  "barge_in_enabled": true,
  "barge_in_min_chars": 5,
  "conversation_memory_limit": 20
}
```

**Errores**:
- `404` — cliente o `ClientConfig` no encontrado

---

### `PUT /internal/client-config/{client_id}`

Actualización parcial de la `ClientConfig` de un cliente. Solo se actualizan los campos enviados.

**Path params**:
- `client_id` — ID del cliente a actualizar

**Body** (todos los campos son opcionales):
```json
{
  "stt_language": "en",
  "tts_voice": "af_sky",
  "barge_in_enabled": false
}
```

Campos permitidos: `stt_language`, `stt_model`, `stt_vad_thold`, `tts_voice`, `tts_speed`, `preferred_model_id`, `system_prompt_extra`, `barge_in_enabled`, `barge_in_min_chars`, `conversation_memory_limit`.

**Respuesta exitosa (200)**: la `ClientConfig` actualizada.

**Errores**:
- `404` — cliente o `ClientConfig` no encontrado
- `422` — se envió un campo no permitido
