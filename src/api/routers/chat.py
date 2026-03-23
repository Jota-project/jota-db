from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

from src.core.database import get_session
from src.core.models import Conversation, Message, Client, AIModel, InferenceClient
from src.api.dependencies import get_current_client, get_inference_service, get_any_authenticated_caller
from src.api.security import verify_api_key

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],

)

# --- DTOs ---
class ConversationCreate(BaseModel):
    title: Optional[str] = None
    model_id: Optional[str] = None  # Modelo de IA inicial para esta conversación

class ConversationUpdate(BaseModel):
    """Permite actualizar campos mutables de una conversación, como el modelo de IA activo."""
    title: Optional[str] = None
    model_id: Optional[str] = None
    status: Optional[str] = None


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

class MessageCreate(BaseModel):
    role: MessageRole
    content: str
    ai_model_id: Optional[str] = None  # Modelo que generó este mensaje (obligatorio para role=assistant)
    metadata: Optional[str] = None  # JSON string for tool metadata etc.

class AIModelRead(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    context_window: int
    file_path: str
    gpu_layers: int

# --- Endpoints ---

@router.get("/models", response_model=List[AIModelRead])
def list_models(
    session: Session = Depends(get_session),
    caller = Depends(get_any_authenticated_caller),
    _: bool = Depends(verify_api_key)
):
    """Devuelve la lista de modelos disponibles con todos sus atributos."""
    models = session.exec(select(AIModel)).all()
    return models

@router.post("/conversations", response_model=Conversation, status_code=status.HTTP_201_CREATED)
def create_conversation(
    conv_data: ConversationCreate, 
    session: Session = Depends(get_session),
    client: Client = Depends(get_current_client),
    _: bool = Depends(verify_api_key)
):
    """Crea una nueva conversación para un cliente autenticado"""
    # El cliente ya viene validado por get_current_client

    conversation = Conversation(
        client_id=client.id,
        title=conv_data.title,
        model_id=conv_data.model_id
    )
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation

@router.get("/conversations", response_model=List[Conversation])
def list_conversations(
    limit: Optional[int] = 50,
    status_filter: Optional[str] = None,
    session: Session = Depends(get_session),
    client: Client = Depends(get_current_client),
    _: bool = Depends(verify_api_key)
):
    """Lista las conversaciones del cliente autenticado, ordenadas por actualización más reciente."""
    query = select(Conversation).where(Conversation.client_id == client.id)
    
    if status_filter:
        query = query.where(Conversation.status == status_filter)
        
    query = query.order_by(Conversation.updated_at.desc()).limit(limit)
    return session.exec(query).all()

@router.patch("/conversations/{conversation_id}", response_model=Conversation)
def update_conversation(
    conversation_id: int,
    update_data: ConversationUpdate,
    session: Session = Depends(get_session),
    client: Client = Depends(get_current_client),
    _: bool = Depends(verify_api_key)
):
    """Actualiza una conversación: puede cambiar el modelo de IA activo, el título o el estado."""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.client_id != client.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this conversation")

    if update_data.model_id is not None:
        # Verificar que el modelo existe
        model = session.get(AIModel, update_data.model_id)
        if not model:
            raise HTTPException(status_code=404, detail=f"AI model '{update_data.model_id}' not found")
        conversation.model_id = update_data.model_id

    if update_data.title is not None:
        conversation.title = update_data.title

    if update_data.status is not None:
        conversation.status = update_data.status

    conversation.updated_at = datetime.utcnow()
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation

@router.get("/{conversation_id}/messages", response_model=List[Message])
def get_conversation_messages(
    conversation_id: int,
    limit: Optional[int] = None,
    session: Session = Depends(get_session),
    client: Client = Depends(get_current_client),
    _: bool = Depends(verify_api_key)
):
    """Obtiene los mensajes de una conversación en orden cronológico"""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    # Verificar propiedad
    if conversation.client_id != client.id:
         raise HTTPException(status_code=403, detail="Not authorized to access this conversation")
        
    statement = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    if limit is not None:
        statement = statement.limit(limit)
    messages = session.exec(statement).all()
    return messages

@router.post("/{conversation_id}/messages", response_model=Message, status_code=status.HTTP_201_CREATED)
def create_message(
    conversation_id: int,
    message_data: MessageCreate,
    session: Session = Depends(get_session),
    client: Client = Depends(get_current_client),
    _: bool = Depends(verify_api_key)
):
    """Agrega un mensaje a una conversación"""
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    # Verificar propiedad
    if conversation.client_id != client.id:
         raise HTTPException(status_code=403, detail="Not authorized to post to this conversation")

    message = Message(
        conversation_id=conversation_id,
        role=message_data.role.value,
        content=message_data.content,
        ai_model_id=message_data.ai_model_id,
        metadata=message_data.metadata
    )
    
    # Actualizar timestamp de la conversación
    conversation.updated_at = datetime.utcnow()
    session.add(conversation)
    
    session.add(message)
    session.commit()
    session.refresh(message)
    return message
