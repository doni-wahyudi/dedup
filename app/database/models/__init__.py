"""Database model base imports and common dependencies"""

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, JSON
from sqlalchemy.sql import func

from app.database.client import Base
# Import all models from domain modules
from .bulk_import import BulkImportJob, BulkImportError, BulkImportStats
from .enrollment import EnrolledFace, FraudCase

# Re-export for convenience
__all__ = [
    'Base',
    'Column', 'Integer', 'String', 'DateTime', 'Text', 'Boolean', 'Float', 'JSON',
    'func', 'sa', 'datetime', 'Optional',
    # Models
    'BulkImportJob', 'BulkImportError', 'BulkImportStats',
    'EnrolledFace', 'FraudCase'
]