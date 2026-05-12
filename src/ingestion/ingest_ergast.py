import time
from typing import Dict, List, Optional

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.ingestion.base import BaseIngestor, IngestionResult
from src.utils.config import get_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ErgastIngestor(BaseIngestor):
    
    @property
    def source_name(self) -> str:
        return "ergast"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_url = self.config.ingestion.ergast_base_url
        self.timeout = self.config.ingestion.ergast_timeout
        self.rate_limit = self.config.ingestion.ergast_rate_limit
        self._last_request_time = 0.0
    
    def _rate_limited_request(self, url: str) -> Dict:

        # Rate limiting
        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / self.rate_limit
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        
        @retry(
            stop=stop_after_attempt(self.config.ingestion.ergast_retry_attempts),
            wait=wait_exponential(
                multiplier=self.config.ingestion.ergast_retry_backoff,
                min=1,
                max=60
            ),
            reraise=True
        )
        def _request() -> Dict:
            response = requests.get(
                url,
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
            return data
        except requests.exceptions.RequestException as e:
            logger.error("ergast_request_failed", url=url, error=str(e))
            raise
    
    def _fetch_paginated(self, endpoint: str, limit: int = 1000) -> List[Dict]:
       
        all_records = []
        offset = 0
        
        while True:
            url = f"{self.base_url}/{endpoint}.json?limit={limit}&offset={offset}"
            logger.debug("fetching_page", url=url, offset=offset)
            
            data = self._rate_limited_request(url)
            mr_data = data.get("MRData", {})
            total = int(mr_data.get("total", 0))
            
            table_key = list(mr_data.get("Table", {}).keys())[0] if mr_data.get("Table") else None
            if not table_key:
                break
                
            records = mr_data["Table"][table_key]
            if not records:
                break
                
            all_records.extend(records)
            offset += limit
            
            if offset >= total:
                break
        
        return all_records
    
    def fetch_races(self, season: int) -> pd.DataFrame:
       
        records = self._fetch_paginated(f"{season}")
        races = []
        
        for record in records:
            race_table = record.get("Races", [])
            for race in race_table:
                circuit = race.get("Circuit", {})
                location = circuit.get("Location", {})
                
                races.append({
                    "year": season,
                    "round": int(race.get("round", 0)),
                    "circuit_ref": circuit.get("circuitId"),
                    "race_name": race.get("raceName"),
                    "date": race.get("date"),
                    "time": race.get("time", "12:00:00Z"),
                    "url": race.get("url"),
                    "circuit_name": circuit.get("circuitName"),
                    "location": location.get("locality"),
                    "country": location.get("country"),
                    "latitude": location.get("lat"),
                    "longitude": location.get("long"),
                    "altitude": location.get("alt")
                })
        
        return pd.DataFrame(races)
    
    def fetch_results(self, season: int) -> pd.DataFrame:
    
        records = self._fetch_paginated(f"{season}/results")
        results = []
        
        for record in records:
            race_info = record.get("Races", [{}])[0]
            race_name = race_info.get("raceName")
            round_num = int(race_info.get("round", 0))
            date = race_info.get("date")
            
            for result in race_info.get("Results", []):
                driver = result.get("Driver", {})
                constructor = result.get("Constructor", {})
                
                results.append({
                    "year": season,
                    "round": round_num,
                    "race_name": race_name,
                    "race_date": date,
                    "driver_ref": driver.get("driverId"),
                    "constructor_ref": constructor.get("constructorId"),
                    "number": int(result.get("number", 0)) if result.get("number") else None,
                    "grid": int(result.get("grid", 0)),
                    "position": int(result.get("position", 0)) if result.get("position") else None,
                    "position_text": result.get("positionText"),
                    "position_order": int(result.get("position", 0)) if result.get("position") else 99,
                    "points": float(result.get("points", 0)),
                    "laps": int(result.get("laps", 0)) if result.get("laps") else 0,
                    "time": result.get("Time", {}).get("time") if result.get("Time") else None,
                    "milliseconds": int(result.get("Time", {}).get("millis", 0)) if result.get("Time") else None,
                    "fastest_lap": int(result.get("FastestLap", {}).get("lap", 0)) if result.get("FastestLap") else None,
                    "rank": int(result.get("FastestLap", {}).get("rank", 0)) if result.get("FastestLap") else None,
                    "fastest_lap_time": result.get("FastestLap", {}).get("Time", {}).get("time") if result.get("FastestLap") else None,
                    "fastest_lap_speed": float(result.get("FastestLap", {}).get("AverageSpeed", {}).get("speed", 0)) if result.get("FastestLap") else None,
                    "status": result.get("status")
                })
        
        return pd.DataFrame(results)
    
    def fetch_drivers(self, season: int) -> pd.DataFrame:
    
        records = self._fetch_paginated(f"{season}/drivers")
        drivers = []
        
        for record in records:
            driver_table = record.get("Drivers", [])
            for driver in driver_table:
                drivers.append({
                    "driver_ref": driver.get("driverId"),
                    "number": int(driver.get("permanentNumber", 0)) if driver.get("permanentNumber") else None,
                    "code": driver.get("code"),
                    "forename": driver.get("givenName"),
                    "surname": driver.get("familyName"),
                    "dob": driver.get("dateOfBirth"),
                    "nationality": driver.get("nationality"),
                    "url": driver.get("url")
                })
        
        return pd.DataFrame(drivers)
    
    def fetch_constructors(self, season: int) -> pd.DataFrame:
        
        records = self._fetch_paginated(f"{season}/constructors")
        constructors = []
        
        for record in records:
            constructor_table = record.get("Constructors", [])
            for constructor in constructor_table:
                constructors.append({
                    "constructor_ref": constructor.get("constructorId"),
                    "name": constructor.get("name"),
                    "nationality": constructor.get("nationality"),
                    "url": constructor.get("url")
                })
        
        return pd.DataFrame(constructors)
    
    def fetch_circuits(self, season: int) -> pd.DataFrame:
        
        records = self._fetch_paginated(f"{season}/circuits")
        circuits = []
        
        for record in records:
            circuit_table = record.get("Circuits", [])
            for circuit in circuit_table:
                location = circuit.get("Location", {})
                circuits.append({
                    "circuit_ref": circuit.get("circuitId"),
                    "name": circuit.get("circuitName"),
                    "location": location.get("locality"),
                    "country": location.get("country"),
                    "latitude": location.get("lat"),
                    "longitude": location.get("long"),
                    "altitude": location.get("alt"),
                    "url": circuit.get("url")
                })
        
        return pd.DataFrame(circuits)
    
    def fetch_lap_times(self, season: int, round_num: int) -> pd.DataFrame:

        records = self._fetch_paginated(f"{season}/{round_num}/laps")
        lap_times = []
        
        for record in records:
            race_info = record.get("Races", [{}])[0]
            for lap in race_info.get("Laps", []):
                lap_num = int(lap.get("number", 0))
                for timing in lap.get("Timings", []):
                    lap_times.append({
                        "year": season,
                        "round": round_num,
                        "lap": lap_num,
                        "driver_ref": timing.get("driverId"),
                        "position": int(timing.get("position", 0)),
                        "time": timing.get("time")
                    })
        
        return pd.DataFrame(lap_times)
    
    # Fetch comprehensive data for a season
    def fetch(self, season: int = 2025, **kwargs) -> pd.DataFrame:
        
        entity = kwargs.get("entity", "results")
        
        fetch_methods = {
            "results": self.fetch_results,
            "drivers": self.fetch_drivers,
            "constructors": self.fetch_constructors,
            "circuits": self.fetch_circuits,
            "races": self.fetch_races,
            "laps": lambda s: self.fetch_lap_times(s, kwargs.get("round", 1))
        }
        
        method = fetch_methods.get(entity, self.fetch_results)
        return method(season)
    
    # Validate Ergast data schema
    def validate_schema(self, df: pd.DataFrame) -> bool:
        
        required_cols = {
            "results": ["year", "round", "driver_ref", "constructor_ref"],
            "drivers": ["driver_ref", "forename", "surname"],
            "constructors": ["constructor_ref", "name"],
            "circuits": ["circuit_ref", "name"],
            "races": ["year", "round", "circuit_ref"],
            "laps": ["year", "round", "lap", "driver_ref"]
        }
        
        # Detect entity type from columns
        entity = None
        for ent, cols in required_cols.items():
            if all(col in df.columns for col in cols[:2]):
                entity = ent
                break
        
        if not entity:
            raise ValueError(f"Could not determine entity type for columns: {list(df.columns)}")
        
        missing = [col for col in required_cols[entity] if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns for {entity}: {missing}")
        
        logger.info("schema_validation_passed", entity=entity, columns=list(df.columns))
        return True
    
    def ingest_season(
        self,
        season: int,
        entities: List[str] = None
    ) -> Dict[str, IngestionResult]:
       
        if entities is None:
            entities = ["circuits", "constructors", "drivers", "races", "results"]
        
        results = {}
        for entity in entities:
            try:
                result = self.ingest(season=season, entity=entity)
                results[entity] = result
                logger.info(f"ingested_{entity}", season=season, records=result.records_count)
            except Exception as e:
                logger.error(f"ingestion_failed_{entity}", season=season, error=str(e))
                raise
        
        return results