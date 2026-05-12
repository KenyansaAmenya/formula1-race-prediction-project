# Base ingestion module defining the abstract interface for all data sources.
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

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
    
    @property
    @abstractmethod
    # Return the data source identifier
    def source_name(self) -> str:
        pass
    
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
    
    # Execute full ingestion pipeline: fetch, validate, save
    def ingest(self, **kwargs) -> IngestionResult:
       
        self.metrics.start()
        
        try:
            #step 1. Fetch data
            logger.info(f"starting_ingestion", source=self.source_name)
            df = self.fetch(**kwargs)
            self.metrics.record_success(len(df))
            
            #step 2. Validate schema
            self.validate_schema(df)
            
            #step 3. Generate filename with timestamp for idempotency
            from datetime import datetime, timezone
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{self.source_name}_{timestamp}.parquet"
            
            #Step 4. Save raw data
            file_path = self.save_raw(df, filename)
            
            # step 5. Build result object
            result = IngestionResult(
                source=self.source_name,
                records_count=len(df),
                file_path=file_path,
                schema_version=self.schema_version,
                validation_status="passed",
                metadata={
                    "columns": list(df.columns),
                    "dtypes": {k: str(v) for k, v in df.dtypes.items()},
                    "fetch_params": kwargs
                }
            )
            
            # Step 6. add metrics to result
            metrics = self.metrics.finalize()
            result.metadata["pipeline_metrics"] = metrics
            
            logger.info(
                "ingestion_completed",
                source=self.source_name,
                records=result.records_count,
                path=file_path
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