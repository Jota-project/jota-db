import pytest
from sqlmodel import Session
from src.core.models import (
    InternalService, InferenceProvider, ProviderType, ClientConfig,
    OrchestratorConfig, TranscriberConfig, SpeakerConfig,
    GatewayConfig, InferenceCenterConfig,
)


# ---- Fixtures de datos ----

@pytest.fixture
def seed_all_services(session: Session):
    """Crea los InternalServices y sus configs para los 5 servicios de test."""
    services = [
        ("test-orchestrator", OrchestratorConfig),
        ("test-transcriptor", TranscriberConfig),
        ("test-speaker", SpeakerConfig),
        ("test-gateway", GatewayConfig),
        ("test-inference", InferenceCenterConfig),
    ]
    for svc_id, config_cls in services:
        if not session.get(InternalService, svc_id):
            session.add(InternalService(id=svc_id, api_key=f"key-{svc_id}", is_active=True))
            session.flush()
        session.add(config_cls(service_id=svc_id))
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

def test_internal_list_service_config_returns_all(client, service_headers, seed_all_services):
    r = client.get("/internal/service-config", headers=service_headers)
    assert r.status_code == 200
    data = r.json()
    service_ids = {entry["service_id"] for entry in data}
    assert "test-orchestrator" in service_ids
    assert "test-transcriptor" in service_ids
    assert "test-speaker" in service_ids
    assert "test-gateway" in service_ids
    assert "test-inference" in service_ids


def test_internal_list_service_config_entry_has_config_dict(client, service_headers, seed_all_services):
    r = client.get("/internal/service-config", headers=service_headers)
    assert r.status_code == 200
    orchestrator_entry = next(e for e in r.json() if e["service_id"] == "test-orchestrator")
    assert "config" in orchestrator_entry
    assert isinstance(orchestrator_entry["config"], dict)


def test_internal_get_service_config_orchestrator(client, service_headers, seed_all_services):
    r = client.get("/internal/service-config/test-orchestrator", headers=service_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["service_id"] == "test-orchestrator"
    assert "default_provider_id" in data


def test_internal_get_service_config_transcriber(client, service_headers, seed_all_services):
    r = client.get("/internal/service-config/test-transcriptor", headers=service_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["service_id"] == "test-transcriptor"
    assert data["model"] == "whisper-large-v3"
    assert data["audio_chunk_ms"] == 200


def test_internal_get_service_config_unknown_returns_404(client, service_headers):
    r = client.get("/internal/service-config/unknown-service", headers=service_headers)
    assert r.status_code == 404


def test_internal_update_service_config_transcriber(client, service_headers, session, seed_all_services):
    r = client.put(
        "/internal/service-config/test-transcriptor",
        headers=service_headers,
        json={"model": "whisper-medium"},
    )
    assert r.status_code == 200
    assert r.json()["model"] == "whisper-medium"
    assert r.json()["audio_chunk_ms"] == 200  # campo no enviado conserva valor


def test_internal_update_service_config_speaker(client, service_headers, seed_all_services):
    r = client.put(
        "/internal/service-config/test-speaker",
        headers=service_headers,
        json={"model": "kokoro-v2"},
    )
    assert r.status_code == 200
    assert r.json()["model"] == "kokoro-v2"


def test_internal_update_service_config_unknown_field_returns_422(client, service_headers, seed_all_services):
    r = client.put(
        "/internal/service-config/test-transcriptor",
        headers=service_headers,
        json={"nonexistent_field": "value"},
    )
    assert r.status_code == 422


def test_internal_update_service_config_unknown_service_returns_404(client, service_headers):
    r = client.put(
        "/internal/service-config/ghost-service",
        headers=service_headers,
        json={"model": "something"},
    )
    assert r.status_code == 404


def test_internal_orchestrator_config_endpoint_gone(client, service_headers):
    """El endpoint ad-hoc /orchestrator-config fue eliminado."""
    r = client.get("/internal/orchestrator-config", headers=service_headers)
    assert r.status_code == 404


# ---- Tests de providers (sin cambios) ----

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


# ---- Tests de client-config (sin cambios) ----

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