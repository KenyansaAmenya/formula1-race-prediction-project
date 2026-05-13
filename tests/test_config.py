import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.utils.config import AppConfig, Environment, get_config, reload_config


class TestAppConfig:
    
    # Test default configuration values
    def test_default_config(self):
        config = AppConfig()
        assert config.environment == Environment.DEVELOPMENT
        assert config.log_level == "INFO"
        assert config.database.pool_size == 10
    
    # Test environment enumeration
    def test_environment_enum(self):
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"
    
    # Test database connection string generation
    def test_database_connection_string(self):
        config = AppConfig()
        conn_str = config.database.connection_string
        
        assert conn_str.startswith("postgresql+psycopg2://")
        assert "sslmode=require" in conn_str
    
    # Test YAML configuration loading
    def test_yaml_loading(self):
        yaml_content = """
                    environment: staging
                    log_level: DEBUG
                    database:
                    pool_size: 25
                    host: custom.host.com
                    """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = AppConfig.from_yaml(temp_path)
            assert config.environment == Environment.STAGING
            assert config.log_level == "DEBUG"
            assert config.database.pool_size == 25
            assert config.database.host == "custom.host.com"
        finally:
            os.unlink(temp_path)
    
    # Test environment variable substitution in YAML
    def test_env_substitution(self):
        os.environ["TEST_DB_HOST"] = "env.host.com"
        os.environ["TEST_POOL"] = "30"
        
        yaml_content = """
                    database:
                    host: ${TEST_DB_HOST}
                    pool_size: ${TEST_POOL}
                    """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = AppConfig.from_yaml(temp_path)
            assert config.database.host == "env.host.com"
            assert config.database.pool_size == 30
        finally:
            os.unlink(temp_path)
            del os.environ["TEST_DB_HOST"]
            del os.environ["TEST_POOL"]
    
    # Test invalid environment rejection
    def test_invalid_environment(self):
        with pytest.raises(ValidationError):
            AppConfig(environment="invalid_env")
    
    # Test storage path generation
    def test_storage_paths(self):
        config = AppConfig()
        
        raw_path = config.get_storage_path("raw")
        assert raw_path.exists()
        assert "raw" in str(raw_path)
        
        processed_path = config.get_storage_path("processed")
        assert processed_path.exists()
        assert "processed" in str(processed_path)