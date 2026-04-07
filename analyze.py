#!/usr/bin/env python3
"""SpritpreisSammler – analysis CLI.

Examples:
    python analyze.py --show-recent
    python analyze.py --cheapest-station --fuel diesel --days 7
    python analyze.py --cheapest-time --fuel e5 --station <uuid> --days 30
    python analyze.py --cheapest-weekday --fuel diesel --station <uuid>
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import db


def load_db_path(config_path: str = "config.json") -> str:
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f).get("db_path", "prices.db")
    except FileNotFoundError:
        return "prices.db"


def _table(headers: list[str], rows: list[list]) -> None:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(fmt.format(*[str(c) for c in row]))


def cmd_show_recent(conn: sqlite3.Connection, limit: int) -> None:
    rows = db.recent_prices(conn, limit)
    if not rows:
        print("No data yet.")
        return
    _table(
        ["timestamp", "station", "fuel_type", "price"],
        [[r["timestamp"], r["station_name"], r["fuel_type"], r["price"] or "—"] for r in rows],
    )


def cmd_cheapest_station(conn: sqlite3.Connection, fuel: str, days: int) -> None:
    end = datetime.now(timezone.utc).isoformat()
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.cheapest_station(conn, fuel, start, end)
    if not rows:
        print(f"No data for fuel={fuel} in the last {days} days.")
        return
    print(f"Average {fuel} price per station (last {days} days):\n")
    _table(
        ["station", "avg_price (€)", "samples"],
        [[r["station_name"], r["avg_price"], r["samples"]] for r in rows],
    )


def _station_label(conn: sqlite3.Connection, station_id: str) -> str:
    """Return 'Name (ID)' if a name is known, otherwise just the ID."""
    row = conn.execute("SELECT name FROM stations WHERE id = ?", (station_id,)).fetchone()
    return f"{row[0]} ({station_id})" if row else station_id


def cmd_cheapest_time(conn: sqlite3.Connection, fuel: str, station: str, days: int) -> None:
    rows = db.price_by_hour(conn, station, fuel)
    if not rows:
        print(f"No data for station={station} fuel={fuel}.")
        return
    station_label = _station_label(conn, station)
    print(f"Average {fuel} price by hour-of-day for {station_label}:\n")
    _table(
        ["hour", "avg_price (€)", "samples"],
        [[f"{r['hour']:02d}:00", r["avg_price"], r["samples"]] for r in rows],
    )
    cheapest = min(rows, key=lambda r: r["avg_price"])
    print(f"\nCheapest hour: {cheapest['hour']:02d}:00  ({cheapest['avg_price']} €)")


def cmd_cheapest_weekday(conn: sqlite3.Connection, fuel: str, station: str) -> None:
    rows = db.price_by_weekday(conn, station, fuel)
    if not rows:
        print(f"No data for station={station} fuel={fuel}.")
        return
    station_label = _station_label(conn, station)
    print(f"Average {fuel} price by weekday for {station_label}:\n")
    _table(
        ["weekday", "avg_price (€)", "samples"],
        [[r["weekday_name"], r["avg_price"], r["samples"]] for r in rows],
    )
    cheapest = min(rows, key=lambda r: r["avg_price"])
    print(f"\nCheapest day: {cheapest['weekday_name']}  ({cheapest['avg_price']} €)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze collected fuel prices.")
    parser.add_argument("--show-recent", action="store_true", help="Show latest N rows")
    parser.add_argument("--cheapest-station", action="store_true", help="Rank stations by avg price")
    parser.add_argument("--cheapest-time", action="store_true", help="Show avg price by hour")
    parser.add_argument("--cheapest-weekday", action="store_true", help="Show avg price by weekday")
    parser.add_argument("--fuel", default="diesel", choices=["diesel", "e5", "e10"])
    parser.add_argument("--days", type=int, default=7, help="Look-back window in days")
    parser.add_argument("--station", help="Station UUID (required for --cheapest-time / --cheapest-weekday)")
    parser.add_argument("--limit", type=int, default=20, help="Row limit for --show-recent")
    args = parser.parse_args()

    db_path = load_db_path()
    conn = db.init_db(db_path)

    if args.show_recent:
        cmd_show_recent(conn, args.limit)
    elif args.cheapest_station:
        cmd_cheapest_station(conn, args.fuel, args.days)
    elif args.cheapest_time:
        if not args.station:
            print("--cheapest-time requires --station <uuid>")
            sys.exit(1)
        cmd_cheapest_time(conn, args.fuel, args.station, args.days)
    elif args.cheapest_weekday:
        if not args.station:
            print("--cheapest-weekday requires --station <uuid>")
            sys.exit(1)
        cmd_cheapest_weekday(conn, args.fuel, args.station)
    else:
        parser.print_help()

    conn.close()


if __name__ == "__main__":
    main()
