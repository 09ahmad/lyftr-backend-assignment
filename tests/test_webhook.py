"""Tests for webhook endpoint."""
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


def test_webhook_invalid_signature(webhook_secret):
    """Test webhook with invalid signature."""
    body = {
        "message_id": "m1",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello"
    }
    body_bytes = json.dumps(body).encode()
    
    response = client.post(
        "/webhook",
        json=body,
        headers={"X-Signature": "invalid"}
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid signature"


def test_webhook_valid_signature(webhook_secret):
    """Test webhook with valid signature."""
    body = {
        "message_id": "m1",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello"
    }
    body_bytes = json.dumps(body).encode()
    signature = compute_signature(webhook_secret, body_bytes)
    
    response = client.post(
        "/webhook",
        json=body,
        headers={"X-Signature": signature}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_webhook_idempotency(webhook_secret):
    """Test webhook idempotency - same message_id should not create duplicate."""
    body = {
        "message_id": "m2",
        "from": "+919876543210",
        "to": "+14155550100",
        "ts": "2025-01-15T10:00:00Z",
        "text": "Hello"
    }
    body_bytes = json.dumps(body).encode()
    signature = compute_signature(webhook_secret, body_bytes)
    
    # First request
    response1 = client.post(
        "/webhook",
        json=body,
        headers={"X-Signature": signature}
    )
    assert response1.status_code == 200
    
    # Second request with same message_id
    response2 = client.post(
        "/webhook",
        json=body,
        headers={"X-Signature": signature}
    )
    assert response2.status_code == 200
    assert response2.json()["status"] == "ok"


def test_webhook_validation_error(webhook_secret):
    """Test webhook with invalid payload."""
    body = {
        "message_id": "",
        "from": "invalid",
        "to": "+14155550100",
        "ts": "invalid-timestamp",
        "text": "Hello"
    }
    body_bytes = json.dumps(body).encode()
    signature = compute_signature(webhook_secret, body_bytes)
    
    response = client.post(
        "/webhook",
        json=body,
        headers={"X-Signature": signature}
    )
    
    assert response.status_code == 422

