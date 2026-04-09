"""
Router /admin/clients/ — gestión admin de Client y ClientConfig.
Auth: Bearer <API_SECRET_KEY> + X-API-Key: <ADMIN_KEY>
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from src.core.database import get_session
from src.core.models import Client, ClientConfig, ClientType, AdminUser
from src.api.dependencies import get_admin_user
from src.api.security import verify_api_key

router = APIRouter(
    prefix="/admin/clients",
    tags=["Admin - Clients"],
)


class ClientCreate(BaseModel):
    name: str
    client_key: str
    client_type: ClientType = ClientType.CHAT


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    client_type: Optional[ClientType] = None


# ============================================================
# CLIENTS
# ============================================================

@router.get("", response_model=List[Client])
def list_clients(
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Lista todos los clientes."""
    return session.exec(select(Client)).all()


@router.post("", response_model=Client, status_code=201)
def create_client(
    body: ClientCreate,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Crea un nuevo cliente y su ClientConfig por defecto."""
    new_client = Client(
        id=body.name,
        name=body.name,
        client_key=body.client_key,
        client_type=body.client_type,
        is_active=True,
    )
    session.add(new_client)
    session.flush()
    session.add(ClientConfig(client_id=new_client.id))
    session.commit()
    session.refresh(new_client)
    return new_client


@router.get("/{client_id}", response_model=Client)
def get_client(
    client_id: str,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Detalle de un cliente."""
    c = session.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return c


@router.put("/{client_id}", response_model=Client)
def update_client(
    client_id: str,
    body: ClientUpdate,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Actualización parcial de un cliente."""
    c = session.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")

    patch = body.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(c, field, value)
    c.updated_at = datetime.utcnow()

    session.add(c)
    session.commit()
    session.refresh(c)
    return c


@router.delete("/{client_id}", response_model=Client)
def deactivate_client(
    client_id: str,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Soft-delete: desactiva el cliente."""
    c = session.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    c.is_active = False
    c.updated_at = datetime.utcnow()
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


# ============================================================
# CLIENT CONFIG (sub-resource)
# ============================================================

def _get_client_and_config(client_id: str, session: Session):
    c = session.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    config = session.exec(
        select(ClientConfig).where(ClientConfig.client_id == client_id)
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="ClientConfig not found")
    return c, config


@router.get("/{client_id}/config", response_model=ClientConfig)
def get_client_config(
    client_id: str,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Devuelve la ClientConfig del cliente indicado."""
    _, config = _get_client_and_config(client_id, session)
    return config


@router.put("/{client_id}/config", response_model=ClientConfig)
def update_client_config(
    client_id: str,
    patch: dict,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Actualización parcial de la ClientConfig de un cliente."""
    _, config = _get_client_and_config(client_id, session)

    allowed_fields = {
        "stt_language", "stt_model", "stt_vad_thold",
        "tts_voice", "tts_speed", "preferred_model_id",
        "system_prompt_extra", "barge_in_enabled",
        "barge_in_min_chars", "conversation_memory_limit",
    }
    unknown = set(patch.keys()) - allowed_fields
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Campos no permitidos: {unknown}",
        )
    for field, value in patch.items():
        setattr(config, field, value)
    config.updated_at = datetime.utcnow()

    session.add(config)
    session.commit()
    session.refresh(config)
    return config


@router.post("/{client_id}/config/reset", response_model=ClientConfig)
def reset_client_config(
    client_id: str,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Restaura la ClientConfig del cliente a los valores por defecto."""
    _, config = _get_client_and_config(client_id, session)

    config.stt_language = "es"
    config.stt_model = None
    config.stt_vad_thold = 0.0
    config.tts_voice = "af_heart"
    config.tts_speed = 1.0
    config.preferred_model_id = None
    config.system_prompt_extra = None
    config.barge_in_enabled = True
    config.barge_in_min_chars = 5
    config.conversation_memory_limit = 20
    config.updated_at = datetime.utcnow()

    session.add(config)
    session.commit()
    session.refresh(config)
    return config
