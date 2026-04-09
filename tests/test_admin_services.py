import pytest
from sqlmodel import Session
from src.core.models import InternalService


@pytest.fixture
def existing_service(session: Session):
    svc = InternalService(id="JotaOrchestrator", api_key="orch-key-001", is_active=True)
    session.add(svc)
    session.commit()
    session.refresh(svc)
    return svc


def test_admin_list_services_empty(client, admin_headers):
    r = client.get("/admin/services", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_admin_list_services(client, admin_headers, existing_service):
    r = client.get("/admin/services", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == "JotaOrchestrator"


def test_admin_create_service(client, admin_headers):
    r = client.post(
        "/admin/services",
        headers=admin_headers,
        json={"id": "NewService", "api_key": "new-service-key"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["id"] == "NewService"
    assert data["is_active"] is True


def test_admin_create_service_duplicate_id_returns_409(client, admin_headers, existing_service):
    r = client.post(
        "/admin/services",
        headers=admin_headers,
        json={"id": "JotaOrchestrator", "api_key": "another-key"},
    )
    assert r.status_code == 409


def test_admin_get_service_by_id(client, admin_headers, existing_service):
    r = client.get("/admin/services/JotaOrchestrator", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["id"] == "JotaOrchestrator"


def test_admin_get_service_unknown_returns_404(client, admin_headers):
    r = client.get("/admin/services/Unknown", headers=admin_headers)
    assert r.status_code == 404


def test_admin_update_service_key(client, admin_headers, existing_service):
    r = client.put(
        "/admin/services/JotaOrchestrator",
        headers=admin_headers,
        json={"api_key": "rotated-key-999"},
    )
    assert r.status_code == 200
    assert r.json()["api_key"] == "rotated-key-999"


def test_admin_deactivate_service(client, admin_headers, existing_service):
    r = client.delete("/admin/services/JotaOrchestrator", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_admin_deactivate_unknown_service_returns_404(client, admin_headers):
    r = client.delete("/admin/services/Unknown", headers=admin_headers)
    assert r.status_code == 404


def test_admin_services_requires_auth(client):
    r = client.get("/admin/services")
    assert r.status_code in (401, 422)
