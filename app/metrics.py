"""Prometheus-style metrics collection."""
from typing import Dict
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import CollectorRegistry, REGISTRY


# Create a custom registry
registry = CollectorRegistry()

# HTTP request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["path", "status"],
    registry=registry
)

# Webhook processing metrics
webhook_requests_total = Counter(
    "webhook_requests_total",
    "Total number of webhook processing outcomes",
    ["result"],
    registry=registry
)

# Request latency histogram
request_latency_ms = Histogram(
    "request_latency_ms",
    "HTTP request latency in milliseconds",
    buckets=[10, 50, 100, 200, 500, 1000, 2000, 5000, float("inf")],
    registry=registry
)


def get_metrics() -> bytes:
    """Get Prometheus metrics in text format."""
    return generate_latest(registry)


def record_request(path: str, status: int, latency_ms: float):
    """Record HTTP request metrics."""
    http_requests_total.labels(path=path, status=str(status)).inc()
    request_latency_ms.observe(latency_ms)


def record_webhook_result(result: str):
    """Record webhook processing result."""
    webhook_requests_total.labels(result=result).inc()

