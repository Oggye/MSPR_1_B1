"""Transformation robuste des émissions CO2 Eurostat ENV_AIR_GGE."""
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
    'RS':'Serbia','SE':'Sweden','SI':'Slovenia','SK':'Slovakia','TR':'Turkey','CY':'Cyprus'
}
TOTAL_SECTOR_PRIORITY = ['TOTAL', 'TOTX4_MEMO', 'TOTXMEMO', 'TOTX4_MEMONIA', 'TOTXMEMONIA']


def _geo(value):
    code = str(value).strip().upper()
    return {'UK':'GB','EL':'GR'}.get(code, code)


def _to_million_tonnes(value: pd.Series, unit: pd.Series) -> pd.Series:
    u = unit.astype('string').str.upper()
    factor = pd.Series(np.nan, index=value.index, dtype=float)
    factor.loc[u.eq('MIO_T')] = 1.0
    factor.loc[u.eq('THS_T')] = 0.001
    factor.loc[u.eq('T')] = 1e-6
    return value * factor


def transform_emissions(raw_dir: str, processed_dir: str) -> dict:
    logger.info("🌍 Transformation des émissions CO2...")
    path = Path(raw_dir) / 'emission_co2' / 'eurostat_env_air_gge_sdmx.csv'
    if not path.exists():
        raise FileNotFoundError(path)

    header = pd.read_csv(path, nrows=0).columns.tolist()
    wanted = [c for c in ['airpol','geo','TIME_PERIOD','OBS_VALUE','src_crf','unit','OBS_FLAG','CONF_STATUS'] if c in header]
    df = pd.read_csv(path, usecols=wanted, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[df['airpol'].astype('string').str.upper() == 'CO2'].copy()
    df['country_code'] = df['geo'].map(_geo)
    df['year'] = pd.to_numeric(df['TIME_PERIOD'], errors='coerce')
    df['co2_raw'] = pd.to_numeric(df['OBS_VALUE'], errors='coerce')
    df = df[df['year'].notna() & df['year'].between(2010, 2024)].copy()
    df['year'] = df['year'].astype(int)
    df['country_name'] = df['country_code'].map(COUNTRY_NAMES).fillna(df['country_code'])
    out = Path(processed_dir) / 'emissions'
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / 'co2_emissions_detailed_processed.csv', index=False)

    canonical = df.copy()
    if 'src_crf' in canonical.columns:
        chosen = None
        sectors = set(canonical['src_crf'].astype('string').str.upper().dropna())
        for sector in TOTAL_SECTOR_PRIORITY:
            if sector in sectors:
                chosen = sector
                break
        if chosen:
            canonical = canonical[canonical['src_crf'].astype('string').str.upper() == chosen].copy()
        else:
            logger.warning("Aucun total CRF standard trouvé ; agrégation prudente des lignes CO2 disponibles.")
    else:
        chosen = 'UNKNOWN'

    if 'unit' not in canonical.columns:
        canonical['unit'] = 'MIO_T'
    canonical['co2_emissions'] = _to_million_tonnes(canonical['co2_raw'], canonical['unit'])
    # Si une unité inconnue est rencontrée mais que les valeurs existent, on ne les mélange pas.
    canonical = canonical[canonical['co2_emissions'].notna()].copy()
    canonical = (
        canonical.groupby(['country_code','year','country_name'], as_index=False)['co2_emissions']
        .median()
    )
    canonical['co2_unit'] = 'MIO_T'
    canonical['source_sector'] = chosen

    # Interpolation uniquement entre deux observations existantes du même pays.
    frames = []
    for country, group in canonical.groupby('country_code', sort=False):
        g = group.sort_values('year').copy()
        observed = g['co2_emissions'].notna()
        g['co2_emissions'] = g['co2_emissions'].interpolate(method='linear', limit_area='inside')
        g['data_quality'] = np.where(observed, 'observed', np.where(g['co2_emissions'].notna(), 'interpolated', 'missing'))
        frames.append(g)
    canonical = pd.concat(frames, ignore_index=True) if frames else canonical
    canonical.to_csv(out / 'co2_emissions_processed.csv', index=False)

    report = {
        'source':'emissions',
        'detailed_co2_records':int(len(df)),
        'total_records':int(len(canonical)),
        'countries':int(canonical['country_code'].nunique()) if not canonical.empty else 0,
        'source_sector':chosen,
        'unit':'MIO_T',
        'missing_values_after':int(canonical['co2_emissions'].isna().sum()) if not canonical.empty else 0,
    }
    logger.info("✅ CO2 : %s lignes détaillées, %s lignes canoniques", f"{len(df):,}", f"{len(canonical):,}")
    return report
