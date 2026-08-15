# app/main.py
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    analysis,
    countries,
    dashboard,
    internal,
    metadata,
    night_trains,
    operators,
    statistics,
)

logger = logging.getLogger(__name__)

# La route IA reste optionnelle au démarrage du serveur :
# les tests API et les déploiements sans modèles ML doivent pouvoir démarrer.
try:
    from app.routers import predict
except ImportError as exc:
    predict = None
    logger.warning("Route /predict désactivée: dépendance IA indisponible: %s", exc)

try:
    from prometheus_fastapi_instrumentator import Instrumentator
except ImportError:
    Instrumentator = None


app = FastAPI(
    title="ObRail API - Observatoire Européen du Rail",
    description=(
        "API de données ferroviaires européennes : services de jour et de "
        "nuit, statistiques par pays, indicateurs environnementaux, qualité "
        "des données et analyses."
    ),
    version="1.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


if Instrumentator is not None:
    Instrumentator().instrument(app).expose(app)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(countries.router)
app.include_router(night_trains.router)
app.include_router(dashboard.router)
app.include_router(analysis.router)
app.include_router(operators.router)
app.include_router(metadata.router)
app.include_router(statistics.router)
app.include_router(internal.router)

if predict is not None:
    app.include_router(predict.router)


@app.get("/")
def read_root():
    return {
        "message": "API",
        "service": "ObRail API",
        "version": app.version,
        "predict_router_enabled": predict is not None,
    }


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "predict_router_enabled": predict is not None,
    }
