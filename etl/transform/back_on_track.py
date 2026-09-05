"""
Transformation Back on Track.

Le fichier source conserve encore le champ historique `night_train`. Dans la
couche transformée ObRail, ce champ devient `train` et la nature jour/nuit est
portée uniquement par le booléen `is_night`.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_YEAR = 2024

COUNTRY_NAMES = {
    'AT':'Austria','BE':'Belgium','BG':'Bulgaria','HR':'Croatia','CY':'Cyprus','CZ':'Czech Republic',
    'DK':'Denmark','EE':'Estonia','FI':'Finland','FR':'France','DE':'Germany','GR':'Greece','HU':'Hungary',
    'IS':'Iceland','IE':'Ireland','IT':'Italy','LV':'Latvia','LI':'Liechtenstein','LT':'Lithuania',
    'LU':'Luxembourg','MT':'Malta','NL':'Netherlands','NO':'Norway','PL':'Poland','PT':'Portugal',
    'RO':'Romania','RS':'Serbia','SK':'Slovakia','SI':'Slovenia','ES':'Spain','SE':'Sweden','CH':'Switzerland',
    'TR':'Turkey','GB':'United Kingdom','UA':'Ukraine','MD':'Moldova','ME':'Montenegro','MK':'North Macedonia',
    'AL':'Albania','BA':'Bosnia and Herzegovina','XK':'Kosovo','BY':'Belarus'
}
THREE_TO_TWO = {
    'GBR':'GB','FRA':'FR','DEU':'DE','ITA':'IT','ESP':'ES','NLD':'NL','BEL':'BE','CHE':'CH','AUT':'AT','CZE':'CZ',
    'POL':'PL','SWE':'SE','NOR':'NO','DNK':'DK','FIN':'FI','PRT':'PT','GRC':'GR','HUN':'HU','ROU':'RO','BGR':'BG',
    'SRB':'RS','HRV':'HR','SVN':'SI','SVK':'SK','LTU':'LT','LVA':'LV','EST':'EE','TUR':'TR','UKR':'UA','BLR':'BY',
    'MDA':'MD','MNE':'ME','MKD':'MK','ALB':'AL','BIH':'BA','XKX':'XK','CYP':'CY','LUX':'LU','ISL':'IS','MLT':'MT'
}
CITY_COUNTRY = {
    'WIEN':'AT','VIENNA':'AT','SALZBURG':'AT','BERLIN':'DE','HAMBURG':'DE','MUNICH':'DE','MUENCHEN':'DE',
    'PARIS':'FR','LYON':'FR','ROMA':'IT','ROME':'IT','MILANO':'IT','MADRID':'ES','BARCELONA':'ES',
    'LONDON':'GB','AMSTERDAM':'NL','BRUSSELS':'BE','BRUXELLES':'BE','PRAGUE':'CZ','PRAHA':'CZ','BUDAPEST':'HU',
    'WARSAW':'PL','WARSZAWA':'PL','STOCKHOLM':'SE','OSLO':'NO','HELSINKI':'FI','COPENHAGEN':'DK','KOBENHAVN':'DK',
    'ZURICH':'CH','GENEVA':'CH','ATHENS':'GR','LISBON':'PT','LISBOA':'PT','DUBLIN':'IE','BUCHAREST':'RO',
    'BUCURESTI':'RO','SOFIA':'BG','ZAGREB':'HR','BELGRADE':'RS','BEOGRAD':'RS','VILNIUS':'LT','RIGA':'LV',
    'TALLINN':'EE','ISTANBUL':'TR','KYIV':'UA','KIEV':'UA','BRATISLAVA':'SK','LJUBLJANA':'SI','TIRANA':'AL',
    'PODGORICA':'ME','SKOPJE':'MK','SARAJEVO':'BA','MINSK':'BY','CHISINAU':'MD','LUXEMBOURG':'LU'
}


def _normalise_country_code(value: str) -> str | None:
    if value is None or pd.isna(value):
        return None
    code = re.sub(r'[^A-Z]', '', str(value).upper())
    if code == 'UK':
        return 'GB'
    if code == 'EL':
        return 'GR'
    if code in THREE_TO_TWO:
        return THREE_TO_TWO[code]
    if len(code) == 2 and code in COUNTRY_NAMES:
        return code
    return None


def extract_country_code_enhanced(route_name, itinerary, countries_field, route_long_name=None):
    # 1) champ countries, le plus fiable
    if pd.notna(countries_field) and str(countries_field).strip():
        tokens = re.split(r'[,;/|\s]+', str(countries_field))
        for token in tokens:
            code = _normalise_country_code(token)
            if code:
                return code

    text = ' '.join(str(v) for v in [route_name, itinerary, route_long_name] if pd.notna(v)).upper()
    padded = f' {text} '

    # 2) codes ISO explicites
    for code in COUNTRY_NAMES:
        if re.search(rf'(?<![A-Z]){re.escape(code)}(?![A-Z])', padded):
            return code

    # 3) noms de pays
    for code, name in COUNTRY_NAMES.items():
        if name.upper() in padded:
            return code

    # 4) villes connues
    for city, code in CITY_COUNTRY.items():
        if city in padded:
            return code
    return 'UNKNOWN'


def _extract_year(*values) -> int:
    for value in values:
        if pd.isna(value):
            continue
        match = re.search(r'20(?:1\d|2\d)', str(value))
        if match:
            return int(match.group())
    return BASE_YEAR


def transform_back_on_track(raw_dir: str, processed_dir: str) -> dict:
    logger.info("🚂 Transformation Back on Track...")
    raw = Path(raw_dir) / "back_on_track"
    out = Path(processed_dir) / "back_on_track"
    out.mkdir(parents=True, exist_ok=True)

    cities_path = raw / "view_ontd_cities.csv"
    cities_df = pd.read_csv(cities_path, low_memory=False) if cities_path.exists() else pd.DataFrame()
    if not cities_df.empty:
        cities_df.columns = [str(c).strip().lower() for c in cities_df.columns]
        if 'stop_id' in cities_df.columns:
            cities_df['stop_id'] = cities_df['stop_id'].astype('string').str.strip()
        if 'stop_cityname_romanized' not in cities_df.columns:
            cities_df['stop_cityname_romanized'] = 'Inconnu'
        cities_df['stop_cityname_romanized'] = cities_df['stop_cityname_romanized'].astype('string').fillna('Inconnu')
        if 'stop_country' not in cities_df.columns:
            cities_df['stop_country'] = 'UNKNOWN'
        cities_df['stop_country'] = cities_df['stop_country'].astype('string').fillna('UNKNOWN').str.upper().str.strip()
        cities_df['country_code'] = cities_df['stop_country'].map(lambda x: _normalise_country_code(x) or 'UNKNOWN')
        cities_df['country_name'] = cities_df['country_code'].map(COUNTRY_NAMES).fillna('Unknown Country')
        cities_df.to_csv(out / "cities_processed.csv", index=False)

    trains_path = raw / "view_ontd_list.csv"
    if not trains_path.exists():
        raise FileNotFoundError(trains_path)
    trains = pd.read_csv(trains_path, low_memory=False)
    trains.columns = [str(c).strip().lower() for c in trains.columns]

    if 'night_train' in trains.columns:
        trains = trains.rename(columns={'night_train': 'train'})
    if 'train' not in trains.columns:
        trains['train'] = trains.get('route_long_name', 'Train de nuit')
    trains['train'] = trains['train'].astype('string').fillna('Train de nuit').str.strip().str.slice(0, 300)

    if 'route_id' not in trains.columns:
        trains['route_id'] = [f"BOT-{i+1}" for i in range(len(trains))]
    trains['route_id'] = trains['route_id'].astype('string').str.strip()

    if 'operators' not in trains.columns:
        trains['operators'] = 'Opérateur inconnu'
    trains['operators'] = trains['operators'].astype('string').fillna('Opérateur inconnu').str.strip()

    trains['year'] = trains.apply(
        lambda r: _extract_year(r.get('train'), r.get('route_long_name'), r.get('source')),
        axis=1,
    )
    trains['country_code'] = trains.apply(
        lambda r: extract_country_code_enhanced(
            r.get('train', ''), r.get('itinerary', ''), r.get('countries', ''), r.get('route_long_name', '')
        ),
        axis=1,
    )
    trains['country_name'] = trains['country_code'].map(COUNTRY_NAMES).fillna('Unknown Country')
    trains['is_night'] = True
    trains['is_synthetic'] = False
    trains['data_source'] = 'back_on_track'
    if 'itinerary' not in trains.columns:
        trains['itinerary'] = trains['train']
    trains['itinerary'] = trains['itinerary'].astype('string').fillna(trains['train']).str.strip()
    trains = trains[trains['year'] >= 2010].drop_duplicates().reset_index(drop=True)
    trains.insert(0, 'source_fact_id', range(1, len(trains) + 1))

    trains.to_csv(out / "trains_processed.csv", index=False)
    counts = trains['country_code'].value_counts()
    report = {
        'source': 'back_on_track',
        'cities_total': int(len(cities_df)),
        'trains_total': int(len(trains)),
        'countries_covered': int(trains['country_code'].nunique()),
        'unknown_countries': int((trains['country_code'] == 'UNKNOWN').sum()),
        'years_range': [int(trains['year'].min()), int(trains['year'].max())] if not trains.empty else [],
        'country_distribution': {str(k): int(v) for k, v in counts.head(20).items()},
    }
    logger.info("✅ Back on Track : %s trains, %s pays", f"{len(trains):,}", report['countries_covered'])
    return report
