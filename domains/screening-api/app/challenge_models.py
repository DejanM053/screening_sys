# Place at: domains/screening-api/app/challenge_models.py
"""AMLCaseXML Pydantic model — goAML-inspired schema extended with geopolitical context."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

CONTROLLED_TYPOLOGY_TAGS: List[str] = [
    "structuring",
    "layering",
    "trade_based_ml",
    "pep_exposure",
    "sanctions_adjacent",
    "crypto_layering",
    "real_estate",
    "correspondent_risk",
    "unknown",
]

RISK_SCORE_KEYS: List[str] = [
    "source_of_wealth",
    "document_consistency",
    "counterparty_opacity",
    "relationship_novelty",
]


class Party(BaseModel):
    entity_name: str
    entity_type: Literal["individual", "company", "financial_institution"]
    country_of_incorporation: str
    account_country: str
    registration_age_days: int
    is_pep: bool
    ownership_opacity_score: float = Field(ge=0.0, le=1.0)


class TradeContext(BaseModel):
    goods_description: Optional[str] = None
    hs_code: Optional[str] = None
    dual_use_flag: bool = False
    invoice_amount: Optional[float] = None
    shipment_country: Optional[str] = None


class CountryGeopoliticalContext(BaseModel):
    FATF_status: Literal["compliant", "monitored", "greylisted", "blacklisted"]
    basel_aml_index_score: float
    active_sanctions_programs: List[str] = Field(default_factory=list)
    export_control_alerts: List[str] = Field(default_factory=list)


class AMLCaseXML(BaseModel):
    # ── Transaction core ──────────────────────────────────────────────────────
    transaction_id: str
    amount: float
    currency: str
    value_date: str  # ISO date string "YYYY-MM-DD"
    product_type: Literal["wire_transfer", "trade_finance", "crypto"]
    direction: Literal["inbound", "outbound"]

    # ── Parties ───────────────────────────────────────────────────────────────
    originator: Party
    beneficiary: Party

    # ── Trade context (nullable — only populated for trade_finance) ───────────
    trade_context: Optional[TradeContext] = None

    # ── Relationship context ──────────────────────────────────────────────────
    relationship_tenure_days: int
    first_transaction_to_counterparty: bool
    referral_origin: Literal["cold_contact", "existing_relationship", "platform", "unknown"]

    # ── Analyst assessment ────────────────────────────────────────────────────
    typology_tags: List[str]  # subset of CONTROLLED_TYPOLOGY_TAGS
    risk_scores: Dict[str, float]  # keys from RISK_SCORE_KEYS, values 0-10
    reviewer_verdict: Literal["approved", "blocked", "escalated"]
    reviewer_rationale: str

    # ── Geopolitical context snapshot (captured at review time) ───────────────
    # Stored alongside the case so future comparisons know the environment
    # at the time of the original decision.
    geopolitical_snapshot: Dict[str, CountryGeopoliticalContext]
