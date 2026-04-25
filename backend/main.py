"""
Generative City-Wallet — FastAPI entry point.

Full Intelligence Loop for GET /get-context:
  1. Concurrently fetch all sensor data (weather, events, merchants, location).
  2. Aggregate into a WorldState.
  3. ScenarioEngine classifies the current city moment → ScenarioResult.
  4. GenerativeEngine produces a structured AI offer card for that scenario.
  5. Return a single "Intelligence Package" (scenario metadata + offer + UI design).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .engine import ScenarioEngine
from .fetchers import (
    fetch_events,
    fetch_merchant_data,
    fetch_user_location,
    fetch_weather,
)
from .generative_engine import GenerativeEngine
from .models import EventState, MerchantState, ScenarioResult, WeatherState, WorldState

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Generative City-Wallet API",
    description="Backend orchestrator for the DSV Gruppe hackathon — privacy-first GenUI offer engine.",
    version="0.1.0",
)

DB_PATH = Path(__file__).parent / "payone_db.json"

_engine = ScenarioEngine()
_generative_engine = GenerativeEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_payone_db() -> dict:
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    payone_merchants_loaded: int


# ---------------------------------------------------------------------------
# Fallbacks used when an individual fetcher raises an unexpected exception
# ---------------------------------------------------------------------------

_FALLBACK_WEATHER = WeatherState(condition="clear", temperature=20.0, is_raining=False)
_FALLBACK_EVENTS = EventState(active_events=[])
_FALLBACK_MERCHANTS: dict[str, MerchantState] = {}


async def _safe_fetch_weather() -> WeatherState:
    try:
        return await fetch_weather()
    except Exception as exc:  # noqa: BLE001
        logger.error("fetch_weather raised unexpectedly: %s", exc)
        return _FALLBACK_WEATHER


async def _safe_fetch_events() -> EventState:
    try:
        return await fetch_events()
    except Exception as exc:  # noqa: BLE001
        logger.error("fetch_events raised unexpectedly: %s", exc)
        return _FALLBACK_EVENTS


async def _safe_fetch_merchants() -> dict[str, MerchantState]:
    try:
        return await fetch_merchant_data()
    except Exception as exc:  # noqa: BLE001
        logger.error("fetch_merchant_data raised unexpectedly: %s", exc)
        return _FALLBACK_MERCHANTS


async def _safe_fetch_location() -> dict:
    try:
        return await fetch_user_location()
    except Exception as exc:  # noqa: BLE001
        logger.error("fetch_user_location raised unexpectedly: %s", exc)
        return {"lat": 0.0, "lon": 0.0, "velocity_ms": 0.0}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    """Confirms the API is alive and the stubbed Payone DB is reachable."""
    db = _load_payone_db()
    return HealthResponse(
        status="ok",
        payone_merchants_loaded=len(db.get("merchants", [])),
    )


@app.get("/get-context", tags=["pipeline"])
async def get_context() -> dict:
    """
    Execute the full Intelligence Loop and return the complete offer package.

    Steps (all I/O runs concurrently where possible):
      - Four sensor fetches dispatched together via asyncio.gather.
      - ScenarioEngine maps the WorldState to a named scenario.
      - GenerativeEngine produces a structured AI offer card for that scenario.

    Response shape:
      {
        "scenario_id":  str,
        "timestamp":    ISO-8601 string (UTC),
        "offer_details": { headline, description, discount_value, tone },
        "ui_styling":    { primary_color, background_gradient, icon_name }
      }
    """
    try:
        weather, events, merchants, location = await asyncio.gather(
            _safe_fetch_weather(),
            _safe_fetch_events(),
            _safe_fetch_merchants(),
            _safe_fetch_location(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected failure during asyncio.gather: %s", exc)
        raise HTTPException(status_code=500, detail="Context ingestion failed.") from exc

    logger.debug("User location snapshot: %s", location)

    state = WorldState(weather=weather, events=events, merchants=merchants)

    scenario: ScenarioResult = await _engine.detect_composite_scenario(state)
    offer_data: dict = await _generative_engine.generate_offer(scenario.scenario_id)

    return {
        "scenario_id": scenario.scenario_id,
        "timestamp": scenario.timestamp.isoformat(),
        "offer_details": offer_data["offer_details"],
        "ui_styling": offer_data["ui_styling"],
    }


# ---------------------------------------------------------------------------
# Development entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
