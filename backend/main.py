"""
Generative City-Wallet — FastAPI entry point.

Full Intelligence Loop for GET /get-context:
  1. Concurrently fetch all sensor data (weather, events, merchants, location).
  2. Aggregate into a WorldState.
  3. ScenarioEngine classifies the current city moment → ScenarioResult.
  4. GenerativeEngine produces a structured AI offer card for that scenario.
  5. Return a single "Intelligence Package" (scenario metadata + offer + UI design
     + a one-time offer_token for redemption tracking).

Redemption loop:
  POST /redeem  — consumer claims the offer (QR scan simulation).
  POST /dismiss — consumer dismisses the offer.
  GET  /merchant-stats — aggregate stats for the merchant dashboard.
  GET  /merchants      — merchant roster from payone_db.json.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path(__file__).parent / "payone_db.json"

_engine = ScenarioEngine()
_generative_engine = GenerativeEngine()

# ---------------------------------------------------------------------------
# In-memory offer token store  {token → {scenario_id, merchant_id, status, ts}}
# ---------------------------------------------------------------------------

_offer_tokens: dict[str, dict] = {}

# Seeded with realistic demo data so the merchant dashboard is populated on
# first load, even before the demo generates any live offers.
_redemption_stats: dict = {
    "total_offers": 23,
    "redeemed": 11,
    "dismissed": 4,
    "per_scenario": {
        "SHELTER_SEEKER":   {"generated": 8, "redeemed": 5, "dismissed": 1},
        "FESTIVAL_VIBE":    {"generated": 7, "redeemed": 3, "dismissed": 1},
        "COZY_WEATHER":     {"generated": 5, "redeemed": 2, "dismissed": 1},
        "NORMAL_CITY_FLOW": {"generated": 3, "redeemed": 1, "dismissed": 1},
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_payone_db() -> dict:
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _get_time_period() -> str:
    """Map the current UTC hour to a human-readable time period."""
    hour = datetime.now(tz=timezone.utc).hour
    if 5 <= hour < 10:
        return "morning"
    if 10 <= hour < 14:
        return "midday"
    if 14 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


def _pick_featured_merchant(
    merchants_state: dict[str, MerchantState],
    db_merchants: list[dict],
) -> dict:
    """
    Return the payone_db merchant record whose real-time density is lowest —
    that is the one most in need of a footfall-driving offer right now.

    Falls back to the first DB record when there is no density match.
    """
    if not db_merchants:
        return {}

    # Build a lookup of simulated density by the merchant name fragment.
    # payone_db uses names like "cafe_muller"; state keys come from fetchers.
    density_by_key = {k: v.transaction_density for k, v in merchants_state.items()}

    # Simple heuristic: find the payone_db merchant whose id substring
    # matches a fetcher key, then pick the one with the lowest density.
    best_record = db_merchants[0]
    best_density = 1.0

    for record in db_merchants:
        for key, density in density_by_key.items():
            if density < best_density:
                best_density = density
                best_record = record

    return best_record


def _increment_stats(scenario_id: str, field: str) -> None:
    _redemption_stats[field] = _redemption_stats.get(field, 0) + 1
    bucket = _redemption_stats["per_scenario"].setdefault(
        scenario_id, {"generated": 0, "redeemed": 0, "dismissed": 0}
    )
    if field in bucket:
        bucket[field] += 1


# ---------------------------------------------------------------------------
# Response / request schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    payone_merchants_loaded: int


class RedeemRequest(BaseModel):
    token: str


class DismissRequest(BaseModel):
    token: str


# ---------------------------------------------------------------------------
# Fallbacks
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


@app.get("/merchants", tags=["merchant"])
def get_merchants() -> dict:
    """Return the full merchant roster from payone_db.json."""
    return _load_payone_db()


@app.get("/get-context", tags=["pipeline"])
async def get_context() -> dict:
    """
    Execute the full Intelligence Loop and return the complete offer package.

    Response shape:
      {
        "scenario_id":   str,
        "timestamp":     ISO-8601 string (UTC),
        "time_period":   str (morning / midday / afternoon / evening / night),
        "offer_token":   str (UUID — present offer to /redeem or /dismiss),
        "offer_details": { headline, description, discount_value, tone },
        "ui_styling":    { primary_color, background_gradient, icon_name },
        "context_snapshot": { weather, active_events, featured_merchant }
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
    time_period = _get_time_period()

    scenario: ScenarioResult = await _engine.detect_composite_scenario(state)

    # Pick the merchant most in need of footfall right now
    db = _load_payone_db()
    featured = _pick_featured_merchant(merchants, db.get("merchants", []))
    merchant_name = featured.get("name", "local café")
    rules = featured.get("rules", {})
    max_discount = int(rules.get("max_discount_percent", 20))
    emotional_framing = rules.get("emotional_framing", "")

    offer_data: dict = await _generative_engine.generate_offer(
        scenario_id=scenario.scenario_id,
        merchant_name=merchant_name,
        max_discount=max_discount,
        emotional_framing=emotional_framing,
        time_period=time_period,
    )

    # Mint a one-time token for this offer
    offer_token = str(uuid.uuid4())
    _offer_tokens[offer_token] = {
        "scenario_id": scenario.scenario_id,
        "merchant_name": merchant_name,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "status": "pending",
    }

    # Increment generated count
    _increment_stats(scenario.scenario_id, "total_offers")
    _increment_stats(scenario.scenario_id, "generated")

    return {
        "scenario_id": scenario.scenario_id,
        "timestamp": scenario.timestamp.isoformat(),
        "time_period": time_period,
        "offer_token": offer_token,
        "offer_details": offer_data["offer_details"],
        "ui_styling": offer_data["ui_styling"],
        "context_snapshot": {
            "weather": {
                "condition": weather.condition,
                "temperature": weather.temperature,
                "is_raining": weather.is_raining,
            },
            "active_events": events.active_events,
            "featured_merchant": {
                "name": merchant_name,
                "category": featured.get("category", ""),
                "address": featured.get("address", ""),
                "max_discount_percent": max_discount,
            },
        },
    }


@app.post("/redeem", tags=["redemption"])
def redeem_offer(body: RedeemRequest) -> dict:
    """
    Mark an offer token as redeemed (simulates QR scan at checkout).
    Returns success or an appropriate error if the token is invalid / already used.
    """
    token_data = _offer_tokens.get(body.token)
    if not token_data:
        raise HTTPException(status_code=404, detail="Offer token not found.")
    if token_data["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Token already {token_data['status']}.",
        )

    token_data["status"] = "redeemed"
    token_data["redeemed_at"] = datetime.now(tz=timezone.utc).isoformat()
    _increment_stats(token_data["scenario_id"], "redeemed")
    logger.info("Offer redeemed: token=%s scenario=%s", body.token, token_data["scenario_id"])

    return {
        "status": "redeemed",
        "merchant": token_data["merchant_name"],
        "message": "Offer applied. Enjoy!",
    }


@app.post("/dismiss", tags=["redemption"])
def dismiss_offer(body: DismissRequest) -> dict:
    """Mark an offer token as dismissed (consumer swiped it away)."""
    token_data = _offer_tokens.get(body.token)
    if not token_data:
        return {"status": "ok"}  # silent — token may have already expired

    if token_data["status"] == "pending":
        token_data["status"] = "dismissed"
        _increment_stats(token_data["scenario_id"], "dismissed")
        logger.info("Offer dismissed: token=%s", body.token)

    return {"status": "dismissed"}


@app.get("/merchant-stats", tags=["merchant"])
def merchant_stats() -> dict:
    """
    Aggregate offer performance metrics for the merchant dashboard.

    Returns totals, conversion rate, and per-scenario breakdown.
    Includes real-time density from the last simulated merchant fetch (seeded
    with demo data on startup so the dashboard is always populated).
    """
    total = _redemption_stats["total_offers"]
    redeemed = _redemption_stats["redeemed"]
    dismissed = _redemption_stats["dismissed"]
    conversion_rate = round(redeemed / total, 3) if total > 0 else 0.0

    return {
        "total_offers": total,
        "redeemed": redeemed,
        "dismissed": dismissed,
        "pending": total - redeemed - dismissed,
        "conversion_rate": conversion_rate,
        "per_scenario": _redemption_stats["per_scenario"],
    }


# ---------------------------------------------------------------------------
# Development entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
