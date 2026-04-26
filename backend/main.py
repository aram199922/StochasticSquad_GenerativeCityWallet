import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("citywallet")

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel
from tavily import TavilyClient

load_dotenv()

app = FastAPI(
    title="Generative City-Wallet API",
    description="Backend orchestrator for the DSV Gruppe hackathon — privacy-first GenUI offer engine.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path(__file__).parent / "payone_db.json"
DEMO_PATH = Path(__file__).parent.parent / "demo"

# Serve the demo UI as static files at /demo
if DEMO_PATH.exists():
    app.mount("/demo", StaticFiles(directory=str(DEMO_PATH), html=True), name="demo")

# ---------------------------------------------------------------------------
# In-memory stores (hackathon MVP — no persistent DB needed)
# ---------------------------------------------------------------------------

# discount_code -> offer record
_active_offers: dict[str, dict] = {}
# merchant_id -> list of offer records
_merchant_offers: dict[str, list] = {}
# discount_code -> redemption record
_redemptions: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_payone_db() -> dict:
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _get_merchant(merchant_id: str) -> dict:
    db = _load_payone_db()
    for m in db["merchants"]:
        if m["id"] == merchant_id:
            return m
    raise HTTPException(status_code=404, detail=f"Merchant '{merchant_id}' not found")


_WEATHER_STUB = {"temp_celsius": 11.0, "description": "overcast clouds", "feels_like": 8.5}

async def _fetch_weather(lat: float, lon: float) -> dict:
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return _WEATHER_STUB
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    )
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
        return {
            "temp_celsius": data["main"]["temp"],
            "description": data["weather"][0]["description"],
            "feels_like": data["main"]["feels_like"],
        }
    except Exception:
        # Invalid key, network error, or quota exceeded — fall back to stub
        return _WEATHER_STUB


def _fetch_events(location: str) -> list[str]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return ["Stuttgart Wochenmarkt", "Stadtbibliothek reading event"]
    try:
        client = TavilyClient(api_key=api_key)
        results = client.search(
            query=f"local events today {location}",
            search_depth="basic",
            max_results=3,
        )
        return [r["title"] for r in results.get("results", [])]
    except Exception:
        return ["Stuttgart Wochenmarkt", "Stadtbibliothek reading event"]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    payone_merchants_loaded: int


class ContextRequest(BaseModel):
    merchant_id: str
    lat: float = 48.7758
    lon: float = 9.1829


class ContextState(BaseModel):
    merchant_id: str
    merchant_name: str
    temp_celsius: float
    weather_description: str
    feels_like: float
    local_events: list[str]
    payone_volume_ratio: float   # current / avg  (<1.0 = quiet, >1.0 = busy)
    current_transactions: int
    avg_transactions: int
    trigger_active: bool          # True when volume is below threshold


class IntentRequest(BaseModel):
    merchant_id: str
    intent: str                   # abstract intent from on-device model, e.g. "seek_warm_drink"
    context: ContextState


class MatchRequest(BaseModel):
    user_context: str                   # situation summary built on-device — no raw signals
    user_profile: str = ""              # GDPR-anonymised spending profile, also built on-device
    user_age_group: str = ""            # self-declared age bucket, e.g. "late 20s" — not exact DOB
    user_sex: str = ""                  # self-declared: male / female / other / prefer not to say
    user_profession: str = ""           # self-declared occupation for contextual tailoring
    user_interests: list[str] = []      # self-declared interest tags for personalisation
    scenario: str = ""                  # demo scenario key — controls which merchant is quiet
    lat: float = 48.7758
    lon: float = 9.1829


class GenUICard(BaseModel):
    offer_id: str
    merchant_id: str
    merchant_name: str
    headline: str
    subline: str
    discount_percent: int
    discount_code: str
    expiry_iso: str
    color_hex: str
    emotional_framing: str
    intent_matched: str
    llm_provider: str = "rule-based stub"


class RedeemRequest(BaseModel):
    discount_code: str
    merchant_id: str


class RedeemResponse(BaseModel):
    success: bool
    message: str
    redeemed_at: str | None = None


class MerchantActivity(BaseModel):
    merchant_id: str
    merchant_name: str
    current_transactions: int
    avg_transactions: int
    payone_volume_ratio: float
    trigger_active: bool
    offers_generated: int
    redemptions_count: int
    recent_offers: list[dict]
    recent_redemptions: list[dict]


# ---------------------------------------------------------------------------
# Routes — System
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    db = _load_payone_db()
    return HealthResponse(
        status="ok",
        payone_merchants_loaded=len(db.get("merchants", [])),
    )


# ---------------------------------------------------------------------------
# Routes — Context Sensing Layer (Module 01)
# ---------------------------------------------------------------------------

@app.post("/context", response_model=ContextState, tags=["context"])
async def get_context(req: ContextRequest) -> ContextState:
    """
    Aggregates real-time context signals: weather, local events, and Payone
    transaction density for the given merchant.
    """
    merchant = _get_merchant(req.merchant_id)
    weather = await _fetch_weather(req.lat, req.lon)
    events = _fetch_events(merchant["address"])

    current = merchant["current_transaction_volume"]
    avg = merchant["avg_hourly_transaction_volume"]
    ratio = round(current / avg, 2) if avg > 0 else 0.0
    threshold = merchant["rules"]["trigger_volume_threshold"]

    return ContextState(
        merchant_id=merchant["id"],
        merchant_name=merchant["name"],
        temp_celsius=weather["temp_celsius"],
        weather_description=weather["description"],
        feels_like=weather["feels_like"],
        local_events=events,
        payone_volume_ratio=ratio,
        current_transactions=current,
        avg_transactions=avg,
        trigger_active=current < threshold,
    )


# ---------------------------------------------------------------------------
# Routes — Generative Offer Engine (Module 02)
# ---------------------------------------------------------------------------

_OFFER_SYSTEM_PROMPT = """
You are the Generative City-Wallet offer engine for DSV Gruppe.
Your job: generate a hyper-personalised, context-aware offer card for a local merchant.

STRICT RULES:
1. Respond ONLY with a valid JSON object — no markdown, no explanation, no code fences.
2. Use the merchant's max_discount_percent as an upper bound; choose a discount that feels genuinely generous.
3. headline: ≤8 words, emotionally resonant, references the context (weather, time, intent).
4. subline: ≤15 words, factual detail (discount amount, min basket, expiry hint).
5. color_hex: choose a warm, inviting hex colour that matches the merchant category and emotional framing.
6. emotional_framing: one of [warm_shelter, scarcity_urgency, celebration, convenience, discovery].

Return exactly this JSON shape:
{
  "headline": "string",
  "subline": "string",
  "discount_percent": integer,
  "color_hex": "#rrggbb",
  "emotional_framing": "string"
}
""".strip()


def _build_offer_user_prompt(req: IntentRequest, merchant: dict) -> str:
    ctx = req.context
    rules = merchant["rules"]
    return (
        f"Merchant: {merchant['name']} ({merchant['category']})\n"
        f"User intent: {req.intent}\n"
        f"Weather: {ctx.weather_description}, {ctx.temp_celsius}°C (feels like {ctx.feels_like}°C)\n"
        f"Nearby events: {', '.join(ctx.local_events) or 'none'}\n"
        f"Payone volume ratio: {ctx.payone_volume_ratio} (current {ctx.current_transactions} vs avg {ctx.avg_transactions} txns/hr)\n"
        f"Merchant rules: max_discount={rules['max_discount_percent']}%, min_basket=€{rules['min_basket_eur']}, "
        f"preferred_framing={rules['emotional_framing']}\n"
        f"Generate the offer card JSON now."
    )


def _offer_stub(merchant: dict) -> dict:
    rules = merchant["rules"]
    return {
        "headline": rules.get("offer_headline_template", "A great deal is waiting for you."),
        "subline": f"{rules['max_discount_percent']}% off — min basket €{rules['min_basket_eur']} · expires in 30 min",
        "discount_percent": rules["max_discount_percent"],
        "color_hex": "#c8702a" if merchant["category"] == "cafe" else "#e8a020",
        "emotional_framing": rules["emotional_framing"],
    }


def _call_openai_compat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list,
    timeout: int = 30,
    temperature: float = 0.72,
) -> dict:
    """Calls any OpenAI-compatible API and returns the parsed JSON offer."""
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=temperature,
        timeout=timeout,
    )
    return json.loads(response.choices[0].message.content)


def _llm_generate_offer(req: IntentRequest, merchant: dict) -> dict:
    """
    Priority order (first key found wins):
      1. Groq  — free, open-weight (Llama 3.1 8B), very fast
      2. Gemini — free, Google (gemini-2.0-flash-lite)
      3. Mistral — free tier (mistral-small-latest)
      4. OpenAI — paid, gpt-4o-mini
      5. Rule-based stub — always works, no model needed
    """
    messages = [
        {"role": "system", "content": _OFFER_SYSTEM_PROMPT},
        {"role": "user", "content": _build_offer_user_prompt(req, merchant)},
    ]

    providers = []

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        providers.append({
            "name": "Groq (Llama 3.1 8B)",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key": groq_key,
            "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        })

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        providers.append({
            "name": "Gemini Flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key": gemini_key,
            "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite"),
        })

    mistral_key = os.getenv("MISTRAL_API_KEY")
    if mistral_key:
        providers.append({
            "name": "Mistral",
            "base_url": "https://api.mistral.ai/v1",
            "api_key": mistral_key,
            "model": os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
        })

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        providers.append({
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "api_key": openai_key,
            "model": "gpt-4o-mini",
        })

    if not providers:
        logger.info("OFFER ENGINE: No API keys set — using rule-based stub")
        return _offer_stub(merchant)

    for provider in providers:
        logger.info(f"OFFER ENGINE: Trying {provider['name']} ({provider['model']}) ...")
        try:
            result = _call_openai_compat(
                base_url=provider["base_url"],
                api_key=provider["api_key"],
                model=provider["model"],
                messages=messages,
            )
            logger.info(f"OFFER ENGINE: Success with {provider['name']} → \"{result.get('headline')}\"")
            return result
        except Exception as e:
            logger.warning(f"OFFER ENGINE: {provider['name']} failed — {e}")
            continue

    logger.info("OFFER ENGINE: All providers failed — using rule-based stub")
    return _offer_stub(merchant)


@app.post("/offer/generate", response_model=GenUICard, tags=["offer"])
def generate_offer(req: IntentRequest) -> GenUICard:
    """
    Receives an abstract user intent + context state and generates a dynamic
    GenUI offer card. Never returns markdown — always a strictly typed JSON card.
    """
    merchant = _get_merchant(req.merchant_id)
    llm_result = _llm_generate_offer(req, merchant)

    offer_id = str(uuid.uuid4())
    discount_code = secrets.token_urlsafe(6).upper()
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    card = GenUICard(
        offer_id=offer_id,
        merchant_id=merchant["id"],
        merchant_name=merchant["name"],
        headline=llm_result.get("headline", "A great deal nearby."),
        subline=llm_result.get("subline", "Limited time offer."),
        discount_percent=int(llm_result.get("discount_percent", 10)),
        discount_code=discount_code,
        expiry_iso=expiry,
        color_hex=llm_result.get("color_hex", "#6366f1"),
        emotional_framing=llm_result.get("emotional_framing", "convenience"),
        intent_matched=req.intent,
    )

    record = card.model_dump()
    _active_offers[discount_code] = record
    _merchant_offers.setdefault(merchant["id"], []).append(record)

    return card


# ---------------------------------------------------------------------------
# Routes — Checkout & Redemption (Module 03)
# ---------------------------------------------------------------------------

@app.post("/offer/redeem", response_model=RedeemResponse, tags=["checkout"])
def redeem_offer(req: RedeemRequest) -> RedeemResponse:
    """
    Validates and redeems a discount code. Called when the merchant scans the
    user's QR code. Closes the loop for the demo.
    """
    offer = _active_offers.get(req.discount_code)

    if not offer:
        return RedeemResponse(success=False, message="Code not found or already redeemed.")

    if offer["merchant_id"] != req.merchant_id:
        return RedeemResponse(success=False, message="Code not valid for this merchant.")

    expiry = datetime.fromisoformat(offer["expiry_iso"])
    if datetime.now(timezone.utc) > expiry:
        return RedeemResponse(success=False, message="Offer has expired.")

    redeemed_at = datetime.now(timezone.utc).isoformat()
    redemption_record = {**offer, "redeemed_at": redeemed_at}
    _redemptions[req.discount_code] = redemption_record
    _merchant_offers.setdefault(req.merchant_id, [])
    del _active_offers[req.discount_code]

    return RedeemResponse(success=True, message="Offer redeemed successfully.", redeemed_at=redeemed_at)


_MATCH_SYSTEM_PROMPT = """
You are the Generative City-Wallet reasoning engine for DSV Gruppe.

You will receive FOUR inputs:
1. USER DEMOGRAPHICS — self-declared age group, sex, profession, and personal interests.
2. USER SPENDING PROFILE — anonymised historical data (no PII).
3. USER CURRENT SITUATION — built on-device from sensor data; no raw location transmitted.
4. NEARBY MERCHANT CATALOG — merchants with live Payone volumes and offer rules.

━━━ DEMOGRAPHIC COPY RULES (mandatory — violations disqualify the response) ━━━

AGE: teens/20s
  Tone: casual, warm, energetic. Use short punchy sentences.
  OK:   "Your coffee break just got better." / "Treat yourself — you've earned it."
  NEVER: formal language, "esteemed", "distinguished", heavy discounts framed as charity.

AGE: 30s
  Tone: practical, efficient, value-focused. Respect their time.
  OK:   "Quick stop, real reward." / "Fresh pick-up on the way."
  NEVER: youth slang, party/FOMO framing, overly casual ("hey girl!").

AGE: 40s–50s
  Tone: calm, quality-focused, no manufactured urgency. Speak to experience.
  OK:   "A well-earned pause." / "Something worth savouring today."
  NEVER: "Flash deal!", exclamation spam, slang, youth references.

AGE: 60s and above
  Tone: warm, respectful, dignified. Comfort and tradition over novelty.
  OK:   "A quiet table is ready for you." / "A familiar warmth awaits."
  NEVER: "Score big!", party framing, slang, urgency pressure, digital-native references.

SEX consideration: adapt emotional hook, not the merchant category.
  Female users: lean toward self-care, warmth, discovery framing when equal options exist.
  Male users: lean toward quality, reliability, efficiency framing when equal options exist.
  Never assume or stereotype beyond these gentle copy-tone adjustments.

━━━ TASK — reason step by step ━━━
A. What tone and vocabulary fits this person's age group and sex (apply rules above)?
B. What do the profession and interests reveal about lifestyle, values, and what resonates with them?
C. What does the spending profile tell you about category preferences and typical needs?
D. Does the current situation reinforce or override those preferences?
E. Which merchant is the best match? Prefer trigger_active = true merchants. Align merchant category to interests and profession where possible.
F. Write a headline and subline that feel personally written for this exact person — not a template. The reasoning must explicitly name how demographics, profession, and interests shaped the copy.

STRICT OUTPUT RULES:
- Respond ONLY with a single valid JSON object — no markdown, no explanation outside the JSON.
- headline: ≤8 words, emotionally resonant, age- and situation-specific.
- subline: ≤15 words, factual (discount, min basket, expiry hint).
- color_hex: muted/warm tones for 50+ users; richer/brighter tones for under-35 users.
- emotional_framing: one of [warm_shelter, scarcity_urgency, celebration, convenience, discovery].

Return exactly this shape:
{
  "reasoning": "2-3 sentences: why this merchant + why this specific copy fits this person's age, sex, profession, interests, history, and moment",
  "merchant_id": "string",
  "merchant_name": "string",
  "headline": "string",
  "subline": "string",
  "discount_percent": integer,
  "color_hex": "#rrggbb",
  "emotional_framing": "string"
}
""".strip()


_MERCHANT_DISTANCES = {
    "merchant_001": 80,
    "merchant_002": 210,
    "merchant_003": 160,
    "merchant_004": 290,
}

# Scenario overrides: set current_transaction_volume per merchant so that
# exactly one merchant has trigger_active=true per scenario, making the
# LLM choice deterministic while still showing genuine reasoning.
# Format: { scenario_key: { merchant_id: current_volume } }
_SCENARIO_VOLUME_OVERRIDES: dict[str, dict[str, int]] = {
    "cold": {
        # Only Café Müller is quiet (3 < threshold 8) → trigger fires
        "merchant_001": 3,   # quiet — trigger ON
        "merchant_002": 18,  # normal — trigger OFF (18 >= 12)
        "merchant_003": 22,  # busy   — trigger OFF
        "merchant_004": 12,  # normal — trigger OFF (12 >= 8)
    },
    "stroll": {
        # Only Thalia bookstore is quiet (4 < threshold 8) → trigger fires
        "merchant_001": 15,  # normal — trigger OFF (15 >= 8)
        "merchant_002": 20,  # normal — trigger OFF (20 >= 12)
        "merchant_003": 22,  # busy   — trigger OFF
        "merchant_004": 4,   # quiet  — trigger ON
    },
    "rainy": {
        # Only Bäckerei Schönleber is quiet (4 < threshold 12) → trigger fires
        "merchant_001": 14,  # normal — trigger OFF (14 >= 8)
        "merchant_002": 4,   # quiet  — trigger ON
        "merchant_003": 22,  # busy   — trigger OFF
        "merchant_004": 11,  # normal — trigger OFF (11 >= 8)
    },
    "senior": {
        # Same Hamburg context as 'cold' — only Café Müller is quiet → trigger fires.
        # Werner and Mia are in the same place with the same merchant available.
        # Only the demographics differ — forcing a pure A/B comparison of the LLM copy.
        "merchant_001": 3,   # quiet  — trigger ON  (same as cold)
        "merchant_002": 18,  # normal — trigger OFF
        "merchant_003": 22,  # busy   — trigger OFF
        "merchant_004": 12,  # normal — trigger OFF
    },
}


def _build_match_user_prompt(
    user_context: str,
    merchants: list,
    user_profile: str = "",
    user_age_group: str = "",
    user_sex: str = "",
    user_profession: str = "",
    user_interests: list | None = None,
    scenario: str = "",
) -> str:
    overrides = _SCENARIO_VOLUME_OVERRIDES.get(scenario, {})
    catalog = []
    for m in merchants:
        current = overrides.get(m["id"], m["current_transaction_volume"])
        avg = m["avg_hourly_transaction_volume"]
        ratio = round(current / avg, 2) if avg > 0 else 0.0
        threshold = m["rules"]["trigger_volume_threshold"]
        trigger = current < threshold
        catalog.append({
            "id": m["id"],
            "name": m["name"],
            "category": m["category"],
            "distance_m": _MERCHANT_DISTANCES.get(m["id"], 300),
            "current_transactions": current,
            "avg_transactions": avg,
            "volume_ratio": ratio,
            "trigger_active": trigger,
            "max_discount_percent": m["rules"]["max_discount_percent"],
            "min_basket_eur": m["rules"]["min_basket_eur"],
            "preferred_framing": m["rules"]["emotional_framing"],
        })

    demo_parts = []
    if user_age_group:
        demo_parts.append(f"Age group: {user_age_group}")
    if user_sex:
        demo_parts.append(f"Sex (self-declared): {user_sex}")
    if user_profession:
        demo_parts.append(f"Profession: {user_profession}")
    if user_interests:
        demo_parts.append(f"Interests: {', '.join(user_interests)}")
    demographics_section = (
        f"USER DEMOGRAPHICS:\n" + "\n".join(demo_parts) + "\n\n"
        if demo_parts
        else "USER DEMOGRAPHICS: Not provided.\n\n"
    )

    profile_section = (
        f"USER SPENDING PROFILE (GDPR-anonymised — no PII):\n{user_profile}\n\n"
        if user_profile.strip()
        else "USER SPENDING PROFILE: Not available — reason from current situation only.\n\n"
    )

    return (
        f"{demographics_section}"
        f"{profile_section}"
        f"USER CURRENT SITUATION (built on-device, no raw data transmitted):\n{user_context}\n\n"
        f"NEARBY MERCHANT CATALOG:\n{json.dumps(catalog, indent=2)}"
    )


def _reasoning_match(
    user_context: str,
    merchants: list,
    user_profile: str = "",
    user_age_group: str = "",
    user_sex: str = "",
    user_profession: str = "",
    user_interests: list | None = None,
    scenario: str = "",
) -> dict:
    """
    Single LLM call: reason about user spending profile + current situation +
    merchant catalog. Selects the best merchant and generates the offer.
    Falls back to stub if no LLM key is configured.
    """
    messages = [
        {"role": "system", "content": _MATCH_SYSTEM_PROMPT},
        {"role": "user", "content": _build_match_user_prompt(
            user_context, merchants, user_profile,
            user_age_group, user_sex, user_profession, user_interests, scenario
        )},
    ]

    providers = []
    if os.getenv("GROQ_API_KEY"):
        providers.append({"name": "Groq", "base_url": "https://api.groq.com/openai/v1",
                          "api_key": os.getenv("GROQ_API_KEY"),
                          "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")})
    if os.getenv("GEMINI_API_KEY"):
        providers.append({"name": "Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                          "api_key": os.getenv("GEMINI_API_KEY"),
                          "model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")})
    if os.getenv("MISTRAL_API_KEY"):
        providers.append({"name": "Mistral", "base_url": "https://api.mistral.ai/v1",
                          "api_key": os.getenv("MISTRAL_API_KEY"),
                          "model": os.getenv("MISTRAL_MODEL", "mistral-small-latest")})
    if os.getenv("OPENAI_API_KEY"):
        providers.append({"name": "OpenAI", "base_url": "https://api.openai.com/v1",
                          "api_key": os.getenv("OPENAI_API_KEY"), "model": "gpt-4o-mini"})

    # Lower temperature for 60+ users: dignified, stable copy. Higher for 20s: creative.
    age_temp_map = {"teens": 0.85, "20s": 0.85, "30s": 0.75, "40s": 0.70, "50s": 0.65, "60s": 0.55, "70s": 0.50}
    temp = next((v for k, v in age_temp_map.items() if k in user_age_group.lower()), 0.72)

    logger.info(f"MATCH ENGINE: user_age_group='{user_age_group}' user_sex='{user_sex}' profession='{user_profession}' interests={user_interests} temperature={temp}")

    for p in providers:
        logger.info(f"MATCH ENGINE: Trying {p['name']} ({p['model']}) ...")
        try:
            result = _call_openai_compat(p["base_url"], p["api_key"], p["model"], messages, temperature=temp)
            logger.info(f"MATCH ENGINE: {p['name']} selected {result.get('merchant_id')} → \"{result.get('headline')}\"")
            logger.info(f"MATCH ENGINE: Reasoning — {result.get('reasoning')}")
            result["llm_provider"] = f"{p['model']} · {p['name']}"
            return result
        except Exception as e:
            logger.warning(f"MATCH ENGINE: {p['name']} failed — {e}")
            continue

    # Stub fallback — pick the quietest merchant (respecting scenario overrides)
    logger.info("MATCH ENGINE: All providers failed — using stub fallback")
    overrides = _SCENARIO_VOLUME_OVERRIDES.get(scenario, {})
    best = min(
        merchants,
        key=lambda m: (
            overrides.get(m["id"], m["current_transaction_volume"])
            / m["avg_hourly_transaction_volume"]
            if m["avg_hourly_transaction_volume"] > 0
            else float("inf")
        ),
    )
    rules = best["rules"]
    return {
        "reasoning": "No LLM available — selected quietest merchant by Payone volume ratio.",
        "merchant_id": best["id"],
        "merchant_name": best["name"],
        "headline": rules.get("offer_headline_template", "A great deal nearby."),
        "subline": f"{rules['max_discount_percent']}% off — min €{rules['min_basket_eur']} · 30 min",
        "discount_percent": rules["max_discount_percent"],
        "color_hex": "#c8702a" if best["category"] == "cafe" else "#e8a020",
        "emotional_framing": rules["emotional_framing"],
    }


@app.post("/offer/match", response_model=GenUICard, tags=["offer"])
def match_offer(req: MatchRequest) -> GenUICard:
    """
    Receives a rich user context description (built on-device — no raw data).
    The LLM reasons about the user's needs, compares against the full merchant
    catalog, selects the best match, and generates a personalised offer card.
    """
    db = _load_payone_db()
    merchants = db["merchants"]

    result = _reasoning_match(
        req.user_context, merchants, req.user_profile,
        req.user_age_group, req.user_sex,
        req.user_profession, req.user_interests,
        req.scenario,
    )

    merchant_id = result.get("merchant_id") or (merchants[0]["id"] if merchants else "unknown")
    offer_id = str(uuid.uuid4())
    discount_code = secrets.token_urlsafe(6).upper()
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    card = GenUICard(
        offer_id=offer_id,
        merchant_id=merchant_id,
        merchant_name=result.get("merchant_name", "Nearby merchant"),
        headline=result.get("headline", "A great deal nearby."),
        subline=result.get("subline", "Limited time offer."),
        discount_percent=int(result.get("discount_percent", 10)),
        discount_code=discount_code,
        expiry_iso=expiry,
        color_hex=result.get("color_hex", "#6366f1"),
        emotional_framing=result.get("emotional_framing", "convenience"),
        intent_matched=result.get("reasoning", ""),
        llm_provider=result.get("llm_provider", "rule-based stub"),
    )

    record = card.model_dump()
    _active_offers[discount_code] = record
    _merchant_offers.setdefault(merchant_id, []).append(record)
    return card


@app.get("/merchant/{merchant_id}/activity", response_model=MerchantActivity, tags=["merchant"])
def merchant_activity(merchant_id: str) -> MerchantActivity:
    """
    Returns live merchant stats: transaction volume, offers generated,
    redemptions. Used by the merchant dashboard.
    """
    merchant = _get_merchant(merchant_id)
    current = merchant["current_transaction_volume"]
    avg = merchant["avg_hourly_transaction_volume"]
    ratio = round(current / avg, 2) if avg > 0 else 0.0
    threshold = merchant["rules"]["trigger_volume_threshold"]

    offers = _merchant_offers.get(merchant_id, [])
    redemptions = [r for r in _redemptions.values() if r["merchant_id"] == merchant_id]

    return MerchantActivity(
        merchant_id=merchant_id,
        merchant_name=merchant["name"],
        current_transactions=current,
        avg_transactions=avg,
        payone_volume_ratio=ratio,
        trigger_active=current < threshold,
        offers_generated=len(offers),
        redemptions_count=len(redemptions),
        recent_offers=offers[-5:],
        recent_redemptions=redemptions[-5:],
    )


@app.get("/debug/env", tags=["system"])
def debug_env() -> dict:
    """Shows which API keys are loaded (masked). Use to diagnose missing keys."""
    def mask(val: str | None) -> str:
        if not val:
            return "NOT SET"
        return val[:6] + "..." + val[-3:]

    return {
        "GROQ_API_KEY": mask(os.getenv("GROQ_API_KEY")),
        "GEMINI_API_KEY": mask(os.getenv("GEMINI_API_KEY")),
        "MISTRAL_API_KEY": mask(os.getenv("MISTRAL_API_KEY")),
        "OPENAI_API_KEY": mask(os.getenv("OPENAI_API_KEY")),
        "OPENWEATHER_API_KEY": mask(os.getenv("OPENWEATHER_API_KEY")),
        "TAVILY_API_KEY": mask(os.getenv("TAVILY_API_KEY")),
    }


@app.get("/merchants", tags=["merchant"])
def list_merchants() -> list[dict]:
    """Returns all merchants from the stubbed Payone DB."""
    db = _load_payone_db()
    return db["merchants"]
