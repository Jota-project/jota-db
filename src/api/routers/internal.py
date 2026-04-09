"""
Router /internal/ — acceso de servicios internos a config operativa.
Auth: Bearer <API_SECRET_KEY> + X-API-Key: <service_api_key>
"""
from datetime import datetime
from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from src.core.database import get_session
from src.core.models import (
    InferenceProvider, ServiceConfig, ClientConfig, Client, InternalService
)
from src.api.dependencies import get_internal_service
from src.api.security import verify_api_key

router = APIRouter(
    prefix="/internal",
    tags=["Internal"],
    responses={
        401: {"description": "Bearer token inválido o X-API-Key de servicio no reconocida"},
        403: {"description": "Servicio inactivo"},
    },
)


# --- DTOs ---

class ServiceConfigUpsert(BaseModel):
    value: Any = Field(description="Valor a almacenar (cualquier tipo JSON: string, número, bool, objeto, array)")
    description: Optional[str] = Field(None, description="Descripción legible del campo (se actualiza solo si se envía)")


# ============================================================
# SERVICE CONFIG
# ============================================================

@router.get("/service-config", response_model=List[ServiceConfig])
def list_service_config(
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Lista toda la ServiceConfig del sistema.

    Devuelve las entradas de configuración de **todos** los servicios.
    El acceso cross-service es intencional: el Orchestrator necesita leer
    la config de Transcriptor, Speaker, etc. para orquestar el pipeline.
    """
    return session.exec(select(ServiceConfig)).all()


@router.get("/service-config/{service_name}", response_model=List[ServiceConfig])
def get_service_config(
    service_name: str = Path(description="Nombre del servicio (ej: `transcriber`, `speaker`, `orchestrator`)"),
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Lista la ServiceConfig de un servicio concreto.

    Devuelve todas las claves de configuración del servicio indicado.
    Retorna lista vacía si el servicio no tiene entradas.
    """
    return session.exec(
        select(ServiceConfig).where(ServiceConfig.service == service_name)
    ).all()


@router.put("/service-config/{service_name}/{key}", response_model=ServiceConfig)
def upsert_service_config(
    service_name: str = Path(description="Nombre del servicio propietario de la clave"),
    key: str = Path(description="Nombre de la clave (soporta notación punto, ej: `audio.chunk_ms`)"),
    body: ServiceConfigUpsert = ...,
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Crea o actualiza una entrada de ServiceConfig.

    Si la clave `{service_name}/{key}` ya existe la sobreescribe; si no, la crea.
    El campo `description` solo se actualiza si se incluye en el body.
    """
    entry = session.exec(
        select(ServiceConfig).where(
            ServiceConfig.service == service_name, ServiceConfig.key == key
        )
    ).first()
    if entry:
        entry.value = body.value
        if body.description is not None:
            entry.description = body.description
        entry.updated_at = datetime.utcnow()
    else:
        entry = ServiceConfig(
            service=service_name,
            key=key,
            value=body.value,
            description=body.description,
        )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.delete(
    "/service-config/{service_name}/{key}",
    status_code=204,
    responses={404: {"description": "Entrada de configuración no encontrada"}},
)
def delete_service_config(
    service_name: str = Path(description="Nombre del servicio propietario de la clave"),
    key: str = Path(description="Nombre de la clave a eliminar"),
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Elimina una entrada de ServiceConfig.

    Retorna 204 sin cuerpo si la operación fue exitosa.
    Retorna 404 si la clave no existe.
    """
    entry = session.exec(
        select(ServiceConfig).where(
            ServiceConfig.service == service_name, ServiceConfig.key == key
        )
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Config entry not found")
    session.delete(entry)
    session.commit()


# ============================================================
# INFERENCE PROVIDERS
# ============================================================

@router.get("/providers", response_model=List[InferenceProvider])
def list_active_providers(
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Lista los InferenceProviders activos.

    Solo devuelve providers con `is_active=true`. Los providers desactivados
    por un admin no aparecen aquí. Usado por el Orchestrator para seleccionar
    a qué backend de inferencia enrutar las peticiones.
    """
    return session.exec(
        select(InferenceProvider).where(InferenceProvider.is_active == True)  # noqa: E712
    ).all()


@router.get(
    "/providers/{provider_id}",
    response_model=InferenceProvider,
    responses={404: {"description": "Provider no encontrado"}},
)
def get_provider(
    provider_id: str = Path(description="UUID del InferenceProvider"),
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Detalle de un InferenceProvider por ID.

    Devuelve el provider independientemente de si está activo o no.
    Útil para que el Orchestrator resuelva el provider referenciado en ServiceConfig.
    """
    provider = session.get(InferenceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


# ============================================================
# CLIENT CONFIG
# ============================================================

@router.get(
    "/client-config/{client_id}",
    response_model=ClientConfig,
    responses={404: {"description": "Cliente o ClientConfig no encontrado"}},
)
def get_client_config(
    client_id: str = Path(description="ID del cliente objetivo"),
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Devuelve la ClientConfig de un cliente.

    Permite al Orchestrator (y otros servicios internos) leer las preferencias
    de un cliente concreto: idioma STT, voz TTS, modelo preferido, barge-in, etc.
    """
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    config = session.exec(
        select(ClientConfig).where(ClientConfig.client_id == client_id)
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="ClientConfig not found")
    return config


@router.put(
    "/client-config/{client_id}",
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
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Actualización parcial de la ClientConfig de un cliente.

    Solo se actualizan los campos enviados en el body. Campos permitidos:
    `stt_language`, `stt_model`, `stt_vad_thold`, `tts_voice`, `tts_speed`,
    `preferred_model_id`, `system_prompt_extra`, `barge_in_enabled`,
    `barge_in_min_chars`, `conversation_memory_limit`.

    Retorna 422 si se envía algún campo fuera de la lista permitida.
    """
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    config = session.exec(
        select(ClientConfig).where(ClientConfig.client_id == client_id)
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="ClientConfig not found")

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

    session.add(config)
    session.commit()
    session.refresh(config)
    return config
