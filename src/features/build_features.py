from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pandas import DataFrame, Series

from src.utils.config import AppConfig, get_config
from src.utils.db import get_db
from src.utils.io_utils import get_io
from src.utils.logger import PipelineMetrics, get_logger

logger = get_logger(__name__)


class FeatureBuilder:
    
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or get_config()
        self.db = get_db()
        self.io = get_io()
        self.metrics = PipelineMetrics("feature_engineering")
        
        self.rolling_window = self.config.features.rolling_window_races          # Last 5 races
        self.form_window = self.config.features.form_window_races                # Last 3 races
        self.min_races = self.config.features.min_races_for_rolling              # Minimun 3 races
    
    # Fetch all historical data up to (but not including) target race
    def _get_historical_data(
        self,
        cutoff_race_id: int,
        cutoff_date: pd.Timestamp
    ) -> DataFrame:
    
        query = """
        SELECT 
            r.race_id, r.year, r.round, r.date as race_date, r.circuit_id,
            res.driver_id, res.constructor_id, res.grid, res.position_order,
            res.points, res.laps, res.milliseconds, res.status,
            d.driver_ref, c.constructor_ref,
            ci.circuit_ref, ci.country as circuit_country
        FROM results res
        JOIN races r ON res.race_id = r.race_id
        JOIN drivers d ON res.driver_id = d.driver_id
        JOIN constructors c ON res.constructor_id = c.constructor_id
        JOIN circuits ci ON r.circuit_id = ci.circuit_id
        WHERE r.date < :cutoff_date
        ORDER BY r.date DESC
        """
        
        df = self.db.execute_dataframe(query, {"cutoff_date": cutoff_date})
        logger.debug(
            "historical_data_fetched",
            cutoff_race=cutoff_race_id,
            cutoff_date=cutoff_date.isoformat(),
            records=len(df)
        )
        return df
    
    # Fetch qualifying data for a specific race
    def _get_qualifying_data(self, race_id: int) -> DataFrame:
        query = """
        SELECT 
            q.race_id, q.driver_id, q.position as quali_position,
            q.q1, q.q2, q.q3
        FROM qualifying q
        WHERE q.race_id = :race_id
        """
        return self.db.execute_dataframe(query, {"race_id": race_id})
    
    # Fetch race metadata
    def _get_race_info(self, race_id: int) -> Dict[str, Any]:
        query = """
        SELECT r.race_id, r.year, r.round, r.circuit_id, r.date,
               c.circuit_ref, c.country
        FROM races r
        JOIN circuits c ON r.circuit_id = c.circuit_id
        WHERE r.race_id = :race_id
        """
        result = self.db.execute_query(query, {"race_id": race_id})
        return result[0] if result else {}
    
    def build_driver_rolling_features(
        self,
        history: DataFrame,
        driver_id: int,
        target_race_date: pd.Timestamp
    ) -> Dict[str, float]:
        
        driver_history = history[
            (history['driver_id'] == driver_id)
        ].sort_values('race_date', ascending=False)
        
        if len(driver_history) < self.min_races:
            return {
                'rolling_avg_points_5r': np.nan,
                'rolling_avg_finish_pos_5r': np.nan,
                'rolling_points_trend': np.nan,
                'recent_form_points': np.nan,
                'recent_form_finish_pos': np.nan,
                'recent_form_quali_pos': np.nan,
                'lap_consistency_std': np.nan,
                'avg_lap_time_ms': np.nan,
                'fastest_lap_time_ms': np.nan,
                'dnf_probability': np.nan,
                'consecutive_finishes': 0,
                'mechanical_dnf_rate': np.nan,
                'wet_race_experience': 0,
                'wet_race_avg_points': np.nan,
                'driver_performance_index': np.nan
            }
        
        # Rolling window (last N races)
        rolling = driver_history.head(self.rolling_window)
        
        # Recent form (last 3 races)
        recent = driver_history.head(self.form_window)
        
        # DNF analysis
        dnf_statuses = ['Engine', 'Transmission', 'Electrical', 'Hydraulics', 
                       'Brakes', 'Suspension', 'Collision', 'Spun off']
        dnfs = driver_history['status'].isin(dnf_statuses)
        mechanical_dnfs = driver_history['status'].isin(
            ['Engine', 'Transmission', 'Electrical', 'Hydraulics', 'Brakes', 'Suspension']
        )
        
        # Consecutive finishes
        consecutive_finishes = 0
        for status in driver_history['status']:
            if status in dnf_statuses:
                break
            consecutive_finishes += 1
        
        features = {
            'rolling_avg_points_5r': rolling['points'].mean(),
            'rolling_avg_finish_pos_5r': rolling['position_order'].mean(),
            'rolling_points_trend': self._calculate_trend(rolling['points']),
            'recent_form_points': recent['points'].mean(),
            'recent_form_finish_pos': recent['position_order'].mean(),
            'recent_form_quali_pos': recent['grid'].mean(),
            'lap_consistency_std': rolling['milliseconds'].std() if 'milliseconds' in rolling.columns else np.nan,
            'avg_lap_time_ms': rolling['milliseconds'].mean() if 'milliseconds' in rolling.columns else np.nan,
            'fastest_lap_time_ms': rolling['milliseconds'].min() if 'milliseconds' in rolling.columns else np.nan,
            'dnf_probability': dnfs.mean(),
            'consecutive_finishes': consecutive_finishes,
            'mechanical_dnf_rate': mechanical_dnfs.mean() if dnfs.sum() > 0 else 0,
            'wet_race_experience': 0,  # Placeholder for weather data integration
            'wet_race_avg_points': np.nan,
            'driver_performance_index': self._compute_driver_index(rolling)
        }
        
        return features
    
    # Build constructor performance metrics
    def build_constructor_features(
        self,
        history: DataFrame,
        constructor_id: int,
        target_race_date: pd.Timestamp
    ) -> Dict[str, float]:
        constructor_history = history[
            (history['constructor_id'] == constructor_id)
        ].sort_values('race_date', ascending=False)
        
        if len(constructor_history) < self.min_races:
            return {
                'constructor_avg_points_5r': np.nan,
                'constructor_reliability_score': np.nan,
                'constructor_performance_index': np.nan
            }
        
        rolling = constructor_history.head(self.rolling_window)
        
        # Reliability: percentage of finishes vs DNFs
        dnf_statuses = ['Engine', 'Transmission', 'Electrical', 'Hydraulics', 
                       'Brakes', 'Suspension', 'Collision', 'Spun off', 'Accident']
        finishes = ~constructor_history['status'].isin(dnf_statuses)
        
        features = {
            'constructor_avg_points_5r': rolling.groupby('race_id')['points'].sum().mean(),
            'constructor_reliability_score': finishes.mean(),
            'constructor_performance_index': self._compute_constructor_index(rolling)
        }
        
        return features
    
    # Build track-specific historical performance
    def build_track_features(
        self,
        history: DataFrame,
        driver_id: int,
        circuit_id: int,
        target_race_date: pd.Timestamp
    ) -> Dict[str, float]:
        track_history = history[
            (history['driver_id'] == driver_id) &
            (history['circuit_id'] == circuit_id)
        ].sort_values('race_date', ascending=False)
        
        if len(track_history) == 0:
            return {
                'track_avg_points': np.nan,
                'track_avg_finish_pos': np.nan,
                'track_best_finish_pos': np.nan,
                'track_experience_races': 0
            }
        
        features = {
            'track_avg_points': track_history['points'].mean(),
            'track_avg_finish_pos': track_history['position_order'].mean(),
            'track_best_finish_pos': track_history['position_order'].min(),
            'track_experience_races': len(track_history)
        }
        
        return features
    
    #  Build qualifying-derived features
    def build_qualifying_features(
        self,
        quali_data: DataFrame,
        driver_id: int,
        pole_time_ms: Optional[int] = None
    ) -> Dict[str, float]:
        driver_quali = quali_data[quali_data['driver_id'] == driver_id]
        
        if driver_quali.empty:
            return {
                'quali_position': np.nan,
                'quali_gap_to_pole_ms': np.nan,
                'grid_position_gain_potential': np.nan
            }
        
        quali_pos = driver_quali['quali_position'].iloc[0]
        
        # Calculate gap to pole if we have Q3 times
        gap_to_pole = np.nan
        if pole_time_ms and 'q3' in driver_quali.columns:
            driver_q3 = self._time_to_milliseconds(driver_quali['q3'].iloc[0])
            if driver_q3 and pole_time_ms:
                gap_to_pole = driver_q3 - pole_time_ms
        
        # Grid position gain potential (historical average positions gained from this grid slot)
        # Simplified: higher grid position = more potential to gain
        grid_potential = max(0, (20 - quali_pos) * 0.5) if not pd.isna(quali_pos) else np.nan
        
        return {
            'quali_position': quali_pos,
            'quali_gap_to_pole_ms': gap_to_pole,
            'grid_position_gain_potential': grid_potential
        }
    
    # Calculate linear trend (slope) of a series
    def _calculate_trend(self, series: Series) -> float:
        if len(series) < 2:
            return 0.0
        
        x = np.arange(len(series))
        y = series.values
        # Simple linear regression slope
        slope = np.polyfit(x, y, 1)[0]
        return float(slope)
    
    # Compute driver performance index (0-100)
    def _compute_driver_index(self, rolling: DataFrame) -> float:
        if rolling.empty:
            return np.nan
        
        avg_points = rolling['points'].mean()
        avg_finish = rolling['position_order'].mean()
        consistency = rolling['position_order'].std() if len(rolling) > 1 else 0
        
        # Normalize: higher points, lower finish position, lower consistency = better
        # Scale to 0-100
        points_score = min(100, (avg_points / 25) * 100)             # Max 25 points per race
        finish_score = max(0, 100 - (avg_finish / 20) * 100)         # Lower finish = higher score
        consistency_score = max(0, 100 - consistency * 5)            # Lower std = higher score
        
        return (points_score * 0.4 + finish_score * 0.4 + consistency_score * 0.2)
    
    # Compute composite constructor performance index (0-100)
    def _compute_constructor_index(self, rolling: DataFrame) -> float:
        if rolling.empty:
            return np.nan
        
        race_points = rolling.groupby('race_id')['points'].sum()
        avg_points = race_points.mean()
        consistency = race_points.std() if len(race_points) > 1 else 0
        
        points_score = min(100, (avg_points / 50) * 100)  # Max ~50 points per race (2 cars)
        consistency_score = max(0, 100 - consistency * 3)
        
        return (points_score * 0.6 + consistency_score * 0.4)
    
    @staticmethod
    def _time_to_milliseconds(time_str: Any) -> Optional[int]:
        if pd.isna(time_str) or time_str is None:
            return None
        
        time_str = str(time_str).strip()
        if time_str in ['nan', 'None', '']:
            return None
        
        try:
            parts = time_str.split(':')
            if len(parts) == 2:
                minutes, seconds_millis = parts
                seconds, millis = seconds_millis.split('.')
                return int(minutes) * 60000 + int(seconds) * 1000 + int(millis.ljust(3, '0')[:3])
            else:
                seconds, millis = time_str.split('.')
                return int(seconds) * 1000 + int(millis.ljust(3, '0')[:3])
        except (ValueError, AttributeError):
            return None
    
    # Build complete feature set for a specific race
    def build_features_for_race(self, race_id: int) -> DataFrame:
        self.metrics.start()
        
        # Get race info (this is the target, not used for features)
        race_info = self._get_race_info(race_id)
        if not race_info:
            raise ValueError(f"Race {race_id} not found")
        
        target_date = pd.to_datetime(race_info['date'])
        circuit_id = race_info['circuit_id']
        
        # Get historical data (anti-leakage boundary)
        history = self._get_historical_data(race_id, target_date)
        
        # Get qualifying data for this race
        quali_data = self._get_qualifying_data(race_id)
        
        # Get participating drivers
        participants_query = """
        SELECT DISTINCT driver_id, constructor_id 
        FROM results 
        WHERE race_id = :race_id
        """
        participants = self.db.execute_dataframe(participants_query, {"race_id": race_id})
        
        if participants.empty:
            logger.warning("no_participants_found", race_id=race_id)
            return pd.DataFrame()
        
        features_list = []
        
        for _, participant in participants.iterrows():
            driver_id = participant['driver_id']
            constructor_id = participant['constructor_id']
            
            # Build feature groups
            driver_features = self.build_driver_rolling_features(
                history, driver_id, target_date
            )
            
            constructor_features = self.build_constructor_features(
                history, constructor_id, target_date
            )
            
            track_features = self.build_track_features(
                history, driver_id, circuit_id, target_date
            )
            
            quali_features = self.build_qualifying_features(
                quali_data, driver_id
            )
            
            # Combine all features
            feature_record = {
                'race_id': race_id,
                'driver_id': driver_id,
                'constructor_id': constructor_id,
                **driver_features,
                **constructor_features,
                **track_features,
                **quali_features
            }
            
            # Compute overall strength index
            feature_record['overall_strength_index'] = self._compute_overall_index(
                feature_record
            )
            
            features_list.append(feature_record)
            self.metrics.record_success()
        
        features_df = pd.DataFrame(features_list)
        
        # Save to database
        self._save_features(features_df)
        
        metrics = self.metrics.finalize()
        logger.info(
            "features_built",
            race_id=race_id,
            drivers=len(features_df),
            features=len(features_df.columns),
            metrics=metrics
        )
        
        return features_df
    
    # Compute overall driver+constructor+circuit strength index
    def _compute_overall_index(self, features: Dict[str, float]) -> float:
        driver_idx = features.get('driver_performance_index', 50)
        constructor_idx = features.get('constructor_performance_index', 50)
        track_exp = features.get('track_experience_races', 0)
        track_avg = features.get('track_avg_points', 0)
        
        # Normalize track experience bonus
        track_bonus = min(10, track_exp * 0.5)
        track_score = min(100, (track_avg / 25) * 100) if track_avg else 50
        
        return (
            driver_idx * 0.35 +
            constructor_idx * 0.35 +
            track_score * 0.20 +
            track_bonus
        )
    
    # Save features to PostgreSQL feature table
    def _save_features(self, df: DataFrame) -> None:
        if df.empty:
            return
        
        # Ensure correct column order for upsert
        columns = [
            'race_id', 'driver_id',
            'rolling_avg_points_5r', 'rolling_avg_finish_pos_5r', 'rolling_points_trend',
            'recent_form_points', 'recent_form_finish_pos', 'recent_form_quali_pos',
            'constructor_avg_points_5r', 'constructor_reliability_score',
            'track_avg_points', 'track_avg_finish_pos', 'track_best_finish_pos', 'track_experience_races',
            'lap_consistency_std', 'avg_lap_time_ms', 'fastest_lap_time_ms',
            'dnf_probability', 'consecutive_finishes', 'mechanical_dnf_rate',
            'quali_position', 'quali_gap_to_pole_ms', 'grid_position_gain_potential',
            'wet_race_experience', 'wet_race_avg_points',
            'driver_performance_index', 'constructor_performance_index', 'overall_strength_index'
        ]
        
        # Only keep columns that exist
        available_cols = [c for c in columns if c in df.columns]
        df_to_save = df[available_cols].copy()
        
        # Add timestamps
        df_to_save['created_at'] = pd.Timestamp.now(tz='UTC')
        df_to_save['updated_at'] = pd.Timestamp.now(tz='UTC')
        
        # Upsert to database
        self.db.bulk_insert_dataframe(
            df_to_save,
            'driver_race_features',
            if_exists='append'
        )
        
        logger.info("features_saved_to_database", records=len(df_to_save))
    
    # Build features for all races in a season sequentially
    def build_features_for_season(self, year: int) -> DataFrame:
        query = """
        SELECT race_id, date 
        FROM races 
        WHERE year = :year 
        ORDER BY date ASC
        """
        races = self.db.execute_dataframe(query, {"year": year})
        
        all_features = []
        for _, race in races.iterrows():
            try:
                features = self.build_features_for_race(race['race_id'])
                all_features.append(features)
            except Exception as e:
                logger.error(
                    "feature_building_failed_for_race",
                    race_id=race['race_id'],
                    error=str(e)
                )
        
        if all_features:
            return pd.concat(all_features, ignore_index=True)
        return pd.DataFrame()