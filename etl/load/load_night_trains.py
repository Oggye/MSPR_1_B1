"""Chargement streaming de facts_night_trains (nom de table legacy)."""
import pandas as pd
from .database import db


def load_night_trains():
    path = 'data/warehouse/facts_night_trains.csv'
    if not db.truncate_table('facts_night_trains'):
        return False
    total = 0
    for chunk in pd.read_csv(path, chunksize=100_000, low_memory=False):
        if not db.insert_dataframe(chunk, 'facts_night_trains', page_size=10_000):
            return False
        total += len(chunk)
        print(f"   ↳ {total:,} trajets chargés")
    print(f"✅ {total:,} trajets chargés avec succès")
    return True
