import os
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["STORAGE_ROOT"] = "test-storage"
os.environ["SECRET_KEY"] = "test-secret"

from app.db.base import Base  # noqa: E402
from app.db.seed import seed_database  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    Path("test.db").unlink(missing_ok=True)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db, include_demo_data=True)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    Path("test.db").unlink(missing_ok=True)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "Admin123!"})
    login = response.json()
    if login["requires_2fa_setup"]:
        setup = client.post("/api/v1/auth/2fa/setup", json={"challenge_token": login["challenge_token"]}).json()
        completed = client.post(
            "/api/v1/auth/2fa/enable",
            json={"challenge_token": login["challenge_token"], "code": pyotp.TOTP(setup["secret"]).now()},
        )
    else:
        raise RuntimeError("The seeded admin was unexpectedly enrolled before the test session")
    assert completed.status_code == 200, completed.text
    token = completed.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
