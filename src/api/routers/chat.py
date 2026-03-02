from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

from src.core.database import get_session
from src.core.models import Conversation, Message, Client, AIModel, InferenceClient
from src.api.dependencies import get_current_client, get_inference_service
from src.api.security import verify_api_key

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    responses={404: {"description": "Not found"}}
)

# --- DTOs ---
class ConversationCreate(BaseModel):
    title: Optional[str] = None



class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class MessageCreate(BaseModel):
    role: MessageRole
    content: str

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
    client: Client = Depends(get_current_client),
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
        title=conv_data.title
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
        content=message_data.content
    )
    
    # Actualizar timestamp de la conversación
    conversation.updated_at = datetime.utcnow()
    session.add(conversation)
    
    session.add(message)
    session.commit()
    session.refresh(message)
    return message
