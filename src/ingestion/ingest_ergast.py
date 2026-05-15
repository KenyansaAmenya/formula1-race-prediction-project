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
        ergast_config = self.config.ingestion.ergast
        self.base_url = ergast_config.base_url  # Use the new Jolpica URL
        self.timeout = ergast_config.timeout
        self.rate_limit = ergast_config.rate_limit
        self.retry_attempts = ergast_config.retry_attempts
        self.retry_backoff = ergast_config.retry_backoff
        self._last_request_time = 0.0
    
    def _rate_limited_request(self, url: str) -> Dict:
        # Rate limiting
        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / self.rate_limit
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        
        @retry(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(
                multiplier=self.retry_backoff,
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
    
    def _fetch_paginated(self, endpoint: str, limit: int = 100) -> List[Dict]:
        
        all_records = []
        offset = 0
        
        while True:
            url = f"{self.base_url}/{endpoint}.json?limit={limit}&offset={offset}"
            logger.debug("fetching_page", url=url, offset=offset)
            
            data = self._rate_limited_request(url)
            mr_data = data.get("MRData", {})
            total = int(mr_data.get("total", 0))
            
            # Handle different response structures
            if "RaceTable" in mr_data:
                # For race results, qualifying, etc.
                race_table = mr_data["RaceTable"]
                if "Races" in race_table and race_table["Races"]:
                    all_records.extend(race_table["Races"])
            elif "DriverTable" in mr_data:
                # For drivers
                driver_table = mr_data["DriverTable"]
                if "Drivers" in driver_table:
                    all_records.extend(driver_table["Drivers"])
            elif "ConstructorTable" in mr_data:
                # For constructors
                constructor_table = mr_data["ConstructorTable"]
                if "Constructors" in constructor_table:
                    all_records.extend(constructor_table["Constructors"])
            elif "CircuitTable" in mr_data:
                # For circuits
                circuit_table = mr_data["CircuitTable"]
                if "Circuits" in circuit_table:
                    all_records.extend(circuit_table["Circuits"])
            else:
                # Fallback to generic Table structure
                table_key = list(mr_data.get("Table", {}).keys())[0] if mr_data.get("Table") else None
                if table_key and mr_data["Table"][table_key]:
                    all_records.extend(mr_data["Table"][table_key])
                else:
                    break
            
            offset += limit
            if offset >= total:
                break
        
        return all_records
    
    def fetch_races(self, season: int) -> pd.DataFrame:
       
        url = f"{self.base_url}/{season}.json?limit=100&offset=0"
        logger.debug("fetching_races", url=url)

        data = self._rate_limited_request(url)
        mr_data = data.get("MRData", {})
        race_table = mr_data.get("RaceTable", {})
        races_data = race_table.get("Races", [])

        races = []

        for race in races_data:
            circuit = race.get("Circuit", {})
            location = circuit.get("Location", {})

            races.append(
                {
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
                    "altitude": location.get("alt"),
                }
            )

        logger.info("fetched_races", season=season, count=len(races))
        return pd.DataFrame(races)
    
    def fetch_results(self, season: int) -> pd.DataFrame:
        """Fetch race results for a specific season"""
        records = self._fetch_paginated(f"{season}/results")
        results = []
        
        for record in records:
            # Handle both direct race records and wrapped records
            if "Races" in record:
                races_list = record.get("Races", [])
            else:
                races_list = [record] if record.get("raceName") else []
            
            for race_info in races_list:
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
        
        logger.info("fetched_results", season=season, count=len(results))
        return pd.DataFrame(results)
    
    def fetch_drivers(self, season: int) -> pd.DataFrame:
        url = f"{self.base_url}/{season}/drivers.json?limit=100"
        logger.debug("fetching_drivers", url=url)
        
        data = self._rate_limited_request(url)
        mr_data = data.get("MRData", {})
        driver_table = mr_data.get("DriverTable", {})
        drivers_data = driver_table.get("Drivers", [])
        
        drivers = []
        for driver in drivers_data:
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
        
        logger.info("fetched_drivers", season=season, count=len(drivers))
        return pd.DataFrame(drivers)
    
    def fetch_constructors(self, season: int) -> pd.DataFrame:
        url = f"{self.base_url}/{season}/constructors.json?limit=100"
        logger.debug("fetching_constructors", url=url)
        
        data = self._rate_limited_request(url)
        mr_data = data.get("MRData", {})
        constructor_table = mr_data.get("ConstructorTable", {})
        constructors_data = constructor_table.get("Constructors", [])
        
        constructors = []
        for constructor in constructors_data:
            constructors.append({
                "constructor_ref": constructor.get("constructorId"),
                "name": constructor.get("name"),
                "nationality": constructor.get("nationality"),
                "url": constructor.get("url")
            })
        
        logger.info("fetched_constructors", season=season, count=len(constructors))
        return pd.DataFrame(constructors)
    
    def fetch_circuits(self, season: int) -> pd.DataFrame:
        # First get races to know which circuits are used
        races_df = self.fetch_races(season)
        if races_df.empty:
            return pd.DataFrame()
        
        circuits = []
        for _, race in races_df.iterrows():
            circuits.append({
                "circuit_ref": race.get("circuit_ref"),
                "name": race.get("circuit_name"),
                "location": race.get("location"),
                "country": race.get("country"),
                "latitude": race.get("latitude"),
                "longitude": race.get("longitude"),
                "altitude": race.get("altitude")
            })
        
        # Remove duplicates
        circuits_df = pd.DataFrame(circuits).drop_duplicates(subset=["circuit_ref"])
        logger.info("fetched_circuits", season=season, count=len(circuits_df))
        return circuits_df
    
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
    
    def fetch(self, season: int = 2025, **kwargs) -> pd.DataFrame:
        entity = kwargs.get("entity", "results")
        
        fetch_methods = {
            "results": self.fetch_results,
            "drivers": self.fetch_drivers,
            "constructors": self.fetch_constructors,
            "circuits": self.fetch_circuits,
            "races": self.fetch_races,
            "laps": lambda: self.fetch_lap_times(season, kwargs.get("round", 1))
        }
        
        method = fetch_methods.get(entity, self.fetch_results)
        return method(season)

    def _time_to_milliseconds(self, time_str: Optional[str]) -> Optional[int]:
        if not time_str:
            return None
        
        try:
            # Handle format "1:32.456" or "92.456"
            if ':' in time_str:
                minutes, seconds = time_str.split(':')
                total_seconds = float(minutes) * 60 + float(seconds)
            else:
                total_seconds = float(time_str)
        
            return int(total_seconds * 1000)
        except (ValueError, AttributeError):
            logger.warning("invalid_time_format", time_str=time_str)
            return None
    
    def validate_schema(self, df: pd.DataFrame) -> bool:
        if df.empty:
            logger.warning(
                "empty_dataframe_validation",
                source=self.source_name,
            )
            return True

        required_cols = {
            "results": ["year", "round", "driver_ref", "constructor_ref"],
            "drivers": ["driver_ref", "forename", "surname"],
            "constructors": ["constructor_ref", "name"],
            "circuits": ["circuit_ref", "name"],
            "races": ["year", "round", "circuit_ref"],
            "laps": ["year", "round", "lap", "driver_ref"],
        }

        # Detect entity type from columns
        entity = None

        for ent, cols in required_cols.items():
            if all(col in df.columns for col in cols):
                entity = ent
                break

        # If not found with full match, try to infer from column names
        if not entity:
            if "driver_ref" in df.columns and "constructor_ref" in df.columns:
                entity = "results"
            elif "driver_ref" in df.columns and "forename" in df.columns:
                entity = "drivers"
            elif "constructor_ref" in df.columns and "name" in df.columns:
                entity = "constructors"
            elif "circuit_ref" in df.columns and "name" in df.columns:
                entity = "circuits"
            elif "circuit_ref" in df.columns and "race_name" in df.columns:
                entity = "races"
            elif "year" in df.columns and "round" in df.columns and "circuit_ref" in df.columns:
                entity = "races"
            else:
                raise ValueError(
                    f"Could not determine entity type for columns: "
                    f"{list(df.columns)}"
                )

        missing = [col for col in required_cols[entity] if col not in df.columns]

        if missing:
            raise ValueError(
                f"Missing required columns for {entity}: {missing}"
            )

        logger.info(
            "schema_validation_passed",
            entity=entity,
            columns=list(df.columns),
        )
        return True
    
    def ingest_season(
        self,
        season: int,
        entities: List[str] = None
    ) -> Dict[str, IngestionResult]:
        if entities is None:
            entities = ["races", "drivers", "constructors", "circuits", "results"]
        
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