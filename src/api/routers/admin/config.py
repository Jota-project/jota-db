"""
Sub-router /admin/config/ — gestión de configs de servicios internos (acceso admin).
Misma lógica que /internal/service-config pero autenticado con AdminUser.
"""
import os
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlmodel import Session, select

from src.core.database import get_session
from src.core.models import (
    AdminUser, InternalService,
    OrchestratorConfig, TranscriberConfig,
    SpeakerConfig, GatewayConfig, InferenceCenterConfig,
)
from src.api.dependencies import get_admin_user
from src.api.security import verify_api_key

router = APIRouter(prefix="/config")

CONFIG_TABLE_MAP: dict[str, type] = {k: v for k, v in {
    os.getenv("INTERNAL_ORCHESTRATOR_ID"): OrchestratorConfig,
    os.getenv("INTERNAL_TRANSCRIPTOR_ID"): TranscriberConfig,
    os.getenv("INTERNAL_SPEAKER_ID"):      SpeakerConfig,
    os.getenv("INTERNAL_GATEWAY_ID"):      GatewayConfig,
    os.getenv("INTERNAL_INFERENCE_ID"):    InferenceCenterConfig,
}.items() if k is not None}

_BASE_FIELDS = {"id", "created_at", "updated_at", "version", "service_id"}


def _get_config(service_id: str, session: Session):
    config_cls = CONFIG_TABLE_MAP.get(service_id)
    if config_cls is None:
        return None, None
    return config_cls, session.exec(
        select(config_cls).where(config_cls.service_id == service_id)
    ).first()


@router.get("")
def list_all_configs(
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Lista la config de todos los servicios internos conocidos."""
    result = []
    for service_id, config_cls in CONFIG_TABLE_MAP.items():
        cfg = session.exec(
            select(config_cls).where(config_cls.service_id == service_id)
        ).first()
        if cfg is not None:
            result.append({"service_id": service_id, "config": cfg.model_dump(exclude=_BASE_FIELDS)})
    return result


@router.get(
    "/{service_id}",
    responses={404: {"description": "Servicio desconocido o sin config"}},
)
def get_service_config(
    service_id: str = Path(description="ID del servicio (ej: 'JotaOrchestrator')"),
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Config completa de un servicio concreto."""
    _, cfg = _get_config(service_id, session)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Service config not found")
    return cfg


@router.put(
    "/{service_id}",
    responses={
        404: {"description": "Servicio desconocido o sin config"},
        422: {"description": "Campo no permitido para este servicio"},
    },
)
def update_service_config(
    service_id: str = Path(description="ID del servicio a actualizar"),
    patch: dict = ...,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Actualización parcial de la config de un servicio."""
    config_cls, cfg = _get_config(service_id, session)
    if config_cls is None:
        raise HTTPException(status_code=404, detail="Unknown service")
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
