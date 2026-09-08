"""Database specification base classes for advanced querying"""

from app.database.specifications.criteria import SearchCriteria, Filter, QueryOperator
from app.database.specifications.specification import Specification

__all__ = ['Specification', 'SearchCriteria', 'Filter', 'QueryOperator']