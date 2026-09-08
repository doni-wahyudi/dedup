"""Specification pattern implementation for SQLAlchemy queries"""

from typing import Any, Tuple

import structlog
from sqlalchemy import desc, asc
from sqlalchemy.orm import Query

from .criteria import SearchCriteria, QueryOperator, SortCriteria

logger = structlog.get_logger(__name__)


class Specification:
    """Specification pattern for building complex database queries"""
    
    def __init__(self, search_criteria: SearchCriteria):
        self.search_criteria = search_criteria
    
    def apply(self, query: Query, model_class: Any = None) -> Query:
        """Apply specification to SQLAlchemy query"""
        
        try:
            # Get model class from query if not provided
            if model_class is None and hasattr(query, 'column_descriptions'):
                if query.column_descriptions:
                    model_class = query.column_descriptions[0].get('entity')
            
            # Apply filters
            for filter_obj in self.search_criteria.filters:
                query = self._apply_filter(query, filter_obj, model_class)
            
            # Apply sorting
            for sort_criteria in self.search_criteria.sorts:
                query = self._apply_sort(query, sort_criteria, model_class)
            
            # Apply pagination
            if self.search_criteria.page and self.search_criteria.page_size:
                offset = (self.search_criteria.page - 1) * self.search_criteria.page_size
                query = query.offset(offset).limit(self.search_criteria.page_size)
            
            return query
            
        except Exception as e:
            logger.error("specification_apply_failed", error=str(e))
            raise
    
    def _apply_filter(self, query: Query, filter_obj: Any, model_class: Any) -> Query:
        """Apply single filter to query"""
        
        try:
            # Get field from model (this also handles joins for relationships)
            field, query = self._get_field(filter_obj.field, model_class, query)
            
            # Apply operator
            if filter_obj.operator == QueryOperator.EQUALS:
                return query.filter(field == filter_obj.value)
            
            elif filter_obj.operator == QueryOperator.NOT_EQUALS:
                return query.filter(field != filter_obj.value)
            
            elif filter_obj.operator == QueryOperator.LIKE:
                return query.filter(field.like(f"%{filter_obj.value}%"))
            
            elif filter_obj.operator == QueryOperator.ILIKE:
                return query.filter(field.ilike(f"%{filter_obj.value}%"))
            
            elif filter_obj.operator == QueryOperator.STARTS_WITH:
                return query.filter(field.like(f"{filter_obj.value}%"))
            
            elif filter_obj.operator == QueryOperator.ENDS_WITH:
                return query.filter(field.like(f"%{filter_obj.value}"))
            
            elif filter_obj.operator == QueryOperator.LESS_THAN:
                return query.filter(field < filter_obj.value)
            
            elif filter_obj.operator == QueryOperator.LESS_EQUAL:
                return query.filter(field <= filter_obj.value)
            
            elif filter_obj.operator == QueryOperator.GREATER_THAN:
                return query.filter(field > filter_obj.value)
            
            elif filter_obj.operator == QueryOperator.GREATER_EQUAL:
                return query.filter(field >= filter_obj.value)
            
            elif filter_obj.operator == QueryOperator.IN:
                return query.filter(field.in_(filter_obj.value))
            
            elif filter_obj.operator == QueryOperator.NOT_IN:
                return query.filter(~field.in_(filter_obj.value))
            
            elif filter_obj.operator == QueryOperator.IS_NULL:
                return query.filter(field.is_(None))
            
            elif filter_obj.operator == QueryOperator.IS_NOT_NULL:
                return query.filter(field.isnot(None))
            
            elif filter_obj.operator == QueryOperator.BETWEEN:
                if isinstance(filter_obj.value, (list, tuple)) and len(filter_obj.value) == 2:
                    return query.filter(field.between(filter_obj.value[0], filter_obj.value[1]))
                else:
                    raise ValueError("BETWEEN operator requires list/tuple with 2 values")
            
            else:
                raise ValueError(f"Unsupported operator: {filter_obj.operator}")
                
        except Exception as e:
            logger.error("apply_filter_failed", field=filter_obj.field, operator=filter_obj.operator, error=str(e))
            raise
    
    def _apply_sort(self, query: Query, sort_criteria: SortCriteria, model_class: Any) -> Query:
        """Apply sorting to query"""
        try:
            field, query = self._get_field(sort_criteria.field, model_class, query)
            order_field = desc(field) if not sort_criteria.ascending else asc(field)
            return query.order_by(order_field)
        except Exception as e:
            logger.error("apply_sort_failed", field=sort_criteria.field, error=str(e))
            raise
    
    def _get_field(self, field_name: str, model_class: Any, query: Query) -> Tuple[Any, Query]:
        """Get field attribute from model, handling relationships with automatic joins
        
        Args:
            field_name: Field name (supports dot notation for relations, e.g., "relation.field")
            model_class: The model class to get the field from
            query: SQLAlchemy query object (may be updated with joins)
            
        Returns:
            Tuple of (field_attribute, updated_query) where query includes necessary joins
        """
        try:
            # Handle nested fields (e.g., "relation.field")
            if '.' in field_name:
                parts = field_name.split('.')
                current_attr = model_class
                
                # Navigate through relationships and perform joins
                for part in parts[:-1]:
                    relation_attr = getattr(current_attr, part)
                    query = query.join(relation_attr)
                    
                    # Get the related model class
                    if hasattr(relation_attr.property, 'mapper'):
                        current_attr = relation_attr.property.mapper.class_
                    else:
                        raise AttributeError(f"Cannot navigate to {part} in {current_attr}")
                
                # Return the final field
                final_field = parts[-1]
                return getattr(current_attr, final_field), query
            else:
                # Simple field on main model
                return getattr(model_class, field_name), query
                
        except AttributeError as e:
            logger.error("field_not_found", field=field_name, model=model_class.__name__ if model_class else None)
            raise AttributeError(f"Field '{field_name}' not found on model")
        except Exception as e:
            logger.error("get_field_failed", field=field_name, error=str(e))
            raise


class CompositeSpecification(Specification):
    """Composite specification for combining multiple specifications"""
    
    def __init__(self, *specifications, logic_operator: str = "and"):
        self.specifications = specifications
        self.logic_operator = logic_operator.lower()
    
    def apply(self, query: Query, model_class: Any = None) -> Query:
        """Apply all specifications with logic operator"""
        
        if not self.specifications:
            return query
        
        # Apply each specification to the query
        for spec in self.specifications:
            query = spec.apply(query, model_class)
        
        return query