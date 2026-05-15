from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import create_engine, text

from src.utils.config import AppConfig, get_config
from src.utils.io_utils import get_io
from src.utils.logger import PipelineMetrics, get_logger

logger = get_logger(__name__)

# Standard return type for ingestion operation
@dataclass
class IngestionResult:
    source: str
    records_count: int
    file_path: Optional[str]
    schema_version: str
    validation_status: str
    metadata: Dict[str, Any]


# This enforces consistent interface across Ergast, OpenF1, and FastF1 sources
class BaseIngestor(ABC):
    
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or get_config()                       # Dependency injection
        self.io = get_io()                                         # Storage abstraction
        self.metrics = PipelineMetrics(self.__class__.__name__)    # Per class metrics
        self.schema_version = "1.0.0"
        self._engine = None  # Database engine (lazy initialization)
    
    @property
    @abstractmethod
    # Return the data source identifier
    def source_name(self) -> str:
        pass
    
    @property
    def engine(self):
        if self._engine is None:
            self._engine = create_engine(self.config.database.connection_string)
        return self._engine
    
    # Fetch data from external source
    @abstractmethod
    def fetch(self, **kwargs) -> pd.DataFrame:
        pass
    
    # Validate DataFrame against expected schema
    @abstractmethod
    def validate_schema(self, df: pd.DataFrame) -> bool:
        pass
    
    # Save raw data to standardized location
    def save_raw(self, df: pd.DataFrame, filename: str) -> str:
        path = self.io.get_raw_path(filename, self.source_name)
        self.io.write_parquet(df, path)
        return str(path)
    
    # Determine table name from DataFrame columns
    def _get_table_name(self, df: pd.DataFrame) -> Optional[str]:
        if 'circuit_ref' in df.columns and 'race_name' in df.columns:
            return 'races'
        elif 'driver_ref' in df.columns and 'forename' in df.columns:
            return 'drivers'
        elif 'constructor_ref' in df.columns and 'name' in df.columns:
            return 'constructors'
        elif 'circuit_ref' in df.columns and 'location' in df.columns:
            return 'circuits'
        elif 'driver_ref' in df.columns and 'constructor_ref' in df.columns:
            return 'results'
        elif 'circuit_ref' in df.columns and 'lap' in df.columns:
            return 'lap_times'
        elif 'driver_ref' in df.columns and 'position' in df.columns and 'lap' not in df.columns:
            return 'qualifying'
        else:
            logger.warning("unknown_table", columns=list(df.columns))
            return None
    
    # Save data to PostgreSQL database
    def save_to_postgres(self, df: pd.DataFrame, table_name: Optional[str] = None, mode: str = 'upsert') -> int:
        if df.empty:
            logger.warning("empty_dataframe", source=self.source_name)
            return 0
        
        # Auto-detect table name if not provided
        if table_name is None:
            table_name = self._get_table_name(df)
            if table_name is None:
                raise ValueError(f"Cannot determine table name for columns: {list(df.columns)}")
        
        logger.info("saving_to_postgres", table=table_name, rows=len(df), mode=mode)
        
        try:
            with self.engine.connect() as conn:
                # Handle different save modes
                if mode == 'replace' and 'year' in df.columns:
                    # For dimension tables, replace data for the specific year
                    year = df['year'].iloc[0] if not df.empty else None
                    if year:
                        conn.execute(text(f"DELETE FROM {table_name} WHERE year = {year}"))
                        conn.commit()
                        logger.info("deleted_existing_data", table=table_name, year=year)
                
                elif mode == 'upsert' and table_name == 'results':
                    
                    temp_table = f"{table_name}_temp"
                    df.to_sql(temp_table, self.engine, if_exists='replace', index=False)
                    
                    columns = df.columns.tolist()
                    update_cols = [col for col in columns if col not in ['year', 'round', 'driver_ref']]
                    
                    conn.execute(text(f"""
                        DELETE FROM {table_name} 
                        WHERE (year, round, driver_ref) IN (
                            SELECT year, round, driver_ref FROM {temp_table}
                        )
                    """))
                    conn.execute(text(f"""
                        INSERT INTO {table_name} 
                        SELECT * FROM {temp_table}
                    """))
                    conn.execute(text(f"DROP TABLE {temp_table}"))
                    conn.commit()
                    return len(df)
            
            df.to_sql(table_name, self.engine, if_exists='append', index=False)
            logger.info("database_saved", table=table_name, rows=len(df))
            return len(df)
            
        except Exception as e:
            logger.error("database_save_failed", table=table_name, error=str(e))
            raise
    
    # Execute full ingestion pipeline: fetch, validate, save to both Parquet and Database
    def ingest(self, save_to_db: bool = True, db_mode: str = 'append', **kwargs) -> IngestionResult:
        self.metrics.start()
        
        try:
            # Step 1. Fetch data
            logger.info(f"starting_ingestion", source=self.source_name)
            df = self.fetch(**kwargs)
            self.metrics.record_success(len(df))
            
            # Step 2. Validate schema
            self.validate_schema(df)
            
            # Step 3. Generate filename with timestamp for idempotency
            from datetime import datetime, timezone
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{self.source_name}_{timestamp}.parquet"
            
            # Step 4. Save raw data to Parquet
            file_path = self.save_raw(df, filename)
            
            # Step 5. Save to PostgreSQL database (optional)
            db_rows = 0
            if save_to_db:
                try:
                    table_name = self._get_table_name(df)
                    db_rows = self.save_to_postgres(df, table_name, mode=db_mode)
                    logger.info("database_save_complete", table=table_name, rows=db_rows)
                except Exception as db_error:
                    logger.error("database_save_failed", error=str(db_error))
            
            # Step 6. Build result object
            result = IngestionResult(
                source=self.source_name,
                records_count=len(df),
                file_path=file_path,
                schema_version=self.schema_version,
                validation_status="passed",
                metadata={
                    "columns": list(df.columns),
                    "dtypes": {k: str(v) for k, v in df.dtypes.items()},
                    "fetch_params": kwargs,
                    "database_rows_saved": db_rows
                }
            )
            
            # Step 7. Add metrics to result
            metrics = self.metrics.finalize()
            result.metadata["pipeline_metrics"] = metrics
            
            logger.info(
                "ingestion_completed",
                source=self.source_name,
                records=result.records_count,
                path=file_path,
                db_rows=db_rows
            )
            
            return result
            
        except Exception as e:
            # Handle failures
            self.metrics.record_failure(e, {"source": self.source_name})
            metrics = self.metrics.finalize()
            logger.error(
                "ingestion_failed",
                source=self.source_name,
                error=str(e),
                metrics=metrics
            )
            raise
    
    # Bulk ingest multiple items
    def ingest_bulk(self, items: List[Dict[str, Any]], save_to_db: bool = True, **kwargs) -> List[IngestionResult]:
        results = []
        
        for i, item_params in enumerate(items, 1):
            logger.info("bulk_ingestion_item", item=i, total=len(items), params=item_params)
            
            try:
                # Merge default kwargs with item-specific params
                params = {**kwargs, **item_params}
                result = self.ingest(save_to_db=save_to_db, **params)
                results.append(result)
            except Exception as e:
                logger.error("bulk_ingestion_item_failed", item=i, error=str(e))
                # Continue with remaining items
                continue
        
        # Summary
        successful = [r for r in results if r.validation_status == "passed"]
        logger.info(
            "bulk_ingestion_complete",
            total=len(items),
            successful=len(successful),
            failed=len(items) - len(successful)
        )
        
        return results