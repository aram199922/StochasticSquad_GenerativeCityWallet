"""
Data Ingestion Layer — fetchers.py

Hybrid strategy:
  • Real APIs  → OpenWeatherMap (weather), Tavily Search (city events).
  • Simulated  → merchant foot-traffic, user location.

Every function is async and returns a Pydantic model from models.py.
Set OPENWEATHERMAP_API_KEY and TAVILY_API_KEY in .env to enable live data;
omit them to run fully on deterministic / random fallbacks (demo-safe).
"""

from __future__ import annotations

import logging
import os
import random

import httpx
from dotenv import load_dotenv

from .models import EventState, MerchantState, WeatherState

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_CITY: str = os.getenv("CITY", "Stuttgart")

_OWM_URL = "https://api.openweathermap.org/data/2.5/weather"
_TAVILY_URL = "https://api.tavily.com/search"

# OWM weather condition groups that imply precipitation
_RAINY_CONDITIONS = {"rain", "drizzle", "thunderstorm", "squall", "tornado"}

# ---------------------------------------------------------------------------
# Fallbacks  (used when API keys are absent or a request fails)
# ---------------------------------------------------------------------------

_WEATHER_FALLBACK = WeatherState(
    condition="clear",
    temperature=20.0,
    is_raining=False,
)

_EVENTS_FALLBACK = EventState(
    active_events=[
        "Stuttgart Wine Festival",
        "City Marathon – road closures until 14:00",
        "Farmer's Market at Marktplatz",
    ]
)

# ---------------------------------------------------------------------------
# Real-API fetchers
# ---------------------------------------------------------------------------

async def fetch_weather() -> WeatherState:
    """
    Fetch current weather from OpenWeatherMap for the configured city.

    Falls back to a sunny 20 °C stub when OPENWEATHERMAP_API_KEY is unset
    or the request fails — so the demo never crashes on a missing key.
    """
    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if not api_key:
        logger.warning("OPENWEATHERMAP_API_KEY not configured — using fallback WeatherState.")
        return _WEATHER_FALLBACK

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                _OWM_URL,
                params={"q": _CITY, "appid": api_key, "units": "metric"},
            )
            response.raise_for_status()
            data: dict = response.json()

        condition: str = data["weather"][0]["main"].lower()
        temperature: float = round(data["main"]["temp"], 1)
        is_raining: bool = condition in _RAINY_CONDITIONS

        logger.info("Weather fetched: %s %.1f°C raining=%s", condition, temperature, is_raining)
        return WeatherState(condition=condition, temperature=temperature, is_raining=is_raining)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Weather fetch failed (%s) — using fallback.", exc)
        return _WEATHER_FALLBACK


async def fetch_events() -> EventState:
    """
    Search for live city events via the Tavily Search API.

    Tavily returns ranked web results; we extract the ``title`` field of each
    result as a concise event label.  Falls back to a curated stub list when
    TAVILY_API_KEY is unset or the request fails.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.warning("TAVILY_API_KEY not configured — using fallback EventState.")
        return _EVENTS_FALLBACK

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(
                _TAVILY_URL,
                json={
                    "api_key": api_key,
                    "query": f"events happening today in {_CITY}",
                    "search_depth": "basic",
                    "max_results": 5,
                },
            )
            response.raise_for_status()
            data: dict = response.json()

        titles: list[str] = [
            result["title"]
            for result in data.get("results", [])
            if result.get("title")
        ]

        if not titles:
            logger.info("Tavily returned no event titles — using fallback.")
            return _EVENTS_FALLBACK

        logger.info("Events fetched: %s", titles)
        return EventState(active_events=titles)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Events fetch failed (%s) — using fallback.", exc)
        return _EVENTS_FALLBACK


# ---------------------------------------------------------------------------
# Simulated fetchers
# ---------------------------------------------------------------------------

#: Merchant roster that mirrors the stub records in payone_db.json.
_MERCHANT_IDS: list[str] = ["cafe_muller", "bakery_stuttgart", "fashion_hub"]


async def fetch_merchant_data() -> dict[str, MerchantState]:
    """
    Simulate real-time foot-traffic for each merchant.

    In a production system this would query a Payone transaction-stream
    endpoint.  For the demo we draw a random density per merchant on every
    call so the AI engine always sees a fresh, non-trivial snapshot.
    """
    merchants: dict[str, MerchantState] = {
        mid: MerchantState(
            merchant_id=mid,
            transaction_density=round(random.uniform(0.0, 1.0), 2),
        )
        for mid in _MERCHANT_IDS
    }
    logger.debug("Simulated merchant densities: %s", {k: v.transaction_density for k, v in merchants.items()})
    return merchants


async def fetch_user_location() -> dict[str, float]:
    """
    Simulate the user's current position and movement speed.

    The mobile app is the authoritative source of location; it would POST
    an abstract intent (not raw coordinates) to the backend.  This stub
    returns a fixed Stuttgart city-centre point with a walking velocity so
    the rest of the pipeline can be exercised without a real device.

    Returns a plain ``dict`` rather than a Pydantic model because location
    is treated as ephemeral transport data, not a persisted domain object.
    Keys: ``lat`` (float), ``lon`` (float), ``velocity_ms`` (float, m/s).
    """
    return {
        "lat": 48.7758,   # Stuttgart Marktplatz
        "lon": 9.1829,
        "velocity_ms": round(random.uniform(0.8, 1.6), 2),  # normal walking pace
    }
