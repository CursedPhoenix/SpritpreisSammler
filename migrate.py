#!/usr/bin/env python3
"""
Einmalige Migration: SQLite (prices.db) → PostgreSQL (DATABASE_URL).

Voraussetzungen:
  1. DATABASE_URL in .env gesetzt (direkt oder via SSH-Tunnel)
  2. PostgreSQL-Schema bereits angelegt (passiert automatisch via db.init_db())

Aufruf:
    python migrate.py
    python migrate.py --sqlite-path /pfad/zu/prices.db   # falls abweichender Pfad

Das Script ist idempotent: bereits vorhandene Rows werden übersprungen (ON CONFLICT DO NOTHING).
"""

import argparse
import json
import logging
import sqlite3
import sys

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("migrate")

BATCH_SIZE = 1000


def load_sqlite(sqlite_path: str) -> tuple[list[dict], list[dict]]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row

    stations = [dict(r) for r in conn.execute("SELECT id, name, brand, street, city FROM stations").fetchall()]
    prices   = [dict(r) for r in conn.execute("SELECT timestamp, station_id, fuel_type, price FROM prices").fetchall()]

    conn.close()
    logger.info("SQLite: %d stations, %d price rows", len(stations), len(prices))
    return stations, prices


def migrate_stations(pg_conn, stations: list[dict]) -> None:
    if not stations:
        return
    import psycopg2.extras
    sql = """
        INSERT INTO stations (id, name, brand, street, city)
        VALUES (%(id)s, %(name)s, %(brand)s, %(street)s, %(city)s)
        ON CONFLICT (id) DO NOTHING
    """
    cur = pg_conn.cursor()
    psycopg2.extras.execute_batch(cur, sql, stations, page_size=500)
    pg_conn.commit()
    cur.close()
    logger.info("Stations migrated: %d", len(stations))


def migrate_prices(pg_conn, prices: list[dict]) -> None:
    if not prices:
        return
    import psycopg2.extras
    sql = """
        INSERT INTO prices (timestamp, station_id, fuel_type, price)
        VALUES (%(timestamp)s, %(station_id)s, %(fuel_type)s, %(price)s)
        ON CONFLICT DO NOTHING
    """
    cur = pg_conn.cursor()
    total = 0
    for i in range(0, len(prices), BATCH_SIZE):
        batch = prices[i:i + BATCH_SIZE]
        psycopg2.extras.execute_batch(cur, sql, batch, page_size=BATCH_SIZE)
        pg_conn.commit()
        total += len(batch)
        logger.info("  %d / %d rows inserted...", total, len(prices))
    cur.close()
    logger.info("Prices migrated: %d", total)


def main() -> None:
    load_dotenv()

    import os
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL ist nicht gesetzt. SSH-Tunnel aktiv? .env korrekt?")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="SQLite → PostgreSQL Migration")
    parser.add_argument("--sqlite-path", default=None, help="Pfad zur prices.db (Standard: aus config.json)")
    args = parser.parse_args()

    sqlite_path = args.sqlite_path
    if not sqlite_path:
        try:
            with open("config.json", encoding="utf-8") as f:
                sqlite_path = json.load(f).get("db_path", "prices.db")
        except FileNotFoundError:
            sqlite_path = "prices.db"

    logger.info("SQLite-Quelle: %s", sqlite_path)
    logger.info("PostgreSQL-Ziel: %s", database_url.split("@")[-1])  # host/db, kein Passwort im Log

    stations, prices = load_sqlite(sqlite_path)

    import psycopg2
    pg_conn = psycopg2.connect(database_url)

    # Schema anlegen falls nötig
    import db as db_module
    db_module._BACKEND = "postgresql"
    db_module._create_schema_pg(pg_conn)

    migrate_stations(pg_conn, stations)
    migrate_prices(pg_conn, prices)

    pg_conn.close()
    logger.info("Migration abgeschlossen.")


if __name__ == "__main__":
    main()
