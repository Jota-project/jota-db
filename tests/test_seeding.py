import os
import pytest
from sqlmodel import select, Session
from src.core.models import AdminUser, InferenceProvider, ServiceConfig
from src.core.database import bootstrap_admin, seed_inference_providers, seed_service_config


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
    bootstrap_admin(session)  # Segunda vez no debe fallar ni duplicar

    results = session.exec(select(AdminUser)).all()
    assert len(results) == 1


def test_bootstrap_admin_skips_if_no_key(session):
    os.environ.pop("ADMIN_KEY", None)
    bootstrap_admin(session)

    admin = session.get(AdminUser, "admin")
    assert admin is None


def test_seed_inference_providers_creates_local(session):
    os.environ["SEED_LOCAL_PROVIDER_URL"] = "ws://jota-inference:8002"
    os.environ["SEED_LOCAL_MODEL_ID"] = "llama-3.2-3b"
    os.environ.pop("SEED_OPENAI_API_KEY", None)
    os.environ.pop("SEED_ANTHROPIC_API_KEY", None)

    seed_inference_providers(session)

    providers = session.exec(select(InferenceProvider)).all()
    assert len(providers) == 1
    assert providers[0].type.value == "local"
    assert providers[0].base_url == "ws://jota-inference:8002"
    assert providers[0].default_model_id == "llama-3.2-3b"


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
    assert "anthropic" not in types


def test_seed_inference_providers_idempotent(session):
    os.environ["SEED_LOCAL_PROVIDER_URL"] = "ws://jota-inference:8002"
    os.environ["SEED_LOCAL_MODEL_ID"] = "llama-3.2-3b"
    os.environ.pop("SEED_OPENAI_API_KEY", None)
    os.environ.pop("SEED_ANTHROPIC_API_KEY", None)

    seed_inference_providers(session)
    seed_inference_providers(session)  # Segunda llamada no duplica

    providers = session.exec(select(InferenceProvider)).all()
    assert len(providers) == 1


def test_seed_service_config_creates_entries(session):
    os.environ["SEED_LOCAL_PROVIDER_URL"] = "ws://jota-inference:8002"
    os.environ["SEED_LOCAL_MODEL_ID"] = "llama-3.2-3b"
    os.environ["SEED_TRANSCRIBER_MODEL"] = "whisper-large-v3"
    os.environ["SEED_TRANSCRIBER_AUDIO_CHUNK_MS"] = "200"
    os.environ["SEED_SPEAKER_MODEL"] = "kokoro-v1"
    os.environ.pop("SEED_OPENAI_API_KEY", None)
    os.environ.pop("SEED_ANTHROPIC_API_KEY", None)

    seed_inference_providers(session)
    seed_service_config(session)

    configs = session.exec(select(ServiceConfig)).all()
    keys = {(c.service, c.key) for c in configs}
    assert ("transcriber", "model") in keys
    assert ("transcriber", "audio.chunk_ms") in keys
    assert ("speaker", "model") in keys
    assert ("orchestrator", "default_provider_id") in keys


def test_seed_service_config_orchestrator_points_to_local_provider(session):
    os.environ["SEED_LOCAL_PROVIDER_URL"] = "ws://jota-inference:8002"
    os.environ["SEED_LOCAL_MODEL_ID"] = "llama-3.2-3b"
    os.environ.pop("SEED_OPENAI_API_KEY", None)
    os.environ.pop("SEED_ANTHROPIC_API_KEY", None)

    seed_inference_providers(session)
    seed_service_config(session)

    local_provider = session.exec(
        select(InferenceProvider).where(InferenceProvider.type == "local")
    ).first()
    config_entry = session.exec(
        select(ServiceConfig).where(
            ServiceConfig.service == "orchestrator",
            ServiceConfig.key == "default_provider_id",
        )
    ).first()

    assert config_entry is not None
    assert config_entry.value == local_provider.id


def test_seed_service_config_idempotent(session):
    os.environ["SEED_LOCAL_PROVIDER_URL"] = "ws://jota-inference:8002"
    os.environ["SEED_LOCAL_MODEL_ID"] = "llama-3.2-3b"
    os.environ.pop("SEED_OPENAI_API_KEY", None)

    seed_inference_providers(session)
    seed_service_config(session)
    seed_service_config(session)  # Segunda vez no duplica

    configs = session.exec(select(ServiceConfig)).all()
    keys = [(c.service, c.key) for c in configs]
    assert len(keys) == len(set(keys))  # Sin duplicados
