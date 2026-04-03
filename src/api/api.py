"""
Cerebro Digital API - Main Application

API REST para gestionar tu ecosistema de datos personal.
Diseñado para ser consumido por humanos y por IAs (futuro MCP Server).
"""
from fastapi import FastAPI

from src.core.database import init_db
from src.api.routers import tasks, events, reminders, auth, chat, config

app = FastAPI(
    title="Cerebro Digital API",
    description="API para gestionar tu ecosistema de datos personal",
    version="1.0.0",
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