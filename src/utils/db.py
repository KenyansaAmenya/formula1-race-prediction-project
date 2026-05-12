from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Type, TypeVar

import pandas as pd
from sqlalchemy import (
    Column, DateTime, Float, Integer, String, Text, create_engine,
    event, text
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from src.utils.config import get_config
from src.utils.logger import SensitiveDataMasker, get_logger

logger = get_logger(__name__)
Base = declarative_base()
T = TypeVar('T', bound=Base)


class DatabaseManager:
    
    _instance: Optional['DatabaseManager'] = None
    _engine = None
    _session_factory = None
    
    def __new__(cls) -> 'DatabaseManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    # Initialize database engine with security settings
    def _initialize(self) -> None:
        
        config = get_config()
        db_config = config.database
        
        # Build connection string from validated config
        connection_string = db_config.connection_string
        
        # Create engine with security-focused pooling
        self._engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=db_config.pool_size,
            max_overflow=db_config.max_overflow,
            pool_timeout=db_config.pool_timeout,
            pool_recycle=db_config.pool_recycle,
            pool_pre_ping=True,  # Verify connections before use
            echo=db_config.echo,
            connect_args={
                'sslmode': db_config.ssl_mode,
                'connect_timeout': 10,
            }
        )
        
        # Add query logging for debugging 
        if config.environment != "production":
            @event.listens_for(self._engine, "before_cursor_execute")
            def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                logger.debug(
                    "sql_query_executing",
                    statement=statement[:200],
                    parameters=SensitiveDataMasker.mask_dict(dict(parameters) if parameters else {})
                )
        
        self._session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine
        )
        
        logger.info(
            "database_initialized",
            host=db_config.host,
            database=db_config.name,
            pool_size=db_config.pool_size,
            ssl_mode=db_config.ssl_mode
        )
    
    @property
    def engine(self):
        return self._engine
    
    # Session context manager
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        
        session = self._session_factory()
        try:
            yield session
            session.commit()
            logger.debug("database_transaction_committed")
        except Exception as e:
            session.rollback()
            logger.error(
                "database_transaction_rolled_back",
                error_type=type(e).__name__,
                error_message=str(e)
            )
            raise
        finally:
            session.close()
    
    # Parameterized query execution
    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
       
        with self.session() as session:
            result = session.execute(text(query), params or {})
            return [dict(row._mapping) for row in result]
    
    # dataframe operations
    def execute_dataframe(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        with self.session() as session:
            return pd.read_sql_query(text(query), session.bind, params=params or {})
    
    def bulk_insert_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        if_exists: str = "append"
    ) -> int:
        if df.empty:
            logger.warning("bulk_insert_empty_dataframe", table=table_name)
            return 0
        
        rows = df.to_sql(
            name=table_name,
            con=self._engine,
            if_exists=if_exists,
            index=False,
            method='multi',  # Batch insert
            chunksize=1000   # 1000 rows per batch
        )
        
        logger.info(
            "bulk_insert_completed",
            table=table_name,
            rows_inserted=rows,
            columns=list(df.columns)
        )
        return rows or 0
    
    # connection testing
    def test_connection(self) -> bool:
        try:
            with self.session() as session:
                result = session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error("database_connection_failed", error=str(e))
            return False
    
    def close(self) -> None:
        if self._engine:
            self._engine.dispose()
            logger.info("database_connections_disposed")


# Convenience function for database access
def get_db() -> DatabaseManager:
    return DatabaseManager()

# RLS aware session
class RLSAwareSession:
    def __init__(self, role: str = "service_role"):
        self.role = role
        self.db = get_db()
    
    @contextmanager
    def secure_session(self) -> Generator[Session, None, None]:
        with self.db.session() as session:
            # Set application context for RLS policies
            session.execute(
                text("SELECT set_config('app.current_role', :role, true)"),
                {"role": self.role}
            )
            yield session


# migration helper
def run_migrations(script_location: str = "sql/alembic") -> None:
    logger.info("migration_runner_placeholder", script_location=script_location)
    # from alembic.config import Config
    # from alembic import command
    # alembic_cfg = Config(f"{script_location}/alembic.ini")
    # command.upgrade(alembic_cfg, "head")