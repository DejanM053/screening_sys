"""regulatory-engine — country-based rule system (CC-04). See CLAUDE.md Section 9."""
from fastapi import FastAPI

from app.routers import requirements

app = FastAPI(title="regulatory-engine", version="1.2.0")
app.include_router(requirements.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "regulatory-engine"}
