# Generative City-Wallet

> Giving local merchants the personalisation infrastructure that only global e-commerce has had — privacy-first, demographically aware, powered by live Payone data and an open-weight LLM.

**Built for:** DSV Gruppe Hackathon · StochasticSquad  
**Stack:** FastAPI · Groq (Llama 3.1 8B) · OpenWeatherMap · Payone · Next.js · Vanilla JS demo

---

## What it does

A user walks past a quiet local café. Their phone — without sending any personal data to a server — builds a GDPR-compliant profile of who they are and what is happening right now. That profile is sent to an LLM alongside the live Payone transaction volumes of every nearby merchant. The LLM reasons across three inputs:

1. **Who is this person?** (age group, sex, spending history — anonymised)
2. **What is happening right now?** (weather, movement, time of day)
3. **Which merchant needs customers right now?** (Payone volume vs. threshold)

It then selects the best merchant and writes a personalised offer card — headline, discount, colour, and emotional framing — tailored to that specific person at that specific moment.

A 28-year-old woman in Hamburg gets: *"Your coffee break just got better — 18% off, min €3.50."*  
A 67-year-old man in the same café at the same moment gets: *"A quiet warmth awaits you — settle in."*

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     USER'S DEVICE (browser)                  │
│                                                              │
│  Raw signals: GPS, movement, stops, transaction history      │
│       │                                                      │
│       ▼  (stays on device — GDPR boundary)                   │
│  encodeContext()  →  situation summary (plain text)          │
│  scenario.profileText  →  spending profile (anonymised text) │
│       │                                                      │
│       └──── POST /offer/match ──────────────────────────────►│
└─────────────────────────────────────────────────────────────┘
         { user_context, user_profile, user_age_group,
           user_sex, user_profession, user_interests,
           scenario, lat, lon }

┌─────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                           │
│                                                              │
│  POST /context  →  OpenWeatherMap + Payone volumes          │
│  POST /offer/match:                                          │
│    1. Load 4-merchant catalog from payone_db.json           │
│    2. Apply scenario volume overrides                        │
│    3. Build LLM prompt (demographics + profile +            │
│       situation + merchant catalog with rules)              │
│    4. Call configured LLM (Groq by default, falls back to   │
│       Gemini / Mistral / OpenAI, then rule-based stub)      │
│    5. Return GenUICard (merchant, headline, discount…)      │
│                                                              │
│  POST /offer/redeem  →  validate + close the loop           │
│  GET  /merchant/{id}/activity  →  dashboard stats           │
└─────────────────────────────────────────────────────────────┘
         GenUICard JSON

┌─────────────────────────────────────────────────────────────┐
│               BROWSER renders offer card                     │
│  QR code → Confirm Redemption → merchant dashboard updated  │
└─────────────────────────────────────────────────────────────┘
```

---

## GDPR Compliance

| Principle | Implementation |
|---|---|
| **Data Minimisation** (Art. 5(1)(c)) | Exact GPS → neighbourhood name; exact timestamps → "Tuesday morning"; exact amounts → "Small purchase €5–20" |
| **Anonymisation** (Recital 26) | User ID → HMAC-SHA256 token; name and email removed entirely |
| **Purpose Limitation** (Art. 5(1)(b)) | Sanitised data used only for offer generation; logged in audit trail |
| **No raw PII to LLM** | LLM prompt contains only categories, buckets, neighbourhood names, age group, and self-declared sex |
| **On-device processing** | Raw GPS, movement, and transaction history never leave the browser |

Run `python gdpr_shield.py` to see the full privacy audit trail printed to the terminal.

---

## Merchant Catalog (Payone stub)

| ID | Name | City | Category | Trigger threshold |
|---|---|---|---|---|
| merchant_001 | Café Müller | Hamburg | cafe | < 8 txns/hr |
| merchant_002 | Bäckerei Schönleber | Frankfurt | bakery | < 12 txns/hr |
| merchant_003 | Metzger & Co. | Munich | restaurant | < 15 txns/hr |
| merchant_004 | Thalia München | Munich | bookstore | < 8 txns/hr |

---

## Demo Scenarios

The demo at `http://127.0.0.1:8000/demo` has four pre-configured personas:

### A/B Pair — Same city, same café, different person

| | Mia | Werner |
|---|---|---|
| Age / Sex | 28 · female | 67 · male |
| City | Hamburg | Hamburg (same) |
| Eligible merchant | Café Müller | Café Müller (same) |
| Expected headline tone | Casual, warm, energetic | Dignified, calm, comfort-focused |

Run both and compare the LLM Reasoning panel — the model explicitly names how it adjusted the copy for each demographic.

### Contextual Variation — Same user type, different city/weather

| | Klaus | Sara |
|---|---|---|
| Age / Sex | 58 · male | 35 · female |
| City | Munich (live weather) | Frankfurt (live weather) |
| Eligible merchant | Thalia München | Bäckerei Schönleber |

---

## Running Locally

### Prerequisites

- Python 3.11+
- `GROQ_API_KEY` — free at [console.groq.com](https://console.groq.com) (recommended — app works without it via rule-based stub fallback)
- `OPENWEATHER_API_KEY` — free at [openweathermap.org](https://openweathermap.org/api) (optional — stubs to 11°C if missing)

### Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Create backend/.env:
# GROQ_API_KEY=your_key
# OPENWEATHER_API_KEY=your_key   (optional)

uvicorn main:app --reload --port 8000
```

Open `http://127.0.0.1:8000/demo` for the user-facing demo.  
Open `http://127.0.0.1:8000/docs` for the full API explorer.  
Open `http://127.0.0.1:8000/debug/env` to verify which keys are loaded.

### Merchant Dashboard

```powershell
cd merchant-dashboard
npm install
npm run dev
# → http://localhost:3000
```

---

## API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/health` | System health + merchant count |
| GET | `/` | Redirects to `/docs` (Swagger UI) |
| GET | `/merchants` | Full merchant catalog |
| POST | `/context` | Weather + Payone volume for a merchant |
| POST | `/offer/match` | LLM reasoning → best merchant → offer card |
| POST | `/offer/generate` | Generate offer for a specific merchant (legacy endpoint) |
| POST | `/offer/redeem` | Validate and redeem a discount code |
| GET | `/merchant/{id}/activity` | Live stats for merchant dashboard |
| GET | `/debug/env` | Check which API keys are loaded (masked) |

### POST `/offer/match` — request body

```json
{
  "user_context":    "Situation summary built on-device (no raw signals)",
  "user_profile":    "GDPR-anonymised spending profile",
  "user_age_group":  "late 20s",
  "user_sex":        "female",
  "user_profession": "UX Designer",
  "user_interests":  ["specialty coffee", "yoga", "design books"],
  "scenario":        "cold",
  "lat": 53.5508,
  "lon": 10.0001
}
```

### GenUICard — response

```json
{
  "offer_id":          "uuid",
  "merchant_id":       "merchant_001",
  "merchant_name":     "Café Müller",
  "headline":          "Your coffee break just got better",
  "subline":           "18% off any drink, min €3.50, expires in 30 min",
  "discount_percent":  18,
  "discount_code":     "X7K2QP",
  "expiry_iso":        "2026-04-26T14:00:00+00:00",
  "color_hex":         "#c8702a",
  "emotional_framing": "warm_shelter",
  "intent_matched":    "LLM reasoning text shown in the demo UI",
  "llm_provider":      "llama-3.1-8b-instant · Groq"
}
```

---

## GDPR Shield — standalone demo

```powershell
cd backend
python gdpr_shield.py
```

Prints the full privacy audit trail: raw data received → each transformation applied → what the LLM actually sees. Demonstrates data minimisation, anonymisation, and purpose limitation live in the terminal.
