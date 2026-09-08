"""Request middleware for correlation ID tracking"""

import uuid
from contextvars import ContextVar
from typing import Callable

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Context variable to store correlation ID
_correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')

logger = structlog.get_logger(__name__)


def get_correlation_id() -> str:
    """Get current correlation ID from context"""
    return _correlation_id.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to all requests and responses
    
    - Extracts correlation ID from X-Correlation-ID or X-Request-ID header
    - Generates new UUID if not provided
    - Adds to request context for access throughout request lifecycle
    - Returns correlation ID in response headers
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get(
            "x-correlation-id",
            request.headers.get("x-request-id", str(uuid.uuid4()))
        )

        # Set in context variable for access throughout request
        _correlation_id.set(correlation_id)

        # Log request with correlation ID
        logger.info(
            "request_started",
            path=request.url.path,
            method=request.method,
            correlation_id=correlation_id,
        )

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        # Log response
        logger.info(
            "request_completed",
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            correlation_id=correlation_id,
        )

        return response
