from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

WAREHOUSE_DIR = ROOT / "data" / "warehouse"
DATA_ML_DIR = ROOT / "data" / "ml"
MODELS_DIR = ROOT / "ia" / "models"
REPORTS_DIR = ROOT / "ia" / "reports"

for directory in [DATA_ML_DIR, MODELS_DIR, REPORTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

STATS_FILE = WAREHOUSE_DIR / "facts_country_stats.csv"
COUNTRIES_FILE = WAREHOUSE_DIR / "dim_countries.csv"
YEARS_FILE = WAREHOUSE_DIR / "dim_years.csv"
TRAINS_FILE = WAREHOUSE_DIR / "facts_night_trains.csv"
QUALITY_FILE = WAREHOUSE_DIR / "country_stats_quality.csv"

REGRESSION_DATASET_PATH = DATA_ML_DIR / "regression_dataset_multihorizon.csv"
CLASSIF_DATASET_PATH = DATA_ML_DIR / "classification_dataset_multihorizon.csv"
DATASET_QUALITY_REPORT_PATH = DATA_ML_DIR / "dataset_quality_report_multihorizon.json"

FORECAST_CLASSIFIER_PATH = MODELS_DIR / "forecast_classifier.joblib"
FORECAST_REGRESSOR_PATH = MODELS_DIR / "forecast_regressor.joblib"
FORECAST_MANIFEST_PATH = MODELS_DIR / "forecast_manifest.json"

DATA_MIN_YEAR = 2010
DATA_MAX_YEAR = 2024
MAX_FORECAST_HORIZON = 3

# Le holdout final reste entièrement hors de la sélection de modèle.
FINAL_TEST_TARGET_START_YEAR = 2022

# Années utilisées pour la sélection en validation temporelle glissante.
CV_VALIDATION_YEARS = [2018, 2019, 2020, 2021]
