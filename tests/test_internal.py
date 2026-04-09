import pytest
from sqlmodel import Session
from src.core.models import ServiceConfig, InferenceProvider, ProviderType, ClientConfig


# ---- Fixtures de datos ----

@pytest.fixture
def seed_config(session: Session):
    session.add(ServiceConfig(service="orchestrator", key="default_provider_id", value="uuid-123"))
    session.add(ServiceConfig(service="transcriber", key="model", value="whisper-large-v3"))
    session.commit()


@pytest.fixture
def seed_providers(session: Session):
    p = InferenceProvider(
        name="Local", type=ProviderType.local,
        base_url="ws://jota-inference:8002", default_model_id="llama-3.2-3b",
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


# ---- Tests de service-config ----

def test_internal_list_service_config(client, service_headers, seed_config):
    r = client.get("/internal/service-config", headers=service_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    services = {d["service"] for d in data}
    assert "orchestrator" in services
    assert "transcriber" in services


def test_internal_get_service_config_by_service(client, service_headers, seed_config):
    r = client.get("/internal/service-config/orchestrator", headers=service_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["key"] == "default_provider_id"


def test_internal_get_service_config_unknown_service_returns_empty(client, service_headers):
    r = client.get("/internal/service-config/unknown-service", headers=service_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_internal_upsert_service_config(client, service_headers):
    r = client.put(
        "/internal/service-config/speaker/model",
        headers=service_headers,
        json={"value": "kokoro-v1", "description": "TTS model"},
    )
    assert r.status_code == 200
    assert r.json()["value"] == "kokoro-v1"


def test_internal_upsert_service_config_updates_existing(client, service_headers, seed_config):
    r = client.put(
        "/internal/service-config/transcriber/model",
        headers=service_headers,
        json={"value": "whisper-medium"},
    )
    assert r.status_code == 200
    assert r.json()["value"] == "whisper-medium"


def test_internal_delete_service_config(client, service_headers, seed_config):
    r = client.delete("/internal/service-config/transcriber/model", headers=service_headers)
    assert r.status_code == 204

    r2 = client.get("/internal/service-config/transcriber", headers=service_headers)
    assert r2.json() == []


def test_internal_delete_nonexistent_config_returns_404(client, service_headers):
    r = client.delete("/internal/service-config/ghost/key", headers=service_headers)
    assert r.status_code == 404


# ---- Tests de providers ----

def test_internal_list_providers(client, service_headers, seed_providers):
    r = client.get("/internal/providers", headers=service_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["type"] == "local"


def test_internal_list_providers_only_active(client, service_headers, session):
    p_active = InferenceProvider(name="Active", type=ProviderType.local, base_url="ws://...", is_active=True)
    p_inactive = InferenceProvider(name="Inactive", type=ProviderType.openai, api_key="sk-x", is_active=False)
    session.add(p_active)
    session.add(p_inactive)
    session.commit()

    r = client.get("/internal/providers", headers=service_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_internal_get_provider_by_id(client, service_headers, seed_providers):
    r = client.get(f"/internal/providers/{seed_providers.id}", headers=service_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Local"


def test_internal_get_provider_unknown_id_returns_404(client, service_headers):
    r = client.get("/internal/providers/nonexistent-uuid", headers=service_headers)
    assert r.status_code == 404


# ---- Tests de client-config ----

def test_internal_get_client_config(client, service_headers, sample_client):
    r = client.get(f"/internal/client-config/{sample_client.id}", headers=service_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["client_id"] == sample_client.id


def test_internal_get_client_config_unknown_client_returns_404(client, service_headers):
    r = client.get("/internal/client-config/nonexistent", headers=service_headers)
    assert r.status_code == 404


def test_internal_update_client_config(client, service_headers, sample_client):
    r = client.put(
        f"/internal/client-config/{sample_client.id}",
        headers=service_headers,
        json={"tts_voice": "bf_emma", "tts_speed": 1.2},
    )
    assert r.status_code == 200
    assert r.json()["tts_voice"] == "bf_emma"
    assert r.json()["tts_speed"] == 1.2


def test_internal_requires_auth(client):
    r = client.get("/internal/service-config")
    assert r.status_code in (401, 422)
