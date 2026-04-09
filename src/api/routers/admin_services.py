"""
Router /admin/services/ — gestión admin de InternalService.
Auth: Bearer <API_SECRET_KEY> + X-API-Key: <ADMIN_KEY>
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from src.core.database import get_session
from src.core.models import InternalService, AdminUser
from src.api.dependencies import get_admin_user
from src.api.security import verify_api_key

router = APIRouter(
    prefix="/admin/services",
    tags=["Admin - Services"],
)


class ServiceCreate(BaseModel):
    id: str
    api_key: str


class ServiceUpdate(BaseModel):
    api_key: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("", response_model=List[InternalService])
def list_services(
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Lista todos los servicios internos."""
    return session.exec(select(InternalService)).all()


@router.post("", response_model=InternalService, status_code=201)
def create_service(
    body: ServiceCreate,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Registra un nuevo servicio interno."""
    existing = session.get(InternalService, body.id)
    if existing:
        raise HTTPException(status_code=409, detail="Service ID already exists")
    svc = InternalService(id=body.id, api_key=body.api_key, is_active=True)
    session.add(svc)
    session.commit()
    session.refresh(svc)
    return svc


@router.get("/{service_id}", response_model=InternalService)
def get_service(
    service_id: str,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Detalle de un servicio interno."""
    svc = session.get(InternalService, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return svc


@router.put("/{service_id}", response_model=InternalService)
def update_service(
    service_id: str,
    body: ServiceUpdate,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Actualiza un servicio interno (key rotation, activar/desactivar)."""
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


@router.delete("/{service_id}", response_model=InternalService)
def deactivate_service(
    service_id: str,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Soft-delete: desactiva el servicio."""
    svc = session.get(InternalService, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    svc.is_active = False
    svc.updated_at = datetime.utcnow()
    session.add(svc)
    session.commit()
    session.refresh(svc)
    return svc
