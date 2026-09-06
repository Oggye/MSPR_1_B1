"""
Enrichissement ObRail Europe - version volumétrique et traçable.

Principes :
1. Les services GTFS réels sont conservés à la granularité trip.
2. Back on Track reste la source réelle dédiée aux trains de nuit.
3. Les pays sans GTFS sont complétés synthétiquement à partir du référentiel
   donnee_pays.csv et calibrés sur les volumes GTFS réellement observés.
4. Aucune donnée réelle n'est transformée artificiellement de jour en nuit.
5. Le champ canonique est `train`; `is_night` porte la nature jour/nuit.
6. Le warehouse conserve le même nom de table facts_night_trains afin de limiter
   les régressions, mais le schéma SQL expose `train` et garde un alias legacy
   `night_train` généré automatiquement pour l'API existante.
7. Les gros faits sont écrits en streaming/chunks afin de supporter plusieurs
   millions de lignes sans charger tout le dataset en RAM.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .dim_stops import build_dim_stops
from .distance import REFERENCE_COORDS, compute_route_distance, haversine
from .duration import compute_night_train_durations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COUNTRY_REFERENCE_FILE = Path(__file__).resolve().parent / "donnee_pays.csv"
ANALYSIS_YEARS = list(range(2010, 2025))
EU27_CODES = [
    'AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IE','IT','LV','LT','LU','MT','NL','PL','PT','RO','SK','SI','ES','SE'
]
SPECIAL_COUNTRIES = {
    'UNKNOWN':'Unknown Country',
    'OTHER':'Other European Country',
    'MULTI':'Multiple Countries',
    'EU27':'European Union (27)',
}


def _country_code(value) -> str:
    code = str(value).strip().upper()
    return {'UK':'GB', 'EL':'GR'}.get(code, code)

# Réglage volontairement paramétrable : le défaut produit déjà une volumétrie
# importante sans multiplier arbitrairement des dizaines de millions de lignes.
SYNTHETIC_DENSITY_FACTOR = float(os.getenv('OBRAIL_SYNTHETIC_DENSITY_FACTOR', '0.20'))
SYNTHETIC_MAX_PER_COUNTRY_YEAR = int(os.getenv('OBRAIL_SYNTHETIC_MAX_PER_COUNTRY_YEAR', '50000'))
SYNTHETIC_MIN_PER_COUNTRY_YEAR = int(os.getenv('OBRAIL_SYNTHETIC_MIN_PER_COUNTRY_YEAR', '250'))
SYNTHETIC_CALIBRATION_CAP = float(os.getenv('OBRAIL_SYNTHETIC_CALIBRATION_CAP', '10000'))
FACT_WRITE_CHUNK = int(os.getenv('OBRAIL_FACT_WRITE_CHUNK', '100000'))

OPERATOR_BY_COUNTRY = {
    'AT':'ÖBB','BE':'SNCB','BG':'BDZ','HR':'HŽ','CZ':'ČD','DK':'DSB','EE':'Elron','FI':'VR','FR':'SNCF',
    'DE':'DB','GR':'Hellenic Train','HU':'MÁV','IE':'Iarnród Éireann','IT':'Trenitalia','LV':'Vivi','LT':'LTG Link',
    'LU':'CFL','NL':'NS','PL':'PKP Intercity','PT':'CP','RO':'CFR Călători','SK':'ŽSSK','SI':'Slovenske železnice',
    'ES':'Renfe','SE':'SJ','CH':'SBB','GB':'National Rail','NO':'Vy',
}

# Les itinéraires proviennent de la logique synthétique déjà présente dans le
# projet, élargie seulement pour fournir plusieurs modèles déterministes.
DAY_ROUTES = {
    'AT':['Wien - Salzburg','Wien - Innsbruck','Wien - Graz'],
    'BE':['Brussels - Liège','Brussels - Antwerp','Brussels - Ghent'],
    'BG':['Sofia - Plovdiv','Sofia - Varna','Sofia - Burgas'],
    'HR':['Zagreb - Split','Zagreb - Rijeka'],
    'CZ':['Praha - Brno','Praha - Ostrava','Brno - Ostrava'],
    'DK':['Copenhagen - Aarhus','Copenhagen - Odense'],
    'EE':['Tallinn - Tartu','Tallinn - Narva'],
    'FI':['Helsinki - Tampere','Helsinki - Turku','Helsinki - Oulu'],
    'FR':['Paris - Lyon','Paris - Marseille','Paris - Lille'],
    'DE':['Berlin - München','Hamburg - Frankfurt','Köln - Stuttgart'],
    'GR':['Athens - Thessaloniki'],
    'HU':['Budapest - Debrecen','Budapest - Szeged','Budapest - Győr'],
    'IE':['Dublin - Cork','Dublin - Galway','Dublin - Belfast'],
    'IT':['Roma - Milano','Roma - Napoli','Milano - Venezia'],
    'LV':['Riga - Daugavpils','Riga - Jelgava'],
    'LT':['Vilnius - Kaunas','Vilnius - Klaipėda'],
    'LU':['Luxembourg - Esch-sur-Alzette','Luxembourg - Troisvierges'],
    'NL':['Amsterdam - Rotterdam','Amsterdam - Utrecht','Amsterdam - Eindhoven'],
    'PL':['Warszawa - Kraków','Warszawa - Wrocław','Warszawa - Gdańsk'],
    'PT':['Lisboa - Porto','Lisboa - Coimbra','Porto - Faro'],
    'RO':['București - Cluj','București - Timișoara','București - Brașov'],
    'SK':['Bratislava - Košice','Bratislava - Žilina'],
    'SI':['Ljubljana - Maribor','Ljubljana - Koper'],
    'ES':['Madrid - Barcelona','Madrid - Valencia','Barcelona - Sevilla'],
    'SE':['Stockholm - Göteborg','Stockholm - Malmö','Stockholm - Umeå'],
    'CH':['Zürich - Bern','Zürich - Genève','Basel - Bern'],
    'GB':['London - Manchester','London - Edinburgh','London - Birmingham'],
    'NO':['Oslo - Bergen','Oslo - Trondheim'],
}

NIGHT_ROUTES = {
    'AT':['Wien - Hamburg','Wien - Zürich'],
    'BE':['Brussels - Berlin'],
    'BG':['Sofia - Varna'],
    'HR':['Zagreb - Split'],
    'CZ':['Praha - Zürich','Praha - Budapest'],
    'DK':['Copenhagen - Hamburg','Copenhagen - Berlin'],
    'EE':['Tallinn - Riga'],
    'FI':['Helsinki - Rovaniemi'],
    'FR':['Paris - Briançon','Paris - Nice'],
    'DE':['Hamburg - Zürich','Berlin - Wien'],
    'GR':['Athens - Thessaloniki'],
    'HU':['Budapest - Zürich','Budapest - Split'],
    'IE':['Dublin - Belfast'],
    'IT':['Roma - Palermo','Milano - Lecce'],
    'LV':['Riga - Vilnius'],
    'LT':['Vilnius - Warsaw'],
    'LU':['Luxembourg - Berlin'],
    'NL':['Amsterdam - Berlin','Amsterdam - Wien'],
    'PL':['Warszawa - Wien','Warszawa - Praha'],
    'PT':['Lisboa - Madrid'],
    'RO':['București - Budapest'],
    'SK':['Bratislava - Košice'],
    'SI':['Ljubljana - Zagreb','Ljubljana - Wien'],
    'ES':['Madrid - Lisboa','Barcelona - Paris'],
    'SE':['Stockholm - Malmö','Stockholm - Berlin'],
    'CH':['Zürich - Wien','Zürich - Hamburg'],
    'GB':['London - Edinburgh'],
    'NO':['Oslo - Trondheim'],
}


def _ratio01(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors='coerce').fillna(0.0)
    if len(values) and values.max() > 1.5:
        values = values / 100.0
    return values.clip(0, 1)


def _max_norm(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors='coerce').fillna(0.0)
    maximum = values.max()
    return values / maximum if maximum and maximum > 0 else values * 0


def load_country_reference() -> pd.DataFrame:
    ref = pd.read_csv(COUNTRY_REFERENCE_FILE)
    ref.columns = [str(c).strip() for c in ref.columns]
    ref['country_code'] = ref['country_code'].map(_country_code)
    ref['country_name'] = ref['country_name'].astype(str).str.strip()
    numeric = [c for c in ref.columns if c not in ['country_code','country_name']]
    for col in numeric:
        ref[col] = pd.to_numeric(ref[col], errors='coerce')
    if ref['country_code'].duplicated().any():
        raise ValueError('Doublons dans donnee_pays.csv')
    if ref[numeric].isna().any().any():
        missing = ref[numeric].isna().sum()
        raise ValueError(f"Valeurs numériques manquantes dans donnee_pays.csv: {missing[missing>0].to_dict()}")

    ref['rail_score'] = (
        0.28 * _ratio01(ref['rail_activity_index']) +
        0.22 * _max_norm(ref['rail_network_km']) +
        0.13 * _max_norm(ref['population_million']) +
        0.10 * _ratio01(ref['tourism_index']) +
        0.09 * _ratio01(ref['urbanization_pct']) +
        0.08 * _ratio01(ref['electrification_pct']) +
        0.06 * _max_norm(ref['high_speed_rail_km']) +
        0.04 * _max_norm(ref['gdp_per_capita_eur'])
    )
    return ref


def _bool_series(series: pd.Series, default=False) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(default)
    text = series.astype('string').str.lower().str.strip()
    return text.map({'true':True,'1':True,'yes':True,'false':False,'0':False,'no':False}).fillna(default).astype(bool)


def _csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open('rb') as handle:
        count = sum(1 for _ in handle)
    return max(0, count - 1)


def _gtfs_service_files(processed: Path) -> list[tuple[str, Path]]:
    root = processed / 'gtfs'
    files = []
    if root.exists():
        for country_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            path = country_dir / 'train_services_processed.csv'
            if path.exists():
                files.append((country_dir.name.upper(), path))
    return files


def _collect_unique_column(path: Path, column: str) -> set[str]:
    values: set[str] = set()
    try:
        for chunk in pd.read_csv(path, usecols=[column], chunksize=200_000, low_memory=False):
            values.update(chunk[column].dropna().astype(str).str.strip())
    except (ValueError, pd.errors.EmptyDataError):
        pass
    return {v for v in values if v}


def _collect_years(path: Path) -> set[int]:
    years = set()
    try:
        for chunk in pd.read_csv(path, usecols=['year'], chunksize=200_000, low_memory=False):
            y = pd.to_numeric(chunk['year'], errors='coerce').dropna().astype(int)
            years.update(y.tolist())
    except (ValueError, pd.errors.EmptyDataError):
        pass
    return years


def _count_in_period_rows(path: Path) -> int:
    count = 0
    try:
        for chunk in pd.read_csv(path, usecols=['year'], chunksize=200_000, low_memory=False):
            years = pd.to_numeric(chunk['year'], errors='coerce')
            count += int(years.between(min(ANALYSIS_YEARS), max(ANALYSIS_YEARS)).sum())
    except (ValueError, pd.errors.EmptyDataError):
        pass
    return count


def _build_dimensions(processed: Path, ref: pd.DataFrame, back: pd.DataFrame):
    observed_codes = set(ref['country_code'])
    years = set(ANALYSIS_YEARS)
    operator_names = set(OPERATOR_BY_COUNTRY.values())
    observed_counts = {}

    for country, path in _gtfs_service_files(processed):
        observed_codes.add(country)
        observed_counts[country] = _count_in_period_rows(path)
        operator_names.update(_collect_unique_column(path, 'operators'))

    if not back.empty:
        observed_codes.update(back['country_code'].dropna().map(_country_code))
        operator_names.update(back['operators'].dropna().astype(str).str.strip())

    country_name_map = dict(zip(ref['country_code'], ref['country_name']))
    country_name_map.update(SPECIAL_COUNTRIES)
    for code in sorted(observed_codes):
        country_name_map.setdefault(code, code)
    dim_countries = pd.DataFrame([
        {'country_code':code, 'country_name':name}
        for code, name in country_name_map.items()
    ]).drop_duplicates('country_code').sort_values('country_code').reset_index(drop=True)
    dim_countries.insert(0, 'country_id', range(1, len(dim_countries) + 1))

    dim_years = pd.DataFrame({'year':sorted(int(y) for y in years if pd.notna(y))})
    dim_years.insert(0, 'year_id', range(1, len(dim_years) + 1))
    dim_years['is_after_2010'] = dim_years['year'] >= 2010

    operator_names = {name for name in operator_names if name and name.lower() not in {'nan','none'}}
    ordered_ops = ['Unknown Operator'] + sorted(operator_names - {'Unknown Operator'})
    dim_operators = pd.DataFrame({'operator_id':range(len(ordered_ops)), 'operator_name':ordered_ops})
    return dim_countries, dim_years, dim_operators, observed_counts


def _country_fallback_distance_map(ref: pd.DataFrame) -> dict[str, float]:
    result = {}
    for _, row in ref.iterrows():
        network = float(row['rail_network_km'])
        if network <= 0:
            result[row['country_code']] = 0.0
        else:
            result[row['country_code']] = float(min(1200, max(35, network * 0.08)))
    return result


def _safe_operator(series: pd.Series, default: str) -> pd.Series:
    s = series.astype('string').fillna('').str.strip()
    return s.where(s.ne(''), default)


def _prepare_fact_chunk(
    chunk: pd.DataFrame,
    fact_start: int,
    country_ids: dict,
    year_ids: dict,
    operator_ids: dict,
    fallback_distance: dict,
) -> pd.DataFrame:
    out = chunk.copy()
    for col, default in [
        ('route_id','UNKNOWN_ROUTE'),('train','Train'),('country_code','UNKNOWN'),
        ('operators','Unknown Operator'),('data_source','unknown')
    ]:
        if col not in out.columns:
            out[col] = default
    if 'year' not in out.columns:
        out['year'] = max(ANALYSIS_YEARS)
    if 'is_night' not in out.columns:
        out['is_night'] = False
    if 'is_synthetic' not in out.columns:
        out['is_synthetic'] = False
    if 'distance_km' not in out.columns:
        out['distance_km'] = np.nan
    if 'duration_min' not in out.columns:
        out['duration_min'] = np.nan

    out['route_id'] = out['route_id'].astype('string').fillna('UNKNOWN_ROUTE').str.strip().str.slice(0, 150)
    out['train'] = out['train'].astype('string').fillna('Train').str.strip().str.slice(0, 300)
    out['country_code'] = out['country_code'].map(_country_code)
    out['operators'] = _safe_operator(out['operators'], 'Unknown Operator').str.slice(0, 200)
    out['year'] = pd.to_numeric(out['year'], errors='coerce')
    out = out[out['year'].between(min(ANALYSIS_YEARS), max(ANALYSIS_YEARS))].copy()
    out['year'] = out['year'].astype(int)
    out['is_night'] = _bool_series(out['is_night'], False)
    out['is_synthetic'] = _bool_series(out['is_synthetic'], False)
    out['data_source'] = out['data_source'].astype('string').fillna('unknown').str.slice(0, 80)

    out['distance_km'] = pd.to_numeric(out['distance_km'], errors='coerce')
    missing_distance = out['distance_km'].isna() | (out['distance_km'] <= 0)
    out.loc[missing_distance, 'distance_km'] = out.loc[missing_distance, 'country_code'].map(fallback_distance).fillna(120.0)

    out['duration_min'] = pd.to_numeric(out['duration_min'], errors='coerce')
    missing_duration = out['duration_min'].isna() | (out['duration_min'] <= 0)
    speed = np.where(out['is_night'], 82.0, 100.0)
    estimated = out['distance_km'] / speed * 60.0
    out.loc[missing_duration, 'duration_min'] = estimated[missing_duration]
    minimum_duration = np.where(out['is_night'].to_numpy(), 60.0, 15.0)
    out['duration_min'] = np.maximum(out['duration_min'].to_numpy(dtype=float), minimum_duration)

    out['country_id'] = out['country_code'].map(country_ids).fillna(country_ids.get('UNKNOWN', 0)).astype(int)
    # L'annee a deja ete filtree; aucune valeur hors periode n'est rabattue.
    out['year_id'] = out['year'].map(year_ids).astype(int)
    out['operator_id'] = out['operators'].map(operator_ids).fillna(0).astype(int)
    out.insert(0, 'fact_id', np.arange(fact_start, fact_start + len(out), dtype=np.int64))

    cols = [
        'fact_id','route_id','train','country_id','year_id','operator_id','is_night',
        'distance_km','duration_min','is_synthetic','data_source'
    ]
    return out[cols]


def _append_facts(df: pd.DataFrame, path: Path, first_write: bool) -> bool:
    if df.empty:
        return first_write
    df.to_csv(path, mode='w' if first_write else 'a', header=first_write, index=False)
    return False


def _normalise_synthetic_stop(value: str) -> str:
    text = str(value).translate(str.maketrans({
        'ł': 'l', 'Ł': 'L', 'ø': 'o', 'Ø': 'O',
        'đ': 'd', 'Đ': 'D', 'ß': 'ss',
    }))
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(char for char in text if not unicodedata.combining(char)).lower()
    text = re.sub(r'[^a-z0-9\- ]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _lookup_synthetic_coord(stop_name: str) -> tuple[float, float] | None:
    name = _normalise_synthetic_stop(stop_name)
    if name in REFERENCE_COORDS:
        return REFERENCE_COORDS[name]
    for key, coords in sorted(REFERENCE_COORDS.items(), key=lambda item: len(item[0]), reverse=True):
        normalised_key = _normalise_synthetic_stop(key)
        if len(normalised_key) >= 4 and re.search(
            rf'(?<![a-z0-9]){re.escape(normalised_key)}(?![a-z0-9])', name
        ):
            return coords
    return None


def _synthetic_route_stops(route: str) -> list[str]:
    text = re.sub(r'<br\s*/?>', ' - ', str(route), flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    stops = re.split(r'\s+(?:--|-|\u2013|\u2014|/)\s+', text)
    return [_normalise_synthetic_stop(stop) for stop in stops if _normalise_synthetic_stop(stop)]


def _resolved_route_distance(route: str) -> float | None:
    stops = _synthetic_route_stops(route)
    if len(stops) >= 2:
        c1 = _lookup_synthetic_coord(stops[0])
        c2 = _lookup_synthetic_coord(stops[-1])
        if c1 and c2:
            return max(20.0, float(haversine(c1[0], c1[1], c2[0], c2[1])) * 1.18)
    return None


def _generic_year_factor(year: int) -> float:
    # Croissance progressive avant 2019, choc Covid, puis reprise.
    pre = {
        2010:0.72,2011:0.74,2012:0.76,2013:0.78,2014:0.80,
        2015:0.83,2016:0.86,2017:0.90,2018:0.94,2019:0.98,
        2020:0.56,2021:0.67,2022:0.82,2023:0.93,2024:1.00,
    }
    return pre.get(int(year), 1.0)


def _legacy_synthetic_targets(ref: pd.DataFrame, observed_counts: dict[str,int]) -> dict[str,int]:
    scored = ref.set_index('country_code')
    ratios = []
    for country, count in observed_counts.items():
        if country in scored.index:
            score = float(scored.loc[country, 'rail_score'])
            network = float(scored.loc[country, 'rail_network_km'])
            if count > 0 and score > 0 and network > 0:
                ratios.append(count / score)
    if ratios:
        # médiane : résistante aux écarts de périmètre entre feeds nationaux.
        calibration = min(float(np.median(ratios)), SYNTHETIC_CALIBRATION_CAP)
    else:
        calibration = SYNTHETIC_CALIBRATION_CAP

    targets = {}
    for _, row in ref.iterrows():
        code = row['country_code']
        if row['rail_network_km'] <= 0:
            targets[code] = 0
            continue
        raw = calibration * float(row['rail_score']) * SYNTHETIC_DENSITY_FACTOR
        targets[code] = int(np.clip(round(raw), SYNTHETIC_MIN_PER_COUNTRY_YEAR, SYNTHETIC_MAX_PER_COUNTRY_YEAR))
    return targets


def _clean_metric(
    data: pd.DataFrame,
    value_col: str,
    metric_col: str | None = None,
    metric_value: str | None = None,
) -> pd.DataFrame:
    required = {'country_code', 'year', value_col}
    if data.empty or not required.issubset(data.columns):
        return pd.DataFrame(columns=['country_code', 'year', value_col])
    cleaned = data.copy()
    if metric_col and metric_col in cleaned.columns:
        cleaned = cleaned[cleaned[metric_col].eq(metric_value)]
    cleaned['country_code'] = cleaned['country_code'].map(_country_code)
    cleaned['year'] = pd.to_numeric(cleaned['year'], errors='coerce')
    cleaned[value_col] = pd.to_numeric(cleaned[value_col], errors='coerce')
    cleaned = cleaned.dropna(subset=['country_code', 'year', value_col])
    cleaned = cleaned[cleaned['year'].between(min(ANALYSIS_YEARS), max(ANALYSIS_YEARS))]
    cleaned = cleaned[cleaned[value_col] > 0].copy()
    cleaned['year'] = cleaned['year'].astype(int)
    return cleaned.sort_values('year').drop_duplicates(['country_code', 'year'], keep='last')


def _robust_recent_value(data: pd.DataFrame, value_col: str) -> float | None:
    recent = data.loc[data['year'].between(2022, 2024), value_col].dropna()
    values = recent if not recent.empty else data.sort_values('year')[value_col].dropna().tail(3)
    return float(values.median()) if not values.empty else None


def _observations(data: pd.DataFrame, country: str, value_col: str) -> dict[int, float]:
    group = data[data['country_code'].eq(country)]
    return {int(row.year): float(getattr(row, value_col)) for row in group[['year', value_col]].itertuples(index=False)}


def _continuous_activity_series(
    observations: dict[int, float],
    profile_observations: dict[int, float] | None = None,
) -> dict[int, float]:
    """Keep observations, interpolate short gaps, and anchor long gaps."""
    if not observations:
        return {}
    profile_observations = profile_observations or {}
    official_years = sorted(observations)
    first_year, last_year = official_years[0], official_years[-1]
    result: dict[int, float] = {}

    for year in ANALYSIS_YEARS:
        if year in observations:
            result[year] = observations[year]
            continue
        if year < first_year:
            result[year] = observations[first_year] * _generic_year_factor(year) / _generic_year_factor(first_year)
            continue
        if year > last_year:
            result[year] = observations[last_year] * _generic_year_factor(year) / _generic_year_factor(last_year)
            continue

        lower = max(item for item in official_years if item < year)
        upper = min(item for item in official_years if item > year)
        missing_years = upper - lower - 1
        if missing_years <= 2:
            share = (year - lower) / (upper - lower)
            result[year] = observations[lower] + share * (observations[upper] - observations[lower])
            continue

        if all(item in profile_observations for item in (lower, year, upper)):
            lower_scale = observations[lower] / profile_observations[lower]
            upper_scale = observations[upper] / profile_observations[upper]
            share = (year - lower) / (upper - lower)
            scale = lower_scale + share * (upper_scale - lower_scale)
            result[year] = profile_observations[year] * scale
        else:
            anchor = lower if year - lower <= upper - year else upper
            result[year] = observations[anchor] * _generic_year_factor(year) / _generic_year_factor(anchor)
    return result


def _allocate_integer_budget(total: int, weights: dict[str, float]) -> dict[str, int]:
    positive = {code: max(0.0, float(value)) for code, value in weights.items()}
    weight_sum = sum(positive.values())
    if total <= 0 or weight_sum <= 0:
        return {code: 0 for code in positive}
    quotas = {code: total * value / weight_sum for code, value in positive.items()}
    allocated = {code: int(math.floor(value)) for code, value in quotas.items()}
    remainder = total - sum(allocated.values())
    order = sorted(quotas, key=lambda code: (-(quotas[code] - allocated[code]), code))
    for code in order[:remainder]:
        allocated[code] += 1
    return allocated


def _build_synthetic_plan(
    ref: pd.DataFrame,
    observed_counts: dict[str, int],
    traffic: pd.DataFrame,
    passengers: pd.DataFrame,
) -> tuple[dict[str, int], dict[tuple[str, int], float], dict[str, str], int]:
    traffic = _clean_metric(traffic, 'traffic', 'traffic_unit', 'THS_TRKM')
    passengers = _clean_metric(passengers, 'passengers', 'passenger_metric', 'MIO_PKM')
    covered_gtfs = {code for code, count in observed_counts.items() if count > 0}
    ref_indexed = ref.set_index('country_code')
    eligible = [
        code for code in ref['country_code']
        if code not in covered_gtfs and code not in {'CY', 'MT'}
    ]

    legacy_targets = _legacy_synthetic_targets(ref, observed_counts)
    nominal_budget = sum(legacy_targets.get(code, 0) for code in eligible)
    train_anchors = {
        code: _robust_recent_value(traffic[traffic['country_code'].eq(code)], 'traffic')
        for code in eligible
    }
    passenger_anchors = {
        code: _robust_recent_value(passengers[passengers['country_code'].eq(code)], 'passengers')
        for code in eligible
    }

    paired = [
        train_anchors[code] / passenger_anchors[code]
        for code in eligible
        if train_anchors[code] is not None and passenger_anchors[code] not in (None, 0)
    ]
    passenger_scale = float(np.median(paired)) if paired else 1.0
    network_rates = [
        train_anchors[code] / float(ref_indexed.loc[code, 'rail_network_km'])
        for code in eligible
        if train_anchors[code] is not None and float(ref_indexed.loc[code, 'rail_network_km']) > 0
    ]
    network_scale = float(np.median(network_rates)) if network_rates else 1.0
    score_rates = [
        train_anchors[code] / float(ref_indexed.loc[code, 'rail_score'])
        for code in eligible
        if train_anchors[code] is not None and float(ref_indexed.loc[code, 'rail_score']) > 0
    ]
    score_scale = float(np.median(score_rates)) if score_rates else 1.0

    weights: dict[str, float] = {}
    sources: dict[str, str] = {}
    anchors: dict[str, float] = {}
    for code in eligible:
        network = float(ref_indexed.loc[code, 'rail_network_km'])
        score = float(ref_indexed.loc[code, 'rail_score'])
        if train_anchors[code] is not None:
            source, anchor, weight = 'train_km', train_anchors[code], train_anchors[code]
        elif passenger_anchors[code] is not None:
            source, anchor = 'passenger_km', passenger_anchors[code]
            weight = anchor * passenger_scale
        elif network > 0:
            source, anchor, weight = 'rail_network_km', network, network * network_scale
        else:
            source, anchor, weight = 'rail_score', score, score * score_scale
        sources[code], anchors[code], weights[code] = source, float(anchor), float(weight)

    allocated = _allocate_integer_budget(nominal_budget, weights)
    targets = {code: 0 for code in ref['country_code']}
    targets.update(allocated)
    factors: dict[tuple[str, int], float] = {}
    for code in eligible:
        if sources[code] == 'train_km':
            series = _continuous_activity_series(
                _observations(traffic, code, 'traffic'),
                _observations(passengers, code, 'passengers'),
            )
        elif sources[code] == 'passenger_km':
            series = _continuous_activity_series(_observations(passengers, code, 'passengers'))
        else:
            series = {year: anchors[code] * _generic_year_factor(year) for year in ANALYSIS_YEARS}
        for year in ANALYSIS_YEARS:
            factors[(code, year)] = max(0.0, float(series[year] / anchors[code]))
    return targets, factors, sources, nominal_budget


def _calibrate_synthetic_targets(
    ref: pd.DataFrame,
    observed_counts: dict[str, int],
    traffic: pd.DataFrame | None = None,
    passengers: pd.DataFrame | None = None,
) -> dict[str, int]:
    if traffic is None and passengers is None:
        return _legacy_synthetic_targets(ref, observed_counts)
    targets, _, _, _ = _build_synthetic_plan(
        ref, observed_counts,
        traffic if traffic is not None else pd.DataFrame(),
        passengers if passengers is not None else pd.DataFrame(),
    )
    return targets


def _night_ratio(row: pd.Series) -> float:
    if float(row['rail_network_km']) <= 0:
        return 0.0
    index = float(row['night_train_index'])
    if index > 1.5:
        index /= 100.0
    return float(np.clip(0.03 + 0.12 * index, 0.02, 0.16))


def _synthetic_route_distances(day_routes: list[str], night_routes: list[str]) -> dict[tuple[bool, str], float]:
    resolved: dict[tuple[bool, str], float] = {}
    for is_night, routes in [(False, day_routes), (True, night_routes)]:
        for route in routes:
            distance = _resolved_route_distance(route)
            if distance is not None:
                resolved[(is_night, route)] = distance

    day_values = [value for (is_night, _), value in resolved.items() if not is_night]
    all_values = list(resolved.values())
    medians = {
        False: float(np.median(day_values)) if day_values else None,
        True: float(np.median([
            value for (is_night, _), value in resolved.items() if is_night
        ])) if any(is_night for is_night, _ in resolved) else None,
    }
    all_median = float(np.median(all_values)) if all_values else None

    distances: dict[tuple[bool, str], float] = {}
    for is_night, routes in [(False, day_routes), (True, night_routes)]:
        for route in routes:
            distance = resolved.get((is_night, route))
            if distance is None:
                if medians[is_night] is not None:
                    distance = medians[is_night]
                elif is_night and medians[False] is not None:
                    # A night template is expected to cover a longer itinerary.
                    distance = 1.5 * medians[False]
                elif all_median is not None:
                    distance = all_median
                else:
                    distance = 180.0 if is_night else 120.0
            lower_bound = 120.0 if is_night else 35.0
            distances[(is_night, route)] = float(np.clip(distance, lower_bound, 1200.0))
    return distances


def _generate_synthetic_chunk(
    country: str,
    year: int,
    n: int,
    night_ratio: float,
    operator: str,
    bot_night_routes: list[str] | None = None,
) -> pd.DataFrame:
    if n <= 0:
        return pd.DataFrame()
    day_routes = DAY_ROUTES.get(country, [f"{country} National Rail Service"])
    night_routes = bot_night_routes or NIGHT_ROUTES.get(country, day_routes)
    route_distances = _synthetic_route_distances(day_routes, night_routes)
    n_night = int(round(n * night_ratio))
    n_day = n - n_night

    frames = []
    if n_day:
        idx = np.arange(n_day)
        routes = np.asarray(day_routes, dtype=object)[idx % len(day_routes)]
        distances = np.array([route_distances[(False, r)] for r in routes], dtype=float)
        frames.append(pd.DataFrame({
            'route_id':[f"SYN-{country}-{year}-D-{i+1}" for i in idx],
            'train':routes,
            'country_code':country,
            'year':year,
            'operators':operator,
            'is_night':False,
            'distance_km':distances,
            'duration_min':np.maximum(20.0, distances / 95.0 * 60.0),
            'is_synthetic':True,
            'data_source':'synthetic_reference',
        }))
    if n_night:
        idx = np.arange(n_night)
        routes = np.asarray(night_routes, dtype=object)[idx % len(night_routes)]
        distances = np.array([route_distances[(True, r)] for r in routes], dtype=float)
        frames.append(pd.DataFrame({
            'route_id':[f"SYN-{country}-{year}-N-{i+1}" for i in idx],
            'train':routes,
            'country_code':country,
            'year':year,
            'operators':operator,
            'is_night':True,
            'distance_km':distances,
            'duration_min':np.maximum(90.0, distances / 78.0 * 60.0),
            'is_synthetic':True,
            'data_source':'synthetic_reference',
        }))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _latest_by_country(df: pd.DataFrame, value_col: str) -> dict[str,float]:
    if df.empty or not {'country_code','year',value_col}.issubset(df.columns):
        return {}
    d = df.copy()
    d['year'] = pd.to_numeric(d['year'], errors='coerce')
    d[value_col] = pd.to_numeric(d[value_col], errors='coerce')
    d = d.dropna(subset=['year',value_col]).sort_values('year')
    return d.groupby('country_code')[value_col].last().to_dict()


def _complete_country_stats(
    ref: pd.DataFrame,
    passengers: pd.DataFrame,
    emissions: pd.DataFrame,
    unece: pd.DataFrame | None = None,
    oecd: pd.DataFrame | None = None,
):
    p_obs: dict[tuple[str, int], tuple[float, str]] = {}

    def add_passenger_source(frame: pd.DataFrame | None, expected_source: str) -> None:
        if frame is None or frame.empty or not {'country_code','year','passengers'}.issubset(frame.columns):
            return
        data = frame.copy()
        data['country_code'] = data['country_code'].map(_country_code)
        data['year'] = pd.to_numeric(data['year'], errors='coerce')
        data['passengers'] = pd.to_numeric(data['passengers'], errors='coerce')
        if 'passenger_metric' in data.columns:
            data = data[data['passenger_metric'].astype('string').str.upper().eq('MIO_PKM')]
        if 'data_source' in data.columns:
            data = data[data['data_source'].astype('string').eq(expected_source)]
        data = data[
            data['year'].between(min(ANALYSIS_YEARS), max(ANALYSIS_YEARS))
            & data['passengers'].notna()
        ]
        for _, item in data.sort_values('year').iterrows():
            key = (item['country_code'], int(item['year']))
            p_obs.setdefault(key, (float(item['passengers']), expected_source))

    # L'ordre des appels constitue la hierarchie explicite de fallback.
    add_passenger_source(passengers, 'eurostat')
    add_passenger_source(passengers, 'eurostat_quarterly')
    add_passenger_source(unece, 'unece')
    add_passenger_source(oecd, 'oecd_itf')

    interpolated: dict[tuple[str, int], float] = {}
    for code in ref['country_code']:
        series = pd.Series(
            {year: value for (country, year), (value, _) in p_obs.items() if country == code},
            dtype=float,
        ).reindex(ANALYSIS_YEARS)
        filled = series.interpolate(method='linear', limit_area='inside')
        for year in ANALYSIS_YEARS:
            if pd.isna(series.loc[year]) and pd.notna(filled.loc[year]):
                interpolated[(code, year)] = float(filled.loc[year])

    e_obs = {}
    if not emissions.empty:
        for _, row in emissions.dropna(subset=['country_code','year','co2_emissions']).iterrows():
            e_obs[(str(row['country_code']), int(row['year']))] = float(row['co2_emissions'])

    # Calibrer le référentiel sur l'échelle réellement utilisée par Eurostat.
    latest_p = {}
    for (code, year), (value, _) in sorted(p_obs.items(), key=lambda item: item[0][1]):
        latest_p[code] = value
    p_ratios = []
    for _, row in ref.iterrows():
        code = row['country_code']
        base = float(row['passengers_reference_million'])
        if code in latest_p and base > 0:
            p_ratios.append(latest_p[code] / base)
    p_scale = float(np.median(p_ratios)) if p_ratios else 1.0

    latest_e = _latest_by_country(emissions, 'co2_emissions')
    e_ratios = []
    for _, row in ref.iterrows():
        code = row['country_code']
        model = float(row['gdp_billion_eur']) * max(float(row['co2_intensity_index']), 0.05)
        if code in latest_e and model > 0:
            e_ratios.append(latest_e[code] / model)
    e_scale = float(np.median(e_ratios)) if e_ratios else 0.1

    records, quality = [], []
    for _, row in ref.iterrows():
        code = row['country_code']
        for year in ANALYSIS_YEARS:
            pk = (code, year)
            if float(row['rail_network_km']) <= 0 and code in {'CY', 'MT'}:
                passenger_value, passenger_source = 0.0, 'structural_zero'
            elif pk in p_obs:
                passenger_value, passenger_source = p_obs[pk]
            elif pk in interpolated:
                passenger_value, passenger_source = interpolated[pk], 'interpolated'
            else:
                passenger_value = float(row['passengers_reference_million']) * p_scale * _generic_year_factor(year)
                passenger_source = 'synthetic_reference'

            if pk in e_obs:
                emission_value, emission_source = e_obs[pk], 'eurostat'
            else:
                base_emission = float(row['gdp_billion_eur']) * max(float(row['co2_intensity_index']), 0.05) * e_scale
                # Les émissions nationales ont plutôt diminué sur la période ;
                # le facteur inverse la croissance ferroviaire pour rester prudent.
                emission_factor = {2020:0.90, 2021:0.94, 2022:0.98, 2023:1.00, 2024:1.00}.get(year, 1.18 - (year-2010)*0.012)
                emission_value = max(0.0, base_emission * emission_factor)
                emission_source = 'synthetic_reference'

            co2_pp = emission_value / passenger_value if passenger_value > 0 else 0.0
            records.append({
                'country_code':code,'year':year,'passengers':passenger_value,
                'co2_emissions':emission_value,'co2_per_passenger':co2_pp,
            })
            quality.append({
                'country_code':code,'year':year,
                'passengers_source':passenger_source,'co2_source':emission_source,
            })
    return pd.DataFrame(records), pd.DataFrame(quality)


def _build_operator_dashboard(facts_path: Path, dim_operators: pd.DataFrame) -> pd.DataFrame:
    aggs = {}
    for chunk in pd.read_csv(facts_path, chunksize=200_000, low_memory=False):
        chunk['distance_km'] = pd.to_numeric(chunk['distance_km'], errors='coerce').fillna(0)
        chunk['duration_min'] = pd.to_numeric(chunk['duration_min'], errors='coerce').fillna(0)
        chunk['is_night'] = _bool_series(chunk['is_night'], False)
        grouped = chunk.groupby('operator_id').agg(
            nb_trains=('fact_id','count'),
            distance_totale_km=('distance_km','sum'),
            duration_sum=('duration_min','sum'),
            nb_trains_nuit=('is_night','sum'),
        )
        for op_id, row in grouped.iterrows():
            bucket = aggs.setdefault(int(op_id), {'nb_trains':0,'distance_totale_km':0.0,'duration_sum':0.0,'nb_trains_nuit':0})
            for key in bucket:
                bucket[key] += float(row[key])

    rows = []
    names = dict(zip(dim_operators['operator_id'], dim_operators['operator_name']))
    for op_id, values in aggs.items():
        n = int(values['nb_trains'])
        night = int(values['nb_trains_nuit'])
        rows.append({
            'operator_id':op_id,'operator_name':names.get(op_id,'Unknown Operator'),
            'nb_trains':n,'distance_totale_km':values['distance_totale_km'],
            'duree_moyenne_min':values['duration_sum']/n if n else 0,
            'nb_trains_nuit':night,'nb_trains_jour':n-night,
        })
    return pd.DataFrame(rows).sort_values('nb_trains', ascending=False) if rows else pd.DataFrame()


def _create_sql() -> str:
    return """
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

-- Nom de table conservé pour compatibilité avec le projet existant.
-- `train` est le champ canonique. `night_train` est seulement un alias SQL
-- généré pour les anciens endpoints et pourra être supprimé plus tard.
CREATE TABLE facts_night_trains (
    fact_id BIGINT PRIMARY KEY,
    route_id VARCHAR(150) NOT NULL,
    train VARCHAR(300) NOT NULL,
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
SELECT c.country_id, c.country_name, c.country_code,
       AVG(s.passengers)::NUMERIC(20,2) AS avg_passengers,
       AVG(s.co2_emissions)::NUMERIC(20,4) AS avg_co2_emissions,
       AVG(s.co2_per_passenger)::NUMERIC(20,6) AS avg_co2_per_passenger
FROM facts_country_stats s
JOIN dim_countries c ON s.country_id = c.country_id
GROUP BY c.country_id, c.country_name, c.country_code;

CREATE VIEW operator_dashboard AS
SELECT o.operator_id, o.operator_name,
       COUNT(f.fact_id) AS nb_trains,
       SUM(CASE WHEN f.is_night THEN 1 ELSE 0 END) AS nb_trains_nuit,
       SUM(CASE WHEN NOT f.is_night THEN 1 ELSE 0 END) AS nb_trains_jour,
       COALESCE(SUM(f.distance_km),0)::NUMERIC(20,2) AS distance_totale_km,
       COALESCE(AVG(f.duration_min),0)::NUMERIC(12,2) AS duree_moyenne_min
FROM dim_operators o
LEFT JOIN facts_night_trains f ON o.operator_id = f.operator_id
GROUP BY o.operator_id, o.operator_name
ORDER BY nb_trains DESC;
"""


def enrich_and_prepare_for_warehouse(processed_dir: str, warehouse_dir: str) -> dict:
    logger.info("🔗 Enrichissement et préparation du warehouse...")
    processed = Path(processed_dir)
    warehouse = Path(warehouse_dir)
    warehouse.mkdir(parents=True, exist_ok=True)
    ref = load_country_reference()

    back_path = processed / 'back_on_track' / 'trains_processed.csv'
    back = pd.read_csv(back_path, low_memory=False) if back_path.exists() else pd.DataFrame()
    passengers_path = processed / 'eurostat' / 'passengers_processed.csv'
    traffic_path = processed / 'eurostat' / 'traffic_processed.csv'
    emissions_path = processed / 'emissions' / 'co2_emissions_processed.csv'
    unece_path = processed / 'unece' / 'passengers_processed.csv'
    oecd_path = processed / 'oecd_itf' / 'passengers_processed.csv'
    passengers = pd.read_csv(passengers_path, low_memory=False) if passengers_path.exists() else pd.DataFrame()
    traffic = pd.read_csv(traffic_path, low_memory=False) if traffic_path.exists() else pd.DataFrame()
    emissions = pd.read_csv(emissions_path, low_memory=False) if emissions_path.exists() else pd.DataFrame()
    unece = pd.read_csv(unece_path, low_memory=False) if unece_path.exists() else pd.DataFrame()
    oecd = pd.read_csv(oecd_path, low_memory=False) if oecd_path.exists() else pd.DataFrame()

    dim_countries, dim_years, dim_operators, observed_counts = _build_dimensions(processed, ref, back)
    dim_stops = build_dim_stops(str(processed), str(warehouse))
    dim_countries.to_csv(warehouse / 'dim_countries.csv', index=False)
    dim_years.to_csv(warehouse / 'dim_years.csv', index=False)
    dim_operators.to_csv(warehouse / 'dim_operators.csv', index=False)

    country_ids = dict(zip(dim_countries['country_code'], dim_countries['country_id']))
    year_ids = dict(zip(dim_years['year'], dim_years['year_id']))
    operator_ids = dict(zip(dim_operators['operator_name'], dim_operators['operator_id']))
    fallback_distance = _country_fallback_distance_map(ref)

    facts_path = warehouse / 'facts_night_trains.csv'
    if facts_path.exists():
        facts_path.unlink()
    first_write = True
    next_fact_id = 1
    real_gtfs_count = 0

    # 1) Services GTFS réels : lecture/écriture par chunks.
    for country, path in _gtfs_service_files(processed):
        logger.info("📦 Injection GTFS réel %s : %s", country, path.name)
        for chunk in pd.read_csv(path, chunksize=FACT_WRITE_CHUNK, low_memory=False):
            prepared = _prepare_fact_chunk(chunk, next_fact_id, country_ids, year_ids, operator_ids, fallback_distance)
            first_write = _append_facts(prepared, facts_path, first_write)
            next_fact_id += len(prepared)
            real_gtfs_count += len(prepared)

    # 2) Back on Track réel. Petit volume : calcul distance/durée plus détaillé.
    bot_count = 0
    bot_night_routes = {}
    if not back.empty:
        for country, group in back.groupby('country_code'):
            bot_night_routes[str(country)] = group['itinerary'].dropna().astype(str).drop_duplicates().tolist()[:50]
        if 'distance_km' not in back.columns:
            back = compute_route_distance(back, dim_stops)
        back = compute_night_train_durations(back)
        prepared = _prepare_fact_chunk(back, next_fact_id, country_ids, year_ids, operator_ids, fallback_distance)
        first_write = _append_facts(prepared, facts_path, first_write)
        next_fact_id += len(prepared)
        bot_count = len(prepared)

    # 3) Synthétique : uniquement les pays sans GTFS réel.
    targets, activity_factors, weight_sources, nominal_budget = _build_synthetic_plan(
        ref, observed_counts, traffic, passengers
    )
    covered_gtfs = {c for c, count in observed_counts.items() if count > 0}
    synthetic_count = 0
    synthetic_country_counts = {}
    ref_indexed = ref.set_index('country_code')

    for country in [c for c in ref['country_code'] if c not in covered_gtfs]:
        row = ref_indexed.loc[country]
        if float(row['rail_network_km']) <= 0:
            synthetic_country_counts[country] = 0
            continue
        base_target = targets.get(country, 0)
        ratio = _night_ratio(row)
        operator = OPERATOR_BY_COUNTRY.get(country, f"National Railway of {country}")
        total_country = 0
        for year in ANALYSIS_YEARS:
            factor = activity_factors.get((country, year), _generic_year_factor(year))
            n = int(round(base_target * factor))
            n = min(n, SYNTHETIC_MAX_PER_COUNTRY_YEAR)
            synthetic = _generate_synthetic_chunk(
                country, year, n, ratio, operator, bot_night_routes.get(country)
            )
            if synthetic.empty:
                continue
            prepared = _prepare_fact_chunk(synthetic, next_fact_id, country_ids, year_ids, operator_ids, fallback_distance)
            first_write = _append_facts(prepared, facts_path, first_write)
            next_fact_id += len(prepared)
            synthetic_count += len(prepared)
            total_country += len(prepared)
        synthetic_country_counts[country] = total_country

    if first_write:
        # Toujours produire un CSV avec en-têtes même si aucune ligne n'est disponible.
        pd.DataFrame(columns=[
            'fact_id','route_id','train','country_id','year_id','operator_id','is_night',
            'distance_km','duration_min','is_synthetic','data_source'
        ]).to_csv(facts_path, index=False)

    # Statistiques pays : toutes les combinaisons pays/année du référentiel.
    stats, stats_quality = _complete_country_stats(ref, passengers, emissions, unece, oecd)
    stats['country_id'] = stats['country_code'].map(country_ids).astype(int)
    stats['year_id'] = stats['year'].map(year_ids).astype(int)
    stats.insert(0, 'stat_id', range(1, len(stats) + 1))
    facts_country_stats = stats[[
        'stat_id','country_id','year_id','passengers','co2_emissions','co2_per_passenger'
    ]]
    facts_country_stats.to_csv(warehouse / 'facts_country_stats.csv', index=False)
    stats_quality.to_csv(warehouse / 'country_stats_quality.csv', index=False)

    dashboard = facts_country_stats.merge(dim_countries, on='country_id', how='left').groupby(
        ['country_id','country_name','country_code'], as_index=False
    ).agg(
        avg_passengers=('passengers','mean'),
        avg_co2_emissions=('co2_emissions','mean'),
        avg_co2_per_passenger=('co2_per_passenger','mean'),
    )
    dashboard.to_csv(warehouse / 'dashboard_metrics.csv', index=False)

    operator_dashboard = _build_operator_dashboard(facts_path, dim_operators)
    operator_dashboard.to_csv(warehouse / 'operator_dashboard.csv', index=False)

    sql = _create_sql()
    (warehouse / 'create_tables.sql').write_text(sql, encoding='utf-8')

    total_trains = real_gtfs_count + bot_count + synthetic_count
    # Compter jour/nuit et provenance sans charger plusieurs millions de lignes.
    night = day = synthetic_verified = 0
    source_counts = {}
    for chunk in pd.read_csv(facts_path, usecols=['is_night','is_synthetic','data_source'], chunksize=250_000):
        is_night = _bool_series(chunk['is_night'], False)
        is_synth = _bool_series(chunk['is_synthetic'], False)
        night += int(is_night.sum())
        day += int((~is_night).sum())
        synthetic_verified += int(is_synth.sum())
        for source, count in chunk['data_source'].value_counts().items():
            source_counts[str(source)] = source_counts.get(str(source), 0) + int(count)

    report = {
        'transformations_applied':[
            'Conservation des GTFS à granularité trip',
            'Traitement stop_times par chunks',
            'Jour/nuit déterminé par horaires réels GTFS',
            'Champ canonique train + booléen is_night',
            'Synthétique réparti par train-km, passenger-km, réseau puis rail_score',
            'Séries synthétiques continues avec observations officielles préservées',
            'Aucune promotion artificielle des trains GTFS réels en train de nuit',
            'Traçabilité réel/synthétique avec is_synthetic et data_source',
            'Statistiques pays complétées 2010-2024 par référentiel quand Eurostat manque',
        ],
        'data_sources':['back_on_track','eurostat','eurostat_quarterly','unece','oecd_itf','emissions'] + [f'gtfs_{c.lower()}' for c in sorted(covered_gtfs)],
        'tables_created':{
            'dimensions':['dim_countries.csv','dim_years.csv','dim_operators.csv','dim_stops.csv'],
            'facts':['facts_night_trains.csv','facts_country_stats.csv'],
            'quality':['country_stats_quality.csv'],
            'dashboard':['dashboard_metrics.csv','operator_dashboard.csv'],
        },
        'data_quality':{
            'total_countries':int(len(dim_countries)),
            'total_years':int(len(dim_years)),
            'total_operators':int(len(dim_operators)),
            'total_stops':int(len(dim_stops)),
            'total_train_records':int(total_trains),
            'real_gtfs_records':int(real_gtfs_count),
            'back_on_track_records':int(bot_count),
            'synthetic_records':int(synthetic_verified),
            'night_train_records':int(night),
            'day_train_records':int(day),
            'country_stats_records':int(len(facts_country_stats)),
            'source_counts':source_counts,
            'synthetic_by_country':synthetic_country_counts,
            'synthetic_weight_sources':weight_sources,
            'synthetic_nominal_budget_2024':int(nominal_budget),
            'gtfs_observed_counts':observed_counts,
            'synthetic_density_factor':SYNTHETIC_DENSITY_FACTOR,
            'synthetic_max_per_country_year':SYNTHETIC_MAX_PER_COUNTRY_YEAR,
            'synthetic_calibration_cap':SYNTHETIC_CALIBRATION_CAP,
        }
    }
    with (warehouse / 'warehouse_schema_report.json').open('w', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    logger.info(
        "✅ Warehouse : %s trains (%s réels GTFS, %s BOT, %s synthétiques) | jour=%s nuit=%s",
        f"{total_trains:,}", f"{real_gtfs_count:,}", f"{bot_count:,}", f"{synthetic_count:,}", f"{day:,}", f"{night:,}"
    )
    return report
