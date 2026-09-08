"""Repository for bulk import operations"""

from typing import List, Optional, Dict

import structlog

from app.database.models.bulk_import import BulkImportJob, BulkImportError, BulkImportStats
from app.database.repositories import BaseRepository

logger = structlog.get_logger(__name__)


class BulkImportJobRepository(BaseRepository[BulkImportJob]):
    """Specialized repository for BulkImportJob operations"""
    
    def __init__(self):
        super().__init__(BulkImportJob)
    
    def find_by_status(self, status: str) -> List[BulkImportJob]:
        """Find jobs by status"""
        return self.find_by(status=status)
    
    def find_active_jobs(self) -> List[BulkImportJob]:
        """Find all active (running/pending) jobs"""
        try:
            with self.db_client.get_session() as session:
                jobs = session.query(self.model).filter(
                    self.model.status.in_(['pending', 'running', 'paused'])
                ).all()
                return jobs
        except Exception as e:
            logger.error("find_active_jobs_failed", error=str(e))
            raise
    
    def find_resumable_jobs(self) -> List[BulkImportJob]:
        """Find jobs that can be resumed"""
        try:
            with self.db_client.get_session() as session:
                jobs = session.query(self.model).filter(
                    self.model.status.in_(['failed', 'paused']),
                    self.model.current_row > 0  # Has some progress
                ).all()
                return jobs
        except Exception as e:
            logger.error("find_resumable_jobs_failed", error=str(e))
            raise


class BulkImportErrorRepository(BaseRepository[BulkImportError]):
    """Specialized repository for BulkImportError operations"""
    
    def __init__(self):
        super().__init__(BulkImportError)
    
    def find_by_job_id(self, job_id: str, limit: int = 100) -> List[BulkImportError]:
        """Find errors by job ID with limit"""
        try:
            with self.db_client.get_session() as session:
                errors = session.query(self.model).filter(
                    self.model.job_id == job_id
                ).order_by(self.model.created_at.desc()).limit(limit).all()
                return errors
        except Exception as e:
            logger.error("find_errors_by_job_failed", job_id=job_id, error=str(e))
            raise
    
    def find_by_category(self, job_id: str, error_category: str) -> List[BulkImportError]:
        """Find errors by category"""
        return self.find_by(job_id=job_id, error_category=error_category)
    
    def get_error_summary(self, job_id: str) -> Dict[str, int]:
        """Get error count summary by category"""
        try:
            with self.db_client.get_session() as session:
                from sqlalchemy import func
                results = session.query(
                    self.model.error_category,
                    func.count(self.model.id).label('count')
                ).filter(
                    self.model.job_id == job_id
                ).group_by(self.model.error_category).all()
                
                return {category: count for category, count in results}
        except Exception as e:
            logger.error("get_error_summary_failed", job_id=job_id, error=str(e))
            raise


class BulkImportStatsRepository(BaseRepository[BulkImportStats]):
    """Specialized repository for BulkImportStats operations"""
    
    def __init__(self):
        super().__init__(BulkImportStats)
    
    def find_by_job_id(self, job_id: str) -> Optional[BulkImportStats]:
        """Find stats by job ID"""
        stats = self.find_by(job_id=job_id)
        return stats[0] if stats else None