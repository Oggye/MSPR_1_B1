"""
ETL/main_etl.py
Pipeline ETL principal – ObRail Europe (MSPR E6.1)
Version complète avec transformation et chargement intégrée 
"""

import time
from datetime import datetime
import sys
from pathlib import Path


# --- EXTRACTION ---
try:
    # Import des modules d'extraction depuis le dossier extract/
    from extract.extract_gtfs_fr import extract_gtfs_fr
    from extract.extract_eurostat import extract_eurostat
    from extract.extract_back_on_track_eu import extract_back_on_track
    from extract.extract_gtfs_ch import extract_gtfs_ch
    from extract.extract_gtfs_de import extract_gtfs_de
    from extract.extract_gtfs_es import extract_gtfs_es
    from extract.extract_gtfs_lu import extract_gtfs_lu
    from extract.extract_gtfs_at import extract_gtfs_at
    from extract.extract_gtfs_be import extract_gtfs_be
    from extract.extract_unece import extract_unece
    from extract.extract_oecd_itf import extract_oecd_itf
    from extract.extract_emission_co2 import download_eurostat_via_api
except ImportError as e:
    print(f"⚠️  Modules d'extraction non trouvés: {e}")
    print("📥 Exécute d'abord les scripts d'extraction séparément si besoin")

# --- TRANSFORMATION ---
try:
    # Import du pipeline de transformation principal
    from transform.main_transform import main_transform_pipeline
except ImportError as e:
    print(f"⚠️  Modules de transformation non trouvés: {e}")

# --- CHARGEMENT ---
try:
    # Import des modules de chargement depuis le dossier load/
    from load.main_load import mainload
    from load.database import db
except ImportError as e:
    print(f"❌ Module de chargement non trouvé: {e}")
    print("\n💡 SOLUTIONS:")
    print("1. Exécutez directement: python load/main_load.py")
    print("2. Vérifiez que database.py est dans le répertoire load/")

def run_extraction():
    """Exécute uniquement la phase d'extraction"""
    print("📥 PHASE 1 : EXTRACTION")
    print("-" * 40)
    
    # Liste des extracteurs avec leur nom et fonction associée
    extractors = [
        ("GTFS France", extract_gtfs_fr),
        ("GTFS Allemagne", extract_gtfs_de),
        ("GTFS Suisse", extract_gtfs_ch),

        # Nouvelle couverture européenne
        ("GTFS Espagne", extract_gtfs_es),
        ("GTFS Luxembourg", extract_gtfs_lu),
        ("GTFS Autriche 2024", extract_gtfs_at),
        ("GTFS Belgique 2024 (archive publique SNCB)", extract_gtfs_be),

        ("Eurostat (trafic ferroviaire)", extract_eurostat),
        ("UNECE (passenger-km ferroviaires)", extract_unece),
        ("OECD / ITF (passenger-km ferroviaires)", extract_oecd_itf),
        ("Back on Track EU", extract_back_on_track),
        ("Émissions CO2", download_eurostat_via_api),
    ]
    
    # Exécution séquentielle de chaque extracteur
    for name, func in extractors:
        print(f"📄 Extraction de {name}...")
        try:
            func()
            print(f"✅ {name} extrait avec succès")
        except Exception as e:
            print(f"❌ Erreur lors de l'extraction de {name}: {e}")
        print()
    
    print("✅ Extraction terminée")

def run_transformation():
    """Exécute uniquement la phase de transformation"""
    print("\n🔄 PHASE 2 : TRANSFORMATION")
    print("-" * 40)
    
    try:
        main_transform_pipeline()
        print("✅ Transformation terminée avec succès")
    except Exception as e:
        print(f"❌ Erreur lors de la transformation: {e}")

def run_chargement():
    """Chargement dans PostgreSQL"""
    print("\n💾 PHASE 3 : CHARGEMENT OBRAIL EUROPE")
    print("-" * 40)
    
    try:
        mainload()
        print("\n✅ Chargement complet terminé!")
    except Exception as e:
        print(f"❌ Erreur lors du Chargement: {e}")

def run_full_etl():
    """Exécute le pipeline ETL complet"""
    print("🚀 LANCEMENT DU PIPELINE ETL COMPLET")
    print(f"Date et heure : {datetime.now()}")
    print("=" * 60)
    
    # EXTRACTION
    run_extraction()
    
    # TRANSFORMATION
    run_transformation()
    
    # CHARGEMENT
    run_chargement()
    
    print("\n" + "=" * 60)
    print("🎉 PIPELINE ETL TERMINÉ AVEC SUCCÈS !")
    print("=" * 60)


def show_menu():
    """Affiche un menu interactif"""
    print("\n" + "=" * 60)
    print("PIPELINE ETL - OBRAIL EUROPE")
    print("=" * 60)
    print("1. 🚀 Exécuter le pipeline complet (Extraction + Transformation + Chargement)")
    print("2. 📥 Exécuter uniquement l'extraction")
    print("3. 🔄 Exécuter uniquement la transformation")
    print("4. 💾 Exécuter uniquement du chargement dans PostgreSQL")
    print("5. 📊 Voir l'état des données ")
    print("6. ❌ Quitter")
    print("=" * 60)
    
    choice = input("👉 Ton choix (1-5): ").strip()
    
    if choice == "1":
        run_full_etl()
    elif choice == "2":
        run_extraction()
    elif choice == "3":
        run_transformation()
    elif choice == "4":
        run_chargement()
    elif choice == "5":
        show_data_status()
    elif choice == "6":
        print("👋 Au revoir!")
        sys.exit(0)
    else:
        print("❌ Choix invalide")
    
    input("\n↵ Appuie sur Entrée pour continuer...")
    show_menu()

def show_data_status():
    """Affiche l'état des données et vérifie l'état de la base de données"""
    BASE_DIR = Path(__file__).parent.parent
    
    print("\n📊 ÉTAT DES DONNÉES")
    print("-" * 40)
    
    # Vérification des fichiers dans data/raw
    raw_dir = BASE_DIR / "data" / "raw"
    if raw_dir.exists():
        raw_files = list(raw_dir.rglob("*.csv"))
        print(f"📁 Données brutes ({raw_dir}):")
        print(f"   📄 {len(raw_files)} fichiers CSV trouvés")
        for source in raw_dir.iterdir():
            if source.is_dir():
                csv_count = len(list(source.glob("*.csv")))
                if csv_count > 0:
                    print(f"   ├─ {source.name}: {csv_count} fichiers")
    else:
        print("📁 Données brutes: ❌ Répertoire non trouvé")
    
    # Vérification des fichiers dans data/processed
    processed_dir = BASE_DIR / "data" / "processed"
    if processed_dir.exists():
        processed_files = list(processed_dir.rglob("*.csv"))
        print(f"\n📁 Données transformées ({processed_dir}):")
        print(f"   📄 {len(processed_files)} fichiers CSV trouvés")
    else:
        print("\n📁 Données transformées: ❌ Répertoire non trouvé")
    
    # Vérification des fichiers dans data/warehouse
    warehouse_dir = BASE_DIR / "data" / "warehouse"
    if warehouse_dir.exists():
        warehouse_files = list(warehouse_dir.glob("*.csv"))
        print(f"\n📁 Data warehouse ({warehouse_dir}):")
        print(f"   📄 {len(warehouse_files)} fichiers CSV trouvés")
        for file in warehouse_files:
            print(f"   ├─ {file.name}")
    else:
        print("\n📁 Data warehouse: ❌ Répertoire non trouvé")

    print("\n🔍 État de la base de données:")
    print("-" * 40)
    
    if not db.connect():
        print("❌ Impossible de se connecter à la base de données")
        return
    
    try:
        # 1. Comptage des lignes dans chaque table
        print("\n📊 NOMBRE D'ENREGISTREMENTS:")

        queries = [
            ("dim_countries", "SELECT COUNT(*) FROM dim_countries"),
            ("dim_years", "SELECT COUNT(*) FROM dim_years"),
            ("dim_operators", "SELECT COUNT(*) FROM dim_operators"),
            ("facts_night_trains", "SELECT COUNT(*) FROM facts_night_trains"),
            ("facts_country_stats", "SELECT COUNT(*) FROM facts_country_stats"),
        ]

        for table_name, query in queries:
            db.cursor.execute(query)
            count = db.cursor.fetchone()[0]
            print(f"   📊 {table_name}: {count} lignes")


        # 2. Jointures entre tables
        print("\n🔗 TEST DES JOINTURES:")
        
        # Vérification des liens entre tables
        tests_jointures = [
            ("Operateurs - Night Trains", """
                SELECT COUNT(*) 
                FROM facts_night_trains ft
                LEFT JOIN dim_operators dop ON ft.operator_id = dop.operator_id
                WHERE dop.operator_id IS NULL
            """),
            ("Pays - Night Trains", """
                SELECT COUNT(*) 
                FROM facts_night_trains ft
                LEFT JOIN dim_countries dc ON ft.country_id = dc.country_id
                WHERE dc.country_id IS NULL
            """),
            ("Années - Night Trains", """
                SELECT COUNT(*) 
                FROM facts_night_trains ft
                LEFT JOIN dim_years dy ON ft.year_id = dy.year_id
                WHERE dy.year_id IS NULL
            """),
            ("Pays - Country Stats", """
                SELECT COUNT(*) 
                FROM facts_country_stats fcs
                LEFT JOIN dim_countries dc ON fcs.country_id = dc.country_id
                WHERE dc.country_id IS NULL
            """),
            ("Années - Country Stats", """
                SELECT COUNT(*) 
                FROM facts_country_stats fcs
                LEFT JOIN dim_years dy ON fcs.year_id = dy.year_id
                WHERE dy.year_id IS NULL
            """)
        ]
        
        erreurs_total = 0
        for nom, query in tests_jointures:
            db.cursor.execute(query)
            count = db.cursor.fetchone()[0]
            if count == 0:
                print(f"   ✅ {nom}: Aucun problème ({count})")
            else:
                print(f"   ❌ {nom}: {count} erreur(s) de référence")
                erreurs_total += count

        # Vérification spécifique pour facts_night_trainss
        db.cursor.execute("""
            SELECT COUNT(*) 
            FROM facts_night_trains ft
            WHERE ft.operator_id IS NOT NULL 
                AND ft.country_id IS NOT NULL 
                AND ft.year_id IS NOT NULL
        """)
        total_complets_night = db.cursor.fetchone()[0]
        db.cursor.execute("SELECT COUNT(*) FROM facts_night_trains")
        total_night = db.cursor.fetchone()[0]

        erreurs_night = total_night - total_complets_night
        if erreurs_night == 0:
            print(f"✅ Tous les {total_night} trajets de nuit ont des opérateurs, pays et années valides")
        else:
            print(f"❌ {erreurs_night}/{total_night} trajets de nuit ont des références manquantes")
                
        # Vérification spécifique pour facts_country_stats
        db.cursor.execute("""
            SELECT COUNT(*) 
            FROM facts_country_stats fcs
            WHERE fcs.country_id IS NOT NULL 
            AND fcs.year_id IS NOT NULL
        """)
        total_complets_stats = db.cursor.fetchone()[0]
        db.cursor.execute("SELECT COUNT(*) FROM facts_country_stats")
        total_stats = db.cursor.fetchone()[0]
        
        erreurs_stats = total_stats - total_complets_stats
        if erreurs_stats == 0:
            print(f"✅ Toutes les {total_stats} statistiques ont des pays et années valides")
        else:
            print(f"❌ {erreurs_stats}/{total_stats} statistiques ont des références manquantes")


        # 3. Affichage de la vue Dashboard
        print("\n📊 DONNÉES DE LA VUE DASHBOARD_METRICS:")
        
        # Structure de la vue
        db.cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'dashboard_metrics'
            ORDER BY ordinal_position
        """)
        print("   Structure de la vue dashboard_metrics:")
        for col in db.cursor.fetchall():
            nom_colonne = col[0]
            type_colonne = col[1]
            print(f"   - {nom_colonne} ({type_colonne})")
        
        # Afficher les premières lignes de la vue
        db.cursor.execute("""
            SELECT 
                country_name,
                country_code,
                ROUND(avg_passengers, 2) as avg_passengers,
                ROUND(avg_co2_emissions, 2) as avg_co2_emissions,
                ROUND(avg_co2_per_passenger, 4) as avg_co2_per_passenger
            FROM dashboard_metrics
            ORDER BY country_name
            LIMIT 10
        """)

        print("\n📋 Échantillon des données (10 premières lignes):")
        for row in db.cursor.fetchall():
            print(f"   Pays: {row[0]} ({row[1]}) | "
                f"Passagers moy: {row[2]:.0f} | "
                f"CO2 moy: {row[3]:,.2f} t | "
                f"CO2/passager: {row[4]:.4f} t")

        # Nombre total de pays dans la vue
        db.cursor.execute("SELECT COUNT(*) FROM dashboard_metrics")
        nb_pays = db.cursor.fetchone()[0]
        print(f"\n🌍 Nombre de pays en total dans la vue: {nb_pays}")
        
    finally:
        db.close()


if __name__ == "__main__":
    # Exécuter le menu interactif
    show_menu()
    # Alternative: run_full_etl() pour exécution directe
