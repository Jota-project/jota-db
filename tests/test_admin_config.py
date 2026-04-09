import os
import pytest
from sqlmodel import Session
from src.core.models import ServiceConfig


@pytest.fixture
def seed_config(session: Session):
    session.add(ServiceConfig(service="orchestrator", key="default_provider_id", value="uuid-abc"))
    session.add(ServiceConfig(service="orchestrator", key="fallback_provider_id", value=None))
    session.add(ServiceConfig(service="transcriber", key="model", value="whisper-large-v3"))
    session.commit()


def test_admin_list_all_config(client, admin_headers, seed_config):
    r = client.get("/admin/config", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_admin_get_config_by_service(client, admin_headers, seed_config):
    r = client.get("/admin/config/orchestrator", headers=admin_headers)
    assert r.status_code == 200
    keys = {e["key"] for e in r.json()}
    assert keys == {"default_provider_id", "fallback_provider_id"}


def test_admin_get_config_unknown_service_returns_empty(client, admin_headers):
    r = client.get("/admin/config/ghost", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_admin_upsert_config_creates_new(client, admin_headers):
    r = client.put(
        "/admin/config/speaker/model",
        headers=admin_headers,
        json={"value": "kokoro-v1", "description": "TTS model"},
    )
    assert r.status_code == 200
    assert r.json()["value"] == "kokoro-v1"
    assert r.json()["service"] == "speaker"
    assert r.json()["key"] == "model"


def test_admin_upsert_config_updates_existing(client, admin_headers, seed_config):
    r = client.put(
        "/admin/config/transcriber/model",
        headers=admin_headers,
        json={"value": "whisper-medium"},
    )
    assert r.status_code == 200
    assert r.json()["value"] == "whisper-medium"

    # Comprobar que no se duplicó
    r2 = client.get("/admin/config/transcriber", headers=admin_headers)
    assert len(r2.json()) == 1


def test_admin_delete_config(client, admin_headers, seed_config):
    r = client.delete("/admin/config/transcriber/model", headers=admin_headers)
    assert r.status_code == 204

    r2 = client.get("/admin/config/transcriber", headers=admin_headers)
    assert r2.json() == []


def test_admin_delete_nonexistent_config_returns_404(client, admin_headers):
    r = client.delete("/admin/config/ghost/key", headers=admin_headers)
    assert r.status_code == 404


def test_admin_reset_service_config(client, admin_headers, seed_config, session):
    os.environ["SEED_LOCAL_PROVIDER_URL"] = "ws://jota-inference:8002"
    os.environ["SEED_LOCAL_MODEL_ID"] = "llama-3.2-3b"
    os.environ["SEED_TRANSCRIBER_MODEL"] = "whisper-large-v3-reset"
    os.environ.pop("SEED_OPENAI_API_KEY", None)
    os.environ.pop("SEED_ANTHROPIC_API_KEY", None)

    # Primero crear el provider local (para que seed_service_config funcione)
    from src.core.models import InferenceProvider, ProviderType
    session.add(InferenceProvider(
        name="Local", type=ProviderType.local,
        base_url="ws://jota-inference:8002", default_model_id="llama-3.2-3b",
    ))
    session.commit()

    r = client.post("/admin/config/transcriber/reset", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    keys = {e["key"] for e in data}
    assert "model" in keys
    model_entry = next(e for e in data if e["key"] == "model")
    assert model_entry["value"] == "whisper-large-v3-reset"


def test_admin_config_requires_auth(client):
    r = client.get("/admin/config")
    assert r.status_code in (401, 422)
