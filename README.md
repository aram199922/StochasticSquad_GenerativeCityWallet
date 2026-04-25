# Generative City-Wallet

## 🎯 The Core Vision
To revitalize inner-city retail by giving local merchants the algorithmic AI power of global e-commerce. We are building a privacy-first mobile app that uses real-world context (weather, events, live store foot-traffic) to dynamically generate hyper-personalized local offers via Generative UI. 

**Powered by:** DSV-Gruppe (German Savings Banks Financial Group).

## 🧑‍🤝‍🧑 The Scenario (Mia)
Mia is 28, walking through Stuttgart. It is 11°C and overcast. Café Müller is 80m away and currently quiet (low Payone transaction volume).
Instead of a generic 30-day coupon, our app detects the context and instantly generates a dynamic UI widget: *"Cold outside? Your cappuccino is waiting."*

## 🚀 Key Modules to Build
1. **Context Sensing Layer:** Combine real-time weather (OpenWeather), local events (Tavily API), location, and stubbed Payone merchant transaction data.
2. **Generative Offer Engine:** Offers are generated on the fly as strict Generative UI (GenUI) JSON payloads, NOT static templates.
3. **Seamless Checkout:** Scan a dynamic QR code to simulate a redeemed offer, closing the loop for the merchant.

## 🛡️ Privacy First
To comply with GDPR, raw location history does not go to the cloud. Local on-device models (or simulated local scripts) extract abstract intents (e.g., `{"intent": "seek_warm_shelter"}`) and only send that abstract signal to the backend.

## 📁 Repository Structure
- `/backend`: FastAPI Python orchestrator & Generative Engine.
- `/mobile-app`: React Native (Expo) consumer wallet app.
- `/merchant-dashboard`: Next.js web interface for rules & checkout simulation.