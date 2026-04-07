"""
Database layer — supports both SQLite (local dev) and PostgreSQL (production).

Connection is determined by the DATABASE_URL environment variable:
  - Not set / empty  →  SQLite, path from config.json "db_path"
  - Set              →  PostgreSQL, e.g. postgresql://user:pw@host:5432/dbname

All public functions accept the connection object returned by init_db().
"""

import os
import sqlite3
from typing import Any

_BACKEND: str = "sqlite"  # set by init_db()


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def _get_backend() -> str:
    return "postgresql" if os.getenv("DATABASE_URL") else "sqlite"


def init_db(db_path: str = "prices.db"):
    """
    Open (and initialise) the database.

    Returns a sqlite3.Connection or psycopg2 connection depending on DATABASE_URL.
    """
    global _BACKEND
    _BACKEND = _get_backend()

    if _BACKEND == "postgresql":
        import psycopg2
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        conn.autocommit = False
        _create_schema_pg(conn)
    else:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        _create_schema_sqlite(conn)

    return conn


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def _create_schema_sqlite(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id     TEXT PRIMARY KEY,
            name   TEXT NOT NULL,
            brand  TEXT,
            street TEXT,
            city   TEXT
        )
    """)
    for col in ("brand", "street", "city"):
        try:
            conn.execute(f"ALTER TABLE stations ADD COLUMN {col} TEXT")
        except Exception:
            pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            station_id  TEXT    NOT NULL,
            fuel_type   TEXT    NOT NULL,
            price       REAL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_lookup
            ON prices (station_id, fuel_type, timestamp)
    """)
    conn.commit()


def _create_schema_pg(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id     TEXT PRIMARY KEY,
            name   TEXT NOT NULL,
            brand  TEXT,
            street TEXT,
            city   TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id          SERIAL PRIMARY KEY,
            timestamp   TEXT   NOT NULL,
            station_id  TEXT   NOT NULL,
            fuel_type   TEXT   NOT NULL,
            price       REAL
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_lookup
            ON prices (station_id, fuel_type, timestamp)
    """)
    conn.commit()
    cur.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _execute(conn, sql: str, params=()) -> Any:
    """Run a single statement, returning the cursor."""
    if _BACKEND == "postgresql":
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    else:
        return conn.execute(sql, params)


def _executemany(conn, sql: str, rows: list):
    if _BACKEND == "postgresql":
        import psycopg2.extras
        cur = conn.cursor()
        psycopg2.extras.execute_batch(cur, sql, rows)
        cur.close()
    else:
        conn.executemany(sql, rows)


def _commit(conn):
    conn.commit()


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _adapt_sql(sql: str) -> str:
    """Convert SQLite-style :name params and ? to %(name)s / %s for PostgreSQL."""
    if _BACKEND != "postgresql":
        return sql
    import re
    sql = re.sub(r":(\w+)", r"%(\1)s", sql)
    sql = sql.replace("?", "%s")
    return sql


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upsert_stations(conn, stations: list[dict]) -> None:
    """Insert or update station metadata. Each dict must have 'id' and 'name'."""
    rows = [
        {"id": s["id"], "name": s["name"], "brand": s.get("brand"),
         "street": s.get("street"), "city": s.get("city")}
        for s in stations
    ]
    if _BACKEND == "postgresql":
        sql = """
            INSERT INTO stations (id, name, brand, street, city)
            VALUES (%(id)s, %(name)s, %(brand)s, %(street)s, %(city)s)
            ON CONFLICT (id) DO UPDATE SET
                name   = COALESCE(EXCLUDED.name,   stations.name),
                brand  = COALESCE(EXCLUDED.brand,  stations.brand),
                street = COALESCE(EXCLUDED.street, stations.street),
                city   = COALESCE(EXCLUDED.city,   stations.city)
        """
    else:
        sql = """
            INSERT INTO stations (id, name, brand, street, city)
            VALUES (:id, :name, :brand, :street, :city)
            ON CONFLICT(id) DO UPDATE SET
                name   = COALESCE(excluded.name,   stations.name),
                brand  = COALESCE(excluded.brand,  stations.brand),
                street = COALESCE(excluded.street, stations.street),
                city   = COALESCE(excluded.city,   stations.city)
        """
    _executemany(conn, sql, rows)
    _commit(conn)


def insert_prices(conn, rows: list[dict]) -> int:
    """Insert a list of {station_id, fuel_type, price, timestamp} dicts."""
    if not rows:
        return 0
    if _BACKEND == "postgresql":
        sql = "INSERT INTO prices (timestamp, station_id, fuel_type, price) VALUES (%(timestamp)s, %(station_id)s, %(fuel_type)s, %(price)s)"
    else:
        sql = "INSERT INTO prices (timestamp, station_id, fuel_type, price) VALUES (:timestamp, :station_id, :fuel_type, :price)"
    _executemany(conn, sql, rows)
    _commit(conn)
    return len(rows)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def cheapest_station(conn, fuel_type: str, start: str, end: str) -> list[dict]:
    sql = _adapt_sql("""
        SELECT p.station_id,
               COALESCE(s.name, p.station_id) AS station_name,
               ROUND(CAST(AVG(p.price) AS NUMERIC), 3) AS avg_price,
               COUNT(*) AS samples
        FROM prices p
        LEFT JOIN stations s ON s.id = p.station_id
        WHERE p.fuel_type = :fuel_type
          AND p.timestamp >= :start
          AND p.timestamp <= :end
          AND p.price IS NOT NULL
        GROUP BY p.station_id, s.name
        ORDER BY avg_price ASC
    """)
    cur = _execute(conn, sql, {"fuel_type": fuel_type, "start": start, "end": end})
    return _rows(cur)


def price_by_hour(conn, station_id: str, fuel_type: str) -> list[dict]:
    if _BACKEND == "postgresql":
        sql = """
            SELECT CAST(EXTRACT(HOUR FROM timestamp::timestamptz) AS INTEGER) AS hour,
                   ROUND(CAST(AVG(price) AS NUMERIC), 3) AS avg_price,
                   COUNT(*) AS samples
            FROM prices
            WHERE station_id = %s AND fuel_type = %s AND price IS NOT NULL
            GROUP BY hour ORDER BY hour
        """
    else:
        sql = """
            SELECT CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
                   ROUND(AVG(price), 3) AS avg_price,
                   COUNT(*) AS samples
            FROM prices
            WHERE station_id = ? AND fuel_type = ? AND price IS NOT NULL
            GROUP BY hour ORDER BY hour
        """
    cur = _execute(conn, sql, (station_id, fuel_type))
    return _rows(cur)


def price_by_weekday(conn, station_id: str, fuel_type: str) -> list[dict]:
    if _BACKEND == "postgresql":
        # EXTRACT(DOW): 0=Sun … 6=Sat → remap to Mon=0 … Sun=6
        sql = """
            SELECT (CAST(EXTRACT(DOW FROM timestamp::timestamptz) AS INTEGER) + 6) % 7 AS weekday,
                   ROUND(CAST(AVG(price) AS NUMERIC), 3) AS avg_price,
                   COUNT(*) AS samples
            FROM prices
            WHERE station_id = %s AND fuel_type = %s AND price IS NOT NULL
            GROUP BY weekday ORDER BY weekday
        """
    else:
        sql = """
            SELECT (CAST(strftime('%w', timestamp) AS INTEGER) + 6) % 7 AS weekday,
                   ROUND(AVG(price), 3) AS avg_price,
                   COUNT(*) AS samples
            FROM prices
            WHERE station_id = ? AND fuel_type = ? AND price IS NOT NULL
            GROUP BY weekday ORDER BY weekday
        """
    cur = _execute(conn, sql, (station_id, fuel_type))
    rows = _rows(cur)
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for row in rows:
        row["weekday_name"] = day_names[row["weekday"]]
    return rows


def recent_prices(conn, limit: int = 20) -> list[dict]:
    if _BACKEND == "postgresql":
        sql = """
            SELECT p.timestamp,
                   COALESCE(s.name, p.station_id) AS station_name,
                   p.fuel_type, p.price
            FROM prices p
            LEFT JOIN stations s ON s.id = p.station_id
            ORDER BY p.timestamp DESC LIMIT %s
        """
        cur = _execute(conn, sql, (limit,))
    else:
        sql = """
            SELECT p.timestamp,
                   COALESCE(s.name, p.station_id) AS station_name,
                   p.fuel_type, p.price
            FROM prices p
            LEFT JOIN stations s ON s.id = p.station_id
            ORDER BY p.timestamp DESC LIMIT ?
        """
        cur = _execute(conn, sql, (limit,))
    return _rows(cur)


def cheapest_in_range(conn, fuel_type: str, start: str, end: str) -> list[dict]:
    sql = _adapt_sql("""
        SELECT timestamp, station_id, price
        FROM prices
        WHERE fuel_type = :fuel_type
          AND timestamp >= :start AND timestamp <= :end
          AND price IS NOT NULL
        ORDER BY price ASC
    """)
    cur = _execute(conn, sql, {"fuel_type": fuel_type, "start": start, "end": end})
    return _rows(cur)
