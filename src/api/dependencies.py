
from fastapi import Header, HTTPException, Depends, status
from sqlmodel import Session, select
from typing import Optional

from src.core.database import get_session
from src.core.models import Client, InternalService, AdminUser

def get_current_client(
    x_api_key: str = Header(..., description="API Key for authentication"),
    x_client_id: Optional[str] = Header(None, description="Target Client ID (Required for Service Access)"),
    session: Session = Depends(get_session)
) -> Client:
    """
    Authenticates the request based on X-API-Key and optionally X-Client-ID.
    
    Logic:
    1. Check if X-API-Key belongs to a Client (Direct Access).
    2. Check if X-API-Key belongs to an InternalService (Service Access).
       - If Service Access, X-Client-ID IS REQUIRED to identify the target client.
    """
    
    # 1. Try Direct Client Access
    statement = select(Client).where(Client.client_key == x_api_key)
    client = session.exec(statement).first()
    
    if client:
        if not client.is_active:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Client is inactive"
            )
        
        # If X-Client-ID provides, verify it matches (prevent spoofing oneself?)
        # Actually, if they key identifies them, X-Client-ID is redundant but must not conflict.
        if x_client_id and str(client.id) != x_client_id:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API Key does not match provided Client ID"
            )
            
        return client

    # 2. Try Service Access (e.g. Orchestrator acting on behalf of a client)
    statement = select(InternalService).where(InternalService.api_key == x_api_key)
    service = session.exec(statement).first()
    
    if service:
        if not service.is_active:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Service is inactive"
            )
            
        if not x_client_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Client-ID header is required for service access"
            )
            
        # Fetch the target client
        target_client = session.get(Client, x_client_id)
        if not target_client:
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target Client not found"
            )
            
        if not target_client.is_active:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Target Client is inactive"
            )
            
        return target_client
        
    # 3. Auth Failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key"
    )

def get_internal_service(
    x_api_key: str = Header(..., description="API Key for internal service authentication"),
    session: Session = Depends(get_session)
) -> InternalService:
    """Authenticates internal services (Orchestrator, InferenceCenter, Transcriptor, etc.)."""
    statement = select(InternalService).where(InternalService.api_key == x_api_key)
    service = session.exec(statement).first()
    
    if not service:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service API Key"
        )
        
    if not service.is_active:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service is inactive"
        )
        
    return service

def get_any_authenticated_caller(
    x_api_key: str = Header(..., description="API Key for authentication"),
    session: Session = Depends(get_session)
):
    """
    Authenticates the request based on X-API-Key.
    Allows BOTH direct clients and internal services, without requiring x-client-id.
    Useful for global endpoints like listing AI models.
    """
    # 1. Try Direct Client Access
    statement = select(Client).where(Client.client_key == x_api_key)
    client = session.exec(statement).first()

    if client:
        if not client.is_active:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Client is inactive"
            )
        return client

    # 2. Try Service Access
    statement = select(InternalService).where(InternalService.api_key == x_api_key)
    service = session.exec(statement).first()

    if service:
        if not service.is_active:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Service is inactive"
            )
        return service

    # 3. Auth Failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key"
    )

def get_admin_user(
    x_api_key: str = Header(..., description="Admin API Key"),
    session: Session = Depends(get_session),
) -> AdminUser:
    """Authenticates the system admin via X-API-Key against AdminUser.api_key in DB."""
    admin = session.get(AdminUser, "admin")
    if not admin or admin.api_key != x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key",
        )
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin user is inactive",
        )
    return admin
