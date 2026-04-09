import pytest
from sqlmodel import Session
from src.core.models import InferenceProvider, ProviderType


@pytest.fixture
def local_provider(session: Session):
    p = InferenceProvider(
        name="Local llama.cpp",
        type=ProviderType.local,
        base_url="ws://jota-inference:8002",
        default_model_id="llama-3.2-3b",
        is_active=True,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def test_admin_list_providers_empty(client, admin_headers):
    r = client.get("/admin/providers", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_admin_list_providers_includes_inactive(client, admin_headers, session):
    session.add(InferenceProvider(name="A", type=ProviderType.local, base_url="ws://x", is_active=True))
    session.add(InferenceProvider(name="B", type=ProviderType.openai, api_key="sk-x", is_active=False))
    session.commit()

    r = client.get("/admin/providers", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_admin_create_provider(client, admin_headers):
    r = client.post(
        "/admin/providers",
        headers=admin_headers,
        json={
            "name": "OpenAI GPT-4o",
            "type": "openai",
            "api_key": "sk-test",
            "default_model_id": "gpt-4o",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "OpenAI GPT-4o"
    assert data["type"] == "openai"
    assert data["is_active"] is True
    assert "id" in data


def test_admin_get_provider_by_id(client, admin_headers, local_provider):
    r = client.get(f"/admin/providers/{local_provider.id}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Local llama.cpp"


def test_admin_get_provider_unknown_id_returns_404(client, admin_headers):
    r = client.get("/admin/providers/nonexistent", headers=admin_headers)
    assert r.status_code == 404


def test_admin_update_provider(client, admin_headers, local_provider):
    r = client.put(
        f"/admin/providers/{local_provider.id}",
        headers=admin_headers,
        json={"default_model_id": "llama-3.3-70b", "is_active": True},
    )
    assert r.status_code == 200
    assert r.json()["default_model_id"] == "llama-3.3-70b"


def test_admin_soft_delete_provider(client, admin_headers, local_provider):
    r = client.delete(f"/admin/providers/{local_provider.id}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # Sigue apareciendo en el listado (soft delete)
    r2 = client.get("/admin/providers", headers=admin_headers)
    assert len(r2.json()) == 1
    assert r2.json()[0]["is_active"] is False


def test_admin_delete_provider_unknown_returns_404(client, admin_headers):
    r = client.delete("/admin/providers/nonexistent", headers=admin_headers)
    assert r.status_code == 404


def test_admin_providers_requires_auth(client):
    r = client.get("/admin/providers")
    assert r.status_code in (401, 422)
