# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**SpritpreisSammler** — collects German fuel prices (Diesel/E5/E10) from specific gas stations every 15 minutes via the Tankerkönig API and stores them in SQLite for later analysis.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in your API key
cp .env.example .env

# Add real station UUIDs to config.json (find them on tankerkoenig.de)
```

## Running

```bash
# Start collecting (runs forever, Ctrl+C to stop)
python main.py

# Analyze collected data
python analyze.py --show-recent
python analyze.py --cheapest-station --fuel diesel --days 7
python analyze.py --cheapest-time --fuel e5 --station <uuid>
python analyze.py --cheapest-weekday --fuel diesel --station <uuid>
```

## Architecture

| File | Role |
|---|---|
| `main.py` | Entry point: loads config/.env, inits DB, runs scheduler loop |
| `collector.py` | Single function `fetch_prices()` — calls Tankerkönig API with retry (3×, 5s backoff) |
| `db.py` | `init_db()`, `insert_prices()`, and query helpers for analysis |
| `analyze.py` | CLI for querying the database (cheapest station/hour/weekday) |
| `config.json` | Station UUIDs, fuel types, interval, DB path |
| `.env` | `TANKERKOENIG_API_KEY` (never commit this) |

## Tankerkönig API

- Endpoint: `https://creativecommons.tankerkoenig.de/api/v4/prices.php?ids=<uuid,...>&apikey=<key>`
- Register for a free key at tankerkoenig.de
- Find station UUIDs via the Tankerkönig station search

## Database Schema

```sql
CREATE TABLE prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,   -- ISO8601, UTC
    station_id  TEXT NOT NULL,
    fuel_type   TEXT NOT NULL,   -- 'diesel', 'e5', 'e10'
    price       REAL             -- NULL when station is closed
);
CREATE INDEX idx_lookup ON prices (station_id, fuel_type, timestamp);
```
