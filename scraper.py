"""
Scraper for clever-tanken.de — used as fallback when no Tankerkönig API key is available.

Interface is identical to collector.fetch_prices() so main.py can swap them transparently.

Station IDs are clever-tanken.de numeric IDs (e.g. 5329), stored as strings.
Find your station ID by searching on clever-tanken.de and copying the number from the URL:
    https://www.clever-tanken.de/tankstelle_details/<ID>
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.clever-tanken.de/tankstelle_details/{}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 15
MAX_RETRIES = 3
RETRY_BACKOFF = 5
INTER_REQUEST_DELAY = 1  # seconds between stations, to be polite

# Prices are displayed as e.g. "2.31 9" (superscript last digit) or "2.319"
# This regex captures all three variants.
_PRICE_RE = re.compile(r'(\d)[.,](\d{2})\s*(\d)')

# Match fuel type labels — E10 must be checked before E5 (longer match first)
_FUEL_LABELS: dict[str, re.Pattern] = {
    "diesel": re.compile(r'\bDiesel\b', re.IGNORECASE),
    "e10":    re.compile(r'\bSuper\s*E10\b', re.IGNORECASE),
    "e5":     re.compile(r'\bSuper\s*E5\b', re.IGNORECASE),
}
# How many characters after the fuel-type label to search for the price
_SEARCH_WINDOW = 200


def _parse_prices(html: str) -> dict[str, float | None]:
    """Return {fuel_type: price} extracted from station page HTML. Price is None if not found."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ")

    prices: dict[str, float | None] = {}
    for fuel_type, label_re in _FUEL_LABELS.items():
        match = label_re.search(text)
        if not match:
            prices[fuel_type] = None
            continue

        snippet = text[match.start(): match.start() + _SEARCH_WINDOW]
        price_match = _PRICE_RE.search(snippet)
        if price_match:
            price_str = f"{price_match.group(1)}.{price_match.group(2)}{price_match.group(3)}"
            prices[fuel_type] = float(price_str)
        else:
            prices[fuel_type] = None  # station may be closed or price unavailable

    return prices


def _fetch_station(station_id: str) -> str | None:
    """Fetch the HTML for a single station page. Returns None if all retries fail."""
    url = BASE_URL.format(station_id)
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning(
                "Station %s – attempt %d/%d failed: %s",
                station_id, attempt, MAX_RETRIES, exc,
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF)

    logger.error("Station %s – all %d retries failed: %s", station_id, MAX_RETRIES, last_exc)
    return None


def fetch_prices(station_ids: list[str], api_key: str = "") -> list[dict]:
    """
    Scrape current fuel prices from clever-tanken.de.

    Parameters
    ----------
    station_ids : list[str]
        clever-tanken.de numeric station IDs (as strings or ints).
    api_key : str
        Ignored — exists only to keep the same signature as collector.fetch_prices().

    Returns
    -------
    list[dict]
        Each dict has keys: station_id, fuel_type, price, timestamp.
        price is None when the station is closed or the price is unavailable.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []

    for i, station_id in enumerate(station_ids):
        station_id = str(station_id)
        html = _fetch_station(station_id)

        if html is None:
            continue

        prices = _parse_prices(html)
        found = sum(1 for p in prices.values() if p is not None)
        logger.info("Station %s – scraped %d/%d prices", station_id, found, len(prices))

        for fuel_type, price in prices.items():
            rows.append({
                "station_id": station_id,
                "fuel_type": fuel_type,
                "price": price,
                "timestamp": timestamp,
            })

        # Polite delay between requests (skip after last station)
        if i < len(station_ids) - 1:
            time.sleep(INTER_REQUEST_DELAY)

    logger.info("Scraper finished: %d price records from %d stations", len(rows), len(station_ids))
    return rows
