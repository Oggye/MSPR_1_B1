# app/dependencies.py
from typing import Generator
from app.database import SessionLocal


def get_db() -> Generator:
    """
    Dépendance pour obtenir une session de base de données.
    Gère automatiquement la fermeture de la session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
