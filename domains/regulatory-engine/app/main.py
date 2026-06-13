"""regulatory-engine — stub implementation. See CLAUDE.md for full spec."""
from fastapi import FastAPI

app = FastAPI(title="regulatory-engine", version="1.2.0")

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "regulatory-engine"}
