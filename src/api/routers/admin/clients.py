"""
Sub-router /admin/clients/ — gestión de Client y ClientConfig.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from src.core.database import get_session
from src.core.models import Client, ClientConfig, ClientType, AdminUser
from src.api.dependencies import get_admin_user
from src.api.security import verify_api_key

router = APIRouter(prefix="/clients")


class ClientCreate(BaseModel):
    name: str = Field(description="Nombre único del cliente (se usa también como ID)")
    client_key: str = Field(description="API key que usará el cliente en `X-API-Key`")
    client_type: ClientType = Field(ClientType.CHAT, description="`CHAT` para conversación con historial, `QUICK` para queries sin contexto")


class ClientUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Nuevo nombre del cliente")
    is_active: Optional[bool] = Field(None, description="Activar (`true`) o desactivar (`false`) el cliente")
    client_type: Optional[ClientType] = Field(None, description="Cambiar el tipo de cliente")


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


# ============================================================
# CLIENTS
# ============================================================

@router.get("", response_model=List[Client])
def list_clients(
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Lista todos los clientes.

    Incluye clientes activos e inactivos.
    """
    return session.exec(select(Client)).all()


@router.post("", response_model=Client, status_code=201)
def create_client(
    body: ClientCreate,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Crea un nuevo cliente.

    Crea el `Client` y su `ClientConfig` con valores por defecto automáticamente.
    El campo `name` se usa también como `id` del cliente.
    """
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


@router.get(
    "/{client_id}",
    response_model=Client,
    responses={404: {"description": "Cliente no encontrado"}},
)
def get_client(
    client_id: str = Path(description="ID del cliente"),
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Detalle de un cliente por ID."""
    c = session.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return c


@router.put(
    "/{client_id}",
    response_model=Client,
    responses={404: {"description": "Cliente no encontrado"}},
)
def update_client(
    client_id: str = Path(description="ID del cliente a actualizar"),
    body: ClientUpdate = ...,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Actualización parcial de un cliente.

    Solo se actualizan los campos incluidos en el body.
    """
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


@router.delete(
    "/{client_id}",
    response_model=Client,
    responses={404: {"description": "Cliente no encontrado"}},
)
def deactivate_client(
    client_id: str = Path(description="ID del cliente a desactivar"),
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Desactiva un cliente (soft-delete).

    Marca el cliente como `is_active=false`. El cliente dejará de poder
    autenticarse. Su historial de conversaciones y configuración se conservan.
    """
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

@router.get(
    "/{client_id}/config",
    response_model=ClientConfig,
    responses={404: {"description": "Cliente o ClientConfig no encontrado"}},
)
def get_client_config(
    client_id: str = Path(description="ID del cliente"),
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Devuelve la ClientConfig de un cliente."""
    _, config = _get_client_and_config(client_id, session)
    return config


@router.put(
    "/{client_id}/config",
    response_model=ClientConfig,
    responses={
        404: {"description": "Cliente o ClientConfig no encontrado"},
        422: {"description": "Campo no permitido en el patch"},
    },
)
def update_client_config(
    client_id: str = Path(description="ID del cliente a actualizar"),
    patch: dict = ...,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Actualización parcial de la ClientConfig de un cliente.

    Solo se actualizan los campos incluidos en el body. Campos permitidos:
    `stt_language`, `stt_model`, `stt_vad_thold`, `tts_voice`, `tts_speed`,
    `preferred_model_id`, `system_prompt_extra`, `barge_in_enabled`,
    `barge_in_min_chars`, `conversation_memory_limit`.

    Retorna 422 si se envía algún campo fuera de la lista permitida.
    """
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


@router.post(
    "/{client_id}/config/reset",
    response_model=ClientConfig,
    responses={404: {"description": "Cliente o ClientConfig no encontrado"}},
)
def reset_client_config(
    client_id: str = Path(description="ID del cliente a resetear"),
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Restaura la ClientConfig a los valores por defecto.

    Defaults: `stt_language=es`, `tts_voice=af_heart`, `tts_speed=1.0`,
    `barge_in_enabled=true`, `barge_in_min_chars=5`, `conversation_memory_limit=20`.
    Campos opcionales (`stt_model`, `preferred_model_id`, `system_prompt_extra`) quedan en `null`.
    """
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
