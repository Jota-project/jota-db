import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Any
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON as SAJson
from pydantic import BaseModel

# --- CLASE BASE (Para no repetir campos en todas las tablas) ---
class BaseUUIDModel(SQLModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # Versionado optimista para prevenir conflictos de escritura concurrente
    version: int = Field(default=1)

class BaseNumericModel(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = Field(default=1)

class BaseStringModel(SQLModel):
    id: str = Field(primary_key=True) # Sin default_factory para asignar manualmente el nombre
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = Field(default=1)

# --- EVENTOS ---
class Event(BaseUUIDModel, table=True):
    title: str
    description: Optional[str] = None
    start_at: datetime
    # end_at puede ser None (indeterminado)
    end_at: Optional[datetime] = None
    all_day: bool = False
    location: Optional[str] = None
    
    # Relación: Un evento puede tener muchas tareas
    tasks: List["Task"] = Relationship(back_populates="event")
    # Relación: Un evento puede tener muchos recordatorios
    reminders: List["Reminder"] = Relationship(back_populates="event")

# --- TAREAS ---
class Task(BaseUUIDModel, table=True):
    title: str
    status: str = Field(default="pending") # pending, doing, done
    priority: int = Field(default=1) # 1 (Baja) a 5 (Crítica)
    
    # Vinculación con Eventos (Opcional)
    event_id: Optional[str] = Field(default=None, foreign_key="event.id")
    event: Optional[Event] = Relationship(back_populates="tasks")
    
    # Campo para definir CUÁNDO se hace la tarea respecto al evento
    # Ej: "before", "during", "after"
    timing_relative_to_event: Optional[str] = None 

    # Relación: Una tarea puede tener muchos recordatorios
    reminders: List["Reminder"] = Relationship(back_populates="task")

# --- RECORDATORIOS ---
class Reminder(BaseUUIDModel, table=True):
    message: str
    trigger_at: datetime
    is_completed: bool = False
    
    # Opcionalmente vinculado a una tarea
    task_id: Optional[str] = Field(default=None, foreign_key="task.id")
    task: Optional[Task] = Relationship(back_populates="reminders")
    
    # Opcionalmente vinculado directamente a un evento
    event_id: Optional[str] = Field(default=None, foreign_key="event.id")
    event: Optional[Event] = Relationship(back_populates="reminders")

# --- INTERNAL SERVICES LAYER ---
class InternalService(BaseStringModel, table=True):
    # El id heredado juega el rol de identificador (ej: "jota_orchestrator", "inference_center", "transcriptor")
    api_key: str # Clave secreta
    is_active: bool = Field(default=True)

# --- MODELS CATALOG LAYER ---
class AIModel(BaseStringModel, table=True):
    name: str
    file_path: str = Field(unique=True)
    context_window: int = Field(default=2048)
    gpu_layers: int = Field(default=-1)
    description: Optional[str] = None

    # Relación inversa: conversaciones que usan este modelo
    conversations: List["Conversation"] = Relationship(back_populates="model")
    # Relación inversa: mensajes generados con este modelo
    messages: List["Message"] = Relationship(back_populates="ai_model")

# --- CHAT LAYER (User Facing) ---
class ClientType(str, Enum):
    CHAT = "CHAT"
    QUICK = "QUICK"

class Client(BaseStringModel, table=True):
    name: str # Mantenemos name para la UI si hace falta
    client_key: str = Field(unique=True, index=True) # La llave que enviará JotaDesktop
    is_active: bool = Field(default=True)
    client_type: ClientType = Field(default=ClientType.CHAT)

    # Relación: Un cliente puede tener muchas conversaciones
    conversations: List["Conversation"] = Relationship(back_populates="client")
    # Relación: Un cliente tiene una configuración (1:1)
    config: Optional["ClientConfig"] = Relationship(back_populates="client")

class ClientConfig(BaseUUIDModel, table=True):
    client_id: str = Field(foreign_key="client.id", unique=True)
    client: Client = Relationship(back_populates="config")

    stt_language: str = Field(default="es")
    stt_model: Optional[str] = None
    stt_vad_thold: float = Field(default=0.0)
    tts_voice: str = Field(default="af_heart")
    tts_speed: float = Field(default=1.0)
    preferred_model_id: Optional[str] = Field(default=None, foreign_key="aimodel.id")
    system_prompt_extra: Optional[str] = None
    barge_in_enabled: bool = Field(default=True)
    barge_in_min_chars: int = Field(default=5)
    conversation_memory_limit: int = Field(default=20)

class Conversation(BaseNumericModel, table=True):
    title: Optional[str] = None
    status: str = Field(default="active") # active, archived
    
    # Vinculación con Client (Client usa UUID)
    client_id: str = Field(foreign_key="client.id")
    client: Client = Relationship(back_populates="conversations")
    
    # Modelo de IA activo para esta conversación (puede cambiar)
    model_id: Optional[str] = Field(default=None, foreign_key="aimodel.id")
    model: Optional["AIModel"] = Relationship(back_populates="conversations")
    
    # Relación: Una conversación tiene muchos mensajes
    messages: List["Message"] = Relationship(back_populates="conversation")

class Message(BaseUUIDModel, table=True):
    content: str
    role: str # user, assistant, system, tool
    extra_data: Optional[str] = None  # JSON string for tool metadata etc.

    # Vinculación con Conversation (Conversation usa int)
    conversation_id: int = Field(foreign_key="conversation.id")
    conversation: Conversation = Relationship(back_populates="messages")

    # Modelo de IA que generó este mensaje (relevante para mensajes de rol "assistant")
    ai_model_id: Optional[str] = Field(default=None, foreign_key="aimodel.id")
    ai_model: Optional["AIModel"] = Relationship(back_populates="messages")

class ProviderType(str, Enum):
    local = "local"
    openai = "openai"
    anthropic = "anthropic"
    custom = "custom"


class ServiceConfig(SQLModel, table=True):
    __tablename__ = "service_config"
    service: str = Field(primary_key=True)
    key: str = Field(primary_key=True)
    value: Optional[Any] = Field(default=None, sa_column=Column(SAJson))
    description: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class InferenceProvider(BaseUUIDModel, table=True):
    __tablename__ = "inferenceprovider"
    name: str
    type: ProviderType
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_model_id: Optional[str] = None
    is_active: bool = Field(default=True)
    extra_config: Optional[Any] = Field(default=None, sa_column=Column(SAJson))


class AdminUser(BaseStringModel, table=True):
    # id siempre "admin" — sistema single-admin
    api_key: str
    is_active: bool = Field(default=True)


# --- RESPONSE SCHEMAS (no son tablas) ---
class SessionResponse(BaseModel):
    """Respuesta de GET /auth/session — identidad completa del cliente para el handshake."""
    client: Client
    config: ClientConfig

    class Config:
        from_attributes = True