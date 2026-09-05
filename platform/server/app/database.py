# app/database.py
"""
Configuration SQLAlchemy.

- En production/Docker : utilise DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD.
- Pour les tests ou un environnement externe : DATABASE_URL peut surcharger
  entièrement la connexion.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "obrail")
DB_USER = os.getenv("DB_USER", "obrail_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    SQLALCHEMY_DATABASE_URL = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@"
        f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

engine_kwargs = {"pool_pre_ping": True}

# Facilite les tests SQLite sans modifier la configuration PostgreSQL.
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
