"""
gdpr_shield.py — Privacy Engineering Module
============================================
Implements the "GDPR Shield" for the Generative City-Wallet.

Key principles applied:
  • Data Minimisation (Art. 5(1)(c) GDPR)  — only the minimum necessary data
    reaches the LLM. Raw PII is stripped before any external call.
  • Anonymisation / Pseudonymisation (Recital 26) — identifiers are replaced with
    deterministic tokens; exact locations are generalised to neighbourhood level.
  • Purpose Limitation (Art. 5(1)(b)) — the sanitised data is used only for the
    single purpose of generating a spending insight.
  • Audit Trail — every transformation is logged so data-flows are auditable.

Usage:
    python gdpr_shield.py                  # run the demo pipeline
    from gdpr_shield import GDPRShield     # import into FastAPI
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from faker import Faker
from loguru import logger

load_dotenv()  # load backend/.env so GROQ_API_KEY is available when run standalone

# ── Logger: structured privacy audit trail ────────────────────────────────────
logger.remove()
logger.add(
    lambda msg: print(msg, end=""),
    format=(
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <22}</level> | "
        "{message}"
    ),
    colorize=True,
    level="DEBUG",
)

# ── Constants ─────────────────────────────────────────────────────────────────

# HMAC secret — in production this would be a rotated HSM-backed key.
# Used to make pseudonymous tokens deterministic but irreversible.
_PSEUDONYM_SECRET = os.getenv("PSEUDONYM_SECRET", "dev-only-secret-rotate-in-prod")

# Stuttgart neighbourhood bounding boxes [lat_min, lat_max, lon_min, lon_max]
_STUTTGART_NEIGHBOURHOODS: list[tuple[str, float, float, float, float]] = [
    ("Stuttgart Mitte",       48.770, 48.785, 9.170, 9.195),
    ("Stuttgart Nord",        48.785, 48.800, 9.170, 9.200),
    ("Stuttgart Süd",         48.750, 48.770, 9.160, 9.200),
    ("Bad Cannstatt",         48.790, 48.815, 9.205, 9.245),
    ("Vaihingen",             48.720, 48.745, 9.095, 9.135),
    ("Degerloch",             48.740, 48.760, 9.175, 9.215),
    ("Zuffenhausen",          48.820, 48.845, 9.155, 9.190),
    ("Feuerbach",             48.800, 48.820, 9.145, 9.175),
    ("Untertürkheim",         48.775, 48.800, 9.235, 9.265),
    ("Möhringen",             48.710, 48.735, 9.145, 9.185),
]

# Transaction amount buckets (GDPR: amounts are PII when granular)
_AMOUNT_BUCKETS: list[tuple[float, str]] = [
    (5,   "Micro purchase  (<€5)"),
    (20,  "Small purchase  (€5–20)"),
    (50,  "Medium purchase (€20–50)"),
    (100, "Large purchase  (€50–100)"),
    (float("inf"), "Premium purchase (>€100)"),
]

# Merchant categories — names are replaced with categories only
_CATEGORY_MAP: dict[str, str] = {
    "cafe":        "Food & Beverage",
    "bakery":      "Food & Beverage",
    "restaurant":  "Food & Beverage",
    "pharmacy":    "Health & Wellbeing",
    "bookstore":   "Retail — Books & Media",
    "clothing":    "Retail — Fashion",
    "supermarket": "Grocery",
    "transport":   "Mobility",
    "gym":         "Health & Wellbeing",
    "cinema":      "Entertainment",
}


# ── 1. Synthetic Data Generator ───────────────────────────────────────────────

@dataclass
class RawTransaction:
    transaction_id: str
    user_id:        str
    timestamp:      datetime
    amount_eur:     float
    merchant_name:  str   # PII — specific business name
    merchant_id:    str   # PII — unique identifier
    category:       str
    lat:            float  # PII — exact location
    lon:            float  # PII — exact location

@dataclass
class RawLocationEvent:
    user_id:    str
    timestamp:  datetime
    lat:        float   # PII
    lon:        float   # PII
    speed_ms:   float
    stops:      int


@dataclass
class RawUserData:
    user_id:        str              # PII
    full_name:      str              # PII
    email:          str              # PII
    transactions:   list[RawTransaction]  = field(default_factory=list)
    location_trail: list[RawLocationEvent] = field(default_factory=list)


class MockUser:
    """
    Generates realistic but entirely synthetic user data.
    Swap `generate()` for a real data-fetch in production.
    """

    def __init__(self, locale: str = "de_DE", seed: int | None = None):
        self._fake = Faker(locale)
        if seed is not None:
            Faker.seed(seed)
            random.seed(seed)

    def generate(
        self,
        n_transactions: int = 8,
        n_location_events: int = 5,
    ) -> RawUserData:
        user_id   = self._fake.uuid4()
        full_name = self._fake.name()
        email     = self._fake.email()

        now = datetime.now(timezone.utc)

        # ── Transactions ──
        merchants = [
            ("Café Müller",        "merchant_001", "cafe",        (3.0,  8.0)),
            ("Bäckerei Schönleber","merchant_002", "bakery",      (1.5,  6.0)),
            ("Maybach Apotheke",   "merchant_003", "pharmacy",    (5.0, 45.0)),
            ("Metzger & Co.",      "merchant_004", "restaurant",  (8.0, 35.0)),
            ("Thalia Stuttgart",   "merchant_005", "bookstore",   (9.0, 60.0)),
            ("Zalando Outlet",     "merchant_006", "clothing",    (20.0,120.0)),
        ]
        transactions = []
        for _ in range(n_transactions):
            name, mid, cat, (lo, hi) = random.choice(merchants)
            amount = round(random.uniform(lo, hi), 2)
            lat = 48.77 + random.uniform(-0.03, 0.03)
            lon = 9.18 + random.uniform(-0.03, 0.03)
            ts  = now - timedelta(
                days=random.randint(0, 6),
                hours=random.randint(0, 10),
                minutes=random.randint(0, 59),
            )
            transactions.append(RawTransaction(
                transaction_id = self._fake.uuid4(),
                user_id        = user_id,
                timestamp      = ts,
                amount_eur     = amount,
                merchant_name  = name,
                merchant_id    = mid,
                category       = cat,
                lat            = lat,
                lon            = lon,
            ))

        # ── Location trail ──
        location_trail = []
        for i in range(n_location_events):
            ts  = now - timedelta(minutes=10 - i * 2)
            lat = 48.7758 + random.uniform(-0.005, 0.005)
            lon = 9.1829  + random.uniform(-0.005, 0.005)
            location_trail.append(RawLocationEvent(
                user_id   = user_id,
                timestamp = ts,
                lat       = lat,
                lon       = lon,
                speed_ms  = round(random.uniform(0.3, 1.5), 2),
                stops     = random.randint(0, 3),
            ))

        return RawUserData(
            user_id        = user_id,
            full_name      = full_name,
            email          = email,
            transactions   = sorted(transactions, key=lambda t: t.timestamp, reverse=True),
            location_trail = location_trail,
        )


# ── 2. The GDPR Shield ────────────────────────────────────────────────────────

class GDPRShield:
    """
    Sanitises raw user data before it reaches any external system (LLM, API, etc.).
    All transformations are logged to the privacy audit trail.
    """

    # ── PII Masking ────────────────────────────────────────────────────────

    @staticmethod
    def _pseudonymise(value: str) -> str:
        """
        HMAC-SHA256 token: deterministic (same input → same token in one session)
        but irreversible without the secret key.
        Returns first 12 hex chars prefixed with [USER_].
        """
        token = hmac.new(
            _PSEUDONYM_SECRET.encode(),
            value.encode(),
            hashlib.sha256,
        ).hexdigest()[:12].upper()
        return f"[USER_{token}]"

    # ── Location Generalisation ────────────────────────────────────────────

    @staticmethod
    def _generalise_location(lat: float, lon: float) -> str:
        """
        Converts exact GPS coords to a neighbourhood name.
        Never returns coordinates — only a human-readable area string.
        """
        for name, lat_min, lat_max, lon_min, lon_max in _STUTTGART_NEIGHBOURHOODS:
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                return name
        # Outside Stuttgart bounding boxes → city-level only
        return "Stuttgart area"

    # ── Transaction Bucketing ──────────────────────────────────────────────

    @staticmethod
    def _bucket_amount(amount: float) -> str:
        for threshold, label in _AMOUNT_BUCKETS:
            if amount < threshold:
                return label
        return "Premium purchase (>€100)"

    @staticmethod
    def _bucket_timestamp(ts: datetime) -> str:
        """Returns day-of-week + time-of-day bucket — not exact time."""
        day  = ts.strftime("%A")
        hour = ts.hour
        if 6  <= hour < 11: period = "morning"
        elif 11 <= hour < 14: period = "lunchtime"
        elif 14 <= hour < 18: period = "afternoon"
        elif 18 <= hour < 22: period = "evening"
        else:                  period = "night"
        return f"{day} {period}"

    # ── Main Sanitiser ─────────────────────────────────────────────────────

    @classmethod
    def sanitize_for_llm(cls, raw: RawUserData) -> dict[str, Any]:
        """
        Applies all GDPR transformations and returns a clean dict
        safe to send to any external LLM or analytics service.

        Transformations applied:
          • user_id, full_name, email  → pseudonymous token
          • transaction_id, merchant_id → removed entirely
          • merchant_name               → replaced with category
          • amount_eur                  → bucketed range string
          • lat/lon in transactions     → neighbourhood string
          • lat/lon in location trail   → neighbourhood string
          • exact timestamps            → day + time-of-day bucket
          • speed, stops                → retained (not PII)
        """
        logger.info("━━━ PRIVACY AUDIT TRAIL ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info("[RAW DATA RECEIVED]")
        logger.info(f"  user_id   : {raw.user_id}")
        logger.info(f"  full_name : {raw.full_name}")
        logger.info(f"  email     : {raw.email}")
        logger.info(f"  transactions   : {len(raw.transactions)} records with exact amounts, coords, merchant IDs")
        logger.info(f"  location_trail : {len(raw.location_trail)} GPS points with timestamps")

        logger.info("[SANITIZATION APPLIED]")

        # Pseudonymise identity
        user_token = cls._pseudonymise(raw.user_id)
        logger.info(f"  user_id   '{raw.user_id[:8]}…' → '{user_token}'")
        logger.info(f"  full_name '{raw.full_name}' → [REMOVED]")
        logger.info(f"  email     '{raw.email}' → [REMOVED]")

        # Sanitise transactions
        clean_transactions = []
        for tx in raw.transactions:
            neighbourhood = cls._generalise_location(tx.lat, tx.lon)
            amount_bucket = cls._bucket_amount(tx.amount_eur)
            time_bucket   = cls._bucket_timestamp(tx.timestamp)
            category      = _CATEGORY_MAP.get(tx.category, tx.category.title())

            logger.info(
                f"  tx: '{tx.merchant_name}' ({tx.amount_eur:.2f}€) @ "
                f"[{tx.lat:.4f},{tx.lon:.4f}] {tx.timestamp.strftime('%H:%M')}"
                f" → category='{category}', amount='{amount_bucket}', "
                f"location='{neighbourhood}', time='{time_bucket}'"
            )

            clean_transactions.append({
                "category":     category,
                "amount":       amount_bucket,
                "location":     neighbourhood,
                "when":         time_bucket,
            })

        # Sanitise location trail
        clean_locations = []
        for ev in raw.location_trail:
            neighbourhood = cls._generalise_location(ev.lat, ev.lon)
            time_bucket   = cls._bucket_timestamp(ev.timestamp)
            logger.info(
                f"  loc: [{ev.lat:.4f},{ev.lon:.4f}] → '{neighbourhood}', "
                f"speed={ev.speed_ms}m/s, stops={ev.stops}"
            )
            clean_locations.append({
                "area":     neighbourhood,
                "when":     time_bucket,
                "speed_ms": ev.speed_ms,
                "stops":    ev.stops,
            })

        clean_data = {
            "user_token":    user_token,
            "transactions":  clean_transactions,
            "location_trail": clean_locations,
            "record_count":  len(raw.transactions),
        }

        logger.info("[CLEAN DATA SENT TO AI]")
        logger.info(
            f"  Fields: user_token, {len(clean_transactions)} sanitised transactions, "
            f"{len(clean_locations)} area-level location events"
        )
        logger.info("  PII removed: full_name, email, transaction_ids, merchant_ids, exact coords, exact timestamps")
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        return clean_data


# ── 3. LLM Analysis ───────────────────────────────────────────────────────────

async def analyze_spending_habits(sanitized_data: dict[str, Any]) -> str:
    """
    Sends ONLY the sanitised data to the LLM.
    No PII reaches this function — enforced by type: the input is already a dict
    produced by GDPRShield.sanitize_for_llm(), not a RawUserData object.

    Replace the placeholder block below with a real API call:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        ...
    or any OpenAI-compatible endpoint (Groq, Gemini, Mistral).
    """
    prompt = (
        "You are the Generative City-Wallet personalisation engine for DSV Gruppe, "
        "a platform that connects local Stuttgart merchants with nearby customers through real-time offers.\n\n"
        "The following anonymised data describes a single user's recent spending and current movement. "
        "All PII has been removed — you only see categories, amount ranges, neighbourhoods, and time-of-day buckets.\n\n"
        "Your task: generate exactly TWO sentences.\n"
        "Sentence 1: What type of local merchant offer would resonate most with this user RIGHT NOW, "
        "based on their spending history and current movement pattern? "
        "Be specific about timing, category, and emotional framing (e.g. warmth, convenience, discovery).\n"
        "Sentence 2: What is the best moment (time of day + day type) to trigger the next offer for this user, "
        "and why does their pattern suggest this?\n\n"
        "Do NOT give budgeting advice. Do NOT mention savings. Focus entirely on merchant offer targeting.\n\n"
        f"User data:\n{json.dumps(sanitized_data, indent=2)}"
    )

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        # ── Real LLM call via Groq (open-weight Llama 3.1 8B, free tier) ──
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
        )
        response = await client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=120,
        )
        insight = response.choices[0].message.content.strip()
    else:
        # ── Deterministic fallback — no API key needed ────────────────────
        categories = [t["category"] for t in sanitized_data["transactions"]]
        top = max(set(categories), key=categories.count)
        whens = [t["when"] for t in sanitized_data["transactions"]]
        top_when = max(set(whens), key=whens.count)
        insight = (
            f"This user's pattern suggests a {top.lower()} offer would resonate most — "
            f"triggered during {top_when} when {categories.count(top)} of {len(categories)} "
            f"past transactions occurred in this category. "
            f"Add GROQ_API_KEY to backend/.env for a full AI-generated targeting insight."
        )

    logger.success(f"[LLM INSIGHT GENERATED] {insight}")
    return insight


# ── 4. Full Pipeline ──────────────────────────────────────────────────────────

async def run_pipeline(seed: int | None = 42) -> dict[str, Any]:
    """
    End-to-end demo:
      MockUser.generate() → GDPRShield.sanitize_for_llm() → analyze_spending_habits()

    In production: replace MockUser.generate() with a real data fetch.
    The GDPRShield and analyze_spending_habits() remain unchanged.
    """
    logger.info("Starting GDPR-compliant LLM pipeline")

    # Step 1: Generate (or fetch) raw data
    user = MockUser(locale="de_DE", seed=seed)
    raw_data = user.generate(n_transactions=8, n_location_events=5)

    # Step 2: Sanitise — this is the GDPR boundary
    sanitized = GDPRShield.sanitize_for_llm(raw_data)

    # Step 3: Analyse using only the clean data
    insight = await analyze_spending_habits(sanitized)

    return {
        "user_token": sanitized["user_token"],
        "insight":    insight,
        "records_analysed": sanitized["record_count"],
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = asyncio.run(run_pipeline())
    print("\n" + "═" * 60)
    print(f"  User token  : {result['user_token']}")
    print(f"  Records     : {result['records_analysed']}")
    print(f"  Insight     : {result['insight']}")
    print("═" * 60 + "\n")
