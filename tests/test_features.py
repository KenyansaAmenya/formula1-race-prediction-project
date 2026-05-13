# Unit tests for feature engineering pipeline.

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.features.build_features import FeatureBuilder
from src.utils.config import AppConfig


class TestFeatureBuilder:
    
    @pytest.fixture
    def builder(self):
        config = MagicMock(spec=AppConfig)
        config.features.rolling_window_races = 5
        config.features.form_window_races = 3
        config.features.min_races_for_rolling = 2
        return FeatureBuilder(config=config)
    
    @pytest.fixture
    def sample_history(self):
        return pd.DataFrame({
            'race_id': [1, 2, 3, 4, 5],
            'year': [2025, 2025, 2025, 2025, 2025],
            'round': [1, 2, 3, 4, 5],
            'race_date': pd.to_datetime([
                '2025-03-02', '2025-03-09', '2025-03-23',
                '2025-04-06', '2025-04-13'
            ], utc=True),
            'circuit_id': [1, 2, 3, 1, 4],
            'driver_id': [44, 44, 44, 44, 44],
            'constructor_id': [1, 1, 1, 1, 1],
            'grid': [1, 2, 3, 1, 2],
            'position_order': [1, 2, 1, 3, 1],
            'points': [25, 18, 25, 15, 25],
            'laps': [57, 57, 58, 56, 57],
            'milliseconds': [5523456, 5524123, 5521000, 5530000, 5519000],
            'status': ['Finished', 'Finished', 'Finished', 'Finished', 'Finished']
        })
    
    def test_calculate_trend(self, builder):
        series = pd.Series([10, 12, 15, 18, 20])
        trend = builder._calculate_trend(series)
        
        assert trend > 0  # Positive trend
    
    def test_driver_rolling_features(self, builder, sample_history):
        target_date = pd.Timestamp('2025-04-20', tz='UTC')
        features = builder.build_driver_rolling_features(
            sample_history, 44, target_date
        )
        
        assert features['rolling_avg_points_5r'] == 21.6  # Average of last 5
        assert features['recent_form_points'] == 21.67  # Average of last 3
        assert features['consecutive_finishes'] == 5
        assert features['dnf_probability'] == 0.0
    
    def test_driver_rolling_features_insufficient_data(self, builder):
        history = pd.DataFrame({
            'race_date': pd.to_datetime(['2025-03-02'], utc=True),
            'driver_id': [44],
            'points': [25],
            'position_order': [1],
            'grid': [1],
            'status': ['Finished'],
            'milliseconds': [5523456]
        })
        
        target_date = pd.Timestamp('2025-03-09', tz='UTC')
        features = builder.build_driver_rolling_features(history, 44, target_date)
        
        assert np.isnan(features['rolling_avg_points_5r'])
        assert features['consecutive_finishes'] == 0
    
    def test_constructor_features(self, builder, sample_history):
        target_date = pd.Timestamp('2025-04-20', tz='UTC')
        features = builder.build_constructor_features(
            sample_history, 1, target_date
        )
        
        assert features['constructor_avg_points_5r'] == 43.2  # Sum per race, then avg
        assert features['constructor_reliability_score'] == 1.0
    
    def test_track_features(self, builder, sample_history):
        target_date = pd.Timestamp('2025-04-20', tz='UTC')
        features = builder.build_track_features(
            sample_history, 44, 1, target_date
        )
        
        assert features['track_experience_races'] == 2  # Races at circuit_id=1
        assert features['track_best_finish_pos'] == 1
    
    def test_overall_index(self, builder):
        features = {
            'driver_performance_index': 80.0,
            'constructor_performance_index': 85.0,
            'track_experience_races': 5,
            'track_avg_points': 20.0
        }
        
        index = builder._compute_overall_index(features)
        assert 0 <= index <= 100
    
    def test_time_to_milliseconds(self, builder):
        assert builder._time_to_milliseconds("1:32.456") == 92456
        assert builder._time_to_milliseconds("92.456") == 92456
        assert builder._time_to_milliseconds(None) is None