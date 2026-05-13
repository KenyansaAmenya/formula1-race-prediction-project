from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.processing.clean_data import DataCleaner
from src.utils.config import AppConfig


class TestDataCleaner:
    
    @pytest.fixture
    def cleaner(self):
        config = MagicMock(spec=AppConfig)
        config.processing.null_threshold_numeric = 0.15
        config.processing.null_threshold_categorical = 0.10
        return DataCleaner(config=config)
    
    @pytest.fixture
    def sample_results(self):
        return pd.DataFrame({
            'year': [2025, 2025, 2025],
            'round': [1, 1, 1],
            'driver_ref': ['hamilton', 'verstappen', 'leclerc'],
            'constructor_ref': ['mercedes', 'red_bull', 'ferrari'],
            'grid': [1, 2, 3],
            'position': [1, 2, 3],
            'position_order': [1, 2, 3],
            'points': [25.0, 18.0, 15.0],
            'laps': [57, 57, 57],
            'milliseconds': [5523456, 5524123, 5525890],
            'status': ['Finished', 'Finished', 'Finished']
        })
    
    def test_normalize_schema(self, cleaner, sample_results):
        df = cleaner.normalize_schema(sample_results, 'results')
        
        assert all(col in df.columns for col in ['year', 'round', 'grid'])
        assert df['year'].dtype == 'Int64'
        assert df['points'].dtype == 'float64'
    
    def test_remove_duplicates(self, cleaner):
        df = pd.DataFrame({
            'year': [2025, 2025, 2025],
            'round': [1, 1, 1],
            'driver_ref': ['hamilton', 'hamilton', 'verstappen'],
            'points': [25, 25, 18]
        })
        
        deduped, removed = cleaner.remove_duplicates(df, ['year', 'round', 'driver_ref'])
        
        assert len(deduped) == 2
        assert removed == 1
    
    def test_handle_missing_values_numeric(self, cleaner):
        df = pd.DataFrame({
            'grid': [1, 2, np.nan, 4, 5],
            'points': [25, np.nan, 15, 12, 10]
        })
        
        cleaned = cleaner.handle_missing_values(df, 'results')
        
        assert cleaned['grid'].isnull().sum() == 0
        assert cleaned['points'].isnull().sum() == 0
        assert cleaned['grid'].iloc[2] == 3.0  # Median
    
    def test_standardize_lap_times(self, cleaner):
        df = pd.DataFrame({
            'time': ['1:32.456', '1:33.123', None, '92.789']
        })
        
        standardized = cleaner.standardize_lap_times(df)
        
        assert 'milliseconds' in standardized.columns
        assert standardized['milliseconds'].iloc[0] == 92456
        assert pd.isna(standardized['milliseconds'].iloc[2])
    
    def test_validation_report(self, cleaner, sample_results):
        report = cleaner.generate_validation_report(sample_results, 'results')
        
        assert report['entity_type'] == 'results'
        assert report['record_count'] == 3
        assert 'validations' in report
        assert report['validations']['negative_points'] == 0