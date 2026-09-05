"""Connexion PostgreSQL + chargement bulk adapté aux gros volumes."""
from __future__ import annotations

import os
import math
import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values


class DatabaseConnection:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.config = {
            'host':os.getenv('DB_HOST','localhost'),
            'port':int(os.getenv('DB_PORT',5432)),
            'database':os.getenv('DB_NAME','obrail'),
            'user':os.getenv('DB_USER','obrail_user'),
            'password':os.getenv('DB_PASSWORD','123456'),
        }

    def connect(self):
        try:
            self.connection = psycopg2.connect(**self.config)
            self.cursor = self.connection.cursor()
            return True
        except Exception as exc:
            print(f"Erreur de connexion: {exc}")
            return False

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        self.cursor = None
        self.connection = None

    def test_connection(self):
        if not self.connect(): return False
        try:
            self.cursor.execute('SELECT 1')
            essential = ['dim_countries','dim_years','dim_operators','dim_stops','facts_night_trains','facts_country_stats']
            missing = []
            for table in essential:
                self.cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s)", (table,))
                if not self.cursor.fetchone()[0]: missing.append(table)
            if missing:
                print('❌ Tables manquantes:', ', '.join(missing)); return False
            print('✅ Connexion PostgreSQL établie')
            return True
        finally:
            self.close()

    def execute_query(self, query, params=None):
        try:
            if not self.connection and not self.connect(): return None
            self.cursor.execute(query, params or None)
            self.connection.commit()
            return self.cursor
        except Exception as exc:
            print(f"❌ Erreur requête: {exc}")
            if self.connection: self.connection.rollback()
            return None

    @staticmethod
    def _clean_value(value):
        if value is None: return None
        try:
            if pd.isna(value): return None
        except Exception:
            pass
        if isinstance(value, (pd.Timestamp,)):
            return value.to_pydatetime()
        if hasattr(value, 'item'):
            try: return value.item()
            except Exception: pass
        return value

    def truncate_table(self, table_name):
        if not self.connect(): return False
        try:
            self.cursor.execute(sql.SQL('TRUNCATE TABLE {} CASCADE').format(sql.Identifier(table_name)))
            self.connection.commit(); return True
        except Exception as exc:
            print(f"❌ Erreur TRUNCATE {table_name}: {exc}")
            self.connection.rollback(); return False
        finally:
            self.close()

    def insert_dataframe(self, df, table_name, page_size=10_000):
        if df.empty: return True
        if not self.connect(): return False
        columns = list(df.columns)
        query = sql.SQL('INSERT INTO {} ({}) VALUES %s').format(
            sql.Identifier(table_name),
            sql.SQL(',').join(map(sql.Identifier, columns)),
        ).as_string(self.connection)
        try:
            rows = [tuple(self._clean_value(v) for v in row) for row in df.itertuples(index=False, name=None)]
            execute_values(self.cursor, query, rows, page_size=page_size)
            self.connection.commit()
            return True
        except Exception as exc:
            print(f"❌ Erreur chargement {table_name}: {exc}")
            self.connection.rollback(); return False
        finally:
            self.close()

    def load_dataframe(self, df, table_name):
        print(f"📥 Chargement de {table_name}... ({len(df):,} lignes)")
        if not self.truncate_table(table_name): return False
        ok = self.insert_dataframe(df, table_name)
        if ok: print(f"   ✅ {table_name} chargé")
        return ok

    def refresh_views(self):
        if not self.connect(): return False
        try:
            self.cursor.execute('DROP VIEW IF EXISTS dashboard_metrics CASCADE')
            self.cursor.execute('DROP VIEW IF EXISTS operator_dashboard CASCADE')
            self.cursor.execute("""
                CREATE VIEW dashboard_metrics AS
                SELECT c.country_id,c.country_name,c.country_code,
                       AVG(s.passengers)::NUMERIC(20,2) avg_passengers,
                       AVG(s.co2_emissions)::NUMERIC(20,4) avg_co2_emissions,
                       AVG(s.co2_per_passenger)::NUMERIC(20,6) avg_co2_per_passenger
                FROM facts_country_stats s JOIN dim_countries c ON s.country_id=c.country_id
                GROUP BY c.country_id,c.country_name,c.country_code
            """)
            self.cursor.execute("""
                CREATE VIEW operator_dashboard AS
                SELECT o.operator_id,o.operator_name,COUNT(f.fact_id) nb_trains,
                       SUM(CASE WHEN f.is_night THEN 1 ELSE 0 END) nb_trains_nuit,
                       SUM(CASE WHEN NOT f.is_night THEN 1 ELSE 0 END) nb_trains_jour,
                       COALESCE(SUM(f.distance_km),0)::NUMERIC(20,2) distance_totale_km,
                       COALESCE(AVG(f.duration_min),0)::NUMERIC(12,2) duree_moyenne_min
                FROM dim_operators o LEFT JOIN facts_night_trains f ON o.operator_id=f.operator_id
                GROUP BY o.operator_id,o.operator_name ORDER BY nb_trains DESC
            """)
            self.connection.commit(); return True
        except Exception as exc:
            print(f"❌ Erreur création vues: {exc}")
            self.connection.rollback(); return False
        finally:
            self.close()


db = DatabaseConnection()
