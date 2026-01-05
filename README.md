# Lyftr AI - Backend Assignment

A production-ready FastAPI service for ingesting and managing WhatsApp-like messages with HMAC signature validation, idempotency, and comprehensive observability.

## Features

-  **Webhook Endpoint** - Ingest messages with HMAC-SHA256 signature validation
-  **Idempotency** - Duplicate message handling via database uniqueness
-  **Message Listing** - Paginated and filterable message retrieval
-  **Analytics** - Message statistics and sender insights
-  **Health Probes** - Liveness and readiness checks
-  **Metrics** - Prometheus-style metrics endpoint
-  **Structured Logging** - JSON logs with request tracking
-  **Dockerized** - Full containerization with Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Make (optional, for convenience commands)

### Running the Application

1. **Set environment variables:**
   ```bash
   export WEBHOOK_SECRET="your-secret-key"
   export DATABASE_URL="sqlite:////data/app.db"
   export LOG_LEVEL="INFO"
   ```

2. **Start the service:**
   ```bash
   make up
   # or: docker compose up -d --build
   ```

3. **Check health:**
   ```bash
   curl http://localhost:8000/health/live
   curl http://localhost:8000/health/ready
   ```

4. **Stop the service:**
   ```bash
   make down
   ```

## API Endpoints

### POST /webhook

Ingest inbound WhatsApp-like messages with HMAC signature validation.

**Request:**
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: <hex-hmac-sha256>" \
  -d '{
    "message_id": "m1",
    "from": "+919876543210",
    "to": "+14155550100",
    "ts": "2025-01-15T10:00:00Z",
    "text": "Hello"
  }'
```

**Signature Calculation:**
```python
import hmac
import hashlib

secret = "your-webhook-secret"
body = '{"message_id":"m1",...}'
signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
```

**Response:**
```json
{
  "status": "ok"
}
```

### GET /messages

List stored messages with pagination and filters.

**Query Parameters:**
- `limit` (int, 1-100, default: 50) - Number of messages per page
- `offset` (int, min: 0, default: 0) - Pagination offset
- `from` (string, optional) - Filter by sender phone number
- `since` (string, optional) - Filter by timestamp (ISO-8601 UTC)
- `q` (string, optional) - Text search in message content

**Example:**
```bash
# Basic listing
curl http://localhost:8000/messages

# With pagination
curl "http://localhost:8000/messages?limit=10&offset=0"

# Filter by sender
curl "http://localhost:8000/messages?from=+919876543210"

# Filter by timestamp
curl "http://localhost:8000/messages?since=2025-01-15T10:00:00Z"

# Text search
curl "http://localhost:8000/messages?q=Hello"
```

**Response:**
```json
{
  "data": [
    {
      "message_id": "m1",
      "from": "+919876543210",
      "to": "+14155550100",
      "ts": "2025-01-15T10:00:00Z",
      "text": "Hello"
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

### GET /stats

Get message-level analytics.

**Example:**
```bash
curl http://localhost:8000/stats
```

**Response:**
```json
{
  "total_messages": 123,
  "senders_count": 10,
  "messages_per_sender": [
    {"from": "+919876543210", "count": 50},
    {"from": "+911234567890", "count": 30}
  ],
  "first_message_ts": "2025-01-10T09:00:00Z",
  "last_message_ts": "2025-01-15T10:00:00Z"
}
```

### GET /health/live

Liveness probe - always returns 200 when the app is running.

### GET /health/ready

Readiness probe - returns 200 only if:
- Database is accessible
- `WEBHOOK_SECRET` is set

### GET /metrics

Prometheus-style metrics endpoint.

**Metrics:**
- `http_requests_total{path, status}` - Total HTTP requests by path and status
- `webhook_requests_total{result}` - Webhook processing outcomes (created, duplicate, invalid_signature, validation_error)
- `request_latency_ms` - Request latency histogram in milliseconds

## Makefile Commands

```bash
make up      # Start the service (docker compose up -d --build)
make down    # Stop the service and remove volumes
make logs    # View application logs
make test    # Run tests
make clean   # Clean up containers and data
```

## Project Structure

```
.
├── app/
│   ├── main.py              # FastAPI app, routes, middleware
│   ├── models.py            # Pydantic models for validation
│   ├── storage.py           # SQLite database operations
│   ├── logging_utils.py     # Structured JSON logging
│   ├── metrics.py           # Prometheus metrics
│   └── config.py            # Environment configuration
├── tests/
│   ├── test_webhook.py      # Webhook endpoint tests
│   ├── test_messages.py     # Messages endpoint tests
│   └── test_stats.py        # Stats endpoint tests
├── Dockerfile               # Multi-stage Docker build
├── docker-compose.yml       # Docker Compose configuration
├── Makefile                 # Convenience commands
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Design Decisions

### HMAC Signature Verification

The HMAC-SHA256 signature is computed as:
```
signature = hex(HMAC_SHA256(secret=WEBHOOK_SECRET, message=raw_request_body_bytes))
```

**Implementation:**
- Signature is verified before any database operations
- Uses `hmac.compare_digest()` for constant-time comparison (prevents timing attacks)
- Invalid signatures return 401 without logging sensitive data
- Missing `WEBHOOK_SECRET` prevents application startup (readiness check fails)

### Idempotency

**Database-level:**
- `message_id` is the PRIMARY KEY in the `messages` table
- SQLite's `INSERT` with duplicate key raises `IntegrityError`

**Application-level:**
- Gracefully handles `IntegrityError` and treats it as a duplicate
- Returns 200 with `{"status": "ok"}` for both new and duplicate messages
- Logs `dup: true` for duplicate messages to track idempotent behavior

### Pagination Contract

**Parameters:**
- `limit`: 1-100 (default: 50)
- `offset`: >= 0 (default: 0)

**Response:**
- `data`: Array of messages for the current page
- `total`: Total number of messages matching filters (not just current page)
- `limit`/`offset`: Echoed back for client reference

**Ordering:**
- Deterministic: `ORDER BY ts ASC, message_id ASC`
- Ensures consistent pagination even with identical timestamps

### Statistics Endpoint

**Computation:**
- Uses SQL aggregations for performance
- `messages_per_sender`: Top 10 senders by message count (sorted DESC)
- `first_message_ts` / `last_message_ts`: MIN/MAX of `ts` column
- Handles empty database gracefully (returns 0/null values)

**Note:** The sum of `messages_per_sender` counts may be less than `total_messages` if there are more than 10 unique senders (only top 10 are returned).

### Metrics

**HTTP Request Metrics:**
- Counter with labels: `path` and `status`
- Tracks all HTTP requests to any endpoint

**Webhook Metrics:**
- Counter with label: `result`
- Values: `created`, `duplicate`, `invalid_signature`, `validation_error`, `insert_error`

**Latency Metrics:**
- Histogram with buckets: [10, 50, 100, 200, 500, 1000, 2000, 5000, +Inf] ms
- Captures request processing time

### Structured Logging

**Format:** One JSON line per log entry

**Required Fields:**
- `ts`: Server timestamp (ISO-8601 UTC)
- `level`: Log level (INFO, ERROR, etc.)
- `request_id`: Unique UUID per request
- `method`: HTTP method
- `path`: Request path
- `status`: HTTP status code
- `latency_ms`: Request processing time

**Webhook-specific Fields:**
- `message_id`: Message identifier
- `dup`: Boolean indicating duplicate
- `result`: Processing result

**Usage:**
```bash
# View logs
make logs

# Filter with jq
docker compose logs api | jq 'select(.path == "/webhook")'
```

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `WEBHOOK_SECRET` | Secret key for HMAC signature verification | Yes | - |
| `DATABASE_URL` | SQLite database path | No | `sqlite:////data/app.db` |
| `LOG_LEVEL` | Logging level (INFO, DEBUG, etc.) | No | `INFO` |

## Testing

Run tests with:
```bash
make test
# or: python -m pytest tests/ -v
```

**Test Coverage:**
- Webhook signature validation
- Idempotency handling
- Message pagination and filtering
- Statistics accuracy

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    from_msisdn TEXT NOT NULL,
    to_msisdn TEXT NOT NULL,
    ts TEXT NOT NULL,           -- ISO-8601 UTC string
    text TEXT,                  -- Optional, max 4096 chars
    created_at TEXT NOT NULL    -- Server timestamp (ISO-8601 UTC)
);
```

## Setup Used

**Development Environment:**
- VSCode + Cursor AI
- Python 3.11
- FastAPI framework
- Docker & Docker Compose for containerization

**Tools:**
- Cursor AI for code generation and assistance
- Manual code review and testing

## License

This project is created for the Lyftr AI backend assignment.

