import logging
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

API_URL = "https://creativecommons.tankerkoenig.de/json/prices.php"
DETAIL_URL = "https://creativecommons.tankerkoenig.de/json/detail.php"
TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = 5  # seconds


BATCH_SIZE = 10  # Tankerkönig prices API silently ignores stations beyond this limit


def _fetch_prices_batch(batch: list[str], api_key: str, timestamp: str) -> tuple[list[dict], set[str]]:
    """Fetch prices for a single batch. Returns (rows, returned_ids)."""
    params = {"ids": ",".join(batch), "apikey": api_key}
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(API_URL, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("Attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF)
            continue

        if not data.get("ok"):
            msg = data.get("message", "unknown API error")
            logger.warning("API returned ok=false: %s", msg)
            raise RuntimeError(f"Tankerkönig API error: {msg}")

        rows = []
        prices_data: dict = data.get("prices", {})
        for station_id, station_prices in prices_data.items():
            if not isinstance(station_prices, dict):
                logger.warning("Unexpected price format for station %s: %r", station_id, station_prices)
                continue
            for fuel_type in ("diesel", "e5", "e10"):
                raw = station_prices.get(fuel_type)
                price = float(raw) if isinstance(raw, (int, float)) else None
                rows.append({
                    "station_id": station_id,
                    "fuel_type": fuel_type,
                    "price": price,
                    "timestamp": timestamp,
                })
        return rows, set(prices_data.keys())

    raise RuntimeError(f"All {MAX_RETRIES} attempts failed. Last error: {last_exc}")


def fetch_prices(station_ids: list[str], api_key: str) -> list[dict]:
    """
    Fetch current fuel prices for the given station UUIDs from the Tankerkönig API.

    Splits into batches of up to 10 (API limit). Returns a list of dicts with keys:
    station_id, fuel_type, price, timestamp.
    Prices are None when a station is closed or the price is unavailable.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    all_rows: list[dict] = []
    all_returned: set[str] = set()

    batches = [station_ids[i:i + BATCH_SIZE] for i in range(0, len(station_ids), BATCH_SIZE)]
    for batch in batches:
        rows, returned = _fetch_prices_batch(batch, api_key, timestamp)
        all_rows.extend(rows)
        all_returned.update(returned)

    missing = set(station_ids) - all_returned
    if missing:
        logger.warning("No data returned for %d station(s): %s", len(missing), ", ".join(sorted(missing)))
    logger.info("Fetched %d price records for %d/%d stations", len(all_rows), len(all_returned), len(station_ids))
    return all_rows


def fetch_station_detail(station_id: str, api_key: str) -> dict | None:
    """
    Fetch station metadata from the Tankerkönig detail endpoint.

    Returns a dict with keys: id, name, brand, street, city.
    Returns None if the request fails (non-fatal — caller should use a fallback).
    """
    params = {"id": station_id, "apikey": api_key}
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(DETAIL_URL, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("Detail fetch for %s – attempt %d/%d failed: %s", station_id, attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF)
            continue

        if not data.get("ok"):
            logger.warning("Detail API returned ok=false for %s: %s", station_id, data.get("message"))
            return None

        s = data.get("station", {})
        street = s.get("street", "")
        if s.get("houseNumber"):
            street = f"{street} {s['houseNumber']}"
        city = f"{s.get('postCode', '')} {s.get('place', '')}".strip()
        name = s.get("name") or s.get("brand") or station_id

        logger.info("Station %s: %s (%s, %s)", station_id, name, street, city)
        return {
            "id": station_id,
            "name": name,
            "brand": s.get("brand"),
            "street": street or None,
            "city": city or None,
        }

    logger.warning("Could not fetch details for station %s: %s", station_id, last_exc)
    return None
