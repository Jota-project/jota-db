from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from src.core.database import get_session
from src.core.models import Client, ClientConfig
from src.api.dependencies import get_current_client
from src.api.security import verify_api_key

router = APIRouter(
    prefix="/config",
    tags=["Config"],
    responses={404: {"description": "Not found"}}
)

def _get_or_create_config(client: Client, session: Session) -> ClientConfig:
    config = session.exec(select(ClientConfig).where(ClientConfig.client_id == client.id)).first()
    if not config:
        config = ClientConfig(client_id=client.id)
        session.add(config)
        session.commit()
        session.refresh(config)
    return config


@router.get("/me", response_model=ClientConfig)
def get_my_config(
    client: Client = Depends(get_current_client),
    session: Session = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Devuelve la configuración del cliente autenticado."""
    return _get_or_create_config(client, session)


@router.put("/me", response_model=ClientConfig)
def update_my_config(
    patch: dict,
    client: Client = Depends(get_current_client),
    session: Session = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Actualiza parcialmente la configuración del cliente autenticado."""
    config = _get_or_create_config(client, session)

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
            detail=f"Campos no permitidos: {unknown}"
        )

    for field, value in patch.items():
        setattr(config, field, value)

    session.add(config)
    session.commit()
    session.refresh(config)
    return config


@router.post("/me/reset", response_model=ClientConfig)
def reset_my_config(
    client: Client = Depends(get_current_client),
    session: Session = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Restaura la configuración del cliente autenticado a los valores por defecto."""
    config = _get_or_create_config(client, session)

    config.stt_language = "es"
    config.stt_model = None
    config.stt_vad_thold = 0.0
    config.tts_voice = "af_heart"
    config.tts_speed = 1.0
    config.preferred_model_id = None
    config.system_prompt_extra = None
    config.barge_in_enabled = True
    config.barge_in_min_chars = 5
    config.conversation_memory_limit = 20

    session.add(config)
    session.commit()
    session.refresh(config)
    return config
