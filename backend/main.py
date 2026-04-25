import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="Generative City-Wallet API",
    description="Backend orchestrator for the DSV Gruppe hackathon — privacy-first GenUI offer engine.",
    version="0.1.0",
)

DB_PATH = Path(__file__).parent / "payone_db.json"

def _load_payone_db() -> dict:
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    payone_merchants_loaded: int


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
