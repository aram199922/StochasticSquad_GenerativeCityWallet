"""
Generative Intelligence Layer — generative_engine.py

Translates a scenario_id into a fully-structured GenUI offer payload using a
local LLM via Ollama (default: phi3).  The output strictly follows the
agreed Data Contract so the mobile renderer never receives free-form text.

Privacy guarantee: the prompt contains ZERO user-identifiable data.
Only the abstract scenario label and city-level atmospheric context are sent
to the model.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scenario context table
# Keys are scenario_ids produced by ScenarioEngine.
# Each entry feeds the human-turn prompt with tone guidance and atmospheric
# framing so the LLM can craft the right emotional register.
# ---------------------------------------------------------------------------

_SCENARIO_CONTEXT: dict[str, dict[str, str]] = {
    "SHELTER_SEEKER": {
        "tone": "warm, comforting, and inviting",
        "situation": (
            "It is currently raining in the city and several nearby merchants "
            "are quieter than usual — a perfect moment to welcome someone in "
            "from the rain with a cosy refuge and a genuinely helpful offer."
        ),
        "primary_color": "#E8863A",
        "background_gradient": "linear-gradient(135deg, #F5A623 0%, #E8863A 100%)",
        "icon_name": "umbrella-cozy",
    },
    "FESTIVAL_VIBE": {
        "tone": "energetic, exciting, and upbeat",
        "situation": (
            "There are live events happening across the city right now and the "
            "weather is dry — the streets are buzzing and people are in a mood "
            "to celebrate, explore, and treat themselves."
        ),
        "primary_color": "#7C3AED",
        "background_gradient": "linear-gradient(135deg, #F472B6 0%, #7C3AED 100%)",
        "icon_name": "confetti-star",
    },
    "COZY_WEATHER": {
        "tone": "warm, hygge-inspired, and gently indulgent",
        "situation": (
            "The temperature has dropped and the air is crisp but dry — the "
            "kind of weather that makes people crave warmth, comfort food, "
            "and a reason to slow down and treat themselves."
        ),
        "primary_color": "#92400E",
        "background_gradient": "linear-gradient(135deg, #D97706 0%, #92400E 100%)",
        "icon_name": "hot-drink",
    },
    "NORMAL_CITY_FLOW": {
        "tone": "friendly, helpful, and effortlessly relevant",
        "situation": (
            "City life is flowing normally — a good moment for a smart, "
            "well-timed everyday offer that feels like a pleasant surprise "
            "rather than a hard sell."
        ),
        "primary_color": "#0369A1",
        "background_gradient": "linear-gradient(135deg, #38BDF8 0%, #0369A1 100%)",
        "icon_name": "city-spark",
    },
}

_DEFAULT_SCENARIO = "NORMAL_CITY_FLOW"

# ---------------------------------------------------------------------------
# Hard-coded fallbacks — returned when Ollama is unavailable or times out.
# Structured identically to the LLM output so the renderer never needs to
# branch on whether the payload came from the model or the fallback.
# ---------------------------------------------------------------------------

_FALLBACKS: dict[str, dict[str, Any]] = {
    "SHELTER_SEEKER": {
        "offer_details": {
            "headline": "Step Inside — It's Warm In Here",
            "description": "Rain outside, calm inside. Enjoy a free upgrade on your next hot drink.",
            "discount_value": "Free size upgrade",
            "tone": "warm, comforting, and inviting",
        },
        "ui_styling": {
            "primary_color": "#E8863A",
            "background_gradient": "linear-gradient(135deg, #F5A623 0%, #E8863A 100%)",
            "icon_name": "umbrella-cozy",
        },
    },
    "FESTIVAL_VIBE": {
        "offer_details": {
            "headline": "The City Is Alive — Join In",
            "description": "Festival energy deserves festival prices. Flash deal active right now.",
            "discount_value": "20% off today only",
            "tone": "energetic, exciting, and upbeat",
        },
        "ui_styling": {
            "primary_color": "#7C3AED",
            "background_gradient": "linear-gradient(135deg, #F472B6 0%, #7C3AED 100%)",
            "icon_name": "confetti-star",
        },
    },
    "COZY_WEATHER": {
        "offer_details": {
            "headline": "Cold Outside, Cosy Inside",
            "description": "Wrap up your afternoon with something warm. A little treat for a chilly day.",
            "discount_value": "15% off warm beverages",
            "tone": "warm, hygge-inspired, and gently indulgent",
        },
        "ui_styling": {
            "primary_color": "#92400E",
            "background_gradient": "linear-gradient(135deg, #D97706 0%, #92400E 100%)",
            "icon_name": "hot-drink",
        },
    },
    "NORMAL_CITY_FLOW": {
        "offer_details": {
            "headline": "A Little Something For Your Day",
            "description": "Because the best surprises are the ones that fit perfectly into your routine.",
            "discount_value": "10% off your next visit",
            "tone": "friendly, helpful, and effortlessly relevant",
        },
        "ui_styling": {
            "primary_color": "#0369A1",
            "background_gradient": "linear-gradient(135deg, #38BDF8 0%, #0369A1 100%)",
            "icon_name": "city-spark",
        },
    },
}

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a Hyper-personalized Local Marketing Expert embedded inside a \
privacy-first city wallet app.

Your sole job is to craft a micro-offer card for a user based ONLY on the \
current atmospheric city scenario — never on personal data, purchase history, \
or any user-identifiable information.

OUTPUT RULES (non-negotiable):
1. Respond with ONLY a single valid JSON object — no markdown, no explanation, \
no trailing text.
2. The JSON must match this exact schema:
{{
  "offer_details": {{
    "headline":       "<max 8 words, punchy and scenario-appropriate>",
    "description":    "<1-2 sentences, emotionally resonant, scenario-aware>",
    "discount_value": "<concise value proposition, e.g. '20% off' or 'Free upgrade'>",
    "tone":           "<the emotional register you used>"
  }},
  "ui_styling": {{
    "primary_color":       "<hex color that matches the mood>",
    "background_gradient": "<CSS linear-gradient() string>",
    "icon_name":           "<lowercase-kebab-case icon hint>"
  }}
}}
3. Never include user names, locations, personal preferences, or any PII.
4. The offer must feel earned and natural for the scenario — not generic.
5. The headline must provoke an emotional reaction in under 3 seconds of reading.\
"""

_HUMAN_PROMPT = """\
Current city scenario: {scenario_id}
Emotional tone required: {tone}
Atmospheric context: {situation}

Generate the offer card JSON now.\
"""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class GenerativeEngine:
    """
    Wraps a LangChain → Ollama chain that generates structured GenUI offer
    payloads from a scenario label.

    The chain is built once at construction time; ``generate_offer`` is the
    only public method and is safe to call concurrently.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
    ) -> None:
        resolved_model = model or os.getenv("OLLAMA_MODEL", "phi3")
        resolved_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        llm = ChatOllama(
            model=resolved_model,
            base_url=resolved_url,
            temperature=temperature,
            # Instruct Ollama to return JSON — models that support the format
            # flag will honour it; others rely on the prompt alone.
            format="json",
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _SYSTEM_PROMPT),
                ("human", _HUMAN_PROMPT),
            ]
        )

        parser = JsonOutputParser()

        # LangChain Expression Language (LCEL) chain: prompt | llm | parser
        self._chain = prompt | llm | parser
        logger.info(
            "GenerativeEngine initialised (model=%s, url=%s)",
            resolved_model,
            resolved_url,
        )

    async def generate_offer(self, scenario_id: str) -> dict[str, Any]:
        """
        Generate a structured GenUI offer payload for the given scenario.

        Falls back to a pre-crafted static payload when Ollama is unreachable
        or returns malformed JSON — the mobile renderer always gets a valid card.

        Args:
            scenario_id: One of the scenario labels from ScenarioEngine.

        Returns:
            A dict matching the GenUI Data Contract (offer_details + ui_styling).
        """
        context = _SCENARIO_CONTEXT.get(scenario_id, _SCENARIO_CONTEXT[_DEFAULT_SCENARIO])
        fallback = _FALLBACKS.get(scenario_id, _FALLBACKS[_DEFAULT_SCENARIO])

        try:
            result: dict[str, Any] = await self._chain.ainvoke(
                {
                    "scenario_id": scenario_id,
                    "tone": context["tone"],
                    "situation": context["situation"],
                }
            )
            _validate_contract(result)
            logger.info("LLM offer generated for scenario=%s", scenario_id)
            return result

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "LLM generation failed for scenario=%s (%s) — using fallback.",
                scenario_id,
                exc,
            )
            return fallback


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_contract(payload: dict[str, Any]) -> None:
    """
    Raise ValueError if the LLM payload is missing required top-level keys.
    A partial payload is worse than a clean fallback, so we reject it early.
    """
    required_top = {"offer_details", "ui_styling"}
    required_offer = {"headline", "description", "discount_value", "tone"}
    required_ui = {"primary_color", "background_gradient", "icon_name"}

    missing_top = required_top - payload.keys()
    if missing_top:
        raise ValueError(f"LLM payload missing top-level keys: {missing_top}")

    missing_offer = required_offer - payload["offer_details"].keys()
    if missing_offer:
        raise ValueError(f"LLM payload missing offer_details keys: {missing_offer}")

    missing_ui = required_ui - payload["ui_styling"].keys()
    if missing_ui:
        raise ValueError(f"LLM payload missing ui_styling keys: {missing_ui}")
