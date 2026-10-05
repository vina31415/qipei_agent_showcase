# plan-P4-1
"""编排层 main.py 测试：入口契约、Redis 会话、审计写入"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from qipei_agent.orchestrator.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_settings():
    mock = MagicMock()
    mock.REDIS_URL = "redis://localhost:6379/0"
    mock.MYSQL_USER = "test"
    mock.MYSQL_PASSWORD = "test"
    mock.MYSQL_HOST = "localhost"
    mock.MYSQL_PORT = 3306
    mock.MYSQL_DB = "test"
    with patch("qipei_agent.orchestrator.main.get_settings", return_value=mock):
        yield mock


@pytest.fixture
def mock_redis():
    r = MagicMock()
    r.get.return_value = None
    r.setex.return_value = True
    with patch("qipei_agent.orchestrator.main._redis_client", r):
        with patch("qipei_agent.orchestrator.main.get_redis", return_value=r):
            yield r


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock()
    db.close = MagicMock()
    with patch("qipei_agent.orchestrator.main._engine", None):
        with patch("qipei_agent.orchestrator.main._SessionLocal", None):
            with patch("qipei_agent.orchestrator.main.get_db_session", return_value=db):
                yield db


def test_chat_minimal_request(client, mock_redis, mock_db):
    response = client.post(
        "/api/v1/chat",
        json={"message": "查 OE 6Q0820803C", "context": {"user_id": "U001", "role": "sales"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "request_id" in data
    assert data["answer"] is not None
    mock_redis.setex.assert_called_once()
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_chat_with_session_id(client, mock_redis, mock_db):
    response = client.post(
        "/api/v1/chat",
        json={
            "session_id": "test-session-123",
            "message": "查 OE 6Q0820803C",
            "context": {"user_id": "U001", "role": "sales"},
        },
    )
    assert response.status_code == 200
    assert response.json()["session_id"] == "test-session-123"


def test_chat_with_full_context(client, mock_redis, mock_db):
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "查 OE 6Q0820803C",
            "context": {
                "user_id": "U001",
                "role": "merchandiser",
                "customer_id": "C100",
                "customer_tier": "A",
                "currency": "CNY",
                "quantity": 100,
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] is not None


def test_chat_request_id_from_header(client, mock_redis, mock_db):
    response = client.post(
        "/api/v1/chat",
        json={"message": "查 OE 6Q0820803C", "context": {"user_id": "U001", "role": "sales"}},
        headers={"X-Request-Id": "custom-rid-123"},
    )
    assert response.status_code == 200
    assert response.json()["request_id"] == "custom-rid-123"


def test_chat_session_saved_with_history(client, mock_redis, mock_db):
    response = client.post(
        "/api/v1/chat",
        json={
            "session_id": "hist-session",
            "message": "查 OE 6Q0820803C",
            "context": {"user_id": "U001", "role": "sales"},
        },
    )
    assert response.status_code == 200
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == "session:hist-session"
    session_data = json.loads(call_args[0][2])
    assert len(session_data["history"]) == 2
    assert session_data["history"][0]["message"] == "查 OE 6Q0820803C"


def test_chat_existing_session_loaded(client, mock_redis, mock_db):
    existing = {
        "intent": "oe_query",
        "params": {},
        "last_query": "查 OE 6Q0820803C",
        "history": [{"role": "user", "message": "查 OE 6Q0820803C"}],
    }
    mock_redis.get.return_value = json.dumps(existing)
    response = client.post(
        "/api/v1/chat",
        json={
            "session_id": "existing-session",
            "message": "库存多少？",
            "context": {"user_id": "U001", "role": "sales"},
        },
    )
    assert response.status_code == 200
    session_data = json.loads(mock_redis.setex.call_args[0][2])
    assert len(session_data["history"]) == 3


def test_audit_log_content(client, mock_redis, mock_db):
    response = client.post(
        "/api/v1/chat",
        json={"message": "查 OE 6Q0820803C", "context": {"user_id": "U001", "role": "sales"}},
    )
    assert response.status_code == 200
    entry = mock_db.add.call_args[0][0]
    assert entry.user_id == "U001"
    assert entry.role == "sales"
    assert entry.query == "查 OE 6Q0820803C"
    assert entry.hit_count == 0
    assert entry.is_fallback is False


def test_chat_invalid_request(client, mock_redis, mock_db):
    response = client.post("/api/v1/chat", json={"message": "查 OE"})
    assert response.status_code == 422


def test_session_ttl(client, mock_redis, mock_db):
    response = client.post(
        "/api/v1/chat",
        json={
            "session_id": "ttl-session",
            "message": "查 OE 6Q0820803C",
            "context": {"user_id": "U001", "role": "sales"},
        },
    )
    assert response.status_code == 200
    assert mock_redis.setex.call_args[0][1] == 1800
