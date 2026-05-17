import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import Field, SecretStr, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DB_",
        extra="allow"  # Allow extra fields from YAML
    )
    
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    name: str = Field(default="postgres", description="Database name")
    user: str = Field(default="postgres", description="Database user")
    password: SecretStr = Field(default=SecretStr(""), description="Database password")
    ssl_mode: str = Field(default="require", description="SSL mode for connections")
    
    # Pool settings
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)
    pool_timeout: int = Field(default=30)
    pool_recycle: int = Field(default=1800)
    echo: bool = Field(default=False)
    
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

class ErgastConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ERGAST_", extra="allow")
    
    base_url: str = "https://ergast.com/api/f1"
    retry_attempts: int = 3
    retry_backoff: float = 2.0
    timeout: int = 30
    rate_limit: float = 1.0

class OpenF1Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENF1_", extra="allow")
    
    base_url: str = "https://api.openf1.org/v1"
    retry_attempts: int = 5
    retry_backoff: float = 2.5
    timeout: int = 45
    rate_limit: float = 2.0

class FastF1Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FASTF1_", extra="allow")
    
    cache_dir: str = "./data/fastf1_cache"
    retry_attempts: int = 3
    timeout: int = 60

class IngestionConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="allow")
    
    ergast: ErgastConfig = Field(default_factory=ErgastConfig)
    openf1: OpenF1Config = Field(default_factory=OpenF1Config)
    fastf1: FastF1Config = Field(default_factory=FastF1Config)

class StorageConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="allow")
    
    raw_data_path: str = "./data/raw"
    processed_data_path: str = "./data/processed"
    telemetry_path: str = "./data/raw/telemetry"
    format: str = "parquet"
    compression: str = "zstd"

class FeatureConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="allow")
    
    rolling_window_races: int = 5
    form_window_races: int = 3
    min_races_for_rolling: int = 2

class SecurityConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="allow")
    
    mask_sensitive_fields: bool = True
    max_query_limit: int = 10000
    enable_rls: bool = True

class MLConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="allow")
    
    model_dir: str = Field(default="./artifacts/models")
    metrics_dir: str = Field(default="./artifacts/metrics")
    random_state: int = Field(default=42)
    test_size: float = Field(default=0.2)
    validation_size: float = Field(default=0.1)
    
    targets: List[str] = Field(default=["is_winner", "is_top3", "points"])
    
    models: Dict[str, List[str]] = Field(default={
        "baseline": ["logistic_regression"],
        "advanced": ["random_forest", "xgboost"]
    })
    
    hyperparameters: Dict[str, Dict[str, List]] = Field(default={
        "random_forest": {
            "n_estimators": [100, 200],
            "max_depth": [10, 20, None],
            "min_samples_split": [2, 5]
        },
        "xgboost": {
            "n_estimators": [100, 200],
            "max_depth": [3, 6, 9],
            "learning_rate": [0.01, 0.1],
            "subsample": [0.8, 1.0]
        }
    })


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow"  # Allow extra fields from YAML
    )
    
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    ml: MLConfig = Field(default_factory=MLConfig)  # ADD THIS LINE
    
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


# Global configuration instance
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