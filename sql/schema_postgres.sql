CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- CORE DIMENSION TABLES

CREATE TABLE IF NOT EXISTS circuits (
    circuit_id SERIAL PRIMARY KEY,
    circuit_ref VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(100),
    country VARCHAR(100),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    altitude INT,
    url VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_circuits_country ON circuits(country);
CREATE INDEX idx_circuits_location ON circuits(location);


CREATE TABLE IF NOT EXISTS constructors (
    constructor_id SERIAL PRIMARY KEY,
    constructor_ref VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    nationality VARCHAR(50),
    url VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_constructors_nationality ON constructors(nationality);


CREATE TABLE IF NOT EXISTS drivers (
    driver_id SERIAL PRIMARY KEY,
    driver_ref VARCHAR(50) UNIQUE NOT NULL,
    number INT,
    code VARCHAR(3),
    forename VARCHAR(50) NOT NULL,
    surname VARCHAR(50) NOT NULL,
    dob DATE,
    nationality VARCHAR(50),
    url VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_drivers_nationality ON drivers(nationality);
CREATE INDEX idx_drivers_code ON drivers(code);

-- EVENT TABLES

CREATE TABLE IF NOT EXISTS races (
    race_id SERIAL PRIMARY KEY,
    year INT NOT NULL,
    round INT NOT NULL,
    circuit_id INT NOT NULL REFERENCES circuits(circuit_id),
    name VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    time TIME,
    url VARCHAR(255),
    fp1_date DATE,
    fp1_time TIME,
    fp2_date DATE,
    fp2_time TIME,
    fp3_date DATE,
    fp3_time TIME,
    quali_date DATE,
    quali_time TIME,
    sprint_date DATE,
    sprint_time TIME,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(year, round)
);

CREATE INDEX idx_races_year ON races(year);
CREATE INDEX idx_races_year_round ON races(year, round);
CREATE INDEX idx_races_circuit ON races(circuit_id);
CREATE INDEX idx_races_date ON races(date);


CREATE TABLE IF NOT EXISTS results (
    result_id SERIAL PRIMARY KEY,
    race_id INT NOT NULL REFERENCES races(race_id),
    driver_id INT NOT NULL REFERENCES drivers(driver_id),
    constructor_id INT NOT NULL REFERENCES constructors(constructor_id),
    number INT,
    grid INT,
    position INT,
    position_text VARCHAR(10),
    position_order INT,
    points DECIMAL(5, 2),
    laps INT,
    time VARCHAR(50),
    milliseconds INT,
    fastest_lap INT,
    rank INT,
    fastest_lap_time VARCHAR(50),
    fastest_lap_speed DECIMAL(7, 3),
    status_id INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_results_race ON results(race_id);
CREATE INDEX idx_results_driver ON results(driver_id);
CREATE INDEX idx_results_constructor ON results(constructor_id);
CREATE INDEX idx_results_year_round ON results(race_id, position_order);
CREATE INDEX idx_results_points ON results(points);


CREATE TABLE IF NOT EXISTS lap_times (
    lap_time_id BIGSERIAL PRIMARY KEY,
    race_id INT NOT NULL REFERENCES races(race_id),
    driver_id INT NOT NULL REFERENCES drivers(driver_id),
    lap INT NOT NULL,
    position INT,
    time VARCHAR(50),
    milliseconds INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_lap_times_race_driver ON lap_times(race_id, driver_id);
CREATE INDEX idx_lap_times_race_lap ON lap_times(race_id, lap);
CREATE INDEX idx_lap_times_milliseconds ON lap_times(milliseconds);


CREATE TABLE IF NOT EXISTS pit_stops (
    pit_stop_id SERIAL PRIMARY KEY,
    race_id INT NOT NULL REFERENCES races(race_id),
    driver_id INT NOT NULL REFERENCES drivers(driver_id),
    stop INT NOT NULL,
    lap INT,
    time TIME,
    duration DECIMAL(8, 3),
    milliseconds INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_pit_stops_race ON pit_stops(race_id, driver_id);


CREATE TABLE IF NOT EXISTS qualifying (
    qualify_id SERIAL PRIMARY KEY,
    race_id INT NOT NULL REFERENCES races(race_id),
    driver_id INT NOT NULL REFERENCES drivers(driver_id),
    constructor_id INT NOT NULL REFERENCES constructors(constructor_id),
    number INT,
    position INT,
    q1 VARCHAR(50),
    q2 VARCHAR(50),
    q3 VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_qualifying_race ON qualifying(race_id);
CREATE INDEX idx_qualifying_position ON qualifying(position);

-- TELEMETRY SUMMARY (Aggregated, not raw telemetry)

CREATE TABLE IF NOT EXISTS telemetry_summary (
    telemetry_id BIGSERIAL PRIMARY KEY,
    race_id INT NOT NULL REFERENCES races(race_id),
    driver_id INT NOT NULL REFERENCES drivers(driver_id),
    lap INT NOT NULL,
    sector1_time DECIMAL(10, 3),
    sector2_time DECIMAL(10, 3),
    sector3_time DECIMAL(10, 3),
    speed_trap DECIMAL(6, 2),
    drs_usage_pct DECIMAL(5, 2),
    throttle_avg DECIMAL(5, 2),
    brake_events INT,
    gear_changes INT,
    tyre_compound VARCHAR(20),
    tyre_age INT,
    air_temp DECIMAL(4, 1),
    track_temp DECIMAL(4, 1),
    humidity DECIMAL(5, 2),
    wind_speed DECIMAL(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_telemetry_race_driver ON telemetry_summary(race_id, driver_id);
CREATE INDEX idx_telemetry_lap ON telemetry_summary(race_id, lap);

-- FEATURE ENGINEERING TABLES

CREATE TABLE IF NOT EXISTS driver_race_features (
    feature_id BIGSERIAL PRIMARY KEY,
    race_id INT NOT NULL REFERENCES races(race_id),
    driver_id INT NOT NULL REFERENCES drivers(driver_id),
    
    -- Rolling Performance Metrics
    rolling_avg_points_5r DECIMAL(5, 2),
    rolling_avg_finish_pos_5r DECIMAL(5, 2),
    rolling_points_trend DECIMAL(5, 2),
    
    -- Recent Form (Last 3 races)
    recent_form_points DECIMAL(5, 2),
    recent_form_finish_pos DECIMAL(5, 2),
    recent_form_quali_pos DECIMAL(5, 2),
    
    -- Constructor Performance
    constructor_avg_points_5r DECIMAL(5, 2),
    constructor_reliability_score DECIMAL(5, 2),
    
    -- Track Specific
    track_avg_points DECIMAL(5, 2),
    track_avg_finish_pos DECIMAL(5, 2),
    track_best_finish_pos INT,
    track_experience_races INT,
    
    -- Lap Pace Metrics
    lap_consistency_std DECIMAL(8, 3),
    avg_lap_time_ms INT,
    fastest_lap_time_ms INT,
    
    -- DNF / Reliability
    dnf_probability DECIMAL(5, 4),
    consecutive_finishes INT,
    mechanical_dnf_rate DECIMAL(5, 4),
    
    -- Qualifying Impact
    quali_position INT,
    quali_gap_to_pole_ms INT,
    grid_position_gain_potential DECIMAL(5, 2),
    
    -- Weather Adaptability
    wet_race_experience INT,
    wet_race_avg_points DECIMAL(5, 2),
    
    -- Composite Indices
    driver_performance_index DECIMAL(8, 4),
    constructor_performance_index DECIMAL(8, 4),
    overall_strength_index DECIMAL(8, 4),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(race_id, driver_id)
);

CREATE INDEX idx_features_race ON driver_race_features(race_id);
CREATE INDEX idx_features_driver ON driver_race_features(driver_id);
CREATE INDEX idx_features_overall ON driver_race_features(overall_strength_index);
CREATE INDEX idx_features_composite ON driver_race_features(
    driver_performance_index, 
    constructor_performance_index
);

-- AUDIT AND LINEAGE TABLES

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pipeline_name VARCHAR(100) NOT NULL,
    run_type VARCHAR(50) NOT NULL,  -- 'ingestion', 'processing', 'feature_engineering'
    status VARCHAR(20) NOT NULL,    -- 'running', 'completed', 'failed'
    source VARCHAR(50),
    records_processed INT DEFAULT 0,
    records_failed INT DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB
);

CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX idx_pipeline_runs_started ON pipeline_runs(started_at);

-- ROW LEVEL SECURITY POLICIES

-- Enable RLS on feature tables (data access control)
ALTER TABLE driver_race_features ENABLE ROW LEVEL SECURITY;

-- Public access policy (read-only, limited to published data)
CREATE POLICY driver_race_features_public_read ON driver_race_features
    FOR SELECT
    USING (true);  -- Simplified; production would check user context

-- Service role policy (full access)
CREATE POLICY driver_race_features_service_role ON driver_race_features
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- TRIGGERS FOR AUDIT TIMESTAMPS

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_circuits_updated_at BEFORE UPDATE ON circuits
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_constructors_updated_at BEFORE UPDATE ON constructors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_drivers_updated_at BEFORE UPDATE ON drivers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_races_updated_at BEFORE UPDATE ON races
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_results_updated_at BEFORE UPDATE ON results
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lap_times_updated_at BEFORE UPDATE ON lap_times
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_features_updated_at BEFORE UPDATE ON driver_race_features
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ANALYTICAL VIEWS

CREATE OR REPLACE VIEW v_driver_standings AS
SELECT 
    r.year,
    d.driver_id,
    d.forename || ' ' || d.surname as driver_name,
    c.name as constructor_name,
    SUM(res.points) as total_points,
    COUNT(CASE WHEN res.position = 1 THEN 1 END) as wins,
    COUNT(CASE WHEN res.position <= 3 THEN 1 END) as podiums,
    AVG(res.position_order) as avg_finish_position,
    COUNT(res.result_id) as races_completed
FROM results res
JOIN races r ON res.race_id = r.race_id
JOIN drivers d ON res.driver_id = d.driver_id
JOIN constructors c ON res.constructor_id = c.constructor_id
GROUP BY r.year, d.driver_id, d.forename, d.surname, c.name;

CREATE OR REPLACE VIEW v_constructor_standings AS
SELECT 
    r.year,
    c.constructor_id,
    c.name as constructor_name,
    SUM(res.points) as total_points,
    COUNT(CASE WHEN res.position = 1 THEN 1 END) as wins,
    COUNT(DISTINCT res.driver_id) as drivers_used
FROM results res
JOIN races r ON res.race_id = r.race_id
JOIN constructors c ON res.constructor_id = c.constructor_id
GROUP BY r.year, c.constructor_id, c.name;