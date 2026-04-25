"""
Scenario Engine — engine.py

Translates a composite WorldState snapshot into a single, named scenario
that the GenUI offer renderer can act on.  All logic is pure (no I/O) so
it is trivially testable and deterministic given the same WorldState.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from .models import ScenarioResult, WorldState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scenario identifiers
# ---------------------------------------------------------------------------

_SHELTER_SEEKER = "SHELTER_SEEKER"
_FESTIVAL_VIBE = "FESTIVAL_VIBE"
_COZY_WEATHER = "COZY_WEATHER"
_NORMAL_CITY_FLOW = "NORMAL_CITY_FLOW"

# Foot-traffic threshold below which a merchant is considered "uncrowded"
_LOW_DENSITY_THRESHOLD = 0.3

# Temperature ceiling (°C) for the COZY_WEATHER trigger
_COLD_TEMP_THRESHOLD = 12.0


class ScenarioEngine:
    """
    Stateless rule engine that maps a WorldState to a ScenarioResult.

    Rules are evaluated in priority order — the first match wins.
    Priority: SHELTER_SEEKER > FESTIVAL_VIBE > COZY_WEATHER > NORMAL_CITY_FLOW.
    """

    async def detect_composite_scenario(self, state: WorldState) -> ScenarioResult:
        """
        Evaluate composite signals and return the best-matching scenario.

        Args:
            state: A fully-populated WorldState from the ingestion layer.

        Returns:
            ScenarioResult with a named scenario_id and a UTC timestamp.
        """
        scenario_id = self._evaluate(state)
        result = ScenarioResult(
            scenario_id=scenario_id,
            timestamp=datetime.now(tz=timezone.utc),
        )
        logger.info(
            "Scenario detected: %s (weather=%s %.1f°C raining=%s | events=%d | merchants=%d)",
            scenario_id,
            state.weather.condition,
            state.weather.temperature,
            state.weather.is_raining,
            len(state.events.active_events),
            len(state.merchants),
        )
        return result

    # ------------------------------------------------------------------
    # Internal rule evaluators (each returns True / False)
    # ------------------------------------------------------------------

    @staticmethod
    def _evaluate(state: WorldState) -> str:
        """Return the first matching scenario ID in priority order."""
        if ScenarioEngine._is_shelter_seeker(state):
            return _SHELTER_SEEKER
        if ScenarioEngine._is_festival_vibe(state):
            return _FESTIVAL_VIBE
        if ScenarioEngine._is_cozy_weather(state):
            return _COZY_WEATHER
        return _NORMAL_CITY_FLOW

    @staticmethod
    def _is_shelter_seeker(state: WorldState) -> bool:
        """Rain + at least one merchant below the low-density threshold."""
        if not state.weather.is_raining:
            return False
        return any(
            m.transaction_density < _LOW_DENSITY_THRESHOLD
            for m in state.merchants.values()
        )

    @staticmethod
    def _is_festival_vibe(state: WorldState) -> bool:
        """Active city events with dry weather — ideal outdoor festival conditions."""
        return bool(state.events.active_events) and not state.weather.is_raining

    @staticmethod
    def _is_cozy_weather(state: WorldState) -> bool:
        """Cold but dry — nudges users toward warm-drink / indoor offers."""
        return (
            state.weather.temperature < _COLD_TEMP_THRESHOLD
            and not state.weather.is_raining
        )
