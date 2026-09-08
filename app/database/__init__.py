"""Database package for enrollment-embedding-service

Clean, organized database layer following domain-driven design principles.
Direct repository access without complex manager layers.
"""

# Core database components
from .client import DatabaseClient, db_client
# Models - organized by domain
from .models.bulk_import import BulkImportJob, BulkImportError, BulkImportStats
from .models.enrollment import EnrolledFace, FraudCase
# Base repository classes
from .repositories import BaseRepository, GenericRepository
# Repositories - organized by domain
from .repositories.bulk_import import (
    BulkImportJobRepository,
    BulkImportErrorRepository,
    BulkImportStatsRepository
)
from .repositories.enrollment import (
    EnrolledFaceRepository,
    FraudCaseRepository
)
# Query specifications
from .specifications.criteria import SearchCriteria, Filter, SortCriteria, QueryOperator
from .specifications.specification import Specification

__all__ = [
    # Database client
    'DatabaseClient',
    'db_client',
    
    # Models - Bulk Import Domain
    'BulkImportJob',
    'BulkImportError', 
    'BulkImportStats',
    
    # Models - Enrollment Domain
    'EnrolledFace',
    'FraudCase',
    
    # Repositories - Base Classes
    'BaseRepository',
    'GenericRepository',
    
    # Repositories - Bulk Import Domain
    'BulkImportJobRepository',
    'BulkImportErrorRepository',
    'BulkImportStatsRepository',
    
    # Repositories - Enrollment Domain
    'EnrolledFaceRepository',
    'FraudCaseRepository',
    
    # Query Specifications
    'SearchCriteria',
    'Filter',
    'SortCriteria',
    'QueryOperator',
    'Specification',
]