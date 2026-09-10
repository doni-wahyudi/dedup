"""Main FastAPI application for Dedup Service"""

import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.correlation_id import CorrelationIdMiddleware
# Configure logging
from app.middleware.logging import configure_logging, LoggingMiddleware

configure_logging()

import structlog
from app.config.settings import settings
from app.core.milvus import milvus_client
from app.database.client import db_client
from app.middleware.error_handler import register_error_handlers
from app.models.schemas import HealthCheckResponse
from app.scheduler.fraud_detector import fraud_detector_scheduler, FraudDetectorScheduler
from app.services.dedup_service import dedup_service

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(
        "starting_dedup_service",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment
    )
    
    try:
        # Warm up InsightFace model/runtime to reduce first-request latency
        logger.info("warming_up_insightface")
        warmup_start = time.time()
        dedup_service.insightface_client.warmup()
        logger.info(
            "insightface_warmup_finished",
            warmup_ms=round((time.time() - warmup_start) * 1000, 1)
        )

        import socket

        def is_service_reachable(host: str, port: int, timeout: float = 0.5) -> bool:
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    return True
            except Exception:
                return False

        # Connect to Milvus (optional for standalone 1:1 face comparison)
        if is_service_reachable(settings.milvus_host, settings.milvus_port, timeout=0.3):
            try:
                milvus_client.connect()
                milvus_client.init_collection()
                logger.info("milvus_connected_successfully")
            except Exception as e:
                logger.warning(
                    "milvus_connection_skipped",
                    error=str(e),
                    note="Running in standalone mode without Milvus. 1:1 face comparison (/faces/compare) is fully functional."
                )
        else:
            logger.info("milvus_port_unreachable_standalone_mode", host=settings.milvus_host, port=settings.milvus_port)

        # Connect to SQL Server Database (optional for standalone 1:1 face comparison)
        if is_service_reachable(settings.db_server, settings.db_port, timeout=0.3):
            try:
                logger.info("initializing_database")
                db_client.connect()
                logger.info("database_initialized")
            except Exception as e:
                logger.warning(
                    "database_connection_skipped",
                    error=str(e),
                    note="Running without SQL Server connection."
                )
        else:
            logger.info("database_port_unreachable_standalone_mode", server=settings.db_server, port=settings.db_port)

        # Start fraud detection scheduler (only if Milvus and DB are both available)
        app.state.scheduler = None
        if settings.fraud_detector_enabled and milvus_client.health_check() and db_client.health_check():
            logger.info("starting_fraud_detector_scheduler")
            if settings.fraud_detector_scheduler_id is not None and settings.fraud_detector_total_schedulers:
                scheduler = FraudDetectorScheduler(
                    scheduler_id=settings.fraud_detector_scheduler_id,
                    total_schedulers=settings.fraud_detector_total_schedulers
                )
                scheduler.start()
                app.state.scheduler = scheduler
            else:
                fraud_detector_scheduler.start()
                app.state.scheduler = fraud_detector_scheduler
        else:
            logger.info("fraud_detector_scheduler_skipped")

        logger.info("dedup_service_started_successfully")
    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("shutting_down_dedup_service")

    try:
        if getattr(app.state, "scheduler", None) is not None:
            app.state.scheduler.stop()
            logger.info("fraud_detector_scheduler_stopped")
    except Exception as e:
        logger.warning("scheduler_stop_warning", error=str(e))

    try:
        if milvus_client._connected:
            milvus_client.disconnect()
            logger.info("milvus_disconnected")
    except Exception as e:
        logger.warning("milvus_disconnect_warning", error=str(e))

    try:
        if db_client._connected:
            db_client.disconnect()
            logger.info("database_disconnected")
    except Exception as e:
        logger.warning("database_disconnect_warning", error=str(e))

    logger.info("dedup_service_shutdown_complete")


# Create FastAPI app
app = FastAPI(
    title="Dedup Service - Face Similarity Search API",
    description="""
    A microservice for searching similar faces and detecting duplicates in enrollment database.
    
    ## Features
    - **Dynamic Top-K**: Configure number of results (1-100)
    - **Adjustable Threshold**: Set minimum similarity score (0.0-1.0)
    - **Fraud Detection**: Automatic analysis of suspicious patterns
    - **Flexible Filtering**: Filter by Sentra ID
    - **L2 Distance**: L2 distance metric for face matching (lower distance = more similar)
    
    ## Use Cases
    - Duplicate detection during enrollment
    - Fraud prevention (same face, different NIK)
    - Identity verification
    - Family member detection
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add middleware - order matters: last added = outermost = executes FIRST on request

# LoggingMiddleware (innermost - executes after CorrelationId is set)
app.add_middleware(LoggingMiddleware)

# CorrelationIdMiddleware (middle - sets correlation_id before logging reads it)
app.add_middleware(CorrelationIdMiddleware)

# CORS middleware (outermost - executes first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register error handlers
register_error_handlers(app)

# Include routers  
from app.api.v1 import faces, enrollments, fraud
app.include_router(faces.router, prefix=settings.api_v1_prefix)
app.include_router(enrollments.router, prefix=settings.api_v1_prefix)
app.include_router(fraud.router, prefix=settings.api_v1_prefix)


@app.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["health"],
    summary="Health check endpoint",
    description="Check the health status of the face search service"
)
async def health_check():
    """Health check endpoint"""
    try:
        is_milvus_healthy = milvus_client.health_check()
        is_db_healthy = db_client.health_check()

        if is_milvus_healthy and is_db_healthy:
            status_text = "healthy"
        elif is_milvus_healthy or is_db_healthy:
            status_text = "degraded"
        else:
            # Standalone mode: InsightFace is available for 1:1 comparison
            status_text = "healthy (standalone mode)"

        return HealthCheckResponse(
            status=status_text,
            version=settings.app_version,
            timestamp=datetime.now()
        )
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return HealthCheckResponse(
            status="unhealthy",
            version=settings.app_version,
            timestamp=datetime.now()
        )


@app.get(
    "/",
    tags=["root"],
    summary="Root endpoint",
    description="Get basic information about the dedup service"
)
async def root():
    """Root endpoint"""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "api": settings.api_v1_prefix
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_config=None,  # Disable Uvicorn's default logging, use structlog instead
        access_log=False  # Disable access log (we handle it with middleware)
    )
