# app/models.py
"""
Modèles SQLAlchemy alignés sur sql/01_init.sql.

Le nom physique de la table `facts_night_trains` est conservé pour compatibilité
avec l'architecture historique. Le champ canonique d'un trajet est désormais
`train`. La propriété Python `night_train` reste disponible comme alias legacy,
sans tenter d'écrire dans la colonne PostgreSQL générée du même nom.
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, DECIMAL, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    """Compte applicatif indépendant du warehouse ferroviaire."""

    __tablename__ = "app_users"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="ck_app_users_role"),
    )

    id = Column(Integer, primary_key=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(10), nullable=False, default="user")
    is_active = Column(Boolean, nullable=False, default=True)
    terms_accepted_at = Column(DateTime(timezone=True), nullable=False)
    legal_version = Column(String(20), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class DimCountries(Base):
    __tablename__ = "dim_countries"

    country_id = Column(Integer, primary_key=True, index=True)
    country_code = Column(String(10), unique=True, nullable=False, index=True)
    country_name = Column(String(100), nullable=False)

    country_stats = relationship("FactsCountryStats", back_populates="country")
    night_trains = relationship("FactsNightTrains", back_populates="country")

    def __repr__(self):
        return (
            f"<Country(id={self.country_id}, code='{self.country_code}', "
            f"name='{self.country_name}')>"
        )


class DimYears(Base):
    __tablename__ = "dim_years"

    year_id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, unique=True, index=True)
    is_after_2010 = Column(Boolean, nullable=False, default=True)

    country_stats = relationship("FactsCountryStats", back_populates="year_dim")
    night_trains = relationship("FactsNightTrains", back_populates="year_dim")

    def __repr__(self):
        return f"<Year(id={self.year_id}, year={self.year})>"


class DimOperators(Base):
    __tablename__ = "dim_operators"

    operator_id = Column(Integer, primary_key=True, index=True)
    operator_name = Column(String(200), nullable=False, index=True)

    night_trains = relationship("FactsNightTrains", back_populates="operator")

    def __repr__(self):
        return f"<Operator(id={self.operator_id}, name='{self.operator_name}')>"


class DimStops(Base):
    __tablename__ = "dim_stops"

    stop_id_dim = Column(BigInteger, primary_key=True, index=True)
    stop_name = Column(String(250), nullable=False)
    stop_lat = Column(DECIMAL(10, 6), nullable=True)
    stop_lon = Column(DECIMAL(10, 6), nullable=True)
    stop_id = Column(String(150), nullable=True)
    source_country = Column(String(3), nullable=True)

    def __repr__(self):
        return f"<Stop(id={self.stop_id_dim}, name='{self.stop_name}')>"


class FactsCountryStats(Base):
    __tablename__ = "facts_country_stats"

    stat_id = Column(BigInteger, primary_key=True, index=True)
    country_id = Column(
        Integer,
        ForeignKey("dim_countries.country_id"),
        nullable=False,
        index=True,
    )
    year_id = Column(
        Integer,
        ForeignKey("dim_years.year_id"),
        nullable=False,
        index=True,
    )

    # `passengers` conserve le nom historique du warehouse.
    # Dans le pipeline actuel, la métrique canonique est MIO_PKM.
    passengers = Column(DECIMAL(20, 4), nullable=False)
    co2_emissions = Column(DECIMAL(20, 6), nullable=False)
    co2_per_passenger = Column(DECIMAL(20, 8), nullable=False)

    country = relationship("DimCountries", back_populates="country_stats")
    year_dim = relationship("DimYears", back_populates="country_stats")

    def __repr__(self):
        return (
            f"<CountryStats(id={self.stat_id}, country={self.country_id}, "
            f"year={self.year_id})>"
        )


class FactsNightTrains(Base):
    """
    Faits des trajets ferroviaires de jour ET de nuit.

    Le nom de table reste legacy. Le champ métier canonique est `train`.
    PostgreSQL possède aussi une colonne générée `night_train = train`, mais elle
    n'est volontairement pas mappée ici afin que SQLAlchemy ne tente jamais de
    l'insérer ou de la modifier.
    """

    __tablename__ = "facts_night_trains"

    fact_id = Column(BigInteger, primary_key=True, index=True)
    route_id = Column(String(150), nullable=False)
    train = Column(String(300), nullable=False, index=True)

    country_id = Column(
        Integer,
        ForeignKey("dim_countries.country_id"),
        nullable=False,
        index=True,
    )
    year_id = Column(
        Integer,
        ForeignKey("dim_years.year_id"),
        nullable=False,
        index=True,
    )
    operator_id = Column(
        Integer,
        ForeignKey("dim_operators.operator_id"),
        nullable=False,
        index=True,
    )

    is_night = Column(Boolean, nullable=False, default=False, index=True)
    distance_km = Column(DECIMAL(12, 2), default=0)
    duration_min = Column(DECIMAL(12, 2), default=0)
    is_synthetic = Column(Boolean, nullable=False, default=False, index=True)
    data_source = Column(String(80), nullable=False, default="unknown")

    country = relationship("DimCountries", back_populates="night_trains")
    year_dim = relationship("DimYears", back_populates="night_trains")
    operator = relationship("DimOperators", back_populates="night_trains")

    @property
    def night_train(self):
        """Alias legacy utilisé par l'ancien front/API."""
        return self.train

    @night_train.setter
    def night_train(self, value):
        """Permet aux anciens fixtures/tests de continuer à initialiser l'objet."""
        self.train = value

    def __repr__(self):
        return (
            f"<Train(id={self.fact_id}, route={self.route_id}, "
            f"train='{self.train}', night={self.is_night}, "
            f"synthetic={self.is_synthetic})>"
        )


class DashboardMetrics(Base):
    """Vue SQL `dashboard_metrics` (lecture seule en production)."""

    __tablename__ = "dashboard_metrics"

    country_id = Column(Integer, primary_key=True)
    country_name = Column(String(100))
    country_code = Column(String(10))
    avg_passengers = Column(DECIMAL(20, 2))
    avg_co2_emissions = Column(DECIMAL(20, 4))
    avg_co2_per_passenger = Column(DECIMAL(20, 6))

    __table_args__ = {"info": {"is_view": True}}


class OperatorDashboard(Base):
    """Vue SQL `operator_dashboard` (lecture seule en production)."""

    __tablename__ = "operator_dashboard"

    operator_id = Column(Integer, primary_key=True)
    operator_name = Column(String(200))
    nb_trains = Column(BigInteger)
    nb_trains_nuit = Column(BigInteger)
    nb_trains_jour = Column(BigInteger)
    distance_totale_km = Column(DECIMAL(20, 2))
    duree_moyenne_min = Column(DECIMAL(12, 2))

    __table_args__ = {"info": {"is_view": True}}


class QualityReport(Base):
    """
    Modèle historique conservé pour compatibilité des tests/outils internes.
    Le endpoint metadata lit désormais le JSON réellement généré par l'ETL.
    """

    __tablename__ = "quality_reports"

    report_id = Column(Integer, primary_key=True, index=True)
    execution_date = Column(String(50), nullable=False)
    project = Column(String(200), nullable=False)
    report_data = Column(String, nullable=False)
    created_at = Column(String(50), nullable=False)


def create_tables_and_views(engine):
    """
    Utilitaire historique.

    En production Docker, le schéma de référence reste `sql/01_init.sql`.
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Tables SQLAlchemy créées avec succès")


if __name__ == "__main__":
    from app.database import engine

    create_tables_and_views(engine)
