"""
Router /admin/providers/ — gestión admin de InferenceProvider.
Auth: Bearer <API_SECRET_KEY> + X-API-Key: <ADMIN_KEY>
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from src.core.database import get_session
from src.core.models import InferenceProvider, ProviderType, AdminUser
from src.api.dependencies import get_admin_user
from src.api.security import verify_api_key

router = APIRouter(
    prefix="/admin/providers",
    tags=["Admin - Providers"],
)


class ProviderCreate(BaseModel):
    name: str
    type: ProviderType
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_model_id: Optional[str] = None
    extra_config: Optional[dict] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_model_id: Optional[str] = None
    is_active: Optional[bool] = None
    extra_config: Optional[dict] = None


@router.get("", response_model=List[InferenceProvider])
def list_providers(
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Lista todos los providers (activos e inactivos)."""
    return session.exec(select(InferenceProvider)).all()


@router.post("", response_model=InferenceProvider, status_code=201)
def create_provider(
    body: ProviderCreate,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Crea un nuevo InferenceProvider."""
    provider = InferenceProvider(**body.model_dump())
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider


@router.get("/{provider_id}", response_model=InferenceProvider)
def get_provider(
    provider_id: str,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Detalle de un provider."""
    provider = session.get(InferenceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.put("/{provider_id}", response_model=InferenceProvider)
def update_provider(
    provider_id: str,
    body: ProviderUpdate,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Actualización parcial de un provider."""
    provider = session.get(InferenceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    patch = body.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(provider, field, value)
    provider.updated_at = datetime.utcnow()

    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider


@router.delete("/{provider_id}", response_model=InferenceProvider)
def deactivate_provider(
    provider_id: str,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Soft-delete: desactiva el provider (is_active=False)."""
    provider = session.get(InferenceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.is_active = False
    provider.updated_at = datetime.utcnow()
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider
