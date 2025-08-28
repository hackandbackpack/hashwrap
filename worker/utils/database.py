"""
Database utilities for worker tasks.
Provides database session management and connection handling.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.app.core.config import get_settings


# Global database engine and session factory
_engine = None
_session_factory = None


def get_engine():
    """Get database engine, creating it if necessary."""
    global _engine
    
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=300,  # 5 minutes
            echo=settings.DEBUG
        )
    
    return _engine


def get_session_factory():
    """Get session factory, creating it if necessary."""
    global _session_factory
    
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False
        )
    
    return _session_factory


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Get database session with automatic cleanup.
    
    Usage:
        with get_db_session() as db:
            # Use db session
            user = db.query(User).first()
            # Session automatically closed and cleaned up
    """
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class DatabaseHealthCheck:
    """Database health check utilities."""
    
    @staticmethod
    def check_connection() -> bool:
        """Check if database connection is healthy."""
        try:
            with get_db_session() as db:
                # Simple query to test connection
                db.execute("SELECT 1")
                return True
        except Exception:
            return False
    
    @staticmethod
    def get_connection_info() -> dict:
        """Get database connection information."""
        try:
            engine = get_engine()
            return {
                'url': str(engine.url).replace(engine.url.password, '***' if engine.url.password else ''),
                'pool_size': engine.pool.size(),
                'checked_in': engine.pool.checkedin(),
                'checked_out': engine.pool.checkedout(),
                'overflow': engine.pool.overflow(),
                'invalid': engine.pool.invalid()
            }
        except Exception as e:
            return {'error': str(e)}


def init_database():
    """Initialize database connection for worker processes."""
    # This function can be called when worker starts
    # to ensure database is properly initialized
    try:
        with get_db_session() as db:
            # Test connection
            db.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        return False