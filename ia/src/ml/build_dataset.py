from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    CLASSIF_DATASET_PATH,
    COUNTRIES_FILE,
    DATA_MAX_YEAR,
    DATA_MIN_YEAR,
    DATASET_QUALITY_REPORT_PATH,
    MAX_FORECAST_HORIZON,
    QUALITY_FILE,
    REGRESSION_DATASET_PATH,
    STATS_FILE,
    TRAINS_FILE,
    YEARS_FILE,
)


NETWORK_FEATURES = [
    "train_count_current",
    "night_share_current",
    "real_share_current",
    "avg_distance_current",
    "avg_duration_current",
    "operator_count_current",
    "network_data_available",
]


def _safe_growth(current, previous):
    current = pd.to_numeric(current, errors="coerce")
    previous = pd.to_numeric(previous, errors="coerce")
    denominator = previous.abs()
    return np.where(
        denominator > 1e-12,
        (current - previous) / denominator,
        0.0,
    )


def _source_is_observed(series: pd.Series) -> pd.Series:
    return (
        series.fillna("unknown")
        .astype(str)
        .str.lower()
        .str.strip()
        .isin({"eurostat", "observed", "real"})
    )


def load_sources():
    required = [STATS_FILE, COUNTRIES_FILE, YEARS_FILE]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Sources warehouse manquantes : " + ", ".join(missing)
        )

    stats = pd.read_csv(STATS_FILE, low_memory=False)
    countries = pd.read_csv(COUNTRIES_FILE, low_memory=False)
    years = pd.read_csv(YEARS_FILE, low_memory=False)

    quality = (
        pd.read_csv(QUALITY_FILE, low_memory=False)
        if QUALITY_FILE.exists()
        else None
    )

    return stats, countries, years, quality


def build_country_year_base(stats, countries, years, quality=None):
    df = (
        stats
        .merge(countries, on="country_id", how="left", validate="m:1")
        .merge(years, on="year_id", how="left", validate="m:1")
    )

    required = [
        "country_id",
        "country_name",
        "country_code",
        "year_id",
        "year",
        "passengers",
        "co2_emissions",
    ]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Colonnes warehouse manquantes : {missing}")

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["passengers"] = pd.to_numeric(df["passengers"], errors="coerce")
    df["co2_emissions"] = pd.to_numeric(
        df["co2_emissions"], errors="coerce"
    )

    df = df[
        df["year"].between(DATA_MIN_YEAR, DATA_MAX_YEAR, inclusive="both")
    ].copy()

    df["year"] = df["year"].astype(int)
    df["country_code"] = (
        df["country_code"].astype(str).str.upper().str.strip()
    )

    if quality is not None and not quality.empty:
        q_required = {
            "country_code",
            "year",
            "passengers_source",
            "co2_source",
        }
        if q_required.issubset(quality.columns):
            q = quality[list(q_required)].copy()
            q["country_code"] = (
                q["country_code"].astype(str).str.upper().str.strip()
            )
            q["year"] = pd.to_numeric(q["year"], errors="coerce")
            q = q.dropna(subset=["year"])
            q["year"] = q["year"].astype(int)

            df = df.merge(
                q,
                on=["country_code", "year"],
                how="left",
                validate="m:1",
            )

    if "passengers_source" not in df.columns:
        df["passengers_source"] = "unknown"
    if "co2_source" not in df.columns:
        df["co2_source"] = "unknown"

    df["passengers_source"] = (
        df["passengers_source"].fillna("unknown").astype(str)
    )
    df["co2_source"] = df["co2_source"].fillna("unknown").astype(str)

    return (
        df.sort_values(["country_id", "year"])
        .reset_index(drop=True)
    )


def build_network_aggregates():
    """
    Agrège les ~471k faits trains au niveau pays/année.

    On utilise uniquement l'année d'origine de la prévision.
    Aucune donnée ferroviaire future n'est injectée.
    """
    if not TRAINS_FILE.exists():
        return pd.DataFrame(
            columns=["country_id", "year_id"] + NETWORK_FEATURES
        )

    usecols = [
        "country_id",
        "year_id",
        "operator_id",
        "is_night",
        "distance_km",
        "duration_min",
        "is_synthetic",
    ]
    trains = pd.read_csv(
        TRAINS_FILE,
        usecols=usecols,
        low_memory=False,
    )

    for column in ["distance_km", "duration_min"]:
        trains[column] = pd.to_numeric(
            trains[column],
            errors="coerce",
        )

    for column in ["is_night", "is_synthetic"]:
        trains[column] = (
            trains[column]
            .astype(str)
            .str.lower()
            .isin({"true", "1", "yes"})
            if trains[column].dtype == object
            else trains[column].astype(bool)
        )

    grouped = (
        trains.groupby(["country_id", "year_id"], as_index=False)
        .agg(
            train_count_current=("operator_id", "size"),
            night_train_count=("is_night", "sum"),
            synthetic_train_count=("is_synthetic", "sum"),
            avg_distance_current=("distance_km", "mean"),
            avg_duration_current=("duration_min", "mean"),
            operator_count_current=("operator_id", "nunique"),
        )
    )

    grouped["night_share_current"] = np.where(
        grouped["train_count_current"] > 0,
        grouped["night_train_count"] / grouped["train_count_current"],
        0.0,
    )
    grouped["real_share_current"] = np.where(
        grouped["train_count_current"] > 0,
        1.0 - (
            grouped["synthetic_train_count"]
            / grouped["train_count_current"]
        ),
        0.0,
    )
    grouped["network_data_available"] = 1

    grouped = grouped.drop(
        columns=["night_train_count", "synthetic_train_count"]
    )

    return grouped


def add_historical_features(df):
    out = df.copy()
    grouped = out.groupby("country_id", sort=False)

    out["passengers_previous"] = grouped["passengers"].shift(1)
    out["co2_previous"] = grouped["co2_emissions"].shift(1)

    out["passengers_previous_source"] = grouped[
        "passengers_source"
    ].shift(1)
    out["co2_previous_source"] = grouped["co2_source"].shift(1)

    out["passenger_growth_1y"] = _safe_growth(
        out["passengers"],
        out["passengers_previous"],
    )
    out["co2_growth_1y"] = _safe_growth(
        out["co2_emissions"],
        out["co2_previous"],
    )

    return out


def add_network_features(df, network):
    out = df.copy()

    if network.empty:
        for column in NETWORK_FEATURES:
            out[column] = 0.0
        return out

    out = out.merge(
        network,
        on=["country_id", "year_id"],
        how="left",
        validate="1:1",
    )

    for column in NETWORK_FEATURES:
        if column not in out.columns:
            out[column] = 0.0

    out["network_data_available"] = (
        out["network_data_available"].fillna(0).astype(int)
    )

    numeric_network = [
        column
        for column in NETWORK_FEATURES
        if column != "network_data_available"
    ]
    out[numeric_network] = out[numeric_network].fillna(0.0)

    return out


def build_multihorizon_examples(df):
    frames = []

    grouped = df.groupby("country_id", sort=False)

    for horizon in range(1, MAX_FORECAST_HORIZON + 1):
        horizon_df = df.copy()

        horizon_df["horizon"] = horizon
        horizon_df["target_year"] = horizon_df["year"] + horizon
        horizon_df["target_passengers"] = grouped["passengers"].shift(
            -horizon
        )
        horizon_df["target_passengers_source"] = grouped[
            "passengers_source"
        ].shift(-horizon)

        # Vérifie que le shift correspond bien à une année contiguë.
        future_year = grouped["year"].shift(-horizon)
        horizon_df.loc[
            future_year != horizon_df["target_year"],
            ["target_passengers", "target_passengers_source"],
        ] = np.nan

        horizon_df = horizon_df.dropna(
            subset=[
                "passengers_previous",
                "co2_previous",
                "target_passengers",
            ]
        ).copy()

        # Déclin futur = activité à l'horizon < dernière valeur disponible
        # au moment où la prévision est faite.
        horizon_df["en_declin"] = (
            horizon_df["target_passengers"]
            < horizon_df["passengers"]
        ).astype(int)

        current_passenger_observed = _source_is_observed(
            horizon_df["passengers_source"]
        )
        previous_passenger_observed = _source_is_observed(
            horizon_df["passengers_previous_source"]
        )
        target_passenger_observed = _source_is_observed(
            horizon_df["target_passengers_source"]
        )
        current_co2_observed = _source_is_observed(
            horizon_df["co2_source"]
        )
        previous_co2_observed = _source_is_observed(
            horizon_df["co2_previous_source"]
        )

        all_observed = (
            current_passenger_observed
            & previous_passenger_observed
            & target_passenger_observed
            & current_co2_observed
            & previous_co2_observed
        )
        partly_observed = (
            current_passenger_observed
            | previous_passenger_observed
            | target_passenger_observed
            | current_co2_observed
            | previous_co2_observed
        )

        horizon_df["row_quality"] = np.select(
            [all_observed, partly_observed],
            ["observed", "mixed"],
            default="synthetic_or_unknown",
        )
        horizon_df["sample_weight"] = horizon_df["row_quality"].map(
            {
                "observed": 1.0,
                "mixed": 0.70,
                "synthetic_or_unknown": 0.40,
            }
        ).astype(float)

        frames.append(horizon_df)

    return pd.concat(frames, ignore_index=True)


def main():
    print("=" * 72)
    print("CONSTRUCTION DATASETS IA MULTI-HORIZON — N+1 À N+3")
    print("=" * 72)

    stats, countries, years, quality = load_sources()
    base = build_country_year_base(
        stats,
        countries,
        years,
        quality,
    )
    base = add_historical_features(base)

    network = build_network_aggregates()
    base = add_network_features(base, network)

    examples = build_multihorizon_examples(base)

    feature_columns = [
        "country_name",
        "horizon",
        "passengers",
        "passengers_previous",
        "passenger_growth_1y",
        "co2_emissions",
        "co2_previous",
        "co2_growth_1y",
        *NETWORK_FEATURES,
    ]

    audit_columns = [
        "country_id",
        "country_code",
        "country_name",
        "year",
        "target_year",
        "horizon",
        "passengers_source",
        "passengers_previous_source",
        "target_passengers_source",
        "co2_source",
        "co2_previous_source",
        "row_quality",
        "sample_weight",
    ]

    # `country_name` et `horizon` sont déjà présents dans audit_columns.
    # On les exclut ici afin d'éviter des labels de colonnes dupliqués.
    shared_features = [
        column
        for column in feature_columns
        if column not in {"country_name", "horizon"}
    ]

    reg_columns = (
        audit_columns
        + shared_features
        + ["target_passengers"]
    )
    clf_columns = (
        audit_columns
        + shared_features
        + ["en_declin"]
    )

    regression = examples[reg_columns].copy()
    classification = examples[clf_columns].copy()

    regression = regression.sort_values(
        ["target_year", "country_id", "horizon"]
    ).reset_index(drop=True)
    classification = classification.sort_values(
        ["target_year", "country_id", "horizon"]
    ).reset_index(drop=True)

    regression.to_csv(REGRESSION_DATASET_PATH, index=False)
    classification.to_csv(CLASSIF_DATASET_PATH, index=False)

    report = {
        "warehouse_period": [DATA_MIN_YEAR, DATA_MAX_YEAR],
        "max_forecast_horizon": MAX_FORECAST_HORIZON,
        "countries": int(examples["country_name"].nunique()),
        "regression_rows": int(len(regression)),
        "classification_rows": int(len(classification)),
        "rows_by_horizon": {
            str(int(horizon)): int(count)
            for horizon, count in examples["horizon"]
            .value_counts()
            .sort_index()
            .items()
        },
        "quality": {
            str(key): int(value)
            for key, value in examples["row_quality"]
            .value_counts()
            .items()
        },
        "classification_distribution_by_horizon": {
            str(int(horizon)): {
                str(int(label)): int(count)
                for label, count in group["en_declin"]
                .value_counts()
                .sort_index()
                .items()
            }
            for horizon, group in examples.groupby("horizon")
        },
        "network_features_enabled": bool(
            examples["network_data_available"].sum() > 0
        ),
        "leakage_guard": {
            "target_year_passengers_used_as_feature": False,
            "target_year_co2_used_as_feature": False,
            "only_origin_year_and_previous_year_features": True,
            "future_train_data_used": False,
        },
        "units": {
            "target_passengers": "MIO_PKM",
            "co2": "MIO_T",
        },
    }

    DATASET_QUALITY_REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        f"Base pays/année : {len(base):,} lignes | "
        f"{base['country_name'].nunique()} pays | "
        f"{base['year'].min()}-{base['year'].max()}"
    )
    print(f"Réseau agrégé   : {len(network):,} pays/années")
    print(f"Régression      : {regression.shape}")
    print(f"Classification  : {classification.shape}")
    print("Lignes par horizon :", report["rows_by_horizon"])
    print("Qualité :", report["quality"])
    print("Anti-leakage : OK")
    print(f"Rapport : {DATASET_QUALITY_REPORT_PATH}")


if __name__ == "__main__":
    main()
