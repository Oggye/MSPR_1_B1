-- ObRail Europe - schéma compatible avec la transformation améliorée.
DROP VIEW IF EXISTS dashboard_metrics CASCADE;
DROP VIEW IF EXISTS operator_dashboard CASCADE;

DROP TABLE IF EXISTS facts_night_trains CASCADE;
DROP TABLE IF EXISTS facts_country_stats CASCADE;
DROP TABLE IF EXISTS dim_stops CASCADE;
DROP TABLE IF EXISTS dim_operators CASCADE;
DROP TABLE IF EXISTS dim_years CASCADE;
DROP TABLE IF EXISTS dim_countries CASCADE;

CREATE TABLE dim_countries (
    country_id INTEGER PRIMARY KEY,
    country_code VARCHAR(10) UNIQUE NOT NULL,
    country_name VARCHAR(100) NOT NULL
);
CREATE TABLE dim_years (
    year_id INTEGER PRIMARY KEY,
    year INTEGER NOT NULL,
    is_after_2010 BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE dim_operators (
    operator_id INTEGER PRIMARY KEY,
    operator_name VARCHAR(200) NOT NULL
);
CREATE TABLE dim_stops (
    stop_id_dim BIGINT PRIMARY KEY,
    stop_name VARCHAR(250) NOT NULL,
    stop_lat NUMERIC(10,6),
    stop_lon NUMERIC(10,6),
    stop_id VARCHAR(150),
    source_country VARCHAR(3)
);

CREATE TABLE facts_night_trains (
    fact_id BIGINT PRIMARY KEY,
    route_id VARCHAR(150) NOT NULL,
    train VARCHAR(300) NOT NULL,
    -- Alias de transition : l'API actuelle peut encore lire night_train.
    night_train VARCHAR(300) GENERATED ALWAYS AS (train) STORED,
    country_id INTEGER NOT NULL REFERENCES dim_countries(country_id),
    year_id INTEGER NOT NULL REFERENCES dim_years(year_id),
    operator_id INTEGER NOT NULL REFERENCES dim_operators(operator_id),
    is_night BOOLEAN NOT NULL DEFAULT FALSE,
    distance_km NUMERIC(12,2) DEFAULT 0,
    duration_min NUMERIC(12,2) DEFAULT 0,
    is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
    data_source VARCHAR(80) NOT NULL DEFAULT 'unknown'
);
CREATE INDEX idx_facts_trains_country ON facts_night_trains(country_id);
CREATE INDEX idx_facts_trains_year ON facts_night_trains(year_id);
CREATE INDEX idx_facts_trains_operator ON facts_night_trains(operator_id);
CREATE INDEX idx_facts_trains_night ON facts_night_trains(is_night);
CREATE INDEX idx_facts_trains_synthetic ON facts_night_trains(is_synthetic);

CREATE TABLE facts_country_stats (
    stat_id BIGINT PRIMARY KEY,
    country_id INTEGER NOT NULL REFERENCES dim_countries(country_id),
    year_id INTEGER NOT NULL REFERENCES dim_years(year_id),
    passengers NUMERIC(20,4) NOT NULL,
    co2_emissions NUMERIC(20,6) NOT NULL,
    co2_per_passenger NUMERIC(20,8) NOT NULL
);

CREATE VIEW dashboard_metrics AS
SELECT c.country_id,c.country_name,c.country_code,
       AVG(s.passengers)::NUMERIC(20,2) AS avg_passengers,
       AVG(s.co2_emissions)::NUMERIC(20,4) AS avg_co2_emissions,
       AVG(s.co2_per_passenger)::NUMERIC(20,6) AS avg_co2_per_passenger
FROM facts_country_stats s
JOIN dim_countries c ON s.country_id=c.country_id
GROUP BY c.country_id,c.country_name,c.country_code;

CREATE VIEW operator_dashboard AS
SELECT o.operator_id,o.operator_name,COUNT(f.fact_id) AS nb_trains,
       SUM(CASE WHEN f.is_night THEN 1 ELSE 0 END) AS nb_trains_nuit,
       SUM(CASE WHEN NOT f.is_night THEN 1 ELSE 0 END) AS nb_trains_jour,
       COALESCE(SUM(f.distance_km),0)::NUMERIC(20,2) AS distance_totale_km,
       COALESCE(AVG(f.duration_min),0)::NUMERIC(12,2) AS duree_moyenne_min
FROM dim_operators o
LEFT JOIN facts_night_trains f ON o.operator_id=f.operator_id
GROUP BY o.operator_id,o.operator_name
ORDER BY nb_trains DESC;
