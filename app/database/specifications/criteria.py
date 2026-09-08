"""Search criteria and query operators for specification pattern"""

from enum import Enum
from typing import List, Any


class QueryOperator(str, Enum):
    """Query operators for filtering"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    LIKE = "like"
    ILIKE = "ilike"
    LESS_THAN = "less_than"
    LESS_EQUAL = "less_equal"
    GREATER_THAN = "greater_than"
    GREATER_EQUAL = "greater_equal"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    BETWEEN = "between"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


class Filter:
    """Filter criteria for database queries"""
    
    def __init__(self, field: str, operator: QueryOperator, value: Any = None):
        self.field = field
        self.operator = operator
        self.value = value
    
    def __repr__(self):
        return f"Filter(field='{self.field}', operator='{self.operator}', value={self.value})"


class SortCriteria:
    """Sort criteria for database queries"""
    
    def __init__(self, field: str, ascending: bool = True):
        self.field = field
        self.ascending = ascending
    
    def __repr__(self):
        direction = "ASC" if self.ascending else "DESC"
        return f"SortCriteria(field='{self.field}', direction='{direction}')"


class SearchCriteria:
    """Complete search criteria with filters and sorting"""
    
    def __init__(
        self, 
        filters: List[Filter] = None,
        sorts: List[SortCriteria] = None,
        page: int = None,
        page_size: int = None
    ):
        self.filters = filters or []
        self.sorts = sorts or []
        self.page = page
        self.page_size = page_size
    
    def add_filter(self, field: str, operator: QueryOperator, value: Any = None) -> 'SearchCriteria':
        """Add filter to search criteria"""
        self.filters.append(Filter(field, operator, value))
        return self
    
    def add_sort(self, field: str, ascending: bool = True) -> 'SearchCriteria':
        """Add sort to search criteria"""
        self.sorts.append(SortCriteria(field, ascending))
        return self
    
    def set_pagination(self, page: int, page_size: int) -> 'SearchCriteria':
        """Set pagination parameters"""
        self.page = page
        self.page_size = page_size
        return self
    
    def __repr__(self):
        return f"SearchCriteria(filters={len(self.filters)}, sorts={len(self.sorts)}, page={self.page})"