"""llm-service — Ollama wrapper for score explanations and SAR drafts (CC-06)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.explain import LLMExplanationGenerator
from app.ollama_client import OllamaClient
from app.routers import explain, sar
from app.sar import SarDraftGenerator


@asynccontextmanager
async def lifespan(app: FastAPI):
    ollama = OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_timeout_seconds)
    app.state.explanation_generator = LLMExplanationGenerator(ollama)
    app.state.sar_generator = SarDraftGenerator(ollama)
    yield


app = FastAPI(title="llm-service", version="1.2.0", lifespan=lifespan)

app.include_router(explain.router)
app.include_router(sar.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "llm-service"}
