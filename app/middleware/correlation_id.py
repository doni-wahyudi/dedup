"""Request middleware for correlation ID tracking"""

import uuid
from contextvars import ContextVar
from typing import Callable

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Context variables to store correlation ID and source channel
_correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')
_source_channel: ContextVar[str] = ContextVar('source_channel', default='')

logger = structlog.get_logger(__name__)


def get_correlation_id() -> str:
    """Get current correlation ID from context"""
    return _correlation_id.get()


def get_source_channel() -> str:
    """Get current source channel from context"""
    return _source_channel.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID and source channel to all requests and responses
    
    - Extracts correlation ID from X-Correlation-ID or X-Request-ID header
    - Extracts source channel from X-Channel, X-Source-Channel, or Channel header
    - Generates new UUID if correlation ID not provided
    - Adds both to request context for access throughout request lifecycle
    - Returns correlation ID and source channel in response headers
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get(
            "x-correlation-id",
            request.headers.get("x-request-id", str(uuid.uuid4()))
        )
        _correlation_id.set(correlation_id)

        # Extract source channel from headers
        source_channel = request.headers.get(
            "x-channel",
            request.headers.get(
                "x-source-channel",
                request.headers.get("channel", "")
            )
        )
        _source_channel.set(source_channel)

        # Log request with correlation ID and source channel
        logger.info(
            "request_started",
            path=request.url.path,
            method=request.method,
            correlation_id=correlation_id,
            source_channel=source_channel or None,
        )

        # Process request
        response = await call_next(request)

        # Add correlation ID and channel to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        if source_channel:
            response.headers["X-Channel"] = source_channel

        # Log response
        logger.info(
            "request_completed",
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            correlation_id=correlation_id,
            source_channel=source_channel or None,
        )

        return response
