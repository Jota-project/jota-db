import pytest
from sqlmodel import Session
from src.core.models import InferenceProvider, ProviderType, Client, ClientType, ClientConfig


@pytest.fixture
def chat_headers(session: Session):
    """Crea un Client y devuelve los headers de autenticación directa."""
    c = Client(id="desktop", name="jota_desktop", client_key="desktop-key", client_type=ClientType.CHAT)
    session.add(c)
    session.flush()
    session.add(ClientConfig(client_id=c.id))
    session.commit()
    return {
        "Authorization": "Bearer test-master-key",
        "X-API-Key": "desktop-key",
    }


@pytest.fixture
def active_provider(session: Session):
    p = InferenceProvider(
        name="Local llama.cpp",
        type=ProviderType.local,
        base_url="ws://jota-inference:8002",
        is_active=True,
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def test_create_conversation_with_valid_provider(client, chat_headers, active_provider):
    r = client.post(
        "/chat/conversations",
        headers=chat_headers,
        json={"title": "Test conv", "provider_id": active_provider.id},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["provider_id"] == active_provider.id
    assert data["title"] == "Test conv"

def test_create_conversation_unknown_provider_returns_404(client, chat_headers):
    r = client.post(
        "/chat/conversations",
        headers=chat_headers,
        json={"title": "Test conv", "provider_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404
    
def test_create_conversation_without_provider_id(client, chat_headers):
    r = client.post(
        "/chat/conversations",
        headers=chat_headers,
        json={"title": "Sin provider"},
    )
    assert r.status_code == 201
    assert r.json()["provider_id"] is None