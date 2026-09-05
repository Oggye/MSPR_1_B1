"""Démonstration C2 : analyses Spark SQL sur les GTFS européens d'ObRail."""

import os
import sys
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import DataFrame, SparkSession, functions as F


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.getenv("GTFS_DATA_ROOT", PROJECT_ROOT / "data" / "raw"))
OUTPUT_ROOT = Path(os.getenv("BIGDATA_OUTPUT_ROOT", PROJECT_ROOT / "data" / "bigdata"))

GTFS_SOURCES = {
    "FR": DATA_ROOT / "gtfs_fr",
    "DE": DATA_ROOT / "gtfs_de",
    "CH": DATA_ROOT / "gtfs_ch",
    "ES": DATA_ROOT / "gtfs_es",
    "LU": DATA_ROOT / "gtfs_lu",
}

REQUIRED_COLUMNS = {
    "stop_times": ("trip_id", "stop_id"),
    "trips": ("trip_id", "route_id"),
    "routes": ("route_id", "route_short_name", "route_long_name"),
    "stops": ("stop_id", "stop_name"),
}


def print_banner(title: str) -> None:
    print("=" * 60)
    print(title)
    print("=" * 60)


def selected_sources() -> dict[str, Path]:
    requested = os.getenv("GTFS_COUNTRIES", "").strip()
    if not requested:
        return GTFS_SOURCES

    codes = [code.strip().upper() for code in requested.split(",") if code.strip()]
    unknown = sorted(set(codes) - set(GTFS_SOURCES))
    if unknown:
        raise ValueError(f"Pays GTFS inconnus : {', '.join(unknown)}")
    return {code: GTFS_SOURCES[code] for code in codes}


def find_available_sources() -> dict[str, Path]:
    available = {}
    expected_files = [f"{dataset}.csv" for dataset in REQUIRED_COLUMNS]

    for country, source in selected_sources().items():
        missing = [name for name in expected_files if not (source / name).is_file()]
        if missing:
            print(
                f"WARNING : dataset GTFS {country} incomplet "
                f"({', '.join(missing)} absent(s)), source ignorée."
            )
            continue
        print(f"{country} : trouvé ({source})")
        available[country] = source

    if not available:
        raise RuntimeError(f"Aucun dataset GTFS complet disponible sous {DATA_ROOT}.")
    return available


def load_gtfs_dataset(
    spark: SparkSession,
    country: str,
    source: Path,
    dataset: str,
) -> DataFrame:
    csv_path = source / f"{dataset}.csv"
    frame = spark.read.option("header", True).option("encoding", "UTF-8").csv(str(csv_path))
    frame = frame.toDF(*[column.strip().lstrip("\ufeff") for column in frame.columns])

    required = REQUIRED_COLUMNS[dataset]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(
            f"Schéma GTFS invalide pour {country}/{csv_path.name} : "
            f"colonne(s) manquante(s) {', '.join(missing)}."
        )

    return frame.select(
        *[F.col(column).cast("string").alias(column) for column in required],
        F.lit(country).alias("country"),
    )


def build_european_datasets(
    spark: SparkSession,
    sources: dict[str, Path],
) -> dict[str, DataFrame]:
    datasets = {}
    for dataset in REQUIRED_COLUMNS:
        country_frames = []
        for country, source in sources.items():
            country_frames.append(load_gtfs_dataset(spark, country, source, dataset))
            print(f"{country} {dataset}.csv : chargé")

        european_frame = country_frames[0]
        for country_frame in country_frames[1:]:
            european_frame = european_frame.unionByName(country_frame)
        datasets[dataset] = european_frame

    return datasets


def register_sql_views(datasets: dict[str, DataFrame]) -> None:
    for name, frame in datasets.items():
        if name == "routes":
            frame = frame.dropDuplicates(["country", "route_id"])
            datasets[name] = frame
        frame.createOrReplaceTempView(name)
        print(f"✓ {name}")


def run_sql_queries(spark: SparkSession) -> dict[str, DataFrame]:
    volume_by_country = spark.sql(
        """
        SELECT
            country,
            COUNT(*) AS total_stop_events,
            COUNT(DISTINCT trip_id) AS total_trips
        FROM stop_times
        GROUP BY country
        ORDER BY total_stop_events DESC
        """
    )

    stops_per_trip = spark.sql(
        """
        SELECT
            country,
            trip_id,
            COUNT(*) AS number_of_stops
        FROM stop_times
        GROUP BY country, trip_id
        ORDER BY number_of_stops DESC
        """
    )

    route_activity = spark.sql(
        """
        WITH route_names AS (
            SELECT
                country,
                route_id,
                MAX(COALESCE(
                    NULLIF(TRIM(route_short_name), ''),
                    NULLIF(TRIM(route_long_name), ''),
                    route_id
                )) AS route_name
            FROM routes
            GROUP BY country, route_id
        )
        SELECT
            t.country,
            t.route_id,
            MAX(r.route_name) AS route_name,
            COUNT(DISTINCT t.trip_id) AS total_trips,
            COUNT(st.stop_id) AS total_stop_events
        FROM trips t
        JOIN stop_times st
          ON t.country = st.country
         AND t.trip_id = st.trip_id
        LEFT JOIN route_names r
          ON t.country = r.country
         AND t.route_id = r.route_id
        GROUP BY t.country, t.route_id
        ORDER BY total_trips DESC, total_stop_events DESC
        """
    )

    print("\n--- Volume par pays ---")
    volume_by_country.show(truncate=False)
    print("\n--- Trajets comportant le plus d'arrêts (top 20) ---")
    stops_per_trip.show(20, truncate=False)
    print("\n--- Routes les plus actives (top 20) ---")
    route_activity.show(20, truncate=False)

    return {
        "volume_by_country": volume_by_country,
        "stops_per_trip": stops_per_trip,
        "route_activity": route_activity,
    }


def export_results(route_activity: DataFrame) -> Path:
    output_path = OUTPUT_ROOT / "gtfs_metrics"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    route_activity.write.mode("overwrite").partitionBy("country").parquet(str(output_path))
    return output_path


def main() -> int:
    spark = None
    try:
        print_banner("OBRAIL EUROPE — C2 BIG DATA / SPARK SQL")
        print("\n[1/5] Recherche des datasets GTFS")
        sources = find_available_sources()

        print("\n[2/5] Lecture avec Apache Spark")
        spark = (
            SparkSession.builder.appName("ObRail-C2-BigData")
            .master(os.getenv("SPARK_MASTER", "local[*]"))
            .config("spark.sql.shuffle.partitions", os.getenv("SPARK_SHUFFLE_PARTITIONS", "16"))
            .config("spark.ui.enabled", "false")
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("WARN")
        datasets = build_european_datasets(spark, sources)
        datasets["stop_times"] = datasets["stop_times"].persist(StorageLevel.DISK_ONLY)
        print(f"Total stop_times : {datasets['stop_times'].count():,} lignes")

        print("\n[3/5] Création des vues Spark SQL")
        register_sql_views(datasets)

        print("\n[4/5] Exécution des requêtes Spark SQL")
        results = run_sql_queries(spark)

        print("\n[5/5] Export Parquet")
        output_path = export_results(results["route_activity"])
        print(f"✓ {output_path}")
        print_banner("TRAITEMENT BIG DATA TERMINÉ")
        return 0
    except Exception as exc:
        print(f"ERROR : {exc}", file=sys.stderr)
        return 1
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    sys.exit(main())
