import os

# Set env vars BEFORE importing app modules
os.environ["API_SECRET_KEY"] = "test-master-key"
os.environ["ADMIN_KEY"] = "test-admin-key"
os.environ["DATABASE_URL"] = "sqlite://"

# Patch sqlalchemy.create_engine BEFORE importing app modules so that
# database.py's module-level engine creation doesn't fail with SQLite.
import sqlalchemy as _sa

_orig_create_engine = _sa.create_engine

def _sqlite_safe_create_engine(url, **kwargs):
    if str(url).startswith("sqlite"):
        for k in ("pool_size", "max_overflow", "pool_timeout", "pool_recycle", "pool_pre_ping"):
            kwargs.pop(k, None)
    return _orig_create_engine(url, **kwargs)

_sa.create_engine = _sqlite_safe_create_engine

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from src.api.api import app
from src.core.database import get_session
from src.core.models import InternalService, Client, ClientType, ClientConfig


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    # Sin context manager = no dispara el startup (init_db) que necesita PostgreSQL
    test_client = TestClient(app, raise_server_exceptions=True)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(name="admin_headers")
def admin_headers_fixture(session: Session):
    """Crea el AdminUser en DB y devuelve los headers correctos."""
    from src.core.models import AdminUser
    admin = AdminUser(id="admin", api_key="test-admin-key", is_active=True)
    session.add(admin)
    session.commit()
    return {
        "Authorization": "Bearer test-master-key",
        "X-API-Key": "test-admin-key",
    }


@pytest.fixture(name="service_headers")
def service_headers_fixture(session: Session):
    """Crea un InternalService en DB y devuelve los headers correctos."""
    svc = InternalService(id="test-orchestrator", api_key="test-service-key", is_active=True)
    session.add(svc)
    session.commit()
    return {
        "Authorization": "Bearer test-master-key",
        "X-API-Key": "test-service-key",
    }


@pytest.fixture(name="sample_client")
def sample_client_fixture(session: Session):
    """Crea un Client de ejemplo en DB."""
    c = Client(id="desktop", name="jota_desktop", client_key="desktop-key", client_type=ClientType.CHAT)
    session.add(c)
    session.flush()
    session.add(ClientConfig(client_id=c.id))
    session.commit()
    session.refresh(c)
    return c
