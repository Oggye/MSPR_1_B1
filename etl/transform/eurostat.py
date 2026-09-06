"""
Transformation Eurostat ferroviaire - version robuste.

Deux niveaux sont produits :
- *_detailed_processed.csv : toutes les observations nettoyées ;
- *_processed.csv : métrique canonique pays/année pour le warehouse.

Le parseur lit dynamiquement les dimensions présentes dans la première colonne
Eurostat (ex. freq,unit,tra_cov,geo\\TIME_PERIOD). Il reste donc compatible avec
les jeux rail_pa_typepas et rail_tf_traveh sans coder en dur leur structure.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COUNTRY_NAMES = {
    'FR':'France','DE':'Germany','CH':'Switzerland','IT':'Italy','ES':'Spain','GB':'United Kingdom',
    'BE':'Belgium','NL':'Netherlands','AT':'Austria','AL':'Albania','BG':'Bulgaria','CZ':'Czech Republic',
    'DK':'Denmark','EE':'Estonia','FI':'Finland','GR':'Greece','HR':'Croatia','HU':'Hungary','IE':'Ireland',
    'IS':'Iceland','LI':'Liechtenstein','LT':'Lithuania','LU':'Luxembourg','LV':'Latvia','ME':'Montenegro',
    'MK':'North Macedonia','MT':'Malta','NO':'Norway','PL':'Poland','PT':'Portugal','RO':'Romania',
    'RS':'Serbia','SE':'Sweden','SI':'Slovenia','SK':'Slovakia','TR':'Turkey','CY':'Cyprus',
    'BA':'Bosnia and Herzegovina','XK':'Kosovo'
}


def _geo(code):
    value = str(code).strip().upper()
    return {'UK':'GB', 'EL':'GR'}.get(value, value)


def _extract_numeric(series: pd.Series) -> pd.Series:
    """Gère ':', '123 p', '45.6 e', etc. sans transformer ':' en zéro."""
    text = series.astype('string').str.strip()
    number = text.str.extract(r'([-+]?\d+(?:\.\d+)?)', expand=False)
    return pd.to_numeric(number, errors='coerce')


def _dimension_names_from_header(composite_header: str) -> list[str]:
    """Extrait automatiquement les dimensions avant \\TIME_PERIOD."""
    left = str(composite_header).split('\\')[0]
    dims = [part.strip() for part in left.split(',') if part.strip()]
    if not dims:
        raise ValueError(f"Impossible de lire les dimensions Eurostat depuis {composite_header!r}")
    return dims


def _wide_to_long(path: Path, value_name: str) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    if df.empty:
        return df

    composite = df.columns[0]
    dimension_names = _dimension_names_from_header(composite)

    long = pd.melt(df, id_vars=[composite], var_name='year', value_name='raw_value')
    split = long[composite].astype('string').str.split(',', expand=True)

    if split.shape[1] != len(dimension_names):
        raise ValueError(
            f"Structure Eurostat inattendue dans {path.name}: {split.shape[1]} dimensions lues, "
            f"{len(dimension_names)} attendues ({dimension_names})"
        )

    split.columns = dimension_names
    long = pd.concat([long.drop(columns=[composite]), split], axis=1)

    for col in dimension_names:
        long[col] = long[col].astype('string').str.strip()

    if 'geo' not in long.columns:
        raise ValueError(f"Dimension geo absente dans {path.name}: {dimension_names}")
    if 'unit' not in long.columns:
        raise ValueError(f"Dimension unit absente dans {path.name}: {dimension_names}")

    long['year'] = pd.to_numeric(long['year'].astype('string').str.strip(), errors='coerce')
    long[value_name] = _extract_numeric(long['raw_value'])
    long['geo'] = long['geo'].map(_geo)

    long = long[long['year'].notna() & long['year'].between(2010, 2024)].copy()
    long['year'] = long['year'].astype(int)
    long['country_name'] = long['geo'].map(COUNTRY_NAMES).fillna(long['geo'])
    return long


def _normalise_pkm(values: pd.Series, unit: pd.Series) -> pd.Series:
    u = unit.astype('string').str.upper().str.strip()
    factor = pd.Series(np.nan, index=values.index, dtype=float)
    factor.loc[u.str.contains(r'(?:MIO|MLN)_PKM', regex=True, na=False)] = 1.0
    factor.loc[u.str.contains(r'THS_PKM', regex=True, na=False)] = 0.001
    factor.loc[u.eq('PKM')] = 1e-6
    return values * factor


def _normalise_passengers(values: pd.Series, unit: pd.Series) -> pd.Series:
    u = unit.astype('string').str.upper().str.strip()
    factor = pd.Series(np.nan, index=values.index, dtype=float)
    factor.loc[u.str.contains(r'(?:MIO|MLN)_(?:PAS|PASS)', regex=True, na=False)] = 1.0
    factor.loc[u.str.contains(r'THS_(?:PAS|PASS)', regex=True, na=False)] = 0.001
    factor.loc[u.isin(['PAS', 'PASS'])] = 1e-6
    return values * factor


def _filter_annual(df: pd.DataFrame) -> pd.DataFrame:
    if 'freq' in df.columns:
        annual = df['freq'].astype('string').str.upper().eq('A')
        if annual.any():
            return df[annual].copy()
    return df.copy()


def _prefer_total_dimensions(df: pd.DataFrame, protected: set[str]) -> pd.DataFrame:
    """
    Pour les dimensions de ventilation (tra_cov, vehicle, train...), préfère TOTAL
    lorsqu'il existe, sans jamais filtrer freq/unit/geo/year.
    """
    d = df.copy()
    for col in d.columns:
        if col in protected:
            continue
        if d[col].dtype.name not in ('string', 'object'):
            continue
        upper = d[col].astype('string').str.upper().str.strip()
        if upper.eq('TOTAL').any():
            d = d[upper.eq('TOTAL')].copy()
    return d


def _interpolate_country_series(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    if df.empty:
        return df
    result = []
    for _, group in df.groupby('country_code', sort=False):
        g = group.sort_values('year').copy()
        observed = g[value_col].notna()
        g[value_col] = g[value_col].interpolate(method='linear', limit_area='inside')
        g['data_quality'] = np.where(
            observed,
            'observed',
            np.where(g[value_col].notna(), 'interpolated', 'missing')
        )
        result.append(g)
    return pd.concat(result, ignore_index=True) if result else df


def _build_passenger_canonical(detail: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    empty_cols = ['country_code','year','passengers','country_name','passenger_metric','data_quality']
    if detail.empty:
        return pd.DataFrame(columns=empty_cols), 'none'

    d = _filter_annual(detail)

    # On choisit d'abord la métrique. Passenger-km est préféré car il mesure
    # mieux le volume de transport qu'un simple nombre de voyageurs.
    pkm = _normalise_pkm(d['passengers_raw'], d['unit'])
    if pkm.notna().any():
        d = d.loc[pkm.notna()].copy()
        d['passengers'] = pkm.loc[d.index]
        metric = 'MIO_PKM'
    else:
        passenger_count = _normalise_passengers(d['passengers_raw'], d['unit'])
        if passenger_count.notna().any():
            d = d.loc[passenger_count.notna()].copy()
            d['passengers'] = passenger_count.loc[d.index]
            metric = 'MIO_PASSENGERS'
        else:
            units = sorted(detail['unit'].dropna().astype(str).str.strip().unique().tolist())
            logger.warning(
                "Aucune unité passager/pkm exploitable dans rail_passengers.csv. Unités présentes: %s",
                units[:20],
            )
            return pd.DataFrame(columns=empty_cols), 'none'

    # Après sélection de l'unité pertinente, on préfère les agrégats TOTAL
    # dans les éventuelles dimensions de couverture/type de transport.
    d = _prefer_total_dimensions(
        d,
        protected={'raw_value','year','passengers_raw','passengers','freq','unit','geo','country_name'}
    )

    d = d[d['passengers'].notna()].copy()
    canonical = (
        d.groupby(['geo','year','country_name'], as_index=False)['passengers']
        .median()
        .rename(columns={'geo':'country_code'})
    )
    canonical['passenger_metric'] = metric
    canonical = _interpolate_country_series(canonical, 'passengers')
    canonical['data_source'] = 'eurostat'
    return canonical, metric


def _quarterly_to_annual(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail_columns = [
        'country_code', 'year', 'quarter', 'passengers', 'country_name',
        'passenger_metric', 'data_quality', 'data_source',
    ]
    annual_columns = [column for column in detail_columns if column != 'quarter']
    empty_detail = pd.DataFrame(columns=detail_columns)
    empty_annual = pd.DataFrame(columns=annual_columns)
    if not path.exists():
        logger.warning("Eurostat trimestriel absent : %s", path)
        return empty_detail, empty_annual

    source = pd.read_csv(path, low_memory=False)
    source.columns = [str(c).strip() for c in source.columns]
    if source.empty:
        return empty_detail, empty_annual

    composite = source.columns[0]
    dimensions = _dimension_names_from_header(composite)
    long = pd.melt(source, id_vars=[composite], var_name='period', value_name='raw_value')
    split = long[composite].astype('string').str.split(',', expand=True)
    if split.shape[1] != len(dimensions):
        raise ValueError(f"Structure Eurostat trimestrielle inattendue dans {path.name}")
    split.columns = dimensions
    long = pd.concat([long.drop(columns=[composite]), split], axis=1)
    for col in dimensions:
        long[col] = long[col].astype('string').str.strip()
    if not {'freq', 'unit', 'geo'}.issubset(long.columns):
        raise ValueError(f"Dimensions trimestrielles incompletes dans {path.name}: {dimensions}")

    parsed_period = long['period'].astype('string').str.strip().str.extract(r'^(\d{4})-?Q([1-4])$')
    long['year'] = pd.to_numeric(parsed_period[0], errors='coerce')
    long['quarter'] = pd.to_numeric(parsed_period[1], errors='coerce')
    long['passengers'] = _normalise_pkm(_extract_numeric(long['raw_value']), long['unit'])
    long['country_code'] = long['geo'].map(_geo)
    long = long[
        long['freq'].str.upper().eq('Q')
        & long['year'].between(2010, 2024)
        & long['quarter'].between(1, 4)
        & long['passengers'].notna()
    ].copy()
    if long.empty:
        return empty_detail, empty_annual

    long['year'] = long['year'].astype(int)
    long['quarter'] = long['quarter'].astype(int)
    detail = long.groupby(
        ['country_code', 'year', 'quarter'], as_index=False
    )['passengers'].median()
    detail['country_name'] = detail['country_code'].map(COUNTRY_NAMES).fillna(detail['country_code'])
    detail['passenger_metric'] = 'MIO_PKM'
    detail['data_quality'] = 'observed_quarter'
    detail['data_source'] = 'eurostat_quarterly'

    complete_keys = (
        detail.groupby(['country_code', 'year'], as_index=False)['quarter'].nunique()
        .query('quarter == 4')[['country_code', 'year']]
    )
    annual = (
        detail.merge(complete_keys, on=['country_code', 'year'], how='inner')
        .groupby(['country_code', 'year'], as_index=False)['passengers'].sum()
    )
    annual['country_name'] = annual['country_code'].map(COUNTRY_NAMES).fillna(annual['country_code'])
    annual['passenger_metric'] = 'MIO_PKM'
    annual['data_quality'] = 'derived_four_quarters'
    annual['data_source'] = 'eurostat_quarterly'
    return detail, annual


def _build_traffic_canonical(detail: pd.DataFrame) -> pd.DataFrame:
    empty_cols = ['country_code','year','traffic','country_name','traffic_unit','data_quality']
    if detail.empty:
        return pd.DataFrame(columns=empty_cols)

    d = _filter_annual(detail)
    unit = d['unit'].astype('string').str.upper().str.strip()
    factor = pd.Series(np.nan, index=d.index, dtype=float)
    factor.loc[unit.eq('THS_TRKM')] = 1.0
    factor.loc[unit.str.contains(r'(?:MIO|MLN)_TRKM', regex=True, na=False)] = 1000.0
    factor.loc[unit.eq('TRKM')] = 0.001
    d['traffic'] = d['traffic_raw'] * factor
    d = d[d['traffic'].notna()].copy()
    if d.empty:
        return pd.DataFrame(columns=empty_cols)

    d = _prefer_total_dimensions(
        d,
        protected={'raw_value','year','traffic_raw','traffic','freq','unit','geo','country_name'}
    )

    canonical = (
        d.groupby(['geo','year','country_name'], as_index=False)['traffic']
        .median()
        .rename(columns={'geo':'country_code'})
    )
    canonical['traffic_unit'] = 'THS_TRKM'
    canonical = _interpolate_country_series(canonical, 'traffic')
    return canonical


def transform_eurostat(raw_dir: str, processed_dir: str) -> dict:
    logger.info("📊 Transformation Eurostat...")
    raw = Path(raw_dir) / 'eurostat'
    out = Path(processed_dir) / 'eurostat'
    out.mkdir(parents=True, exist_ok=True)

    passengers_path = raw / 'rail_passengers.csv'
    quarterly_path = raw / 'rail_passengers_quarterly.csv'
    traffic_path = raw / 'rail_traffic.csv'
    if not passengers_path.exists():
        raise FileNotFoundError(passengers_path)
    if not traffic_path.exists():
        raise FileNotFoundError(traffic_path)

    passengers_detail = _wide_to_long(passengers_path, 'passengers_raw')
    traffic_detail = _wide_to_long(traffic_path, 'traffic_raw')

    passengers_detail.to_csv(out / 'passengers_detailed_processed.csv', index=False)
    traffic_detail.to_csv(out / 'traffic_detailed_processed.csv', index=False)

    passengers, metric = _build_passenger_canonical(passengers_detail)
    quarterly_detail, quarterly_annual = _quarterly_to_annual(quarterly_path)
    quarterly_detail.to_csv(out / 'passengers_quarterly_detailed_processed.csv', index=False)
    quarterly_annual.to_csv(out / 'passengers_quarterly_annual_processed.csv', index=False)
    if not quarterly_annual.empty:
        annual_keys = set(zip(passengers['country_code'], passengers['year']))
        missing_annual = quarterly_annual[
            ~quarterly_annual.apply(
                lambda row: (row['country_code'], row['year']) in annual_keys,
                axis=1,
            )
        ]
        passengers = pd.concat([passengers, missing_annual], ignore_index=True)
    traffic = _build_traffic_canonical(traffic_detail)
    passengers.to_csv(out / 'passengers_processed.csv', index=False)
    traffic.to_csv(out / 'traffic_processed.csv', index=False)

    report = {
        'source':'eurostat',
        'passengers_detailed_records':int(len(passengers_detail)),
        'traffic_detailed_records':int(len(traffic_detail)),
        'passengers_records':int(len(passengers)),
        'passengers_quarterly_records':int(len(quarterly_detail)),
        'passengers_derived_from_four_quarters':int(len(quarterly_annual)),
        'traffic_records':int(len(traffic)),
        'passenger_metric':metric,
        'countries_passengers':int(passengers['country_code'].nunique()) if not passengers.empty else 0,
        'countries_traffic':int(traffic['country_code'].nunique()) if not traffic.empty else 0,
        'passengers_interpolated':int((passengers.get('data_quality') == 'interpolated').sum()) if not passengers.empty else 0,
        'traffic_interpolated':int((traffic.get('data_quality') == 'interpolated').sum()) if not traffic.empty else 0,
        'passenger_units_seen': sorted(passengers_detail['unit'].dropna().astype(str).unique().tolist())[:30] if not passengers_detail.empty else [],
    }
    logger.info(
        "✅ Eurostat : %s lignes détaillées passagers, %s trafic | canonique passagers=%s (%s)",
        f"{len(passengers_detail):,}", f"{len(traffic_detail):,}", f"{len(passengers):,}", metric,
    )
    return report
