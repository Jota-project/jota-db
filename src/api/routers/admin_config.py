"""
Router /admin/config/ — gestión admin de ServiceConfig.
Auth: Bearer <API_SECRET_KEY> + X-API-Key: <ADMIN_KEY>
"""
import os
from datetime import datetime
from typing import Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from src.core.database import get_session
from src.core.models import ServiceConfig, InferenceProvider, ProviderType, AdminUser
from src.api.dependencies import get_admin_user
from src.api.security import verify_api_key

router = APIRouter(
    prefix="/admin/config",
    tags=["Admin - Config"],
)


class ServiceConfigUpsert(BaseModel):
    value: Any
    description: Optional[str] = None


@router.get("", response_model=List[ServiceConfig])
def list_all_config(
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Lista toda la configuración de todos los servicios."""
    return session.exec(select(ServiceConfig)).all()


@router.get("/{service_name}", response_model=List[ServiceConfig])
def get_config_by_service(
    service_name: str,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Devuelve todas las claves de config de un servicio."""
    return session.exec(
        select(ServiceConfig).where(ServiceConfig.service == service_name)
    ).all()


@router.put("/{service_name}/{key}", response_model=ServiceConfig)
def upsert_config(
    service_name: str,
    key: str,
    body: ServiceConfigUpsert,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
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
            service=service_name, key=key,
            value=body.value, description=body.description,
        )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.delete("/{service_name}/{key}", status_code=204)
def delete_config(
    service_name: str,
    key: str,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
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


def _seed_service_entries_for(service_name: str, session: Session) -> List[ServiceConfig]:
    """Re-genera las entradas de un servicio desde las vars de entorno actuales."""
    # Borrar entradas actuales del servicio
    existing = session.exec(
        select(ServiceConfig).where(ServiceConfig.service == service_name)
    ).all()
    for e in existing:
        session.delete(e)
    session.flush()

    entries = []

    if service_name == "transcriber":
        entries.append(ServiceConfig(
            service="transcriber", key="model",
            value=os.getenv("SEED_TRANSCRIBER_MODEL", "whisper-large-v3"),
            description="Modelo de Whisper a usar",
        ))
        entries.append(ServiceConfig(
            service="transcriber", key="audio.chunk_ms",
            value=int(os.getenv("SEED_TRANSCRIBER_AUDIO_CHUNK_MS", "200")),
            description="Tamaño de chunk de audio en ms",
        ))

    elif service_name == "speaker":
        entries.append(ServiceConfig(
            service="speaker", key="model",
            value=os.getenv("SEED_SPEAKER_MODEL", "kokoro-v1"),
            description="Modelo TTS a usar",
        ))

    elif service_name == "orchestrator":
        local_provider = session.exec(
            select(InferenceProvider).where(InferenceProvider.type == ProviderType.local)
        ).first()
        entries.append(ServiceConfig(
            service="orchestrator", key="default_provider_id",
            value=local_provider.id if local_provider else None,
            description="UUID del InferenceProvider por defecto",
        ))
        entries.append(ServiceConfig(
            service="orchestrator", key="fallback_provider_id",
            value=None,
            description="UUID del InferenceProvider de fallback",
        ))

    for e in entries:
        session.add(e)
    session.commit()
    for e in entries:
        session.refresh(e)
    return entries


@router.post("/{service_name}/reset", response_model=List[ServiceConfig])
def reset_service_config(
    service_name: str,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Restaura la configuración de un servicio a los defaults de las vars de entorno."""
    return _seed_service_entries_for(service_name, session)
