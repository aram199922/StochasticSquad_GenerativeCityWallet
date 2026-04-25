"""
Data Contract models for the Generative City-Wallet pipeline.

Every layer of the pipeline (ingestion → AI engine → GenUI renderer) must
import from here so that a single change propagates everywhere.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Atomic context states
# ---------------------------------------------------------------------------

class WeatherState(BaseModel):
    """Current ambient weather at the user's approximate location."""

    condition: str = Field(
        ...,
        description="Human-readable weather condition, e.g. 'clear', 'rain', 'snow'.",
    )
    temperature: float = Field(
        ...,
        description="Ambient temperature in degrees Celsius.",
    )
    is_raining: bool = Field(
        ...,
        description="True when precipitation is currently occurring.",
    )


class EventState(BaseModel):
    """Live city-event context that may influence offer relevance."""

    active_events: list[str] = Field(
        default_factory=list,
        description="Names or short descriptions of events active near the user.",
    )


class MerchantState(BaseModel):
    """Real-time foot-traffic snapshot for a single merchant."""

    merchant_id: str = Field(
        ...,
        description="Unique identifier matching a record in payone_db.json.",
    )
    transaction_density: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Normalised foot-traffic intensity: 0.0 = empty, 1.0 = peak capacity."
        ),
    )


# ---------------------------------------------------------------------------
# Composite world state
# ---------------------------------------------------------------------------

class WorldState(BaseModel):
    """
    Full environmental snapshot passed to the AI offer engine.

    ``merchants`` is keyed by ``merchant_id`` so look-ups are O(1) and the
    structure self-documents which merchant a state belongs to.
    """

    weather: WeatherState
    events: EventState
    merchants: dict[str, MerchantState] = Field(
        default_factory=dict,
        description="Map of merchant_id → MerchantState for all active merchants.",
    )


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

class ScenarioResult(BaseModel):
    """Identifies a completed offer-generation scenario for tracing and replay."""

    scenario_id: str = Field(
        ...,
        description="Unique identifier for this scenario run (e.g. a UUID).",
    )
    timestamp: datetime = Field(
        ...,
        description="UTC datetime at which the scenario result was produced.",
    )
