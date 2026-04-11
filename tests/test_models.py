from datetime import datetime
from sqlmodel import select, Session
from src.core.models import (
    InternalService,
    OrchestratorConfig, TranscriberConfig, SpeakerConfig,
    GatewayConfig, InferenceCenterConfig,
    InferenceProvider, ProviderType, AdminUser,
)


def _make_service(session: Session, id: str) -> InternalService:
    svc = InternalService(id=id, api_key="key", is_active=True)
    session.add(svc)
    session.flush()
    return svc


def test_orchestrator_config_create(session):
    svc = _make_service(session, "orch-1")
    cfg = OrchestratorConfig(service_id=svc.id)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)

    result = session.exec(
        select(OrchestratorConfig).where(OrchestratorConfig.service_id == svc.id)
    ).first()
    assert result is not None
    assert result.default_provider_id is None
    assert result.fallback_provider_id is None


def test_transcriber_config_defaults(session):
    svc = _make_service(session, "trans-1")
    cfg = TranscriberConfig(service_id=svc.id)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)

    assert cfg.model == "whisper-large-v3"
    assert cfg.audio_chunk_ms == 200


def test_speaker_config_defaults(session):
    svc = _make_service(session, "spk-1")
    cfg = SpeakerConfig(service_id=svc.id)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)

    assert cfg.model == "kokoro-v1"


def test_gateway_config_create(session):
    svc = _make_service(session, "gw-1")
    cfg = GatewayConfig(service_id=svc.id)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)

    result = session.get(GatewayConfig, cfg.id)
    assert result is not None
    assert result.service_id == svc.id


def test_inference_center_config_create(session):
    svc = _make_service(session, "inf-1")
    cfg = InferenceCenterConfig(service_id=svc.id)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)

    result = session.get(InferenceCenterConfig, cfg.id)
    assert result is not None
    assert result.service_id == svc.id


def test_service_config_unique_per_service(session):
    """Cada servicio solo puede tener una config (unique constraint en service_id)."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    svc = _make_service(session, "orch-unique")
    session.add(OrchestratorConfig(service_id=svc.id))
    session.commit()

    with pytest.raises(IntegrityError):
        session.add(OrchestratorConfig(service_id=svc.id))
        session.commit()


# ---- Tests de InferenceProvider y AdminUser (sin cambios) ----

def test_inference_provider_create(session):
    p = InferenceProvider(
        name="Local llama.cpp",
        type=ProviderType.local,
        base_url="ws://jota-inference:8002",
        default_model_id="llama-3.2-3b",
    )
    session.add(p)
    session.commit()
    session.refresh(p)

    assert p.id is not None
    assert p.is_active is True
    assert p.type == ProviderType.local


def test_inference_provider_soft_delete(session):
    p = InferenceProvider(name="OpenAI", type=ProviderType.openai, api_key="sk-test")
    session.add(p)
    session.commit()
    session.refresh(p)

    p.is_active = False
    session.add(p)
    session.commit()

    result = session.get(InferenceProvider, p.id)
    assert result.is_active is False


def test_admin_user_create(session):
    admin = AdminUser(id="admin", api_key="super-secret", is_active=True)
    session.add(admin)
    session.commit()

    result = session.get(AdminUser, "admin")
    assert result is not None
    assert result.api_key == "super-secret"