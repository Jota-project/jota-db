"""
Router /admin/ — gestión administrativa del sistema.
Auth: Bearer <API_SECRET_KEY> + X-API-Key: <ADMIN_KEY>
"""
from fastapi import APIRouter

from . import config, providers, clients, services

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    responses={
        401: {"description": "Bearer token inválido o ADMIN_KEY incorrecta"},
        403: {"description": "Admin inactivo"},
    },
)

router.include_router(config.router)
router.include_router(providers.router)
router.include_router(clients.router)
router.include_router(services.router)
