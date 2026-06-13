"""review-queue — stub implementation. See CLAUDE.md for full spec."""
from fastapi import FastAPI

app = FastAPI(title="review-queue", version="1.2.0")

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "review-queue"}
