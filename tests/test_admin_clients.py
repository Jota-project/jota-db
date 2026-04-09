import pytest
from sqlmodel import Session, select
from src.core.models import Client, ClientConfig, ClientType


def test_admin_list_clients_empty(client, admin_headers):
    r = client.get("/admin/clients", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_admin_list_clients(client, admin_headers, sample_client):
    r = client.get("/admin/clients", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == sample_client.id


def test_admin_create_client(client, admin_headers):
    r = client.post(
        "/admin/clients",
        headers=admin_headers,
        json={"name": "jota-pill", "client_key": "pill-key-001", "client_type": "QUICK"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "jota-pill"
    assert data["client_type"] == "QUICK"
    assert data["is_active"] is True


def test_admin_create_client_auto_creates_config(client, admin_headers, session):
    client.post(
        "/admin/clients",
        headers=admin_headers,
        json={"name": "new-device", "client_key": "new-key-001", "client_type": "CHAT"},
    )
    new_client = session.exec(
        select(Client).where(Client.client_key == "new-key-001")
    ).first()
    config = session.exec(
        select(ClientConfig).where(ClientConfig.client_id == new_client.id)
    ).first()
    assert config is not None


def test_admin_get_client_by_id(client, admin_headers, sample_client):
    r = client.get(f"/admin/clients/{sample_client.id}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["id"] == sample_client.id


def test_admin_get_client_unknown_returns_404(client, admin_headers):
    r = client.get("/admin/clients/nonexistent", headers=admin_headers)
    assert r.status_code == 404


def test_admin_update_client(client, admin_headers, sample_client):
    r = client.put(
        f"/admin/clients/{sample_client.id}",
        headers=admin_headers,
        json={"client_type": "QUICK"},
    )
    assert r.status_code == 200
    assert r.json()["client_type"] == "QUICK"


def test_admin_deactivate_client(client, admin_headers, sample_client):
    r = client.delete(f"/admin/clients/{sample_client.id}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_admin_get_client_config(client, admin_headers, sample_client):
    r = client.get(f"/admin/clients/{sample_client.id}/config", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["client_id"] == sample_client.id


def test_admin_update_client_config(client, admin_headers, sample_client):
    r = client.put(
        f"/admin/clients/{sample_client.id}/config",
        headers=admin_headers,
        json={"tts_voice": "bf_emma", "tts_speed": 1.5},
    )
    assert r.status_code == 200
    assert r.json()["tts_voice"] == "bf_emma"
    assert r.json()["tts_speed"] == 1.5


def test_admin_reset_client_config(client, admin_headers, sample_client):
    # Primero modificar
    client.put(
        f"/admin/clients/{sample_client.id}/config",
        headers=admin_headers,
        json={"tts_voice": "bf_emma"},
    )
    # Luego reset
    r = client.post(f"/admin/clients/{sample_client.id}/config/reset", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["tts_voice"] == "af_heart"  # valor por defecto


def test_admin_clients_requires_auth(client):
    r = client.get("/admin/clients")
    assert r.status_code in (401, 422)
