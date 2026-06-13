"""Screening API — core verdict engine."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import fiat, crypto

app = FastAPI(
    title="Sanctions Screening API",
    version="1.2.0",
    description="KYB-first sanctions screening — two-track verdict engine",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fiat.router)
app.include_router(crypto.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "screening-api", "version": "1.2.0"}
