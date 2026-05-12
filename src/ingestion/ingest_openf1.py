import time
from typing import Dict, List, Optional

import pandas as pd
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.ingestion.base import BaseIngestor, IngestionResult
from src.utils.config import get_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenF1Ingestor(BaseIngestor):
    
    @property
    def source_name(self) -> str:
        return "openf1"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_url = self.config.ingestion.openf1_base_url
        self.timeout = self.config.ingestion.openf1_timeout
        self.rate_limit = self.config.ingestion.openf1_rate_limit
        self._circuit_open = True
        self._last_request_time = 0.0
    
    # Execute rate-limited request with circuit breaker pattern
    def _rate_limited_request(self, endpoint: str, params: Dict = None) -> List[Dict]:
        # Circuit breaker check
        if not self._circuit_open:
            logger.warning("circuit_breaker_open", source="openf1")
            raise ConnectionError("Circuit breaker is open for OpenF1 API")
        
        # Rate limiting
        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / self.rate_limit
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        
        @retry(
            stop=stop_after_attempt(self.config.ingestion.openf1_retry_attempts),
            wait=wait_exponential(
                multiplier=self.config.ingestion.openf1_retry_backoff,
                min=1,
                max=120
            ),
            retry=retry_if_exception_type((
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError
            )),
            reraise=True
        )
        def _request() -> List[Dict]:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "F1-Data-Platform/1.0"
                }
            )
            response.raise_for_status()
            return response.json()
        
        try:
            data = _request()
            self._last_request_time = time.time()
            self._circuit_open = True  # Reset on success
            return data
        except requests.exceptions.RequestException as e:
            self._circuit_open = False  # Trip circuit breaker
            logger.error("openf1_request_failed", endpoint=endpoint, error=str(e))
            raise
    
    # Session data fetching
    def fetch_sessions(self, year: int = 2026) -> pd.DataFrame:
        data = self._rate_limited_request("sessions", {"year": year})
        
        sessions = []
        for session in data:
            sessions.append({
                "session_key": session.get("session_key"),
                "session_name": session.get("session_name"),
                "session_type": session.get("session_type"),
                "year": session.get("year"),
                "country_code": session.get("country_code"),
                "circuit_short_name": session.get("circuit_short_name"),
                "date_start": session.get("date_start"),
                "date_end": session.get("date_end"),
                "gmt_offset": session.get("gmt_offset")
            })
        
        return pd.DataFrame(sessions)
    
    # Fetch driver list for a specific session
    def fetch_drivers(self, session_key: int) -> pd.DataFrame:
        data = self._rate_limited_request("drivers", {"session_key": session_key})
        
        drivers = []
        for driver in data:
            drivers.append({
                "session_key": session_key,
                "driver_number": driver.get("driver_number"),
                "broadcast_name": driver.get("broadcast_name"),
                "full_name": driver.get("full_name"),
                "name_acronym": driver.get("name_acronym"),
                "team_name": driver.get("team_name"),
                "team_colour": driver.get("team_colour"),
                "country_code": driver.get("country_code")
            })
        
        return pd.DataFrame(drivers)
    
    # Fetch lap data for a specific session
    def fetch_laps(self, session_key: int) -> pd.DataFrame:
        data = self._rate_limited_request("laps", {"session_key": session_key})
        
        laps = []
        for lap in data:
            laps.append({
                "session_key": session_key,
                "driver_number": lap.get("driver_number"),
                "lap_number": lap.get("lap_number"),
                "lap_duration": lap.get("lap_duration"),
                "duration_sector_1": lap.get("duration_sector_1"),
                "duration_sector_2": lap.get("duration_sector_2"),
                "duration_sector_3": lap.get("duration_sector_3"),
                "i1_speed": lap.get("i1_speed"),
                "i2_speed": lap.get("i2_speed"),
                "st_speed": lap.get("st_speed"),
                "date_start": lap.get("date_start"),
                "is_pit_out_lap": lap.get("is_pit_out_lap")
            })
        
        return pd.DataFrame(laps)
    
    # Fetch car telemetry data
    def fetch_car_data(self, session_key: int, driver_number: int) -> pd.DataFrame:
        
        data = self._rate_limited_request(
            "car_data",
            {"session_key": session_key, "driver_number": driver_number}
        )
        
        telemetry = []
        for record in data:
            telemetry.append({
                "session_key": session_key,
                "driver_number": driver_number,
                "date": record.get("date"),
                "rpm": record.get("rpm"),
                "speed": record.get("speed"),
                "n_gear": record.get("n_gear"),
                "throttle": record.get("throttle"),
                "brake": record.get("brake"),
                "drs": record.get("drs")
            })
        
        return pd.DataFrame(telemetry)
    
    # Fetch OpenF1 data
    def fetch(self, session_key: Optional[int] = None, **kwargs) -> pd.DataFrame:
        
        entity = kwargs.get("entity", "sessions")
        
        if entity == "sessions":
            return self.fetch_sessions(kwargs.get("year", 2026))
        elif entity == "drivers":
            if not session_key:
                raise ValueError("session_key required for drivers entity")
            return self.fetch_drivers(session_key)
        elif entity == "laps":
            if not session_key:
                raise ValueError("session_key required for laps entity")
            return self.fetch_laps(session_key)
        elif entity == "car_data":
            if not session_key:
                raise ValueError("session_key required for car_data entity")
            return self.fetch_car_data(session_key, kwargs.get("driver_number", 1))
        else:
            raise ValueError(f"Unknown entity: {entity}")
    
    # Validate OpenF1 data schema
    def validate_schema(self, df: pd.DataFrame) -> bool:
    
        if df.empty:
            logger.warning("openf1_empty_dataframe")
            return True
        
        # Detect entity from columns
        if "session_key" in df.columns and "lap_number" in df.columns:
            required = ["session_key", "driver_number", "lap_number"]
        elif "session_key" in df.columns and "driver_number" in df.columns:
            required = ["session_key", "driver_number"]
        elif "session_key" in df.columns and "rpm" in df.columns:
            required = ["session_key", "driver_number", "date"]
        else:
            required = ["session_key", "session_name"]
        
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required OpenF1 columns: {missing}")
        
        return True
    
    # Ingest complete session data
    def ingest_session(
        self,
        session_key: int,
        include_telemetry: bool = False
    ) -> Dict[str, IngestionResult]:
        
        results = {}
        
        # Always fetch drivers and laps
        for entity in ["drivers", "laps"]:
            result = self.ingest(session_key=session_key, entity=entity)
            results[entity] = result
        
        # Optionally fetch telemetry (stored in Parquet, not DB)
        if include_telemetry:
            drivers_df = results["drivers"].metadata.get("dataframe")
            if drivers_df is not None:
                for driver_number in drivers_df["driver_number"].unique():
                    try:
                        result = self.ingest(
                            session_key=session_key,
                            entity="car_data",
                            driver_number=driver_number
                        )
                        results[f"telemetry_{driver_number}"] = result
                    except Exception as e:
                        logger.error(
                            "telemetry_ingestion_failed",
                            driver=driver_number,
                            error=str(e)
                        )
        
        return results