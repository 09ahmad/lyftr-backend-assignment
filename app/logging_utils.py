"""Structured JSON logging utilities."""
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Add request context if available (from middleware)
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "status"):
            log_data["status"] = record.status
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
        if hasattr(record, "message_id"):
            log_data["message_id"] = record.message_id
        if hasattr(record, "dup"):
            log_data["dup"] = record.dup
        if hasattr(record, "result"):
            log_data["result"] = record.result
        
        # Add extra fields from logger.info(..., extra={...})
        # These are stored in record.__dict__
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            }
        }
        log_data.update(extra_fields)
        
        return json.dumps(log_data)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests in structured JSON format."""
    
    async def dispatch(self, request: Request, call_next):
        """Process request and log structured data."""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Store request_id in request state
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Create log record
        logger = logging.getLogger("http")
        log_record = logging.LogRecord(
            name="http",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=f"{request.method} {request.url.path} {response.status_code}",
            args=(),
            exc_info=None
        )
        log_record.request_id = request_id
        log_record.method = request.method
        log_record.path = request.url.path
        log_record.status = response.status_code
        log_record.latency_ms = latency_ms
        
        logger.handle(log_record)
        
        return response


def setup_logging(log_level: str = "INFO"):
    """Setup structured JSON logging."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Add console handler with JSON formatter
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    return logger

