"""Orchestrateur de transformation ObRail Europe."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from etl.transform.back_on_track import transform_back_on_track
from etl.transform.eurostat import transform_eurostat
from etl.transform.emissions import transform_emissions
from etl.transform.unece import transform_unece
from etl.transform.oecd_itf import transform_oecd_itf
from etl.transform.gtfs import transform_all_gtfs
from etl.transform.enrichment import enrich_and_prepare_for_warehouse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, np.bool_): return bool(obj)
        return super().default(obj)


def _native(obj):
    if isinstance(obj, dict): return {k:_native(v) for k,v in obj.items()}
    if isinstance(obj, list): return [_native(v) for v in obj]
    if isinstance(obj, tuple): return [_native(v) for v in obj]
    if isinstance(obj, np.integer): return int(obj)
    if isinstance(obj, np.floating): return float(obj)
    if isinstance(obj, np.bool_): return bool(obj)
    return obj


def _csv_row_count(path: Path) -> int:
    try:
        with path.open('rb') as handle:
            return max(0, sum(1 for _ in handle) - 1)
    except OSError:
        return 0


def main_transform_pipeline():
    logger.info("🚀 Démarrage du pipeline de transformation ETL")
    base_dir = Path(__file__).resolve().parents[2]
    raw_dir = base_dir / 'data' / 'raw'
    processed_dir = base_dir / 'data' / 'processed'
    warehouse_dir = base_dir / 'data' / 'warehouse'
    if not raw_dir.exists():
        raise FileNotFoundError(f"Répertoire raw absent : {raw_dir}")
    processed_dir.mkdir(parents=True, exist_ok=True)
    warehouse_dir.mkdir(parents=True, exist_ok=True)

    reports = []
    stages = [
        ('BACK ON TRACK', lambda: transform_back_on_track(str(raw_dir), str(processed_dir))),
        ('EUROSTAT', lambda: transform_eurostat(str(raw_dir), str(processed_dir))),
        ('UNECE', lambda: transform_unece(str(raw_dir), str(processed_dir))),
        ('OECD / ITF', lambda: transform_oecd_itf(str(raw_dir), str(processed_dir))),
        ('ÉMISSIONS CO2', lambda: transform_emissions(str(raw_dir), str(processed_dir))),
    ]
    for title, func in stages:
        print('\n' + '='*70 + f'\nTRANSFORMATION {title}\n' + '='*70)
        report = func()
        if report: reports.append(_native(report))

    print('\n' + '='*70 + '\nTRANSFORMATION GTFS (FR, CH, DE, ES, LU, AT, BE)\n' + '='*70)
    gtfs_reports = transform_all_gtfs(str(raw_dir), str(processed_dir))
    reports.extend(_native(r) for r in gtfs_reports if r)

    print('\n' + '='*70 + '\nENRICHISSEMENT ET PRÉPARATION DATA WAREHOUSE\n' + '='*70)
    traceability = _native(enrich_and_prepare_for_warehouse(str(processed_dir), str(warehouse_dir)))

    quality = {
        'execution_date':datetime.now().isoformat(),
        'project':'ObRail Europe - MSPR E6.1',
        'reports':reports,
        'traceability':traceability,
        'summary':{
            'total_sources_processed':len(reports),
            'success':True,
        },
    }
    with (warehouse_dir / 'quality_reports.json').open('w', encoding='utf-8') as handle:
        json.dump(quality, handle, indent=2, ensure_ascii=False, cls=NumpyEncoder)

    print('\n' + '='*70)
    print('[OK] PIPELINE DE TRANSFORMATION TERMINÉ AVEC SUCCÈS')
    print('='*70)
    dq = traceability.get('data_quality', {})
    print(f"Trains total      : {dq.get('total_train_records', 0):,}")
    print(f"GTFS réels        : {dq.get('real_gtfs_records', 0):,}")
    print(f"Back on Track     : {dq.get('back_on_track_records', 0):,}")
    print(f"Synthétiques      : {dq.get('synthetic_records', 0):,}")
    print(f"Jour              : {dq.get('day_train_records', 0):,}")
    print(f"Nuit              : {dq.get('night_train_records', 0):,}")

    print('\n📁 DATA WAREHOUSE')
    for path in sorted(warehouse_dir.glob('*.csv')):
        # Comptage ligne à ligne : ne recharge jamais plusieurs millions de lignes en RAM.
        print(f"  {path.name:<36} {_csv_row_count(path):>12,} lignes")
    for path in sorted(warehouse_dir.glob('*.json')):
        print(f"  {path.name}")
    return quality


if __name__ == '__main__':
    main_transform_pipeline()
