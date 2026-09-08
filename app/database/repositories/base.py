"""Base repository classes for database operations"""

from typing import List, Type, TypeVar, Generic, Optional, Dict, Any

import structlog
from sqlalchemy.orm import joinedload

from app.database.client import db_client
from app.database.specifications import Specification
from app.database.specifications.criteria import SearchCriteria, Filter

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """Base repository class with common database operations"""

    def __init__(self, model: Type[T]):
        self.model = model
        self.db_client = db_client

    def add(self, entity: T) -> T:
        """Add single entity to database"""
        try:
            with self.db_client.get_session() as session:
                session.add(entity)
                session.flush()
                session.refresh(entity)
                logger.debug("entity_added", model=self.model.__name__, id=getattr(entity, 'id', None))
                return entity
        except Exception as e:
            logger.error("add_entity_failed", model=self.model.__name__, error=str(e))
            raise

    def get(self, entity_id: int) -> Optional[T]:
        """Get entity by ID"""
        try:
            with self.db_client.get_session() as session:
                entity = session.get(self.model, entity_id)
                logger.debug("entity_retrieved", model=self.model.__name__, id=entity_id, found=entity is not None)
                return entity
        except Exception as e:
            logger.error("get_entity_failed", model=self.model.__name__, id=entity_id, error=str(e))
            raise

    def get_all(self, load_relationships: bool = False) -> List[T]:
        """Get all entities"""
        try:
            with self.db_client.get_session() as session:
                query = session.query(self.model)
                if load_relationships:
                    query = query.options(joinedload('*'))
                entities = query.all()
                logger.debug("entities_retrieved", model=self.model.__name__, count=len(entities))
                return entities
        except Exception as e:
            logger.error("get_all_entities_failed", model=self.model.__name__, error=str(e))
            raise

    def update(self, entity: T) -> T:
        """Update existing entity"""
        try:
            with self.db_client.get_session() as session:
                merged_entity = session.merge(entity)
                session.flush()
                session.refresh(merged_entity)
                logger.debug("entity_updated", model=self.model.__name__, id=getattr(merged_entity, 'id', None))
                return merged_entity
        except Exception as e:
            logger.error("update_entity_failed", model=self.model.__name__, error=str(e))
            raise

    def delete(self, entity: T) -> bool:
        """Delete entity"""
        try:
            with self.db_client.get_session() as session:
                session.delete(entity)
                logger.debug("entity_deleted", model=self.model.__name__, id=getattr(entity, 'id', None))
                return True
        except Exception as e:
            logger.error("delete_entity_failed", model=self.model.__name__, error=str(e))
            raise

    def find_by(self, **kwargs) -> List[T]:
        """Find entities by field values"""
        try:
            with self.db_client.get_session() as session:
                query = session.query(self.model)

                for field, value in kwargs.items():
                    if hasattr(self.model, field):
                        query = query.filter(getattr(self.model, field) == value)

                entities = query.all()
                logger.debug("entities_found", model=self.model.__name__, criteria=kwargs, count=len(entities))
                return entities
        except Exception as e:
            logger.error("find_by_failed", model=self.model.__name__, criteria=kwargs, error=str(e))
            raise

    def get_by_specification(
        self,
        filters: Optional[List[Filter]] = None,
        sorts: Optional[List[tuple]] = None,
        load_relationships: bool = False
    ) -> List[T]:
        """
        Get entities by specification without pagination

        Args:
            filters: List of Filter objects
            sorts: List of (field_name, ascending) tuples
            load_relationships: Load all relationships

        Returns:
            List of entities matching the specification
        """
        try:
            filters = filters or []
            sorts = sorts or []

            search_criteria = SearchCriteria(filters=filters)
            for field, ascending in sorts:
                search_criteria.add_sort(field, ascending=ascending)

            spec = Specification(search_criteria)

            with self.db_client.get_session() as session:
                query = spec.apply(session.query(self.model), self.model)
                if load_relationships:
                    query = query.options(joinedload('*'))
                entities = query.all()
                logger.debug(
                    "get_by_specification_success",
                    model=self.model.__name__,
                    count=len(entities)
                )
                return entities
        except Exception as e:
            logger.error("get_by_specification_failed", model=self.model.__name__, error=str(e))
            raise


class GenericRepository(BaseRepository[T]):
    """Generic repository with additional functionality"""

    def bulk_insert(self, entities: List[T]) -> List[T]:
        """Bulk insert entities"""
        try:
            with self.db_client.get_session() as session:
                session.add_all(entities)
                session.flush()
                for entity in entities:
                    session.refresh(entity)
                logger.debug("bulk_entities_added", model=self.model.__name__, count=len(entities))
                return entities
        except Exception as e:
            logger.error("bulk_insert_failed", model=self.model.__name__, count=len(entities), error=str(e))
            raise

    def paginate(
        self,
        filters: Optional[List[Filter]] = None,
        sorts: Optional[List[tuple]] = None,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        Paginate query results with filters and sorting

        Args:
            filters: List of Filter objects
            sorts: List of (field_name, ascending) tuples
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Dict with data and pagination metadata
        """
        try:
            filters = filters or []
            sorts = sorts or []

            count_criteria = SearchCriteria(filters=filters)
            count_spec = Specification(count_criteria)

            with self.db_client.get_session() as session:
                count_query = count_spec.apply(session.query(self.model), self.model)
                total_count = count_query.count()

                search_criteria = SearchCriteria(filters=filters)
                for field, ascending in sorts:
                    search_criteria.add_sort(field, ascending=ascending)
                search_criteria.set_pagination(page, page_size)

                fetch_spec = Specification(search_criteria)
                paginated_query = fetch_spec.apply(session.query(self.model), self.model)
                data = paginated_query.all()

                total_pages = (total_count + page_size - 1) // page_size

                logger.debug(
                    "pagination_success",
                    model=self.model.__name__,
                    page=page,
                    page_size=page_size,
                    total_count=total_count,
                    returned_count=len(data)
                )

                return {
                    "data": data,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_count": total_count,
                        "total_pages": total_pages
                    }
                }
        except Exception as e:
            logger.error(
                "pagination_failed",
                model=self.model.__name__,
                page=page,
                page_size=page_size,
                error=str(e)
            )
            raise

