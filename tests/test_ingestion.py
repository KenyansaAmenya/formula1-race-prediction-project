# Unit tests for data ingestors.

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.ingestion.base import IngestionResult
from src.ingestion.ingest_ergast import ErgastIngestor
from src.ingestion.ingest_openf1 import OpenF1Ingestor
from src.utils.config import AppConfig


class TestErgastIngestor:
    
    @pytest.fixture
    # Create mock configuration
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.ingestion.ergast_base_url = "https://ergast.com/api/f1"
        config.ingestion.ergast_timeout = 30
        config.ingestion.ergast_rate_limit = 1.0
        config.ingestion.ergast_retry_attempts = 3
        config.ingestion.ergast_retry_backoff = 2.0
        return config
    
    @pytest.fixture
    def sample_race_data(self):
        return pd.DataFrame({
            'year': [2025, 2025],
            'round': [1, 2],
            'circuit_ref': ['bahrain', 'jeddah'],
            'race_name': ['Bahrain GP', 'Saudi Arabian GP'],
            'date': ['2025-03-02', '2025-03-09'],
            'time': ['15:00:00Z', '17:00:00Z']
        })
    
    def test_source_name(self, mock_config):
        ingestor = ErgastIngestor(config=mock_config)
        assert ingestor.source_name == "ergast"
    
    def test_time_to_milliseconds(self, mock_config):
        ingestor = ErgastIngestor(config=mock_config)
        
        assert ingestor._time_to_milliseconds("1:32.456") == 92456
        assert ingestor._time_to_milliseconds("92.456") == 92456
        assert ingestor._time_to_milliseconds(None) is None
        assert ingestor._time_to_milliseconds("invalid") is None
    
    def test_validate_schema_pass(self, mock_config, sample_race_data):
        ingestor = ErgastIngestor(config=mock_config)
        
        # Add required columns for races entity
        df = sample_race_data.copy()
        assert ingestor.validate_schema(df) is True
    
    def test_validate_schema_fail(self, mock_config):
        ingestor = ErgastIngestor(config=mock_config)
        
        df = pd.DataFrame({'invalid_col': [1, 2]})
        with pytest.raises(ValueError):
            ingestor.validate_schema(df)


# Test for OpenF1 API ingestor
class TestOpenF1Ingestor:
    
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        config.ingestion.openf1_base_url = "https://api.openf1.org/v1"
        config.ingestion.openf1_timeout = 45
        config.ingestion.openf1_rate_limit = 2.0
        config.ingestion.openf1_retry_attempts = 5
        config.ingestion.openf1_retry_backoff = 2.5
        return config
    
    def test_circuit_breaker(self, mock_config):
        ingestor = OpenF1Ingestor(config=mock_config)
        
        # Simulate circuit breaker trip
        ingestor._circuit_open = False
        
        with pytest.raises(ConnectionError):
            ingestor._rate_limited_request("sessions")
    
    def test_validate_schema_empty(self, mock_config):
        ingestor = OpenF1Ingestor(config=mock_config)
        df = pd.DataFrame()
        
        assert ingestor.validate_schema(df) is True