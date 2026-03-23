from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlmodel import Session, select
from typing import Optional

from src.core.database import get_session
from src.core.models import InternalService, Client
from src.api.security import verify_api_key

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
    responses={404: {"description": "Not found"}}
)

@router.get("/internal", response_model=InternalService)
def validate_internal_client(
    x_service_id: str = Header(..., alias="X-Service-ID", description="Service Identifier"),
    x_api_key: str = Header(..., alias="X-API-Key", description="Service API Key"),
    session: Session = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """
    Valida un servicio interno (ej: JotaOrchestrator) para permitir el uso del motor de C++.
    Requires Bearer token + X-Service-ID + X-API-Key headers.
    """
    statement = select(InternalService).where(InternalService.id == x_service_id)
    client = session.exec(statement).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Client not found"
        )
        
    # TODO: Implementar hash comparison seguro. Por ahora texto plano según requisitos.
    if client.api_key != x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid API Key"
        )
        
    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Client is inactive"
        )
        
    return client

@router.get("/client", response_model=Client)
def validate_external_client(
    x_api_key: str = Header(..., alias="X-API-Key", description="Desktop Client Key"),
    session: Session = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """
    Valida un cliente externo (ej: JotaDesktop) para permitir la conexión al Orquestador.
    Requires Bearer token + X-API-Key header.
    """
    statement = select(Client).where(Client.client_key == x_api_key)
    client = session.exec(statement).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Client not found"
        )
        
    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Client is inactive"
        )
        
    return client
