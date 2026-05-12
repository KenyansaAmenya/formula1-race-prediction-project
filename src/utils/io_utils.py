import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.utils.config import get_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# abstract storageBackend interface
class StorageBackend:

    def read(self, path: Union[str, Path]) -> pd.DataFrame:
        raise NotImplementedError
    
    def write(
        self,
        df: pd.DataFrame,
        path: Union[str, Path],
        **kwargs
    ) -> None:
        raise NotImplementedError
    
    def exists(self, path: Union[str, Path]) -> bool:
        raise NotImplementedError
    
    def list_files(self, pattern: str) -> List[Path]:
        raise NotImplementedError

class LocalStorageBackend(StorageBackend):
    
    # Read Parquet file to DataFrame
    def read(self, path: Union[str, Path]) -> pd.DataFrame:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        logger.debug("reading_parquet", path=str(path))
        return pd.read_parquet(path)
    
    def write(
        self,
        df: pd.DataFrame,
        path: Union[str, Path],
        compression: str = "zstd",
        **kwargs
    ) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write with schema preservation
        table = pa.Table.from_pandas(df)
        pq.write_table(
            table,
            path,
            compression=compression,
            use_dictionary=True,
            write_statistics=True
        )
        
        logger.info(
            "parquet_written",
            path=str(path),
            rows=len(df),
            columns=len(df.columns),
            compression=compression
        )
    
    def exists(self, path: Union[str, Path]) -> bool:
        return Path(path).exists()
    
    # List files with pattern matching
    def list_files(self, pattern: str) -> List[Path]:
        return list(Path(".").glob(pattern))

#AWS S3 storage backend (placeholder for future implementation)
class S3StorageBackend(StorageBackend):
    
    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        self.region = region
        logger.info("s3_backend_placeholder", bucket=bucket)
    
    def read(self, path: Union[str, Path]) -> pd.DataFrame:
        raise NotImplementedError("S3 backend not yet implemented")
    
    def write(self, df: pd.DataFrame, path: Union[str, Path], **kwargs) -> None:
        raise NotImplementedError("S3 backend not yet implemented")
    
    def exists(self, path: Union[str, Path]) -> bool:
        raise NotImplementedError("S3 backend not yet implemented")
    
    def list_files(self, pattern: str) -> List[Path]:
        raise NotImplementedError("S3 backend not yet implemented")

# Centralized I/O utility with storage abstraction
class IOUtils:
    
    def __init__(self, backend: Optional[StorageBackend] = None):
        self.backend = backend or LocalStorageBackend()
        self.config = get_config()
    
    def read_parquet(self, path: Union[str, Path]) -> pd.DataFrame:
        return self.backend.read(path)
    
    def write_parquet(
        self,
        df: pd.DataFrame,
        path: Union[str, Path],
        partition_cols: Optional[List[str]] = None
    ) -> None:
        self.backend.write(
            df,
            path,
            compression=self.config.storage.compression
        )
    
    # Read JSON file to dictionary
    def read_json(self, path: Union[str, Path]) -> Dict[str, Any]:
        with open(path, 'r') as f:
            return json.load(f)
    
    # Write dictionary to JSON file
    def write_json(
        self,
        data: Dict[str, Any],
        path: Union[str, Path]
    ) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def get_raw_path(self, filename: str, source: str) -> Path:
        base = Path(self.config.storage.raw_data_path)
        path = base / source / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_processed_path(self, filename: str) -> Path:
        base = Path(self.config.storage.processed_data_path)
        path = base / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


# Singleton instance
_io_instance: Optional[IOUtils] = None


def get_io() -> IOUtils:
    global _io_instance
    if _io_instance is None:
        _io_instance = IOUtils()
    return _io_instance