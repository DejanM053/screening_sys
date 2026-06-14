"""crypto-screener — stablecoin/wallet compliance screening (Section 10, CC-05)."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.attribution import WalletAttributor
from app.config import settings
from app.freeze_risk import FreezeRiskRegister
from app.hop_tracer import OnChainHopTracer
from app.issuer_blacklist import IssuerBlacklistChecker
from app.kyb_registry import KYBWalletRegistry
from app.mica import MiCAComplianceTagger
from app.ofac_wallets import OFACWalletScreener
from app.routers import admin, screen
from app.store import InMemoryStore, RedisStore
from app.travel_rule import TravelRuleEnforcer
from app.wallet_screener import StablecoinScreener

logger = logging.getLogger("crypto-screener")


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_store = RedisStore(settings.redis_url)
    try:
        await redis_store.ping()
        store = redis_store
    except Exception as exc:  # pragma: no cover - exercised only without Redis
        logger.warning("Redis unavailable (%s); falling back to in-memory store", exc)
        await redis_store.close()
        store = InMemoryStore()

    app.state.kyb_registry = KYBWalletRegistry(store)
    app.state.ofac_screener = OFACWalletScreener(store)
    app.state.screener = StablecoinScreener(
        kyb_registry=app.state.kyb_registry,
        ofac_screener=app.state.ofac_screener,
        issuer_checker=IssuerBlacklistChecker(),
        hop_tracer=OnChainHopTracer(store),
        attributor=WalletAttributor(),
        mica_tagger=MiCAComplianceTagger(),
        freeze_register=FreezeRiskRegister(store),
        travel_rule=TravelRuleEnforcer(),
    )

    # Kick off OFAC XML sync in background — doesn't block service startup
    async def _ofac_sync():
        try:
            n = await app.state.ofac_screener.sync_from_ofac_xml()
            logger.info("OFAC startup sync complete: %d addresses loaded", n)
        except Exception as exc:
            logger.warning("OFAC startup sync failed: %s", exc)

    asyncio.create_task(_ofac_sync())

    yield

    if isinstance(store, RedisStore):
        await store.close()


app = FastAPI(title="crypto-screener", version="1.2.0", lifespan=lifespan)
app.include_router(screen.router)
app.include_router(admin.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "crypto-screener"}
