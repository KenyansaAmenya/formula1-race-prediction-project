import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import Field, PostgresDsn, SecretStr, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_")
    
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(default="postgres", description="Database name")
    user: str = Field(default="postgres", description="Database user")
    password: SecretStr = Field(default=SecretStr(""), description="Database password")
    ssl_mode: str = Field(default="require", description="SSL mode for connections")
    
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800
    
    # connection string property
    @property
    def connection_string(self) -> str:
        password = self.password.get_secret_value() if self.password else ""
        return (
            f"postgresql+psycopg2://{self.user}:{password}"
            f"@{self.host}:{self.port}/{self.name}"
            f"?sslmode={self.ssl_mode}"
        )
    
    @property
    def async_connection_string(self) -> str:
        password = self.password.get_secret_value() if self.password else ""
        return (
            f"postgresql+asyncpg://{self.user}:{password}"
            f"@{self.host}:{self.port}/{self.name}"
            f"?sslmode={self.ssl_mode}"
        )

# configuration for external F1 data APIs
class IngestionConfig(BaseSettings):
    ergast_base_url: str = "https://ergast.com/api/f1"
    ergast_retry_attempts: int = 3
    ergast_retry_backoff: float = 2.0
    ergast_timeout: int = 30
    ergast_rate_limit: float = 1.0
    
    openf1_base_url: str = "https://api.openf1.org/v1"
    openf1_retry_attempts: int = 5
    openf1_retry_backoff: float = 2.5
    openf1_timeout: int = 45
    openf1_rate_limit: float = 2.0
    
    fastf1_cache_dir: str = "./data/fastf1_cache"
    fastf1_retry_attempts: int = 3
    fastf1_timeout: int = 60

# defines the data lake directory structure
class StorageConfig(BaseSettings):
    raw_data_path: str = "./data/raw"
    processed_data_path: str = "./data/processed"
    telemetry_path: str = "./data/raw/telemetry"
    format: str = "parquet"
    compression: str = "zstd"

# Configuration for feature engineering for ML models
class FeatureConfig(BaseSettings):
    rolling_window_races: int = 5
    form_window_races: int = 3
    min_races_for_rolling: int = 2

# Security controls for data access
class SecurityConfig(BaseSettings):
    mask_sensitive_fields: bool = True
    max_query_limit: int = 10000
    enable_rls: bool = True


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    #    
    @classmethod
    def from_yaml(cls, config_path: str = "config/settings.yaml") -> "AppConfig":
        path = Path(config_path)
        if not path.exists():
            return cls()
        
        with open(path, "r") as f:
            yaml_content = yaml.safe_load(f)
        
        # Environment variable substitution
        yaml_content = cls._substitute_env_vars(yaml_content)
        
        return cls(**yaml_content)
    
    @staticmethod
    def _substitute_env_vars(obj: Any) -> Any:

        if isinstance(obj, dict):
            return {k: AppConfig._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [AppConfig._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            import re
            pattern = r'\$\{([^}]+)\}'
            
            def replace(match):
                env_expr = match.group(1)
                if ':-' in env_expr:
                    var, default = env_expr.split(':-', 1)
                    return os.getenv(var, default)
                return os.getenv(env_expr, match.group(0))
            
            return re.sub(pattern, replace, obj)
        return obj
    
    def get_storage_path(self, layer: str) -> Path:
        base = Path(self.storage.raw_data_path).parent
        paths = {
            'raw': self.storage.raw_data_path,
            'processed': self.storage.processed_data_path,
            'telemetry': self.storage.telemetry_path
        }
        path = Path(paths.get(layer, self.storage.raw_data_path))
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()


# Global configuration instance (singleton pattern)
_config_instance: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _config_instance
    if _config_instance is None:
        _config_instance = AppConfig.from_yaml()
    return _config_instance


def reload_config() -> AppConfig:
    global _config_instance
    _config_instance = AppConfig.from_yaml()
    return _config_instance