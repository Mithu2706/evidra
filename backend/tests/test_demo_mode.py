"""Guest demo mode: password-less sign-in and reseed-on-start (EVIDRA_DEMO_MODE)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.auth_routes import DEMO_PASSWORD
from app.auth import hash_password
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import Organization, User


@pytest.fixture(scope="module")
def client():
    from app.main import app

    init_db()
    with SessionLocal() as db:
        org = Organization(name="Demo Mode Test Org")
        db.add(org)
        db.flush()
        for email, role in [("marcus@demo.evidra.app", "judge"), ("dana@demo.evidra.app", "organizer")]:
            if db.scalar(select(User).where(User.email == email)) is None:
                db.add(User(organization_id=org.id, email=email, name=email.split("@")[0].title(), role=role,
                            password_hash=hash_password(DEMO_PASSWORD)))
        db.commit()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def demo_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", True)


def test_demo_login_is_disabled_by_default(client):
    assert get_settings().demo_mode is False
    r = client.post("/api/auth/demo")
    assert r.status_code == 404


def test_demo_login_signs_in_as_demo_judge(client, demo_on):
    r = client.post("/api/auth/demo")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"token", "user"}  # same shape as /api/auth/login
    assert body["user"]["email"] == "marcus@demo.evidra.app"
    assert body["user"]["role"] == "judge"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "marcus@demo.evidra.app"


def test_demo_login_can_switch_to_organizer(client, demo_on):
    r = client.post("/api/auth/demo", json={"role": "organizer"})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["email"] == "dana@demo.evidra.app"
    assert r.json()["user"]["role"] == "organizer"


def test_demo_login_rejects_unknown_role(client, demo_on):
    assert client.post("/api/auth/demo", json={"role": "admin"}).status_code == 422


def test_password_login_still_works_in_demo_mode(client, demo_on):
    r = client.post("/api/auth/login", json={"email": "dana@demo.evidra.app", "password": DEMO_PASSWORD})
    assert r.status_code == 200


def test_demo_mode_reseeds_on_every_start(monkeypatch):
    from app.main import app
    from app.seed import seed as seed_module

    calls = []
    monkeypatch.setattr(seed_module, "seed", lambda **kw: calls.append(kw))
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "auto_seed", True)
    monkeypatch.setattr(settings, "demo_mode", True)
    with TestClient(app):
        pass
    with TestClient(app):
        pass
    assert calls == [{"reset": True}, {"reset": True}]


def test_health_reports_demo_mode(client, demo_on):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["demo_mode"] is True


def test_cors_origins_tolerate_trailing_slash_and_spaces():
    from app.config import Settings

    s = Settings(EVIDRA_CORS_ORIGINS=" https://evidra.vercel.app/ , http://localhost:5173")
    assert s.cors_origin_list == ["https://evidra.vercel.app", "http://localhost:5173"]
