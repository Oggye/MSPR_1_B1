-- Démonstration C2 : SQL relationnel sur le warehouse PostgreSQL existant.
-- Lecture seule : aucune table ni vue n'est créée ou modifiée.

-- 1. Nombre de trains par pays.
SELECT
    c.country_code,
    c.country_name,
    COUNT(f.fact_id) AS total_trains
FROM dim_countries AS c
LEFT JOIN facts_night_trains AS f ON f.country_id = c.country_id
GROUP BY c.country_code, c.country_name
ORDER BY total_trains DESC, c.country_code;

-- 2. Moyennes passagers et CO2 par pays via la vue existante.
SELECT
    country_code,
    country_name,
    avg_passengers,
    avg_co2_emissions,
    avg_co2_per_passenger
FROM dashboard_metrics
ORDER BY avg_passengers DESC NULLS LAST, country_code;

-- 3. Répartition jour/nuit et activité par opérateur via la vue existante.
SELECT
    operator_name,
    nb_trains,
    nb_trains_jour,
    nb_trains_nuit,
    distance_totale_km,
    duree_moyenne_min
FROM operator_dashboard
ORDER BY nb_trains DESC, operator_name
LIMIT 20;
