import os
import pytest
from sqlmodel import select, Session
from src.core.models import (
    AdminUser, InferenceProvider, ProviderType,
    InternalService,
    OrchestratorConfig, TranscriberConfig, SpeakerConfig,
    GatewayConfig, InferenceCenterConfig,
)
from src.core.database import bootstrap_admin, seed_inference_providers, seed_service_configs


# ---- Tests de bootstrap_admin (sin cambios) ----

def test_bootstrap_admin_creates_admin(session):
    os.environ["ADMIN_KEY"] = "test-admin-key"
    bootstrap_admin(session)

    admin = session.get(AdminUser, "admin")
    assert admin is not None
    assert admin.api_key == "test-admin-key"
    assert admin.is_active is True


def test_bootstrap_admin_idempotent(session):
    os.environ["ADMIN_KEY"] = "test-admin-key"
    bootstrap_admin(session)
    bootstrap_admin(session)

    results = session.exec(select(AdminUser)).all()
    assert len(results) == 1


def test_bootstrap_admin_skips_if_no_key(session):
    os.environ.pop("ADMIN_KEY", None)
    bootstrap_admin(session)

    admin = session.get(AdminUser, "admin")
    assert admin is None


# ---- Tests de seed_inference_providers (sin cambios) ----

def test_seed_inference_providers_creates_local(session):
    os.environ["SEED_LOCAL_PROVIDER_URL"] = "ws://jota-inference:8002"
    os.environ["SEED_LOCAL_MODEL_ID"] = "llama-3.2-3b"
    os.environ.pop("SEED_OPENAI_API_KEY", None)
    os.environ.pop("SEED_ANTHROPIC_API_KEY", None)

    seed_inference_providers(session)

    providers = session.exec(select(InferenceProvider)).all()
    assert len(providers) == 1
    assert providers[0].type.value == "local"


def test_seed_inference_providers_creates_openai_if_key_present(session):
    os.environ["SEED_LOCAL_PROVIDER_URL"] = "ws://jota-inference:8002"
    os.environ["SEED_LOCAL_MODEL_ID"] = "llama-3.2-3b"
    os.environ["SEED_OPENAI_API_KEY"] = "sk-test-openai"
    os.environ["SEED_OPENAI_DEFAULT_MODEL"] = "gpt-4o"
    os.environ.pop("SEED_ANTHROPIC_API_KEY", None)

    seed_inference_providers(session)

    providers = session.exec(select(InferenceProvider)).all()
    types = {p.type.value for p in providers}
    assert "local" in types
    assert "openai" in types


def test_seed_inference_providers_idempotent(session):
    os.environ["SEED_LOCAL_PROVIDER_URL"] = "ws://jota-inference:8002"
    os.environ["SEED_LOCAL_MODEL_ID"] = "llama-3.2-3b"
    os.environ.pop("SEED_OPENAI_API_KEY", None)
    os.environ.pop("SEED_ANTHROPIC_API_KEY", None)

    seed_inference_providers(session)
    seed_inference_providers(session)

    providers = session.exec(select(InferenceProvider)).all()
    assert len(providers) == 1


# ---- Tests de seed_service_configs ----

def _setup_services(session: Session, ids: dict):
    """Crea InternalServices en DB para los ids dados."""
    for service_id in ids.values():
        if service_id:
            svc = InternalService(id=service_id, api_key="test-key", is_active=True)
            session.add(svc)
    session.commit()


def test_seed_service_configs_creates_transcriber_config(session):
    ids = {
        "INTERNAL_ORCHESTRATOR_ID": "seed-orch",
        "INTERNAL_TRANSCRIPTOR_ID": "seed-trans",
        "INTERNAL_SPEAKER_ID": "seed-spk",
        "INTERNAL_GATEWAY_ID": "seed-gw",
        "INTERNAL_INFERENCE_ID": "seed-inf",
    }
    for k, v in ids.items():
        os.environ[k] = v
    os.environ["SEED_TRANSCRIBER_MODEL"] = "whisper-large-v3"
    os.environ["SEED_TRANSCRIBER_AUDIO_CHUNK_MS"] = "200"

    _setup_services(session, ids)
    seed_service_configs(session)

    cfg = session.exec(
        select(TranscriberConfig).where(TranscriberConfig.service_id == "seed-trans")
    ).first()
    assert cfg is not None
    assert cfg.model == "whisper-large-v3"
    assert cfg.audio_chunk_ms == 200


def test_seed_service_configs_creates_speaker_config(session):
    ids = {
        "INTERNAL_ORCHESTRATOR_ID": "seed2-orch",
        "INTERNAL_TRANSCRIPTOR_ID": "seed2-trans",
        "INTERNAL_SPEAKER_ID": "seed2-spk",
        "INTERNAL_GATEWAY_ID": "seed2-gw",
        "INTERNAL_INFERENCE_ID": "seed2-inf",
    }
    for k, v in ids.items():
        os.environ[k] = v
    os.environ["SEED_SPEAKER_MODEL"] = "kokoro-v1"

    _setup_services(session, ids)
    seed_service_configs(session)

    cfg = session.exec(
        select(SpeakerConfig).where(SpeakerConfig.service_id == "seed2-spk")
    ).first()
    assert cfg is not None
    assert cfg.model == "kokoro-v1"


def test_seed_service_configs_creates_orchestrator_config(session):
    ids = {
        "INTERNAL_ORCHESTRATOR_ID": "seed3-orch",
        "INTERNAL_TRANSCRIPTOR_ID": "seed3-trans",
        "INTERNAL_SPEAKER_ID": "seed3-spk",
        "INTERNAL_GATEWAY_ID": "seed3-gw",
        "INTERNAL_INFERENCE_ID": "seed3-inf",
    }
    for k, v in ids.items():
        os.environ[k] = v
    os.environ["SEED_ORCHESTRATOR_DEFAULT_PROVIDER_ID"] = "some-uuid"
    os.environ.pop("SEED_ORCHESTRATOR_FALLBACK_PROVIDER_ID", None)

    _setup_services(session, ids)
    seed_service_configs(session)

    cfg = session.exec(
        select(OrchestratorConfig).where(OrchestratorConfig.service_id == "seed3-orch")
    ).first()
    assert cfg is not None
    assert cfg.default_provider_id == "some-uuid"
    assert cfg.fallback_provider_id is None


def test_seed_service_configs_idempotent(session):
    ids = {
        "INTERNAL_ORCHESTRATOR_ID": "idem-orch",
        "INTERNAL_TRANSCRIPTOR_ID": "idem-trans",
        "INTERNAL_SPEAKER_ID": "idem-spk",
        "INTERNAL_GATEWAY_ID": "idem-gw",
        "INTERNAL_INFERENCE_ID": "idem-inf",
    }
    for k, v in ids.items():
        os.environ[k] = v

    _setup_services(session, ids)
    seed_service_configs(session)
    seed_service_configs(session)  # Segunda llamada no duplica

    assert len(session.exec(select(OrchestratorConfig)).all()) == 1
    assert len(session.exec(select(TranscriberConfig)).all()) == 1
    assert len(session.exec(select(SpeakerConfig)).all()) == 1
    assert len(session.exec(select(GatewayConfig)).all()) == 1
    assert len(session.exec(select(InferenceCenterConfig)).all()) == 1


def test_seed_service_configs_skips_missing_service_id(session):
    """Si INTERNAL_*_ID no está en env, no intenta crear la config."""
    os.environ.pop("INTERNAL_ORCHESTRATOR_ID", None)
    os.environ["INTERNAL_TRANSCRIPTOR_ID"] = "skip-trans"
    os.environ.pop("INTERNAL_SPEAKER_ID", None)
    os.environ.pop("INTERNAL_GATEWAY_ID", None)
    os.environ.pop("INTERNAL_INFERENCE_ID", None)

    svc = InternalService(id="skip-trans", api_key="key", is_active=True)
    session.add(svc)
    session.commit()

    seed_service_configs(session)  # No debe lanzar excepción

    assert session.exec(select(OrchestratorConfig)).first() is None
    assert session.exec(select(TranscriberConfig)).first() is not None