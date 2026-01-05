"""Tests for stats endpoint."""
import pytest
import hmac
import hashlib
import json
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

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
    """Seed test messages for stats."""
    messages = [
        {
            "message_id": "s1",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T09:00:00Z",
            "text": "Message 1"
        },
        {
            "message_id": "s2",
            "from": "+919876543210",
            "to": "+14155550100",
            "ts": "2025-01-15T10:00:00Z",
            "text": "Message 2"
        },
        {
            "message_id": "s3",
            "from": "+911234567890",
            "to": "+14155550100",
            "ts": "2025-01-15T11:00:00Z",
            "text": "Message 3"
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


def test_get_stats(seed_messages):
    """Test stats endpoint."""
    response = client.get("/stats")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "total_messages" in data
    assert "senders_count" in data
    assert "messages_per_sender" in data
    assert "first_message_ts" in data
    assert "last_message_ts" in data
    
    assert data["total_messages"] >= 3
    assert data["senders_count"] >= 2
    assert len(data["messages_per_sender"]) > 0


def test_stats_empty_database():
    """Test stats with empty database."""
    # This test assumes a clean database
    response = client.get("/stats")
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_messages"] == 0
    assert data["senders_count"] == 0

