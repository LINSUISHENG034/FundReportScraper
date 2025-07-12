"""
Database connection and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator

from src.core.config import settings
from src.core.logging import get_logger
from src.models.database import Base

logger = get_logger(__name__)


class DatabaseManager:
    """Database connection manager."""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or settings.database.url
        self._engine = None
        self._session_factory = None
        
    @property
    def engine(self):
        """Get database engine, create if not exists."""
        if self._engine is None:
            logger.info("database.engine.creating", url=self.database_url)
            
            # Engine configuration
            engine_kwargs = {
                "echo": settings.debug,  # Log SQL in debug mode
                "pool_pre_ping": True,   # Validate connections
            }
            
            # Special handling for SQLite (testing)
            if self.database_url.startswith("sqlite"):
                engine_kwargs.update({
                    "poolclass": StaticPool,
                    "connect_args": {"check_same_thread": False}
                })
            
            self._engine = create_engine(self.database_url, **engine_kwargs)
            logger.info("database.engine.created")
            
        return self._engine
    
    @property
    def session_factory(self):
        """Get session factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory
    
    def create_tables(self):
        """Create all tables."""
        logger.info("database.tables.creating")
        Base.metadata.create_all(bind=self.engine)
        logger.info("database.tables.created")
    
    def drop_tables(self):
        """Drop all tables (use with caution)."""
        logger.warning("database.tables.dropping")
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("database.tables.dropped")
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.session_factory()
    
    def close(self):
        """Close database connections."""
        if self._engine:
            logger.info("database.connections.closing")
            self._engine.dispose()
            self._engine = None
            self._session_factory = None


# Global database manager instance
db_manager = DatabaseManager()


def get_db_session() -> Generator[Session, None, None]:
    """
    Dependency for getting database session.
    Used with FastAPI dependency injection.
    """
    session = db_manager.get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database():
    """Initialize database tables."""
    logger.info("database.initializing")
    db_manager.create_tables()
    logger.info("database.initialized")