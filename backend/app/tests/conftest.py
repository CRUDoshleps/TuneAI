import os
import tempfile
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = tempfile.mkdtemp(prefix="tuneai-tests-")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tuneai-suite")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_ROOT}/test.db"
os.environ["UPLOAD_DIR"] = f"{TEST_ROOT}/uploads"
os.environ["YANDEX_MOCK"] = "true"
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"

from app.db.base import Base
from app.db.session import SessionLocal, engine, get_db
from app.main import app, rate_windows


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    rate_windows.clear()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_and_login(client: TestClient, email: str, password: str = "password123", full_name: str = "Test User"):
    client.post("/auth/register", json={"email": email, "password": password, "full_name": full_name})
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
