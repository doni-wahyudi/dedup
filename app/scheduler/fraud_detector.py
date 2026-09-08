"""Fraud detection scheduler using APScheduler"""

from datetime import datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config.settings import settings
from app.core.milvus import milvus_client
from app.services.fraud_detection_service import fraud_detection_service

logger = structlog.get_logger(__name__)


class FraudDetectorScheduler:
    """Scheduler for running fraud detection tasks
    
    Supports concurrent execution with modulo-based distribution.
    """
    
    def __init__(self, scheduler_id: int = None, total_schedulers: int = None):
        """Initialize scheduler
        
        Args:
            scheduler_id: Scheduler ID (0-indexed) for multi-instance
            total_schedulers: Total number of scheduler instances
        """
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.scheduler_id = scheduler_id
        self.total_schedulers = total_schedulers
        self._job_id = f"fraud_detector_job_{scheduler_id}" if scheduler_id is not None else "fraud_detector_job"
    
    def start(self):
        """Start the fraud detection scheduler"""
        if not settings.fraud_detector_enabled:
            logger.info("fraud_detector_disabled", enabled=False)
            return
        
        if self.is_running:
            logger.warning("scheduler_already_running")
            return
        
        # Initialize Milvus client for fraud detection service
        fraud_detection_service.set_milvus_client(milvus_client)
        
        # Configure scheduler distribution if specified
        if self.scheduler_id is not None and self.total_schedulers:
            fraud_detection_service.set_scheduler(
                scheduler_id=self.scheduler_id,
                total_schedulers=self.total_schedulers
            )
        
        # Add job to scheduler
        self.scheduler.add_job(
            func=self._run_fraud_detection,
            trigger=IntervalTrigger(seconds=settings.fraud_detector_interval_seconds),
            id=self._job_id,
            name="Fraud Detection Job",
            replace_existing=True,
            max_instances=1,  # Prevent concurrent executions - WAIT for previous job to finish
            misfire_grace_time=None,  # Never skip missed runs - always execute when ready
            coalesce=True  # If multiple runs are pending, merge them into one
        )
        
        # Start scheduler
        self.scheduler.start()
        self.is_running = True
        
        logger.info(
            "fraud_detector_scheduler_started",
            scheduler_id=self.scheduler_id,
            total_schedulers=self.total_schedulers,
            interval_seconds=settings.fraud_detector_interval_seconds,
            batch_size=settings.fraud_detector_batch_size,
            threshold=settings.fraud_detector_threshold,
            top_k=settings.fraud_detector_top_k
        )
    
    def stop(self):
        """Stop the fraud detection scheduler"""
        if not self.is_running:
            logger.warning("scheduler_not_running")
            return
        
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("fraud_detector_scheduler_stopped")
    
    def _run_fraud_detection(self):
        """Execute fraud detection batch processing"""
        try:
            start_time = datetime.now()
            logger.info("fraud_detection_job_started")
            
            # Process batch
            stats = fraud_detection_service.process_fraud_detection_batch()
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                "fraud_detection_job_completed",
                duration_seconds=duration,
                **stats
            )
            
        except Exception as e:
            logger.error(
                "fraud_detection_job_failed",
                error=str(e),
                error_type=type(e).__name__
            )
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            "enabled": settings.fraud_detector_enabled,
            "running": self.is_running,
            "interval_seconds": settings.fraud_detector_interval_seconds,
            "next_run": self.scheduler.get_job(self._job_id).next_run_time.isoformat() 
                        if self.is_running and self.scheduler.get_job(self._job_id) else None
        }


# Global instance
fraud_detector_scheduler = FraudDetectorScheduler()
