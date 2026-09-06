import pandas as pd

from transform.enrichment import (
    ANALYSIS_YEARS,
    SYNTHETIC_CALIBRATION_CAP,
    _build_synthetic_plan,
    _calibrate_synthetic_targets,
    _complete_country_stats,
    _continuous_activity_series,
    _generate_synthetic_chunk,
    _lookup_synthetic_coord,
    _normalise_synthetic_stop,
    _prepare_fact_chunk,
    _synthetic_route_distances,
    load_country_reference,
)
from transform.eurostat import _quarterly_to_annual
from transform.gtfs import _prepare_calendar
from transform.oecd_itf import transform_oecd_itf
from transform.unece import transform_unece


def test_calendar_keeps_only_service_years_in_warehouse_period():
    calendar = pd.DataFrame(
        [
            {"service_id": "old", "date": "20241231"},
            {"service_id": "mixed", "date": "20241231"},
            {"service_id": "mixed", "date": "20250101"},
            {"service_id": "future", "date": "20260101"},
        ]
    )

    _, service_years, default_year = _prepare_calendar(calendar)

    assert service_years == {"old": 2024, "mixed": 2024}
    assert default_year == 2024
    assert "future" not in service_years


def test_fact_preparation_drops_out_of_period_years_without_relabeling():
    chunk = pd.DataFrame(
        [
            {"route_id": "valid", "train": "Valid", "country_code": "UK", "year": 2024},
            {"route_id": "future", "train": "Future", "country_code": "EL", "year": 2026},
        ]
    )
    country_ids = {"GB": 1, "GR": 2, "UNKNOWN": 3}
    year_ids = {year: index + 1 for index, year in enumerate(ANALYSIS_YEARS)}

    result = _prepare_fact_chunk(chunk, 1, country_ids, year_ids, {"Unknown Operator": 0}, {})

    assert len(result) == 1
    assert result.iloc[0]["route_id"] == "valid"
    assert result.iloc[0]["country_id"] == country_ids["GB"]
    assert result.iloc[0]["year_id"] == year_ids[2024]


def test_country_reference_uses_canonical_eurostat_codes():
    codes = set(load_country_reference()["country_code"])

    assert "GB" in codes and "UK" not in codes
    assert "GR" in codes and "EL" not in codes


def test_synthetic_calibration_is_bounded_when_gtfs_coverage_shrinks():
    reference = load_country_reference()
    targets = _calibrate_synthetic_targets(reference, {"AT": 20576, "BE": 22756})
    score = reference.set_index("country_code").loc["DE", "rail_score"]
    expected_upper_bound = round(SYNTHETIC_CALIBRATION_CAP * score * 0.20)

    assert targets["DE"] <= expected_upper_bound


def test_synthetic_plan_uses_official_hierarchy_and_keeps_structural_zeros():
    reference = pd.DataFrame([
        {"country_code": "GT", "rail_network_km": 100, "rail_score": 1.0},
        {"country_code": "TR", "rail_network_km": 100, "rail_score": 1.0},
        {"country_code": "PK", "rail_network_km": 200, "rail_score": 0.8},
        {"country_code": "NW", "rail_network_km": 300, "rail_score": 0.6},
        {"country_code": "SC", "rail_network_km": 0, "rail_score": 0.4},
        {"country_code": "CY", "rail_network_km": 0, "rail_score": 0.2},
        {"country_code": "MT", "rail_network_km": 0, "rail_score": 0.2},
    ])
    traffic = pd.DataFrame([
        {"country_code": "TR", "year": 2024, "traffic": 1000, "traffic_unit": "THS_TRKM"},
    ])
    passengers = pd.DataFrame([
        {"country_code": "TR", "year": 2024, "passengers": 10, "passenger_metric": "MIO_PKM"},
        {"country_code": "PK", "year": 2024, "passengers": 20, "passenger_metric": "MIO_PKM"},
    ])

    targets, factors, sources, budget = _build_synthetic_plan(
        reference, {"GT": 1000}, traffic, passengers
    )

    assert sources == {
        "TR": "train_km", "PK": "passenger_km",
        "NW": "rail_network_km", "SC": "rail_score",
    }
    assert targets["GT"] == targets["CY"] == targets["MT"] == 0
    assert sum(targets.values()) == budget
    assert min(targets.values()) >= 0
    assert all(factors[(country, 2024)] >= 0 for country in sources)


def test_activity_series_interpolates_only_short_gaps_and_preserves_covid():
    short = _continuous_activity_series({2017: 100.0, 2019: 120.0})
    assert short[2018] == 110.0

    profile = {year: 100.0 for year in ANALYSIS_YEARS}
    profile[2020] = 40.0
    long_gap = _continuous_activity_series({2013: 100.0, 2023: 100.0}, profile)
    assert long_gap[2020] == 40.0
    assert long_gap[2020] != 100.0

    observed_covid = _continuous_activity_series({
        2019: 100.0, 2020: 55.0, 2021: 60.0, 2022: 80.0, 2023: 95.0,
    })
    assert [observed_covid[year] for year in (2020, 2021, 2022)] == [55.0, 60.0, 80.0]


def test_synthetic_distances_are_bounded_and_name_matching_is_safe():
    assert _normalise_synthetic_stop("Wrocław") == "wroclaw"
    assert _lookup_synthetic_coord("Wrocław") is not None
    assert _lookup_synthetic_coord("Hel") is None

    distances = _synthetic_route_distances(
        ["London - Manchester", "London - Birmingham"],
        ["London - Edinburgh", "London - Aberdeen"],
    )
    assert distances[(False, "London - Birmingham")] < 1200
    assert distances[(True, "London - Aberdeen")] < 1200
    assert all(0 < distance <= 1200 for distance in distances.values())


def test_generated_synthetic_chunk_keeps_provenance_and_day_majority():
    generated = _generate_synthetic_chunk("FR", 2024, 100, 0.10, "SNCF")

    assert generated["year"].eq(2024).all()
    assert generated["is_synthetic"].all()
    assert generated["data_source"].eq("synthetic_reference").all()
    assert generated["is_night"].sum() < (~generated["is_night"]).sum()
    assert generated["distance_km"].between(0, 1200, inclusive="right").all()


def test_country_stats_apply_official_fallback_order_and_interpolation():
    reference = load_country_reference()
    reference = reference[reference["country_code"].isin(["BE", "CY"])].copy()
    annual = pd.DataFrame([
        {"country_code": "BE", "year": 2010, "passengers": 100.0, "passenger_metric": "MIO_PKM", "data_source": "eurostat"},
        {"country_code": "BE", "year": 2011, "passengers": 999.0, "passenger_metric": "MIO_PKM", "data_source": "eurostat_quarterly"},
    ])
    unece = pd.DataFrame([
        {"country_code": "BE", "year": 2011, "passengers": 110.0, "passenger_metric": "MIO_PKM", "data_source": "unece"},
        {"country_code": "BE", "year": 2012, "passengers": 120.0, "passenger_metric": "MIO_PKM", "data_source": "unece"},
    ])
    oecd = pd.DataFrame([
        {"country_code": "BE", "year": 2012, "passengers": 888.0, "passenger_metric": "MIO_PKM", "data_source": "oecd_itf"},
        {"country_code": "BE", "year": 2014, "passengers": 140.0, "passenger_metric": "MIO_PKM", "data_source": "oecd_itf"},
    ])

    stats, quality = _complete_country_stats(reference, annual, pd.DataFrame(), unece, oecd)
    sources = quality[quality["country_code"] == "BE"].set_index("year")["passengers_source"]
    values = stats[stats["country_code"] == "BE"].set_index("year")["passengers"]

    assert sources.loc[2010] == "eurostat"
    assert sources.loc[2011] == "eurostat_quarterly"
    assert sources.loc[2012] == "unece"
    assert sources.loc[2013] == "interpolated"
    assert values.loc[2013] == 130.0
    assert sources.loc[2014] == "oecd_itf"
    assert set(quality.loc[quality["country_code"] == "CY", "passengers_source"]) == {"structural_zero"}
    assert stats.loc[stats["country_code"] == "CY", "passengers"].eq(0).all()


def test_quarterly_eurostat_requires_four_quarters_and_keeps_units_separate(tmp_path):
    source = tmp_path / "quarterly.csv"
    pd.DataFrame(
        {
            "freq,unit,geo\\TIME_PERIOD": ["Q,MIO_PKM,BE", "Q,THS_PAS,BE", "Q,MIO_PKM,HU"],
            "2024-Q1": [1.0, 999.0, 10.0],
            "2024-Q2": [2.0, 999.0, 20.0],
            "2024-Q3": [3.0, 999.0, 30.0],
            "2024-Q4": [4.0, 999.0, None],
        }
    ).to_csv(source, index=False)

    detail, annual = _quarterly_to_annual(source)

    assert len(detail[detail["country_code"] == "BE"]) == 4
    assert annual.to_dict("records") == [{
        "country_code": "BE", "year": 2024, "passengers": 10.0,
        "country_name": "Belgium", "passenger_metric": "MIO_PKM",
        "data_quality": "derived_four_quarters", "data_source": "eurostat_quarterly",
    }]


def test_unece_transform_normalises_countries_and_period(tmp_path):
    source = tmp_path / "raw" / "unece"
    source.mkdir(parents=True)
    pd.DataFrame([
        {"Passengers": "Total", "Topic": "Passenger-km (millions)", "Country": "United Kingdom", "Year": 2024, "Value": 64036},
        {"Passengers": "Total", "Topic": "Passenger-km (millions)", "Country": "Belgium", "Year": 2010, "Value": 10565},
        {"Passengers": "Total", "Topic": "Passenger-km (millions)", "Country": "France", "Year": 2025, "Value": 999999},
    ]).to_csv(source / "rail_passenger_km.csv", index=False)

    report = transform_unece(str(tmp_path / "raw"), str(tmp_path / "processed"))
    output = pd.read_csv(tmp_path / "processed" / "unece" / "passengers_processed.csv")

    assert report["records"] == 2
    assert set(output["country_code"]) == {"BE", "GB"}
    assert output["year"].max() == 2024


def test_oecd_transform_applies_unit_multiplier_and_exact_filters(tmp_path):
    source = tmp_path / "raw" / "oecd_itf"
    source.mkdir(parents=True)
    pd.DataFrame([
        {"REF_AREA": "BEL", "FREQ": "A", "MEASURE": "PASSENGER", "UNIT_MEASURE": "PASKM", "TRANSPORT_MODE": "RAIL", "TRANSPORT_TYPE": "RAIL", "TIME_PERIOD": 2023, "OBS_VALUE": 10441, "UNIT_MULT": 6},
        {"REF_AREA": "HUN", "FREQ": "A", "MEASURE": "PASSENGER", "UNIT_MEASURE": "PASKM", "TRANSPORT_MODE": "RAIL", "TRANSPORT_TYPE": "RAIL", "TIME_PERIOD": 2024, "OBS_VALUE": 15.00558, "UNIT_MULT": 9},
        {"REF_AREA": "BEL", "FREQ": "A", "MEASURE": "PASSENGER", "UNIT_MEASURE": "PAS", "TRANSPORT_MODE": "RAIL", "TRANSPORT_TYPE": "RAIL", "TIME_PERIOD": 2024, "OBS_VALUE": 999, "UNIT_MULT": 6},
    ]).to_csv(source / "rail_passenger_km.csv", index=False)

    report = transform_oecd_itf(str(tmp_path / "raw"), str(tmp_path / "processed"))
    output = pd.read_csv(tmp_path / "processed" / "oecd_itf" / "passengers_processed.csv")

    assert report["records"] == 2
    assert output.loc[output["country_code"] == "BE", "passengers"].iloc[0] == 10441
    assert output.loc[output["country_code"] == "HU", "passengers"].iloc[0] == 15005.58
