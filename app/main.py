"""FastAPI application with webhook, messages, stats, health, and metrics endpoints."""
import hmac
import hashlib
import json
import logging
import uuid
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Header, Query
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.config import settings
from app.models import (
    WebhookRequest,
    WebhookResponse,
    MessagesListResponse,
    MessageResponse,
    StatsResponse
)
from app.storage import db
from app.logging_utils import setup_logging, RequestLoggingMiddleware
from app.metrics import get_metrics, record_request, record_webhook_result

# Setup logging
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Add CORS middleware (optional, but good practice)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_signature(body: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    if not settings.WEBHOOK_SECRET:
        return False
    
    expected_signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


@app.post("/webhook", response_model=WebhookResponse)
async def webhook(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature")
):
    """
    Ingest inbound WhatsApp-like messages with HMAC signature validation.
    Implements idempotency via message_id uniqueness.
    """
    # Get request_id from middleware (set by RequestLoggingMiddleware)
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
    
    # Get raw body for signature verification (must be done before parsing)
    body = await request.body()
    
    # Verify signature
    if not x_signature or not verify_signature(body, x_signature):
        logger.error(
            "Invalid signature",
            extra={
                "request_id": request_id,
                "result": "invalid_signature"
            }
        )
        record_webhook_result("invalid_signature")
        raise HTTPException(status_code=401, detail="invalid signature")
    
    # Parse JSON body
    try:
        body_json = json.loads(body.decode())
        webhook_data = WebhookRequest(**body_json)
    except json.JSONDecodeError as e:
        logger.error(
            "Invalid JSON",
            extra={
                "request_id": request_id,
                "result": "validation_error",
                "error": str(e)
            }
        )
        record_webhook_result("validation_error")
        raise HTTPException(status_code=422, detail=f"Invalid JSON: {str(e)}")
    except ValidationError as e:
        logger.error(
            "Validation error",
            extra={
                "request_id": request_id,
                "result": "validation_error",
                "error": str(e)
            }
        )
        record_webhook_result("validation_error")
        raise HTTPException(status_code=422, detail=str(e))
    
    # Insert message (handles idempotency)
    success, is_duplicate = db.insert_message(
        message_id=webhook_data.message_id,
        from_msisdn=webhook_data.from_,
        to_msisdn=webhook_data.to,
        ts=webhook_data.ts,
        text=webhook_data.text
    )
    
    if not success:
        logger.error(
            "Failed to insert message",
            extra={
                "request_id": request_id,
                "message_id": webhook_data.message_id,
                "result": "insert_error"
            }
        )
        record_webhook_result("insert_error")
        raise HTTPException(status_code=500, detail="internal server error")
    
    # Determine result
    result = "duplicate" if is_duplicate else "created"
    
    # Log webhook event
    logger.info(
        "Webhook processed",
        extra={
            "request_id": request_id,
            "message_id": webhook_data.message_id,
            "dup": is_duplicate,
            "result": result
        }
    )
    
    record_webhook_result(result)
    
    return WebhookResponse(status="ok")


@app.get("/messages", response_model=MessagesListResponse)
async def get_messages(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_: Optional[str] = Query(None, alias="from"),
    since: Optional[str] = Query(None),
    q: Optional[str] = Query(None)
):
    """
    List stored messages with pagination and filters.
    Supports filtering by sender, timestamp, and text search.
    """
    messages, total = db.get_messages(
        limit=limit,
        offset=offset,
        from_msisdn=from_,
        since=since,
        q=q
    )
    
    return MessagesListResponse(
        data=[MessageResponse(**msg) for msg in messages],
        total=total,
        limit=limit,
        offset=offset
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats(request: Request):
    """
    Provide simple message-level analytics.
    Returns total messages, senders count, top senders, and timestamp range.
    """
    stats = db.get_stats()
    return StatsResponse(**stats)


@app.get("/health/live")
async def health_live():
    """Liveness probe - always returns 200 once app is running."""
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    """
    Readiness probe - returns 200 only if DB is reachable and WEBHOOK_SECRET is set.
    """
    if not settings.is_ready():
        raise HTTPException(status_code=503, detail="not ready")
    
    if not db.test_connection():
        raise HTTPException(status_code=503, detail="database not accessible")
    
    return {"status": "ready"}


@app.get("/metrics")
async def metrics():
    """Prometheus-style metrics endpoint."""
    return Response(content=get_metrics(), media_type="text/plain")


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Add request timing for metrics."""
    import time
    start_time = time.time()
    request.state.start_time = start_time
    response = await call_next(request)
    latency_ms = (time.time() - start_time) * 1000
    record_request(request.url.path, response.status_code, latency_ms)
    return response


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    logger.info("Application starting up")
    db._init_db()
    logger.info("Database initialized")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    logger.info("Application shutting down")

