"""
Router /internal/ — acceso de servicios internos a config operativa.
Auth: Bearer <API_SECRET_KEY> + X-API-Key: <service_api_key>
"""
import os
from datetime import datetime
from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel
from sqlmodel import Session, select

from src.core.database import get_session
from src.core.models import (
    InferenceProvider, ClientConfig, Client, InternalService,
    OrchestratorConfig, TranscriberConfig, SpeakerConfig,
    GatewayConfig, InferenceCenterConfig,
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


# ---- Dispatch ----

# Mapa estático service_id → clase de config.
# Se evalúa una vez al arrancar; load_dotenv() ya corrió antes.
CONFIG_TABLE_MAP: dict[str, type] = {k: v for k, v in {
    "orchestrator": OrchestratorConfig,
    "transcriptor": TranscriberConfig,
    "speaker":      SpeakerConfig,
    "gateway":      GatewayConfig,
    os.getenv("INTERNAL_INFERENCE_ID"):    InferenceCenterConfig,
}.items() if k is not None}

# Campos de BaseUUIDModel que no se exponen en el patch ni en la respuesta config
_BASE_FIELDS = {"id", "created_at", "updated_at", "version", "service_id"}


def _get_config_for_service(service_id: str, session: Session):
    """Devuelve la instancia de config para service_id, o None si no existe."""
    config_cls = CONFIG_TABLE_MAP.get(service_id)
    if config_cls is None:
        return None
    return session.exec(
        select(config_cls).where(config_cls.service_id == service_id)
    ).first()


# ---- DTOs ----

class ServiceConfigEntry(BaseModel):
    service_id: str
    config: dict


# ============================================================
# SERVICE CONFIG
# ============================================================

@router.get("/service-config", response_model=List[ServiceConfigEntry])
def list_service_config(
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Lista la config de todos los servicios internos conocidos.

    Solo incluye los servicios que tienen un registro de config en DB.
    """
    result = []
    for service_id in CONFIG_TABLE_MAP:
        cfg = _get_config_for_service(service_id, session)
        if cfg is not None:
            result.append(ServiceConfigEntry(
                service_id=service_id,
                config=cfg.model_dump(exclude=_BASE_FIELDS),
            ))
    return result


@router.get(
    "/service-config/{service_id}",
    responses={404: {"description": "Servicio desconocido o sin config"}},
)
def get_service_config(
    service_id: str = Path(description="ID del servicio (ej: 'jota_orchestrator', 'transcriptor')"),
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Config completa de un servicio concreto.

    Devuelve el objeto tipado del servicio (OrchestratorConfig, TranscriberConfig, etc.).
    404 si el service_id no corresponde a ningún servicio conocido o no tiene config aún.
    """
    cfg = _get_config_for_service(service_id, session)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Service config not found")
    return cfg


@router.put(
    "/service-config/{service_id}",
    responses={
        404: {"description": "Servicio desconocido o sin config"},
        422: {"description": "Campo no permitido para este servicio"},
    },
)
def update_service_config(
    service_id: str = Path(description="ID del servicio a actualizar"),
    patch: dict = ...,
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Actualización parcial de la config de un servicio.

    Solo se actualizan los campos enviados. Los campos base (id, created_at,
    updated_at, version, service_id) no se pueden modificar.
    422 si se envía un campo fuera del schema del servicio.
    """
    config_cls = CONFIG_TABLE_MAP.get(service_id)
    if config_cls is None:
        raise HTTPException(status_code=404, detail="Unknown service")

    cfg = session.exec(
        select(config_cls).where(config_cls.service_id == service_id)
    ).first()
    if cfg is None:
        raise HTTPException(status_code=404, detail="Service config not found")

    allowed_fields = set(config_cls.model_fields.keys()) - _BASE_FIELDS
    unknown = set(patch.keys()) - allowed_fields
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Campos no permitidos para {service_id}: {unknown}",
        )

    for field, value in patch.items():
        setattr(cfg, field, value)
    cfg.updated_at = datetime.utcnow()

    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


# ============================================================
# INFERENCE PROVIDERS
# ============================================================

@router.get("/providers", response_model=List[InferenceProvider])
def list_active_providers(
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Lista los InferenceProviders activos."""
    return session.exec(
        select(InferenceProvider).where(InferenceProvider.is_active == True)  # noqa: E712
    ).all()


@router.get(
    "/providers/{provider_id}",
    response_model=InferenceProvider,
    responses={404: {"description": "Provider no encontrado"}},
)
def get_provider(
    provider_id: str = Path(description="Slug del InferenceProvider (ej: `local`, `openai`)"),
    _: bool = Depends(verify_api_key),
    caller: InternalService = Depends(get_internal_service),
    session: Session = Depends(get_session),
):
    """Detalle de un InferenceProvider por ID."""
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
    """Devuelve la ClientConfig de un cliente."""
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