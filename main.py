#!/usr/bin/env python3
"""SpritpreisSammler – fuel price collector.

Runs once and exits — scheduling is handled externally (GitHub Actions cron).

Usage:
    python main.py

Source is selected via config.json → "source":
    "api"      – Tankerkönig API (requires TANKERKOENIG_API_KEY)
    "scraper"  – scrape clever-tanken.de (no API key required)
"""

import json
import logging
import os
import sys

from dotenv import load_dotenv

import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def load_config(path: str = "config.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    load_dotenv()
    config = load_config()

    source: str = config.get("source", "api")
    db_path: str = config.get("db_path", "prices.db")

    if source == "api":
        import collector
        fetch_prices = collector.fetch_prices
        raw_stations = config.get("tankerkoenig_stations", [])
        api_key = os.getenv("TANKERKOENIG_API_KEY", "")
        if not api_key:
            logger.error("TANKERKOENIG_API_KEY is not set.")
            sys.exit(1)
        if not raw_stations or raw_stations[0] == "placeholder-uuid-1":
            logger.error("No station UUIDs configured in config.json.")
            sys.exit(1)
        station_ids: list[str] = [str(s) for s in raw_stations]
    elif source == "scraper":
        import scraper
        fetch_prices = scraper.fetch_prices
        station_entries: list[dict] = config.get("stations", [])
        api_key = ""
        if not station_entries or station_entries[0]["id"] == "12345":
            logger.error("No station IDs configured for scraper in config.json.")
            sys.exit(1)
        station_ids = [str(s["id"]) for s in station_entries]
    else:
        logger.error("Unknown source %r in config.json.", source)
        sys.exit(1)

    logger.info("Source: %s | Stations: %d", source, len(station_ids))

    conn = db.init_db(db_path)

    # Upsert station metadata (only fetches from API if names not yet known)
    if source == "api":
        station_entries = []
        for sid in station_ids:
            detail = collector.fetch_station_detail(sid, api_key)
            station_entries.append(detail if detail else {"id": sid, "name": sid, "brand": None, "street": None, "city": None})
    db.upsert_stations(conn, station_entries)

    # Collect and store
    try:
        rows = fetch_prices(station_ids, api_key)
        count = db.insert_prices(conn, rows)
        logger.info("Stored %d rows.", count)
    except Exception as exc:
        logger.error("Collection failed: %s", exc)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
