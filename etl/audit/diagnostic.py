# =========================================================
# etl/audit/diagnostic_complet.py
# Diagnostic automatique complet du pipeline ETL ObRail
# Vérifie : données brutes, données transformées, data warehouse
# =========================================================

import pandas as pd
from pathlib import Path
import glob
import sys
import os
from datetime import datetime

# Chemins de base
BASE_DIR = Path(__file__).parent.parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
WAREHOUSE_DIR = BASE_DIR / "data" / "warehouse"

def lister_sources_raw():
    """Retourne les sources RAW reellement presentes sur disque."""
    if not RAW_DIR.exists():
        return {}
    return {
        dossier.name: dossier
        for dossier in sorted(RAW_DIR.iterdir())
        if dossier.is_dir()
    }

def compter_lignes_csv(chemin):
    """Compte les lignes d'un CSV de manière efficace"""
    try:
        lignes = 0
        dernier_octet = b''
        with open(chemin, 'rb') as f:
            for bloc in iter(lambda: f.read(1024 * 1024), b''):
                lignes += bloc.count(b'\n')
                dernier_octet = bloc[-1:]
        if dernier_octet and dernier_octet != b'\n':
            lignes += 1
        return max(lignes - 1, 0)  # -1 pour l'en-tête
    except:
        return None

def analyser_fichier_csv(chemin, nrows=10):
    """Analyse un fichier CSV et retourne ses informations"""
    result = {
        'nom': Path(chemin).name,
        'chemin': str(chemin),
        'existe': True,
        'lignes': 0,
        'colonnes': 0,
        'colonnes_noms': [],
        'taille_kb': 0,
        'apercu': None,
        'erreur': None
    }
    
    try:
        result['taille_kb'] = Path(chemin).stat().st_size / 1024
        result['lignes'] = compter_lignes_csv(chemin)
        
        # Lire l'aperçu
        df = pd.read_csv(chemin, nrows=nrows, low_memory=False)
        result['colonnes'] = len(df.columns)
        result['colonnes_noms'] = df.columns.tolist()
        result['apercu'] = df.head(nrows)
        
    except Exception as e:
        result['erreur'] = str(e)[:100]
        
    return result

def diagnostiquer_raw():
    """Diagnostic des données brutes (raw)"""
    print("\n" + "="*70)
    print("📥 PHASE 1 : DONNÉES BRUTES (RAW)")
    print("="*70)
    
    stats_raw = {}
    total_fichiers = 0
    total_lignes = 0
    
    for source, dossier in lister_sources_raw().items():
        print(f"\n📁 {source.upper()}")
        print("-" * 50)
        
        if not dossier.exists():
            print(f"   ❌ Dossier introuvable : {dossier}")
            stats_raw[source] = {'fichiers': 0, 'lignes': 0, 'erreur': 'Dossier manquant'}
            continue
        
        fichiers_csv = list(dossier.glob("*.csv")) + list(dossier.glob("*.tsv"))
        stats_raw[source] = {'fichiers': len(fichiers_csv), 'lignes': 0, 'details': []}
        
        for fichier in sorted(fichiers_csv):
            result = analyser_fichier_csv(fichier, nrows=3)
            total_fichiers += 1
            
            if result['erreur']:
                print(f"   ⚠️  {result['nom']} : ERREUR - {result['erreur']}")
                stats_raw[source]['details'].append(result)
            else:
                total_lignes += result['lignes']
                stats_raw[source]['lignes'] += result['lignes']
                print(f"   ✅ {result['nom']:<35} {result['lignes']:>10,} lignes | {result['colonnes']} colonnes | {result['taille_kb']:>8.1f} KB")
                stats_raw[source]['details'].append(result)
    
    print(f"\n📊 TOTAL RAW : {total_fichiers} fichiers, {total_lignes:,} lignes")
    return stats_raw

def diagnostiquer_processed():
    """Diagnostic des données transformées (processed) - version récursive"""
    print("\n" + "="*70)
    print("🔄 PHASE 2 : DONNÉES TRANSFORMÉES (PROCESSED)")
    print("="*70)
    
    stats_processed = {}
    total_fichiers = 0
    total_lignes = 0
    
    if not PROCESSED_DIR.exists():
        print("   ❌ Dossier processed introuvable")
        return stats_processed
    
    # Parcourir récursivement tous les sous-dossiers
    for source_dir in sorted(PROCESSED_DIR.iterdir()):
        if source_dir.is_dir():
            source_name = source_dir.name
            
            # Récupérer TOUS les CSV, y compris dans les sous-dossiers
            fichiers_csv = list(source_dir.rglob("*.csv"))
            
            if not fichiers_csv:
                # Vérifier les sous-dossiers
                for sub_dir in source_dir.iterdir():
                    if sub_dir.is_dir():
                        sub_files = list(sub_dir.glob("*.csv"))
                        if sub_files:
                            sous_source = f"{source_name}/{sub_dir.name}"
                            print(f"\n📁 {sous_source.upper()}")
                            print("-" * 50)
                            
                            stats_processed[sous_source] = {'fichiers': len(sub_files), 'lignes': 0, 'details': []}
                            
                            for fichier in sorted(sub_files):
                                result = analyser_fichier_csv(fichier, nrows=3)
                                total_fichiers += 1
                                
                                if result['erreur']:
                                    print(f"   ⚠️  {result['nom']} : ERREUR - {result['erreur']}")
                                else:
                                    total_lignes += result['lignes']
                                    stats_processed[sous_source]['lignes'] += result['lignes']
                                    print(f"   ✅ {result['nom']:<35} {result['lignes']:>10,} lignes | {result['colonnes']} colonnes | {result['taille_kb']:>8.1f} KB")
                                    stats_processed[sous_source]['details'].append(result)
                continue
            
            print(f"\n📁 {source_name.upper()}")
            print("-" * 50)
            
            stats_processed[source_name] = {'fichiers': len(fichiers_csv), 'lignes': 0, 'details': []}
            
            for fichier in sorted(fichiers_csv):
                result = analyser_fichier_csv(fichier, nrows=3)
                total_fichiers += 1
                
                if result['erreur']:
                    print(f"   ⚠️  {result['nom']} : ERREUR - {result['erreur']}")
                else:
                    total_lignes += result['lignes']
                    stats_processed[source_name]['lignes'] += result['lignes']
                    print(f"   ✅ {result['nom']:<35} {result['lignes']:>10,} lignes | {result['colonnes']} colonnes | {result['taille_kb']:>8.1f} KB")
                    stats_processed[source_name]['details'].append(result)
    
    print(f"\n📊 TOTAL PROCESSED : {total_fichiers} fichiers, {total_lignes:,} lignes")
    return stats_processed

def diagnostiquer_warehouse():
    """Diagnostic du data warehouse"""
    print("\n" + "="*70)
    print("💾 PHASE 3 : DATA WAREHOUSE")
    print("="*70)
    
    stats_warehouse = {
        'dimensions': [],
        'faits': [],
        'dashboard': [],
        'autres': []
    }
    
    if not WAREHOUSE_DIR.exists():
        print("   ❌ Dossier warehouse introuvable")
        return stats_warehouse
    
    fichiers_csv = sorted(WAREHOUSE_DIR.glob("*.csv"))
    fichiers_json = sorted(WAREHOUSE_DIR.glob("*.json"))
    fichiers_sql = sorted(WAREHOUSE_DIR.glob("*.sql"))
    
    # Classifier les fichiers
    for fichier in fichiers_csv:
        nom = fichier.name.lower()
        result = analyser_fichier_csv(fichier, nrows=5)
        
        if nom.startswith('dim_'):
            stats_warehouse['dimensions'].append(result)
        elif nom.startswith('facts_'):
            stats_warehouse['faits'].append(result)
        elif 'dashboard' in nom or 'operator' in nom:
            stats_warehouse['dashboard'].append(result)
        else:
            stats_warehouse['autres'].append(result)
    
    # Affichage
    categories = [
        ("📐 DIMENSIONS", stats_warehouse['dimensions']),
        ("📊 FAITS", stats_warehouse['faits']),
        ("📈 DASHBOARD", stats_warehouse['dashboard']),
        ("📄 AUTRES", stats_warehouse['autres']),
    ]
    
    total_lignes = 0
    for titre, fichiers in categories:
        if fichiers:
            print(f"\n{titre}")
            print("-" * 50)
            for result in fichiers:
                total_lignes += result['lignes']
                status = "✅" if not result['erreur'] else "⚠️"
                print(f"   {status} {result['nom']:<35} {result['lignes']:>10,} lignes | {result['colonnes']} colonnes | {result['taille_kb']:>8.1f} KB")
                
                # Afficher les colonnes
                if result['colonnes_noms']:
                    print(f"      Colonnes : {', '.join(result['colonnes_noms'][:8])}", end="")
                    if len(result['colonnes_noms']) > 8:
                        print(f" (+ {len(result['colonnes_noms']) - 8} autres)")
                    else:
                        print()
    
    # Fichiers non-CSV
    if fichiers_json or fichiers_sql:
        print(f"\n📋 AUTRES FICHIERS")
        print("-" * 50)
        for f in fichiers_json:
            taille = f.stat().st_size / 1024
            print(f"   📋 {f.name:<35} {taille:>8.1f} KB")
        for f in fichiers_sql:
            taille = f.stat().st_size / 1024
            print(f"   📜 {f.name:<35} {taille:>8.1f} KB")
    
    print(f"\n📊 TOTAL WAREHOUSE : {len(fichiers_csv)} fichiers CSV, {total_lignes:,} lignes")
    return stats_warehouse

def verifier_coherence(raw_stats, processed_stats, warehouse_stats):
    """Vérifie la cohérence entre les phases du pipeline"""
    print("\n" + "="*70)
    print("🔍 VÉRIFICATION DE COHÉRENCE")
    print("="*70)
    
    alerts = []
    checks = []
    
    # Vérifier que les données raw ont bien été transformées
    sources_raw = set(raw_stats.keys())
    sources_processed = set(processed_stats.keys())
    
    for source in sources_raw:
        if source in ['back_on_track', 'eurostat', 'emission_co2']:
            source_name = source.replace('_', ' ')
            if source not in sources_processed and source != 'emission_co2':
                alerts.append(f"⚠️  {source} : présent en raw mais absent en processed")
            elif source == 'emission_co2' and 'emissions' not in sources_processed:
                alerts.append(f"⚠️  emissions : présent en raw mais absent en processed")
    
    # Vérifier les dimensions essentielles
    dims_attendues = ['dim_countries', 'dim_years', 'dim_operators', 'dim_stops']
    dims_presentes = [r['nom'].replace('.csv', '') for r in warehouse_stats['dimensions']]
    
    for dim in dims_attendues:
        if dim in dims_presentes:
            checks.append(f"✅ {dim} : présent")
        else:
            alerts.append(f"❌ {dim} : MANQUANT")
    
    # Vérifier les tables de faits
    faits_attendus = ['facts_night_trains', 'facts_country_stats']
    faits_presents = [r['nom'].replace('.csv', '') for r in warehouse_stats['faits']]
    
    for fait in faits_attendus:
        if fait in faits_presents:
            checks.append(f"✅ {fait} : présent")
        else:
            alerts.append(f"❌ {fait} : MANQUANT")
    
    # Vérifier les colonnes importantes dans facts_night_trains
    for result in warehouse_stats['faits']:
        if 'facts_night_trains' in result['nom']:
            colonnes = result['colonnes_noms']
            cols_attendues = ['distance_km', 'duration_min', 'country_id', 'year_id', 'operator_id', 'is_night']
            for col in cols_attendues:
                if col in colonnes:
                    checks.append(f"✅ facts_night_trains.{col} : présent")
                else:
                    alerts.append(f"❌ facts_night_trains.{col} : MANQUANT")
    
    # Vérifier operator_dashboard
    dashboard_noms = [r['nom'] for r in warehouse_stats['dashboard']]
    if 'operator_dashboard.csv' in dashboard_noms:
        checks.append(f"✅ operator_dashboard.csv : présent")
    else:
        alerts.append(f"⚠️  operator_dashboard.csv : non trouvé (optionnel)")
    
    # Affichage
    print("\n✅ CONTRÔLES RÉUSSIS :")
    for check in checks:
        print(f"   {check}")
    
    if alerts:
        print("\n⚠️  ALERTES :")
        for alert in alerts:
            print(f"   {alert}")
    else:
        print("\n✅ Aucune alerte détectée")
    
    return len(alerts) == 0

def generer_rapport_json(raw_stats, processed_stats, warehouse_stats, coherence_ok, chemin_rapport=None):
    """Génère un rapport JSON complet du diagnostic"""
    if chemin_rapport is None:
        chemin_rapport = BASE_DIR / "data" / "audit" / "diagnostic_report.json"
    
    chemin_rapport.parent.mkdir(parents=True, exist_ok=True)
    
    def convertir_stats(stats_dict):
        """Convertit les stats en format sérialisable"""
        result = {}
        for key, value in stats_dict.items():
            if isinstance(value, dict):
                if 'details' in value:
                    # Simplifier les détails
                    details_simples = []
                    for d in value['details']:
                        details_simples.append({
                            'nom': d.get('nom', ''),
                            'lignes': d.get('lignes', 0),
                            'colonnes': d.get('colonnes', 0),
                            'taille_kb': d.get('taille_kb', 0),
                            'erreur': d.get('erreur')
                        })
                    result[key] = {
                        'fichiers': value.get('fichiers', 0),
                        'lignes': value.get('lignes', 0),
                        'details': details_simples
                    }
                else:
                    result[key] = {
                        k: v for k, v in value.items() if k != 'apercu'
                    }
            else:
                result[key] = value
        return result
    
    rapport = {
        'date_diagnostic': datetime.now().isoformat(),
        'projet': 'ObRail Europe - MSPR E6.1',
        'raw': convertir_stats(raw_stats),
        'processed': convertir_stats(processed_stats),
        'warehouse': convertir_stats(warehouse_stats),
        'statut': 'OK' if coherence_ok else 'A_VERIFIER'
    }
    
    import json
    with open(chemin_rapport, 'w', encoding='utf-8') as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📋 Rapport JSON sauvegardé : {chemin_rapport}")

def main():
    """Fonction principale du diagnostic"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("="*70)
    print("🔬 DIAGNOSTIC COMPLET DU PIPELINE ETL OBRAIL EUROPE")
    print(f"📅 Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Phase 1 : Données brutes
    raw_stats = diagnostiquer_raw()
    
    # Phase 2 : Données transformées
    processed_stats = diagnostiquer_processed()
    
    # Phase 3 : Data warehouse
    warehouse_stats = diagnostiquer_warehouse()
    
    # Vérification de cohérence
    coherence_ok = verifier_coherence(raw_stats, processed_stats, warehouse_stats)
    
    # Rapport JSON
    generer_rapport_json(raw_stats, processed_stats, warehouse_stats, coherence_ok)
    
    # Résumé final
    print("\n" + "="*70)
    print("📊 RÉSUMÉ FINAL")
    print("="*70)
    
    total_raw = sum(s.get('lignes', 0) for s in raw_stats.values())
    total_processed = sum(s.get('lignes', 0) for s in processed_stats.values())
    total_warehouse = sum(
        r.get('lignes', 0) 
        for cat in ['dimensions', 'faits', 'dashboard', 'autres'] 
        for r in warehouse_stats.get(cat, [])
    )
    
    print(f"   📥 Données brutes      : {total_raw:>12,} lignes")
    print(f"   🔄 Données transformées : {total_processed:>12,} lignes")
    print(f"   💾 Data warehouse      : {total_warehouse:>12,} lignes")
    print(f"\n   Statut global : {'✅ OK' if coherence_ok else '⚠️  VÉRIFIER LES ALERTES'}")
    print("="*70)

if __name__ == "__main__":
    # Accepter un argument --csv pour exporter aussi en CSV
    main()
