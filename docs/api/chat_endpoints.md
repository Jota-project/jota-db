# Chat Endpoints

Estos endpoints gestionan el ciclo de vida de las conversaciones del usuario y el intercambio de mensajes con la IA (o sistema).

**URL Base**: `/chat`
**Autenticación Requerida**: Client (Bearer Token + `X-API-Key`)

---

## `POST /conversations`
Crea una nueva conversación para el cliente autenticado.

**Request Body (JSON)**:
- `title` (str, opcional): Título o descripción corta de la conversación.

**Respuesta Exitosa (HTTP 201 Created)**
```json
{
  "id": 1,
  "title": "Ayuda con Python",
  "client_id": 1,
  "status": "active",
  "created_at": "2026-02-25T10:00:00Z",
  "updated_at": "2026-02-25T10:00:00Z",
  "version": 1
}
```

---

## `GET /conversations`
Lista las conversaciones del cliente autenticado, ordenadas desde la más reciente a la más antigua.

**Query Parameters**:
- `limit` (int, opcional): Número máximo de conversaciones a devolver (por defecto 50).
- `status_filter` (str, opcional): Filtro por estado (ej. `active`, `archived`).

**Respuesta Exitosa (HTTP 200 OK)**
```json
[
  {
    "id": 1,
    "title": "Ayuda con Python",
    "client_id": 1,
    "status": "active",
    "created_at": "...",
    "updated_at": "...",
    "version": 1
  }
]
```

---

## `GET /{conversation_id}/messages`
Obtiene los mensajes de una conversación en orden cronológico (del más antiguo al más nuevo).

**Query Parameters**:
- `limit` (int, opcional): Número máximo de mensajes a devolver. Si no se envía, retorna todos.

**Respuesta Exitosa (HTTP 200 OK)**
```json
[
  {
    "id": 1,
    "conversation_id": 1,
    "role": "user",
    "content": "¿Qué es asyncio?",
    "created_at": "2026-02-25T10:01:00Z",
    "updated_at": "2026-02-25T10:01:00Z",
    "version": 1
  }
]
```

---

## `POST /{conversation_id}/messages`
Agrega un nuevo mensaje a una conversación existente.

**Request Body (JSON)**:
- `role` (str, requerido): El rol del emisor. Opciones: `"user"`, `"assistant"`, `"system"`.
- `content` (str, requerido): El contenido en texto del mensaje.

**Respuesta Exitosa (HTTP 201 Created)**
```json
{
  "id": 2,
  "conversation_id": 1,
  "role": "assistant",
  "content": "Asyncio es una librería...",
  "created_at": "2026-02-25T10:01:05Z",
  "updated_at": "2026-02-25T10:01:05Z",
  "version": 1
}
```
*Nota: Este endpoint también actualiza automáticamente el campo `updated_at` de la `Conversation` padre.*

---

## `GET /models`
Devuelve la lista de todos los modelos de IA disponibles con su configuración completa, incluyendo rutas internas.

**Respuesta Exitosa (HTTP 200 OK)**
```json
[
  {
    "id": "qwen-7b-chat",
    "name": "Qwen 7b Chat",
    "description": "Modelo auto-descubierto: qwen-7b-chat.gguf",
    "context_window": 2048,
    "file_path": "./models/qwen-7b-chat.gguf",
    "gpu_layers": -1
  }
]
```
