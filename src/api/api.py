from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.database import init_db
from src.api.routers import tasks, events, reminders, auth, chat, config, internal
from src.api.routers import admin

_DESCRIPTION = """
API REST del ecosistema **Cerebro Digital** — gestiona tareas, eventos, recordatorios,
conversaciones con IA y la configuración operativa de todos los servicios.

## Autenticación

Todos los endpoints requieren:

```
Authorization: Bearer <API_SECRET_KEY>
```

Los endpoints de `/chat` y `/config` también identifican al llamante mediante `X-API-Key`:

- **Acceso directo** (cliente): `X-API-Key: <client_key>`
- **Acceso de servicio** (Orchestrator actuando en nombre de un cliente):
  `X-API-Key: <service_api_key>` + `X-Client-ID: <client_id>`

Los endpoints de `/internal` aceptan únicamente `X-API-Key` de servicio interno.

Los endpoints de `/admin` requieren adicionalmente `X-API-Key: <ADMIN_KEY>`.

## Grupos de endpoints

| Prefijo | Consumidor principal | Descripción |
|---|---|---|
| `/tasks`, `/events`, `/reminders` | Clientes | CRUD de datos personales |
| `/auth` | jota-gateway | Handshake de sesión |
| `/chat` | jota-desktop, jota-pill | Conversaciones con IA |
| `/config` | jota-gateway, jota-desktop | Configuración por cliente |
| `/internal` | Servicios internos | Config operativa + providers |
| `/admin` | Operador del sistema | Gestión completa del sistema |
"""

_TAGS = [
    {
        "name": "Health",
        "description": "Estado del servicio.",
    },
    {
        "name": "Auth",
        "description": "Handshake de sesión para jota-gateway. Resuelve `client_key → Client + ClientConfig`.",
    },
    {
        "name": "Tasks",
        "description": "CRUD de tareas personales.",
    },
    {
        "name": "Events",
        "description": "CRUD de eventos del calendario.",
    },
    {
        "name": "Reminders",
        "description": "CRUD de recordatorios.",
    },
    {
        "name": "Chat",
        "description": "Conversaciones con IA. Soporta historial (CHAT) y queries rápidas (QUICK).",
    },
    {
        "name": "Config",
        "description": "Lectura y escritura de `ClientConfig` por el cliente autenticado.",
    },
    {
        "name": "Internal",
        "description": """Endpoints para consumo exclusivo de servicios internos (Orchestrator, InferenceCenter, Transcriptor…).

**Auth requerida:** `Authorization: Bearer <API_SECRET_KEY>` + `X-API-Key: <service_api_key>`

Incluye acceso a:
- `ServiceConfig` — configuración operativa de cada servicio
- `InferenceProvider` — providers de inferencia activos
- `ClientConfig` — preferencias de un cliente concreto (para que el Orchestrator las lea)
""",
    },
    {
        "name": "Admin",
        "description": """Gestión administrativa completa del sistema.

**Auth requerida:** `Authorization: Bearer <API_SECRET_KEY>` + `X-API-Key: <ADMIN_KEY>`

Subrutas:

| Prefijo | Recurso |
|---|---|
| `/admin/config` | `ServiceConfig` — configuración clave-valor por servicio |
| `/admin/providers` | `InferenceProvider` — providers de inferencia (local, OpenAI, Anthropic…) |
| `/admin/clients` | `Client` + `ClientConfig` — clientes externos y sus preferencias |
| `/admin/services` | `InternalService` — servicios internos del sistema |
""",
    },
]

app = FastAPI(
    title="Cerebro Digital API",
    description=_DESCRIPTION,
    version="1.0.0",
    openapi_tags=_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configuración de CORS
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todos los orígenes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Event handlers
@app.on_event("startup")
def on_startup():
    """Inicializa la base de datos al arrancar la aplicación"""
    init_db()


# Health check endpoint
@app.get("/health", tags=["Health"])
def health_check():
    """Verificar el estado del servicio"""
    return {"status": "ok", "service": "Cerebro Digital API"}


# Include routers
app.include_router(tasks.router)
app.include_router(events.router)
app.include_router(reminders.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(config.router)
app.include_router(internal.router)
app.include_router(admin.router)