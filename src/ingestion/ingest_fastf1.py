# This Provides detailed lap timing, weather data, and session information
import os
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from src.ingestion.base import BaseIngestor, IngestionResult
from src.utils.config import get_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FastF1Ingestor(BaseIngestor):
    
    @property
    def source_name(self) -> str:
        return "fastf1"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache_dir = Path(self.config.ingestion.fastf1_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure FastF1 cache
        try:
            import fastf1
            fastf1.Cache.enable_cache(str(self.cache_dir))
            logger.info("fastf1_cache_enabled", path=str(self.cache_dir))
        except ImportError:
            logger.warning("fastf1_not_installed")
            raise
    
    def _load_session(
        self,
        year: int,
        round_num: int,
        session_type: str = 'R'
    ) -> Optional[Any]:
        
        import fastf1
        
        @retry(
            stop=stop_after_attempt(self.config.ingestion.fastf1_retry_attempts),
            wait=wait_exponential(multiplier=2, min=1, max=60),
            reraise=True
        )
        def _load():
            session = fastf1.get_session(year, round_num, session_type)
            session.load(laps=True, weather=True, telemetry=False)
            return session
        
        try:
            from tenacity import retry, wait_exponential, stop_after_attempt
            session = _load()
            logger.info(
                "fastf1_session_loaded",
                year=year,
                round=round_num,
                session=session_type,
                event_name=session.event.EventName
            )
            return session
        except Exception as e:
            logger.error(
                "fastf1_session_load_failed",
                year=year,
                round=round_num,
                error=str(e)
            )
            raise
    
    # Fetch detailed lap data including sector times
    def fetch_laps(self, year: int, round_num: int) -> pd.DataFrame:
        session = self._load_session(year, round_num, 'R')
        
        if session.laps is None or session.laps.empty:
            logger.warning("fastf1_no_lap_data", year=year, round=round_num)
            return pd.DataFrame()
        
        laps_df = session.laps.copy()
        
        # Standardize column names 
        column_mapping = {
            'Driver': 'driver_code',
            'DriverNumber': 'driver_number',
            'LapTime': 'lap_time',
            'LapNumber': 'lap_number',
            'Stint': 'stint',
            'PitOutTime': 'pit_out_time',
            'PitInTime': 'pit_in_time',
            'Sector1Time': 'sector1_time',
            'Sector2Time': 'sector2_time',
            'Sector3Time': 'sector3_time',
            'SpeedI1': 'speed_i1',
            'SpeedI2': 'speed_i2',
            'SpeedFL': 'speed_fl',
            'SpeedST': 'speed_st',
            'Compound': 'tyre_compound',
            'TyreLife': 'tyre_life',
            'FreshTyre': 'fresh_tyre',
            'Team': 'team',
            'TrackStatus': 'track_status',
            'Deleted': 'deleted',
            'IsAccurate': 'is_accurate'
        }
        
        laps_df = laps_df.rename(columns=column_mapping)
        laps_df['year'] = year
        laps_df['round'] = round_num
        
        # Convert timedelta columns to milliseconds
        time_cols = ['lap_time', 'sector1_time', 'sector2_time', 'sector3_time',
                     'pit_out_time', 'pit_in_time']
        for col in time_cols:
            if col in laps_df.columns:
                laps_df[col] = laps_df[col].apply(
                    lambda x: int(x.total_seconds() * 1000) if pd.notna(x) else None
                )
        
        return laps_df
    
    # Fetch weather data for a race session
    def fetch_weather(self, year: int, round_num: int) -> pd.DataFrame:
        session = self._load_session(year, round_num, 'R')
        
        if session.weather_data is None or session.weather_data.empty:
            logger.warning("fastf1_no_weather_data", year=year, round=round_num)
            return pd.DataFrame()
        
        weather_df = session.weather_data.copy()
        weather_df['year'] = year
        weather_df['round'] = round_num
        
        # Standardize columns
        column_mapping = {
            'Time': 'session_time',
            'AirTemp': 'air_temperature',
            'Humidity': 'humidity',
            'Pressure': 'pressure',
            'Rainfall': 'rainfall',
            'TrackTemp': 'track_temperature',
            'WindDirection': 'wind_direction',
            'WindSpeed': 'wind_speed'
        }
        
        weather_df = weather_df.rename(columns=column_mapping)
        return weather_df
    
    # Fetch session metadata and event information
    def fetch_session_info(self, year: int, round_num: int) -> pd.DataFrame:
        import fastf1
        
        event = fastf1.get_event(year, round_num)
        
        session_data = {
            'year': year,
            'round': round_num,
            'event_name': event.EventName,
            'event_date': event.EventDate,
            'country': event.Country,
            'location': event.Location,
            'circuit': event.OfficialEventName,
            'session1_date': event.Session1Date,
            'session2_date': event.Session2Date,
            'session3_date': event.Session3Date,
            'session4_date': event.Session4Date,
            'session5_date': event.Session5Date,
            'session1': event.Session1,
            'session2': event.Session2,
            'session3': event.Session3,
            'session4': event.Session4,
            'session5': event.Session5
        }
        
        return pd.DataFrame([session_data])
    
    def fetch(self, year: int = 2025, round_num: int = 1, **kwargs) -> pd.DataFrame:
       
        entity = kwargs.get("entity", "laps")
        
        fetch_methods = {
            "laps": self.fetch_laps,
            "weather": self.fetch_weather,
            "session_info": self.fetch_session_info
        }
        
        method = fetch_methods.get(entity)
        if not method:
            raise ValueError(f"Unknown FastF1 entity: {entity}")
        
        return method(year, round_num)
    
    def validate_schema(self, df: pd.DataFrame) -> bool:
        """Validate FastF1 data schema."""
        if df.empty:
            logger.warning("fastf1_empty_dataframe")
            return True
        
        # Detect entity type
        if "lap_number" in df.columns:
            required = ["year", "round", "driver_number", "lap_number"]
        elif "air_temperature" in df.columns:
            required = ["year", "round", "session_time"]
        elif "event_name" in df.columns:
            required = ["year", "round", "event_name"]
        else:
            raise ValueError(f"Unknown FastF1 schema: {list(df.columns)}")
        
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required FastF1 columns: {missing}")
        
        return True
    
    def ingest_season(
        self,
        year: int,
        rounds: List[int] = None,
        entities: List[str] = None
    ) -> Dict[str, List[IngestionResult]]:
       
        if entities is None:
            entities = ["laps", "weather", "session_info"]
        
        if rounds is None:
            # Default to all rounds in season
            rounds = list(range(1, 25))
        
        results = {entity: [] for entity in entities}
        
        for round_num in rounds:
            for entity in entities:
                try:
                    result = self.ingest(year=year, round_num=round_num, entity=entity)
                    results[entity].append(result)
                    logger.info(
                        "fastf1_round_ingested",
                        year=year,
                        round=round_num,
                        entity=entity,
                        records=result.records_count
                    )
                except Exception as e:
                    logger.error(
                        "fastf1_round_ingestion_failed",
                        year=year,
                        round=round_num,
                        entity=entity,
                        error=str(e)
                    )
                    # Continue with next round rather than failing entire season
        
        return results