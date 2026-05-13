# Data cleaning and validation pipeline.
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pandas import DataFrame

from src.utils.config import AppConfig, get_config
from src.utils.db import get_db
from src.utils.io_utils import get_io
from src.utils.logger import PipelineMetrics, SensitiveDataMasker, get_logger

logger = get_logger(__name__)

class DataCleaner:
    
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or get_config()
        self.io = get_io()
        self.metrics = PipelineMetrics("data_cleaning")
        self.null_threshold_numeric = self.config.processing.null_threshold_numeric
        self.null_threshold_categorical = self.config.processing.null_threshold_categorical
    
    def normalize_schema(self, df: DataFrame, entity_type: str) -> DataFrame:
       
        df = df.copy()
        
        # Column name standardization
        df.columns = df.columns.str.lower().str.strip()
        
        # Type normalization based on entity
        type_mapping = self._get_type_mapping(entity_type)
        
        for col, dtype in type_mapping.items():
            if col in df.columns:
                try:
                    if dtype == 'datetime':
                        df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)
                    elif dtype == 'int':
                        df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                    elif dtype == 'float':
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    elif dtype == 'string':
                        df[col] = df[col].astype(str).replace('nan', None).replace('None', None)
                    elif dtype == 'timedelta_ms':
                        # Convert time strings to milliseconds
                        df[col] = df[col].apply(self._time_to_milliseconds)
                except Exception as e:
                    logger.warning(
                        "type_conversion_failed",
                        column=col,
                        target_type=dtype,
                        error=str(e)
                    )
        
        logger.info("schema_normalized", entity=entity_type, columns=list(df.columns))
        return df
    
    def _get_type_mapping(self, entity_type: str) -> Dict[str, str]:
        mappings = {
            'results': {
                'year': 'int',
                'round': 'int',
                'grid': 'int',
                'position': 'int',
                'position_order': 'int',
                'points': 'float',
                'laps': 'int',
                'milliseconds': 'int',
                'fastest_lap': 'int',
                'rank': 'int',
                'fastest_lap_speed': 'float',
                'race_date': 'datetime'
            },
            'laps': {
                'year': 'int',
                'round': 'int',
                'lap': 'int',
                'position': 'int',
                'milliseconds': 'int',
                'time': 'timedelta_ms'
            },
            'drivers': {
                'number': 'int',
                'dob': 'datetime'
            },
            'races': {
                'year': 'int',
                'round': 'int',
                'date': 'datetime',
                'time': 'string'
            },
            'telemetry': {
                'session_key': 'int',
                'driver_number': 'int',
                'lap': 'int',
                'sector1_time': 'float',
                'sector2_time': 'float',
                'sector3_time': 'float',
                'speed_trap': 'float',
                'drs_usage_pct': 'float',
                'throttle_avg': 'float',
                'brake_events': 'int',
                'gear_changes': 'int',
                'tyre_age': 'int',
                'air_temp': 'float',
                'track_temp': 'float',
                'humidity': 'float',
                'wind_speed': 'float'
            }
        }
        return mappings.get(entity_type, {})
    
    @staticmethod
    def _time_to_milliseconds(time_str: Any) -> Optional[int]:
        if pd.isna(time_str) or time_str is None:
            return None
        
        if isinstance(time_str, (int, float)):
            return int(time_str)
        
        time_str = str(time_str).strip()
        if time_str in ['nan', 'None', '']:
            return None
        
        try:
            # Handle formats: "1:32.456", "92.456", "1:32:45.678"
            parts = time_str.split(':')
            if len(parts) == 3:
                minutes, seconds, millis = parts
                return int(minutes) * 60000 + int(seconds) * 1000 + int(millis)
            elif len(parts) == 2:
                minutes, seconds_millis = parts
                seconds, millis = seconds_millis.split('.')
                return int(minutes) * 60000 + int(seconds) * 1000 + int(millis.ljust(3, '0')[:3])
            else:
                # Assume seconds.milliseconds
                seconds, millis = time_str.split('.')
                return int(seconds) * 1000 + int(millis.ljust(3, '0')[:3])
        except (ValueError, AttributeError):
            return None
    
    # Maps source-specific identifiers to canonical databases IDs
    def reconcile_keys(
        self,
        df: DataFrame,
        key_mapping: Dict[str, Dict[str, int]]
    ) -> DataFrame:
        df = df.copy()
        
        for column, mapping in key_mapping.items():
            if column in df.columns:
                df[f"{column}_canonical"] = df[column].map(mapping)
                
                # Log unreconciled keys
                unreconciled = df[df[f"{column}_canonical"].isna() & df[column].notna()]
                if not unreconciled.empty:
                    logger.warning(
                        "unreconciled_keys",
                        column=column,
                        count=len(unreconciled),
                        samples=unreconciled[column].unique()[:5].tolist()
                    )
        
        logger.info("keys_reconciled", columns=list(key_mapping.keys()))
        return df
    
    # Normalize timestamp to UTC
    def normalize_timestamps(self, df: DataFrame, timestamp_cols: List[str]) -> DataFrame:
        df = df.copy()
        
        for col in timestamp_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)
                
                # Log timezone conversions
                if df[col].dt.tz is None:
                    df[col] = df[col].dt.tz_localize('UTC')
        
        logger.info("timestamps_normalized", columns=timestamp_cols)
        return df
    
    def standardize_lap_times(self, df: DataFrame, time_col: str = 'time') -> DataFrame:
        df = df.copy()
        
        if time_col in df.columns and 'milliseconds' not in df.columns:
            df['milliseconds'] = df[time_col].apply(self._time_to_milliseconds)
            
            # Validate: milliseconds should be positive and reasonable (< 5 minutes)
            invalid = df[(df['milliseconds'] <= 0) | (df['milliseconds'] > 300000)]
            if not invalid.empty:
                logger.warning(
                    "invalid_lap_times_detected",
                    count=len(invalid),
                    threshold_ms=300000
                )
                df.loc[invalid.index, 'milliseconds'] = np.nan
        
        return df
    
    # Removing duplicates using composite keys
    def remove_duplicates(
        self,
        df: DataFrame,
        composite_keys: List[str]
    ) -> Tuple[DataFrame, int]:
       
        initial_count = len(df)
        
        # Validate all key columns exist
        missing_keys = [k for k in composite_keys if k not in df.columns]
        if missing_keys:
            raise ValueError(f"Composite key columns missing: {missing_keys}")
        
        # Remove duplicates keeping last (most recent)
        df_deduped = df.drop_duplicates(subset=composite_keys, keep='last')
        removed = initial_count - len(df_deduped)
        
        if removed > 0:
            logger.info(
                "duplicates_removed",
                composite_keys=composite_keys,
                removed=removed,
                remaining=len(df_deduped)
            )
        
        return df_deduped, removed
    
    # Handle missing values with entity-specific strategies
    def handle_missing_values(self, df: DataFrame, entity_type: str) -> DataFrame:
        
        df = df.copy()
        
        # Calculate null percentages
        null_pct = df.isnull().mean()
        high_null_cols = null_pct[null_pct > self.null_threshold_numeric].index.tolist()
        
        if high_null_cols:
            logger.warning(
                "high_null_columns",
                columns=high_null_cols,
                null_percentages=null_pct[high_null_cols].to_dict()
            )
        
        # Entity-specific imputation strategies
        strategies = self._get_imputation_strategies(entity_type)
        
        for col, strategy in strategies.items():
            if col not in df.columns:
                continue
            
            null_count = df[col].isnull().sum()
            if null_count == 0:
                continue
            
            if strategy == 'median':
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                logger.debug("imputed_median", column=col, value=median_val, count=null_count)
            
            elif strategy == 'group_median':
                # Group by related columns and fill with group median
                group_cols = self._get_group_columns(entity_type, col)
                if group_cols and all(g in df.columns for g in group_cols):
                    df[col] = df.groupby(group_cols)[col].transform(
                        lambda x: x.fillna(x.median())
                    )
                    # Fill remaining with overall median
                    df[col] = df[col].fillna(df[col].median())
                else:
                    df[col] = df[col].fillna(df[col].median())
            
            elif strategy == 'unknown':
                df[col] = df[col].fillna('Unknown')
                logger.debug("imputed_unknown", column=col, count=null_count)
            
            elif strategy == 'zero':
                df[col] = df[col].fillna(0)
                logger.debug("imputed_zero", column=col, count=null_count)
            
            elif strategy == 'forward_fill':
                df[col] = df[col].fillna(method='ffill')
                logger.debug("imputed_ffill", column=col, count=null_count)
        
        return df
    
    def _get_imputation_strategies(self, entity_type: str) -> Dict[str, str]:
        strategies = {
            'results': {
                'grid': 'median',
                'position': 'group_median',
                'position_order': 'group_median',
                'points': 'zero',
                'laps': 'group_median',
                'milliseconds': 'group_median',
                'fastest_lap_speed': 'group_median',
                'status': 'unknown'
            },
            'laps': {
                'position': 'forward_fill',
                'milliseconds': 'group_median',
                'sector1_time': 'group_median',
                'sector2_time': 'group_median',
                'sector3_time': 'group_median'
            },
            'drivers': {
                'number': 'zero',
                'code': 'unknown',
                'dob': 'unknown'
            },
            'telemetry': {
                'sector1_time': 'group_median',
                'sector2_time': 'group_median',
                'sector3_time': 'group_median',
                'speed_trap': 'group_median',
                'drs_usage_pct': 'group_median',
                'throttle_avg': 'group_median',
                'brake_events': 'zero',
                'gear_changes': 'zero',
                'air_temp': 'group_median',
                'track_temp': 'group_median',
                'humidity': 'group_median',
                'wind_speed': 'group_median'
            }
        }
        return strategies.get(entity_type, {})
    
    def _get_group_columns(self, entity_type: str, column: str) -> List[str]:
        groupings = {
            'results': {
                'position': ['year', 'round'],
                'position_order': ['year', 'round'],
                'laps': ['year', 'round'],
                'milliseconds': ['year', 'round', 'driver_id'],
                'fastest_lap_speed': ['year', 'round']
            },
            'laps': {
                'milliseconds': ['year', 'round', 'driver_number'],
                'sector1_time': ['year', 'round', 'driver_number'],
                'sector2_time': ['year', 'round', 'driver_number'],
                'sector3_time': ['year', 'round', 'driver_number']
            },
            'telemetry': {
                'sector1_time': ['session_key', 'driver_number'],
                'sector2_time': ['session_key', 'driver_number'],
                'sector3_time': ['session_key', 'driver_number'],
                'speed_trap': ['session_key', 'driver_number'],
                'drs_usage_pct': ['session_key', 'driver_number'],
                'throttle_avg': ['session_key', 'driver_number'],
                'air_temp': ['session_key'],
                'track_temp': ['session_key'],
                'humidity': ['session_key'],
                'wind_speed': ['session_key']
            }
        }
        entity_groups = groupings.get(entity_type, {})
        return entity_groups.get(column, [])
    
    def generate_validation_report(self, df: DataFrame, entity_type: str) -> Dict[str, Any]:
        report = {
            'entity_type': entity_type,
            'record_count': len(df),
            'column_count': len(df.columns),
            'columns': list(df.columns),
            'null_summary': df.isnull().sum().to_dict(),
            'null_percentage': (df.isnull().mean() * 100).round(2).to_dict(),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024,
            'dtypes': {k: str(v) for k, v in df.dtypes.items()},
            'timestamp': pd.Timestamp.now(tz='UTC').isoformat()
        }
        
        # Entity-specific validations
        if entity_type == 'results':
            report['validations'] = {
                'negative_points': (df['points'] < 0).sum(),
                'grid_out_of_range': ((df['grid'] < 0) | (df['grid'] > 30)).sum(),
                'position_order_out_of_range': ((df['position_order'] < 1) | (df['position_order'] > 30)).sum(),
                'future_dates': (df['race_date'] > pd.Timestamp.now(tz='UTC')).sum() if 'race_date' in df.columns else 0
            }
        elif entity_type == 'laps':
            report['validations'] = {
                'negative_lap_times': (df['milliseconds'] <= 0).sum() if 'milliseconds' in df.columns else 0,
                'lap_number_out_of_range': ((df['lap'] < 1) | (df['lap'] > 100)).sum() if 'lap' in df.columns else 0
            }
        
        logger.info("validation_report_generated", entity=entity_type, **SensitiveDataMasker.mask_dict(report))
        return report
    
    def process(
        self,
        df: DataFrame,
        entity_type: str,
        composite_keys: List[str],
        key_mapping: Optional[Dict[str, Dict[str, int]]] = None,
        timestamp_cols: Optional[List[str]] = None
    ) -> Tuple[DataFrame, Dict[str, Any]]:
        self.metrics.start()
        initial_rows = len(df)
        
        try:
            # Step 1: Schema normalization
            df = self.normalize_schema(df, entity_type)
            self.metrics.record_success()
            
            # Step 2: Key reconciliation
            if key_mapping:
                df = self.reconcile_keys(df, key_mapping)
                self.metrics.record_success()
            
            # Step 3: Timestamp normalization
            if timestamp_cols:
                df = self.normalize_timestamps(df, timestamp_cols)
                self.metrics.record_success()
            
            # Step 4: Lap time standardization
            if entity_type in ['laps', 'results']:
                df = self.standardize_lap_times(df)
                self.metrics.record_success()
            
            # Step 5: Duplicate removal
            df, duplicates_removed = self.remove_duplicates(df, composite_keys)
            self.metrics.record_success()
            
            # Step 6: Missing value handling
            df = self.handle_missing_values(df, entity_type)
            self.metrics.record_success()
            
            # Step 7: Validation report
            report = self.generate_validation_report(df, entity_type)
            report['duplicates_removed'] = duplicates_removed
            report['rows_final'] = len(df)
            report['rows_dropped'] = initial_rows - len(df)
            
            metrics = self.metrics.finalize()
            report['pipeline_metrics'] = metrics
            
            logger.info(
                "cleaning_completed",
                entity=entity_type,
                initial_rows=initial_rows,
                final_rows=len(df),
                duplicates_removed=duplicates_removed
            )
            
            return df, report
            
        except Exception as e:
            self.metrics.record_failure(e, {"entity": entity_type})
            metrics = self.metrics.finalize()
            logger.error("cleaning_failed", entity=entity_type, error=str(e), metrics=metrics)
            raise