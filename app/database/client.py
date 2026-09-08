"""SQL Server database client using SQLAlchemy"""

from contextlib import contextmanager
from typing import Optional

import structlog
from sqlalchemy import create_engine, text, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import QueuePool

from app.config.settings import settings
from app.utils.exceptions import DatabaseError

logger = structlog.get_logger(__name__)

# SQLAlchemy Base for models with custom schema support
metadata = MetaData(schema=settings.db_schema)
Base = declarative_base(metadata=metadata)


class DatabaseClient:
    """SQL Server database client with SQLAlchemy"""
    
    def __init__(self):
        self.database_url = settings.database_url
        self.engine: Optional[object] = None
        self.session_factory: Optional[sessionmaker] = None
        self._connected = False
    
    def connect(self) -> None:
        """Establish connection to SQL Server"""
        try:
            # Create synchronous engine with connection pooling
            self.engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=settings.db_pool_size,
                pool_recycle=settings.db_pool_recycle,
                pool_pre_ping=True,  # Validate connections before use
                echo=settings.db_echo,  # Log SQL queries if enabled
                isolation_level="READ_COMMITTED"
            )
            
            # Test connection
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as test"))
                test_value = result.scalar()
                if test_value != 1:
                    raise DatabaseError("Database connection test failed")
            
            # Create session factory
            self.session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
            
            self._connected = True
            
            logger.info(
                "connected_to_database",
                server=settings.db_server,
                database=settings.db_name,
                pool_size=settings.db_pool_size
            )
            
        except Exception as e:
            logger.error("database_connection_failed", error=str(e))
            raise DatabaseError(
                message=f"Failed to connect to SQL Server: {str(e)}",
                details={
                    "server": settings.db_server,
                    "database": settings.db_name,
                    "driver": settings.db_driver
                }
            )
    
    def disconnect(self) -> None:
        """Disconnect from SQL Server"""
        try:
            if self.engine:
                self.engine.dispose()
                self.engine = None
                self.session_factory = None
                self._connected = False
                logger.info("disconnected_from_database")
        except Exception as e:
            logger.warning("database_disconnect_warning", error=str(e))
    
    def create_tables(self) -> None:
        """Create all tables defined by SQLAlchemy models"""
        try:
            if not self._connected:
                raise DatabaseError("Database not connected")
            
            # Import models here to avoid circular imports
            from app.database.models import BulkImportJob, BulkImportError, BulkImportStats
            
            # Create all tables
            Base.metadata.create_all(bind=self.engine)
            
            logger.info("database_tables_created")
            
        except Exception as e:
            logger.error("table_creation_failed", error=str(e))
            raise DatabaseError(f"Failed to create tables: {str(e)}")
    
    @contextmanager
    def get_session(self) -> Session:
        """Get database session with automatic cleanup"""
        if not self._connected or not self.session_factory:
            raise DatabaseError("Database not connected")
        
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("database_session_error", error=str(e))
            raise
        finally:
            session.close()
    
    def execute_query(self, query: str, params: Optional[dict] = None) -> list:
        """Execute raw SQL query and return results"""
        try:
            with self.get_session() as session:
                result = session.execute(text(query), params or {})
                
                # Handle different result types
                if result.returns_rows:
                    return [dict(row._mapping) for row in result]
                else:
                    return [{"affected_rows": result.rowcount}]
                    
        except Exception as e:
            logger.error("query_execution_failed", query=query, error=str(e))
            raise DatabaseError(f"Failed to execute query: {str(e)}")
    
    def health_check(self) -> bool:
        """Check database connection health"""
        try:
            if not self._connected:
                return False
            
            with self.get_session() as session:
                result = session.execute(text("SELECT 1 as health_check"))
                return result.scalar() == 1
                
        except Exception as e:
            logger.warning("database_health_check_failed", error=str(e))
            return False
    
    def get_stats(self) -> dict:
        """Get database connection statistics"""
        try:
            stats = {
                "connected": self._connected,
                "pool_size": settings.db_pool_size,
                "database_name": settings.db_name,
                "server": settings.db_server
            }
            
            if self.engine and hasattr(self.engine, 'pool'):
                pool = self.engine.pool
                stats.update({
                    "pool_checked_in": pool.checkedin(),
                    "pool_checked_out": pool.checkedout(),
                    "pool_overflow": pool.overflow(),
                    "pool_invalid": pool.invalid()
                })
            
            return stats
            
        except Exception as e:
            logger.error("get_database_stats_failed", error=str(e))
            return {"connected": False, "error": str(e)}


# Global database client instance
db_client = DatabaseClient()