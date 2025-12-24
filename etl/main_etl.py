# =========================================================
# etl/main_etl.py
# Pipeline ETL principal – ObRail Europe (MSPR E6.1)
# =========================================================

from extract.extract_gtfs_fr import extract_gtfs
from extract.extract_eurostat import extract_eurostat
from extract.extract_back_on_track_eu import extract_back_on_track

def run_etl():
    print("🚆 DÉMARRAGE DU PIPELINE ETL – ObRail Europe")

    # -----------------------------
    print("\n[1/3] Extraction GTFS France (SNCF)")
    extract_gtfs()

    # -----------------------------
    print("\n[2/3] Extraction Eurostat (trafic et passagers)")
    extract_eurostat()

    # -----------------------------
    print("\n[3/3] Extraction Back-on-Track Europe (trains de nuit & villes)")
    extract_back_on_track()

    print("\n✅ EXTRACTION TERMINÉE – Données disponibles dans data/raw/")
    print("📁 Structure recommandée :")
    print("""
data/raw/
├── gtfs_fr/
├── eurostat/
└── back_on_track/
    """)

if __name__ == "__main__":
    run_etl()
