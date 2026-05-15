# Unit tests for data ingestors.

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.ingestion.base import BaseIngestor, IngestionResult
from src.ingestion.ingest_ergast import ErgastIngestor
from src.utils.config import AppConfig


class TestErgastIngestor:
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration with nested ergast config"""
        config = MagicMock(spec=AppConfig)
        
        # Create nested ergast config
        ergast_config = MagicMock()
        ergast_config.base_url = "https://api.jolpi.ca/ergast/f1"
        ergast_config.timeout = 30
        ergast_config.rate_limit = 1.0
        ergast_config.retry_attempts = 3
        ergast_config.retry_backoff = 2.0
        
        # Create nested ingestion config
        ingestion_config = MagicMock()
        ingestion_config.ergast = ergast_config
        
        config.ingestion = ingestion_config
        return config
    
    @pytest.fixture
    def ingestor(self, mock_config):
        """Create ingestor instance"""
        return ErgastIngestor(config=mock_config)
    
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
    
    def test_source_name(self, ingestor):
        assert ingestor.source_name == "ergast"
    
    def test_time_to_milliseconds(self, ingestor):
        """Test time conversion to milliseconds"""
        # Add this method if it doesn't exist in your ingestor
        assert ingestor._time_to_milliseconds("1:32.456") == 92456
        assert ingestor._time_to_milliseconds("92.456") == 92456
        assert ingestor._time_to_milliseconds(None) is None
        assert ingestor._time_to_milliseconds("invalid") is None
    
    def test_validate_schema_pass(self, ingestor, sample_race_data):
        """Test schema validation passes"""
        # Add required columns for races entity
        df = sample_race_data.copy()
        assert ingestor.validate_schema(df) is True
    
    def test_validate_schema_fail(self, ingestor):
        """Test schema validation fails with invalid columns"""
        df = pd.DataFrame({'invalid_col': [1, 2]})
        with pytest.raises(ValueError):
            ingestor.validate_schema(df)
    
    def test_fetch_races(self, ingestor):
        """Test fetching races from API"""
        # This will make a real API call
        races = ingestor.fetch_races(2025)
        assert len(races) > 0
        assert 'round' in races.columns
        assert 'race_name' in races.columns
    
    def test_ingest_season(self, ingestor):
        """Test full season ingestion"""
        # Test with just races entity to avoid too many API calls
        results = ingestor.ingest_season(2025, entities=["races"])
        assert "races" in results
        assert results["races"].records_count > 0


# Test for OpenF1 API ingestor (skip if not implemented)
@pytest.mark.skip(reason="OpenF1Ingestor not yet implemented")
class TestOpenF1Ingestor:
    
    @pytest.fixture
    def mock_config(self):
        config = MagicMock(spec=AppConfig)
        
        # Create nested openf1 config
        openf1_config = MagicMock()
        openf1_config.base_url = "https://api.openf1.org/v1"
        openf1_config.timeout = 45
        openf1_config.rate_limit = 2.0
        openf1_config.retry_attempts = 5
        openf1_config.retry_backoff = 2.5
        
        ingestion_config = MagicMock()
        ingestion_config.openf1 = openf1_config
        config.ingestion = ingestion_config
        return config
    
    def test_circuit_breaker(self, mock_config):
        from src.ingestion.ingest_openf1 import OpenF1Ingestor
        ingestor = OpenF1Ingestor(config=mock_config)
        
        # Simulate circuit breaker trip
        ingestor._circuit_open = False
        
        with pytest.raises(ConnectionError):
            ingestor._rate_limited_request("sessions")
    
    def test_validate_schema_empty(self, mock_config):
        from src.ingestion.ingest_openf1 import OpenF1Ingestor
        ingestor = OpenF1Ingestor(config=mock_config)
        df = pd.DataFrame()
        
        assert ingestor.validate_schema(df) is True


# Integration test (optional)
@pytest.mark.integration
class TestRealAPICalls:
    
    def test_ergast_real_data(self):
        """Test real API calls to Jolpica"""
        ingestor = ErgastIngestor()
        
        # Test races
        races = ingestor.fetch_races(2025)
        assert len(races) == 24
        assert races.iloc[0]['race_name'] == 'Australian Grand Prix'
        
        # Test drivers
        drivers = ingestor.fetch_drivers(2025)
        assert len(drivers) > 0
        assert 'driver_ref' in drivers.columns
        
        # Test constructors
        constructors = ingestor.fetch_constructors(2025)
        assert len(constructors) > 0
        assert 'constructor_ref' in constructors.columns