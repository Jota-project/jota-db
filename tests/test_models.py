from datetime import datetime
from sqlmodel import select
from src.core.models import (
    ServiceConfig, InferenceProvider, ProviderType, AdminUser
)


def test_service_config_composite_pk(session):
    sc = ServiceConfig(service="orchestrator", key="default_provider_id", value="some-uuid")
    session.add(sc)
    session.commit()

    result = session.exec(
        select(ServiceConfig).where(
            ServiceConfig.service == "orchestrator",
            ServiceConfig.key == "default_provider_id",
        )
    ).first()
    assert result is not None
    assert result.value == "some-uuid"


def test_service_config_upsert_by_pk(session):
    sc = ServiceConfig(service="transcriber", key="model", value="whisper-large-v3")
    session.add(sc)
    session.commit()

    sc.value = "whisper-medium"
    session.add(sc)
    session.commit()

    results = session.exec(
        select(ServiceConfig).where(ServiceConfig.service == "transcriber")
    ).all()
    assert len(results) == 1
    assert results[0].value == "whisper-medium"


def test_inference_provider_create(session):
    p = InferenceProvider(
        name="Local llama.cpp",
        type=ProviderType.local,
        base_url="ws://jota-inference:8002",
        default_model_id="llama-3.2-3b",
    )
    session.add(p)
    session.commit()
    session.refresh(p)

    assert p.id is not None
    assert p.is_active is True
    assert p.type == ProviderType.local


def test_inference_provider_soft_delete(session):
    p = InferenceProvider(name="OpenAI", type=ProviderType.openai, api_key="sk-test")
    session.add(p)
    session.commit()
    session.refresh(p)

    p.is_active = False
    session.add(p)
    session.commit()

    result = session.get(InferenceProvider, p.id)
    assert result.is_active is False


def test_admin_user_create(session):
    admin = AdminUser(id="admin", api_key="super-secret", is_active=True)
    session.add(admin)
    session.commit()

    result = session.get(AdminUser, "admin")
    assert result is not None
    assert result.api_key == "super-secret"
