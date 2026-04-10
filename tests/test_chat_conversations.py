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

@pytest.fixture
def existing_conversation(client, chat_headers, session: Session):
    """Crea una conversación vacía para tests de PATCH."""
    r = client.post(
        "/chat/conversations",
        headers=chat_headers,
        json={"title": "Conv para patch"},
    )
    assert r.status_code == 201
    return r.json()

def test_patch_conversation_assign_provider(client, chat_headers, active_provider, existing_conversation):
    r = client.patch(
        f"/chat/conversations/{existing_conversation['id']}",
        headers=chat_headers,
        json={"provider_id": active_provider.id},
    )
    assert r.status_code == 200
    assert r.json()["provider_id"] == active_provider.id
    
def test_patch_conversation_remove_provider(client, chat_headers, active_provider, session: Session):
    # Crear conversación con provider asignado
    r = client.post(
        "/chat/conversations",
        headers=chat_headers,
        json={"title": "Con provider", "provider_id": active_provider.id},
    )
    assert r.status_code == 201
    conv_id = r.json()["id"]

    # Quitar el provider
    r2 = client.patch(
        f"/chat/conversations/{conv_id}",
        headers=chat_headers,
        json={"provider_id": None},
    )
    assert r2.status_code == 200
    assert r2.json()["provider_id"] is None
    
def test_patch_conversation_invalid_provider_returns_404(client, chat_headers, existing_conversation):
    r = client.patch(
        f"/chat/conversations/{existing_conversation['id']}",
        headers=chat_headers,
        json={"provider_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404
    
def test_patch_conversation_without_provider_id_does_not_change_it(client, chat_headers, active_provider, session: Session):
    # Crear con provider asignado
    r = client.post(
        "/chat/conversations",
        headers=chat_headers,
        json={"title": "Con provider", "provider_id": active_provider.id},
    )
    conv_id = r.json()["id"]

    # PATCH sin provider_id
    r2 = client.patch(
        f"/chat/conversations/{conv_id}",
        headers=chat_headers,
        json={"title": "Nuevo título"},
    )
    assert r2.status_code == 200
    assert r2.json()["provider_id"] == active_provider.id  # sin cambios