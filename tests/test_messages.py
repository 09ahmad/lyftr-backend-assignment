"""Tests for messages endpoint."""
import pytest
import hmac
import hashlib
import json
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.storage import db

client = TestClient(app)


def compute_signature(secret: str, body: bytes) -> str:
    """Compute HMAC-SHA256 signature."""
    return hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()


@pytest.fixture
def webhook_secret():
    """Set webhook secret for testing."""
    original = settings.WEBHOOK_SECRET
    settings.WEBHOOK_SECRET = "testsecret"
    yield "testsecret"
    settings.WEBHOOK_SECRET = original


@pytest.fixture
def seed_messages(webhook_secret):
    """Seed test messages."""
    messages = [
        {
            "message_id": "m1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T09:00:00Z",
            "text": "First message"
        },
        {
            "message_id": "m2",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Second message"
        },
        {
            "message_id": "m3",
            "from": "+911234567890",
            "to": "+14155550100",
            "ts": "2025-01-15T11:00:00Z",
            "text": "Third message"
        }
    ]
    
    for msg in messages:
        body_bytes = json.dumps(msg).encode()
        signature = compute_signature(webhook_secret, body_bytes)
        client.post(
            "/webhook",
            json=msg,
            headers={"X-Signature": signature}
        )
    
    yield messages


def test_get_messages_basic(seed_messages):
    """Test basic messages listing."""
    response = client.get("/messages")
    
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert len(data["data"]) > 0


def test_get_messages_pagination(seed_messages):
    """Test messages pagination."""
    response = client.get("/messages?limit=2&offset=0")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0


def test_get_messages_filter_by_from(seed_messages):
    """Test filtering messages by sender."""
    response = client.get("/messages?from=+919876543210")
    
    assert response.status_code == 200
    data = response.json()
    assert all(msg["from"] == "+919876543210" for msg in data["data"])


def test_get_messages_filter_by_since(seed_messages):
    """Test filtering messages by timestamp."""
    response = client.get("/messages?since=2025-01-15T10:00:00Z")
    
    assert response.status_code == 200
    data = response.json()
    # All messages should have ts >= since
    for msg in data["data"]:
        assert msg["ts"] >= "2025-01-15T10:00:00Z"


def test_get_messages_search(seed_messages):
    """Test text search in messages."""
    response = client.get("/messages?q=First")
    
    assert response.status_code == 200
    data = response.json()
    assert any("First" in msg.get("text", "").lower() for msg in data["data"])

