import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./filecode-test.db"
os.environ["WECOM_AUTH_MODE"] = "mock"
os.environ["AI_MODE"] = "rules"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["FRONTEND_URL"] = "http://localhost:5173"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ["RULE_FILE_PATH"] = str(PROJECT_ROOT / "编号规则采集模板.yaml")
os.environ["ABBREVIATION_FILE_PATH"] = str(PROJECT_ROOT / "文件简号.xlsx")

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def login(
    client: TestClient,
    role: str = "user",
    user_id: str | None = None,
) -> str:
    user_id = user_id or f"{role}-001"
    response = client.post(
        "/api/auth/dev-login",
        json={
            "user_id": user_id,
            "name": "管理员" if role == "admin" else "普通用户",
            "role": role,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]
