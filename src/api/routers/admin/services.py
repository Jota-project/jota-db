"""
Sub-router /admin/services/ — gestión de InternalService.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from src.core.database import get_session
from src.core.models import InternalService, AdminUser
from src.api.dependencies import get_admin_user
from src.api.security import verify_api_key

router = APIRouter(prefix="/services")


class ServiceCreate(BaseModel):
    id: str = Field(description="ID único del servicio (ej: `JotaOrchestrator`, `Transcriptor`). Debe coincidir con `INTERNAL_*_ID` en el entorno del servicio")
    api_key: str = Field(description="API key que usará el servicio en `X-API-Key`")


class ServiceUpdate(BaseModel):
    api_key: Optional[str] = Field(None, description="Nueva API key (rotación de credencial)")
    is_active: Optional[bool] = Field(None, description="Activar (`true`) o desactivar (`false`) el servicio")


@router.get("", response_model=List[InternalService])
def list_services(
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Lista todos los servicios internos.

    Incluye servicios activos e inactivos.
    """
    return session.exec(select(InternalService)).all()


@router.post(
    "",
    response_model=InternalService,
    status_code=201,
    responses={409: {"description": "El ID de servicio ya existe"}},
)
def create_service(
    body: ServiceCreate,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Registra un nuevo servicio interno.

    Retorna 409 si ya existe un servicio con el mismo ID.
    El servicio se crea activo por defecto.
    """
    existing = session.get(InternalService, body.id)
    if existing:
        raise HTTPException(status_code=409, detail="Service ID already exists")
    svc = InternalService(id=body.id, api_key=body.api_key, is_active=True)
    session.add(svc)
    session.commit()
    session.refresh(svc)
    return svc


@router.get(
    "/{service_id}",
    response_model=InternalService,
    responses={404: {"description": "Servicio no encontrado"}},
)
def get_service(
    service_id: str = Path(description="ID del servicio interno"),
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Detalle de un servicio interno por ID."""
    svc = session.get(InternalService, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return svc


@router.put(
    "/{service_id}",
    response_model=InternalService,
    responses={404: {"description": "Servicio no encontrado"}},
)
def update_service(
    service_id: str = Path(description="ID del servicio interno a actualizar"),
    body: ServiceUpdate = ...,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Actualiza un servicio interno.

    Útil para rotación de API key (`{"api_key": "nueva_key"}`) o para
    activar/desactivar el servicio (`{"is_active": false}`).
    Solo se actualizan los campos incluidos en el body.
    """
    svc = session.get(InternalService, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    patch = body.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(svc, field, value)
    svc.updated_at = datetime.utcnow()

    session.add(svc)
    session.commit()
    session.refresh(svc)
    return svc


@router.delete(
    "/{service_id}",
    response_model=InternalService,
    responses={404: {"description": "Servicio no encontrado"}},
)
def deactivate_service(
    service_id: str = Path(description="ID del servicio interno a desactivar"),
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Desactiva un servicio interno (soft-delete).

    Marca el servicio como `is_active=false`. El servicio dejará de poder
    autenticarse en los endpoints `/internal/`. El registro se conserva en DB.
    """
    svc = session.get(InternalService, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    svc.is_active = False
    svc.updated_at = datetime.utcnow()
    session.add(svc)
    session.commit()
    session.refresh(svc)
    return svc
