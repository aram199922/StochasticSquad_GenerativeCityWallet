# Generative City-Wallet

## The Core Vision
Revitalise inner-city retail by giving local merchants the algorithmic AI power of global e-commerce. A privacy-first mobile app that uses real-world context (weather, events, live Payone foot-traffic) to dynamically generate hyper-personalised local offers via Generative UI.

**Powered by:** DSV-Gruppe | MIT Club of Northern California & Germany

---

## The Three Modules

| Module | What it does |
|---|---|
| **01 Context Sensing** | Aggregates weather, Tavily events, and Payone transaction volume |
| **02 Generative Offer Engine** | LLM generates a strict GenUI JSON card — never markdown |
| **03 Seamless Checkout** | Dynamic QR code → redemption API → merchant dashboard confirms |

**GDPR:** Raw location stays on-device. An on-device intent function (simulated SLM) converts signals into an abstract string (e.g. `seek_warm_drink`) — only that goes to the backend.

---

## Repository Structure

```
/backend              FastAPI orchestrator & GenUI offer engine
/mobile-app           React Native (Expo) consumer wallet app
/merchant-dashboard   Next.js 14 merchant portal
```

---

## Running Locally

### 1. Backend

```bash
cd backend
cp .env.example .env        # add your API keys
pip install -r requirements.txt
uvicorn main:app --reload
# → http://127.0.0.1:8000/docs
```

**Required env vars** (all optional — app stubs gracefully when missing):
- `OPENAI_API_KEY` — used for dynamic offer generation (falls back to rule-based stub)
- `OPENWEATHER_API_KEY` — weather context (falls back to 11°C overcast stub)
- `TAVILY_API_KEY` — local event signals (falls back to demo events)

### 2. Mobile App

```bash
cd mobile-app
cp .env.example .env        # set EXPO_PUBLIC_API_URL to your backend IP
npm install
npx expo start
```

Scan the QR code with Expo Go on your phone, or press `w` for the web version.

### 3. Merchant Dashboard

```bash
cd merchant-dashboard
cp .env.example .env.local  # set NEXT_PUBLIC_API_URL
npm install
npm run dev
# → http://localhost:3000
```

---

## Demo Flow (End-to-End)

1. Start backend → open `/docs` to confirm `/health` returns 2 merchants loaded
2. Open mobile app → tap **Find Nearby Offers**
3. Context signals appear (weather, Payone volume, local events)
4. On-device intent is shown (e.g. `seek_warm_drink`) — raw coords never leave device
5. GenUI offer card appears with dynamic headline, colour, and discount
6. Tap **Claim Offer** → QR code screen
7. Tap **Confirm Redemption** → ✓ success screen
8. Open merchant dashboard → see the offer in the log and redemption count incremented

---

## API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/health` | System health + merchant DB count |
| GET | `/merchants` | List all Payone merchants |
| POST | `/context` | Aggregate context signals for a merchant |
| POST | `/offer/generate` | Generate a GenUI offer card |
| POST | `/offer/redeem` | Validate and redeem a discount code |
| GET | `/merchant/{id}/activity` | Live stats for merchant dashboard |
