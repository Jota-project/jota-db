"""
Sub-router /admin/providers/ — gestión de InferenceProvider.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from src.core.database import get_session
from src.core.models import InferenceProvider, ProviderType, AdminUser
from src.api.dependencies import get_admin_user
from src.api.security import verify_api_key

router = APIRouter(prefix="/providers")


class ProviderCreate(BaseModel):
    name: str = Field(description="Nombre legible del provider (ej: `Local LLM`, `OpenAI`)")
    type: ProviderType = Field(description="Tipo de provider: `local`, `openai` o `anthropic`")
    base_url: Optional[str] = Field(None, description="URL base del endpoint (requerido para `local`; ignorado en OpenAI/Anthropic)")
    api_key: Optional[str] = Field(None, description="API key del proveedor externo (requerido para `openai` y `anthropic`)")
    default_model_id: Optional[str] = Field(None, description="Modelo por defecto a usar con este provider (ej: `gpt-4o`, `claude-sonnet-4-6`)")
    extra_config: Optional[dict] = Field(None, description="Configuración adicional en formato JSON libre")


class ProviderUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Nuevo nombre legible")
    base_url: Optional[str] = Field(None, description="Nueva URL base del endpoint")
    api_key: Optional[str] = Field(None, description="Nueva API key (rotación de credencial)")
    default_model_id: Optional[str] = Field(None, description="Nuevo modelo por defecto")
    is_active: Optional[bool] = Field(None, description="Activar (`true`) o desactivar (`false`) el provider")
    extra_config: Optional[dict] = Field(None, description="Nueva configuración adicional")


@router.get("", response_model=List[InferenceProvider])
def list_providers(
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Lista todos los InferenceProviders.

    Incluye tanto activos como inactivos (soft-deleted). Para ver solo los
    activos usar el endpoint `/internal/providers`.
    """
    return session.exec(select(InferenceProvider)).all()


@router.post("", response_model=InferenceProvider, status_code=201)
def create_provider(
    body: ProviderCreate,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Crea un nuevo InferenceProvider.

    El provider se crea activo por defecto. El ID se genera automáticamente (UUID).
    """
    provider = InferenceProvider(**body.model_dump())
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider


@router.get(
    "/{provider_id}",
    response_model=InferenceProvider,
    responses={404: {"description": "Provider no encontrado"}},
)
def get_provider(
    provider_id: str = Path(description="UUID del InferenceProvider"),
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Detalle de un InferenceProvider por ID."""
    provider = session.get(InferenceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.put(
    "/{provider_id}",
    response_model=InferenceProvider,
    responses={404: {"description": "Provider no encontrado"}},
)
def update_provider(
    provider_id: str = Path(description="UUID del InferenceProvider a actualizar"),
    body: ProviderUpdate = ...,
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Actualización parcial de un InferenceProvider.

    Solo se actualizan los campos incluidos en el body.
    Para rotar la API key enviar solo `{"api_key": "nueva_key"}`.
    Para reactivar un provider desactivado enviar `{"is_active": true}`.
    """
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


@router.delete(
    "/{provider_id}",
    response_model=InferenceProvider,
    responses={404: {"description": "Provider no encontrado"}},
)
def deactivate_provider(
    provider_id: str = Path(description="UUID del InferenceProvider a desactivar"),
    _: bool = Depends(verify_api_key),
    admin: AdminUser = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    """Desactiva un InferenceProvider (soft-delete).

    Marca el provider como `is_active=false`. No elimina el registro de la base
    de datos. El provider dejará de aparecer en `/internal/providers` pero
    seguirá siendo recuperable por ID desde `/admin/providers/{id}`.

    Para eliminarlo permanentemente se requeriría acceso directo a la DB.
    """
    provider = session.get(InferenceProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.is_active = False
    provider.updated_at = datetime.utcnow()
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider
