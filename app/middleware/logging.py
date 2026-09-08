"""Request/Response logging middleware"""

import logging
import time
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.correlation_id import get_correlation_id


def configure_logging():
    """Configure structured logging for production"""
    
    # Suppress verbose third-party logging dan warnings
    import warnings

    warnings.filterwarnings("ignore", category=FutureWarning, module="insightface")
    
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.schedulers.base").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors.base").setLevel(logging.WARNING)
    logging.getLogger("pymilvus").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("insightface").setLevel(logging.WARNING)
    
    # Configure standard logging with JSON formatter
    # UNBUFFERED output (line buffering)
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
        force=True,
    )
    
    # Configure structlog for production JSON output
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(serializer=_json_serializer)
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _json_serializer(obj, **kwargs):
    """Custom JSON serializer for non-JSON-serializable objects"""
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    return str(obj)


logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses in JSON format"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details in structured JSON format"""
        # Get correlation ID (set by CorrelationIdMiddleware)
        correlation_id = get_correlation_id()
        
        # Start timer
        start_time = time.time()
        
        # Extract client info
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else 0
        
        # Log incoming request
        logger.info(
            "http.request.start",
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            query_string=str(request.url.query) if request.url.query else None,
            client_host=client_host,
            client_port=client_port,
            user_agent=request.headers.get("user-agent", "unknown"),
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log successful response
            logger.info(
                "http.request.completed",
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
                client_host=client_host,
            )
            
            # Ensure correlation ID is in response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error response
            logger.error(
                "http.request.failed",
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                error=str(e),
                error_type=type(e).__name__,
                client_host=client_host,
            )
            
            # Re-raise exception to be handled by error handler
            raise
