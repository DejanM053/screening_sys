"""StablecoinScreener — orchestrates wallet screening (Section 10.3)."""
from __future__ import annotations

from app.attribution import WalletAttributor
from app.freeze_risk import FreezeRiskRegister
from app.issuer_blacklist import IssuerBlacklistChecker
from app.hop_tracer import OnChainHopTracer
from app.kyb_registry import KYBWalletRegistry
from app.mica import MiCAComplianceTagger
from app.models import (
    HopAnalysis,
    ScreenWalletRequest,
    ScreenWalletResponse,
    UBOResolutionStatus,
)
from app.ofac_wallets import OFACWalletScreener
from app.scorer import RawFactors, compute_composite, recommend_verdict
from app.travel_rule import TravelRuleEnforcer
from app.volume_anomaly import VolumeAnomalyDetector

# country corridor is passed as "XX->YY"
_CORRIDOR_SEPARATOR = "->"


class StablecoinScreener:
    def __init__(
        self,
        kyb_registry: KYBWalletRegistry,
        ofac_screener: OFACWalletScreener,
        issuer_checker: IssuerBlacklistChecker,
        hop_tracer: OnChainHopTracer,
        attributor: WalletAttributor,
        mica_tagger: MiCAComplianceTagger,
        freeze_register: FreezeRiskRegister,
        travel_rule: TravelRuleEnforcer,
    ) -> None:
        self._kyb_registry = kyb_registry
        self._ofac_screener = ofac_screener
        self._issuer_checker = issuer_checker
        self._hop_tracer = hop_tracer
        self._attributor = attributor
        self._mica_tagger = mica_tagger
        self._freeze_register = freeze_register
        self._travel_rule = travel_rule

    async def screen_wallet(self, req: ScreenWalletRequest) -> ScreenWalletResponse:
        originator_country, beneficiary_country = self._split_corridor(req.corridor, req.originator_country, req.beneficiary_country)

        # ── Step 1b: KYB Registry Lookup (first) ───────────────────────────
        kyb_record = await self._kyb_registry.lookup(req.address)
        kyb_verified = kyb_record is not None
        is_internal = False
        ubo_status = UBOResolutionStatus.UNRESOLVED

        if kyb_verified:
            is_internal = await self._kyb_registry.is_internal_pair(req.address, req.counterparty_address)
            ubo_status = kyb_record.ubo_resolution_status
            if ubo_status == UBOResolutionStatus.UNRESOLVED:
                # Even platform members with unresolved UBO get full external treatment.
                kyb_verified = False
                is_internal = False

        # ── Step 1: OFAC SDN wallet list ────────────────────────────────────
        ofac_match = await self._ofac_screener.lookup(req.address)
        ofac_score = 1.0 if ofac_match else 0.0

        # ── Step 2: Issuer blacklist check ─────────────────────────────────
        issuer_result = await self._issuer_checker.check(req.address, req.chain, req.stablecoin)

        # ── Step 3: On-chain hop analysis ──────────────────────────────────
        hop_depth = 1 if is_internal else 3
        hop_analysis: HopAnalysis = await self._hop_tracer.trace(req.address, req.chain, hop_depth)

        # ── Step 4: Attribution (skipped for KYB-verified addresses) ───────
        attribution = None
        if not kyb_verified:
            attribution = await self._attributor.lookup(req.address, req.chain)

        # ── Step 5: Volume anomaly ──────────────────────────────────────────
        volume_anomaly_score = VolumeAnomalyDetector.detect(req.amount_usd, hop_analysis)

        # ── Step 6: MiCA / TRON EU corridor / country sanctions ────────────
        policy = await self._mica_tagger.check(req.stablecoin, req.chain, originator_country, beneficiary_country)

        # ── Travel Rule ──────────────────────────────────────────────────
        travel_rule_status = self._travel_rule.enforce(req.amount_usd, originator_country, is_internal)

        # ── Entity risk score ───────────────────────────────────────────────
        entity_risk_score = kyb_record.onboarding_score if kyb_record else 0.0
        historical_flag_rate = kyb_record.historical_flag_rate if kyb_record else 0.0
        if WalletAttributor.is_mixer(attribution):
            from app.attribution import MIXER_SCORE_BOOST

            entity_risk_score = min(1.0, entity_risk_score + MIXER_SCORE_BOOST)

        factors = RawFactors(
            identity_match=ofac_score,
            behavioral_anomaly=volume_anomaly_score,
            network_exposure=hop_analysis.hop_score,
            entity_risk_profile=entity_risk_score,
            doc_integrity=0.0,
            historical_flag_rate=historical_flag_rate,
        )
        score_breakdown = compute_composite(factors)

        recommended_verdict = recommend_verdict(
            ofac_match=ofac_match,
            issuer_frozen=issuer_result.frozen,
            country_block=policy.country_block,
            composite=score_breakdown.composite,
            ubo_status=ubo_status,
        )

        # ── Freeze-risk register ───────────────────────────────────────────
        has_nonzero_flag = ofac_match or issuer_result.frozen or score_breakdown.composite > 0.0
        await self._freeze_register.update_register(req.address, has_nonzero_flag)

        return ScreenWalletResponse(
            address=req.address,
            chain=req.chain,
            kyb_verified=kyb_verified,
            is_internal=is_internal,
            entity_id=kyb_record.entity_id if kyb_record else None,
            ubo_status=ubo_status,
            ofac_match=ofac_match,
            ofac_score=ofac_score,
            country_block=policy.country_block,
            country_sanctions_program=policy.country_sanctions_program,
            issuer_frozen=issuer_result.frozen,
            issuer=issuer_result.issuer,
            hop_analysis=hop_analysis,
            hop_score=hop_analysis.hop_score,
            attribution=attribution.category if attribution else None,
            volume_anomaly_score=volume_anomaly_score,
            mica_flag=policy.mica_compliance_risk,
            tron_eu_corridor_flag=policy.tron_eu_corridor_review,
            travel_rule=travel_rule_status,
            entity_risk_score=entity_risk_score,
            historical_flag_rate=historical_flag_rate,
            composite_score=score_breakdown.composite,
            score_breakdown=score_breakdown,
            recommended_verdict=recommended_verdict,
        )

    @staticmethod
    def _split_corridor(corridor: str, originator_country: str | None, beneficiary_country: str | None) -> tuple[str, str]:
        if originator_country and beneficiary_country:
            return originator_country, beneficiary_country
        if corridor and _CORRIDOR_SEPARATOR in corridor:
            originator, beneficiary = corridor.split(_CORRIDOR_SEPARATOR, 1)
            return originator.strip(), beneficiary.strip()
        return "", ""
