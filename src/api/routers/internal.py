"""
Router /internal/ — acceso de servicios internos a config operativa.
Auth: Bearer <API_SECRET_KEY> + X-API-Key: <service_api_key>
"""
from datetime import datetime
from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
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
    responses={401: {"description": "Unauthorized"}},
)


# --- DTOs ---

class ServiceConfigUpsert(BaseModel):
    value: Any
    description: Optional[str] = None


# ============================================================
# SERVICE CONFIG
# ============================================================

@router.get("/service-config", response_model=List[ServiceConfig])
def list_service_config(
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Lista toda la configuración de servicios (acceso cross-service intencional: el Orchestrator lee config de todos)."""
    return session.exec(select(ServiceConfig)).all()


@router.get("/service-config/{service_name}", response_model=List[ServiceConfig])
def get_service_config(
    service_name: str,
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Devuelve todas las claves de config de un servicio concreto."""
    return session.exec(
        select(ServiceConfig).where(ServiceConfig.service == service_name)
    ).all()


@router.put("/service-config/{service_name}/{key}", response_model=ServiceConfig)
def upsert_service_config(
    service_name: str,
    key: str,
    body: ServiceConfigUpsert,
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Crea o actualiza un valor de configuración."""
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


@router.delete("/service-config/{service_name}/{key}", status_code=204)
def delete_service_config(
    service_name: str,
    key: str,
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Elimina una entrada de configuración."""
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
    """Lista solo los InferenceProviders activos."""
    return session.exec(
        select(InferenceProvider).where(InferenceProvider.is_active == True)  # noqa: E712
    ).all()


@router.get("/providers/{provider_id}", response_model=InferenceProvider)
def get_provider(
    provider_id: str,
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Detalle de un InferenceProvider."""
    provider = session.get(InferenceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


# ============================================================
# CLIENT CONFIG
# ============================================================

@router.get("/client-config/{client_id}", response_model=ClientConfig)
def get_client_config(
    client_id: str,
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Devuelve la ClientConfig del cliente indicado."""
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    config = session.exec(
        select(ClientConfig).where(ClientConfig.client_id == client_id)
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="ClientConfig not found")
    return config


@router.put("/client-config/{client_id}", response_model=ClientConfig)
def update_client_config(
    client_id: str,
    patch: dict,
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Actualización parcial de la ClientConfig de un cliente."""
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
