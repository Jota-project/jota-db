# Auth Endpoints

Maneja la autenticación y validación tanto de clientes finales (apps cliente) como de servicios de la propia infraestructura (motor de inferencia, orquestador, etc).

**URL Base**: `/auth`

---

## `GET /client`
Valida la identidad de un **Cliente Externo** (ej. JotaDesktop, un móvil, un frontend frontend Web).

**Headers Requeridos**:
- `Authorization: Bearer <API_SECRET_KEY>`: Clave maestra global definida en `.env`.
- `X-API-Key: <client_key>`: La llave secreta que identifica a un cliente específico en la tabla `Client`.

**Respuesta Exitosa (HTTP 200 OK)**
```json
{
  "id": 1,
  "name": "Desktop Client",
  "client_key": "desktop_client_01",
  "is_active": true,
  "created_at": "...",
  "updated_at": "...",
  "version": 1
}
```

**Errores Posibles**:
- `401 Unauthorized`: Cliente inactivo, clave incorrecta, o no se encuentra en la base de datos.
- `403 Forbidden`: Cliente existe pero está desactivado (`is_active = false`).

---

## `GET /internal`
Valida la identidad de un **Servicio Interno** (Infraestructura, ej. InferenceCenter en C++, Orquestador en Python, Transcriptor). Esta ruta comprueba contra la tabla `InternalService`.

**Headers Requeridos**:
- `Authorization: Bearer <API_SECRET_KEY>`: Clave maestra global definida en `.env`.
- `X-Service-ID: <service_id>`: Identificador del servicio de infraestructura (ej. `"JotaOrchestrator"`).
- `X-API-Key: <service_key>`: La clave secreta asignada al servicio.

**Respuesta Exitosa (HTTP 200 OK)**
```json
{
  "id": 1,
  "client_id": "JotaOrchestrator",
  "api_key": "jota_orchestrator_...",
  "is_active": true,
  "created_at": "...",
  "updated_at": "...",
  "version": 1
}
```

**Errores Posibles**:
- `401 Unauthorized`: API Key inválida o el servicio no se encuentra.
- `403 Forbidden`: El servicio está desactivado.
