"""RegulatoryEngineRouter — aggregates applicable jurisdiction rules for a payment (CC-04 §5)."""
from __future__ import annotations

from app.country_risk import CountryRiskClassifier
from app.models import (
    CountryRiskTier,
    GetRequirementsResponse,
    PolicyFlag,
    RegulatoryPaymentContext,
    ScoreThresholds,
)
from app.rules import (
    AUSTRACRule,
    DFSARule,
    EUAMLRule,
    FATFBaseRule,
    FCARule,
    FINTRACRule,
    JurisdictionRule,
    OFACRule,
    TRONCorriderPolicyRule,
)

# Specific jurisdiction rules, checked first. FATFBaseRule is the fallback,
# applied only when none of these match.
JURISDICTION_RULES: list[JurisdictionRule] = [
    OFACRule(),
    FCARule(),
    EUAMLRule(),
    AUSTRACRule(),
    FINTRACRule(),
    DFSARule(),
]

FALLBACK_RULE = FATFBaseRule()
TRON_POLICY_RULE = TRONCorriderPolicyRule()


class RegulatoryEngineRouter:
    def __init__(self, country_risk: CountryRiskClassifier | None = None):
        self.country_risk = country_risk or CountryRiskClassifier()

    def applicable_rules(self, payment: RegulatoryPaymentContext) -> list[JurisdictionRule]:
        matched = [r for r in JURISDICTION_RULES if r.applies_to(payment)]
        if not matched:
            matched = [FALLBACK_RULE]
        if TRON_POLICY_RULE.applies_to(payment):
            matched = matched + [TRON_POLICY_RULE]
        return matched

    def get_requirements(self, payment: RegulatoryPaymentContext) -> GetRequirementsResponse:
        rules = self.applicable_rules(payment)

        required_lists: set = set()
        reporting: list = []
        policy_flags: set[PolicyFlag] = set()
        retention_days = 0
        travel_rule_thresholds: list[float] = []
        ede_required = False

        # Strictest threshold wins: lowest MATCH/REVIEW boundary across rules.
        match_threshold = 1.0
        review_threshold = 1.0

        for rule in rules:
            required_lists.update(rule.get_required_lists())
            reporting.extend(rule.get_reporting_requirements(payment))
            policy_flags.update(rule.get_policy_flags(payment))
            retention_days = max(retention_days, rule.get_retention_period_days())

            thresholds = rule.get_thresholds()
            match_threshold = min(match_threshold, thresholds.match)
            review_threshold = min(review_threshold, thresholds.review)

            trt = rule.get_travel_rule_threshold_usd()
            if trt is not None:
                travel_rule_thresholds.append(trt)

            ede_required = ede_required or rule.get_enhanced_due_diligence(payment)

        thresholds = ScoreThresholds(match=match_threshold, review=review_threshold)

        # Travel Rule applies to stablecoin payments if any applicable rule
        # defines a threshold that the payment amount meets or exceeds.
        # EU/UK rules define a 0 USD threshold, so any stablecoin transfer
        # on those corridors always requires it.
        travel_rule_required = False
        if payment.asset_type == "stablecoin" and travel_rule_thresholds:
            min_threshold = min(travel_rule_thresholds)
            travel_rule_required = payment.amount_usd >= min_threshold

        # Country risk: worst of originator/beneficiary.
        country_risk_o = self.country_risk.classify(payment.originator_country)
        country_risk_b = self.country_risk.classify(payment.beneficiary_country)
        worst = self.country_risk.worst_of(payment.originator_country, payment.beneficiary_country)

        country_sanctions_program = None
        if worst.tier == CountryRiskTier.BLACK:
            country_sanctions_program = (
                f"Comprehensive sanctions / FATF Call to Action — {worst.country} (BLACK tier)"
            )

        return GetRequirementsResponse(
            required_lists=sorted(required_lists, key=lambda s: s.value),
            thresholds=thresholds,
            reporting_obligations=reporting,
            country_risk_tiers={
                "originator": country_risk_o,
                "beneficiary": country_risk_b,
            },
            applicable_rules=[r.name for r in rules],
            travel_rule_required=travel_rule_required,
            policy_flags=sorted(policy_flags, key=lambda f: f.value),
            auto_block=worst.auto_block,
            country_sanctions_program=country_sanctions_program,
            review_threshold=thresholds.review,
            country_risk_multiplier=worst.score_multiplier,
            mica_compliance_risk=PolicyFlag.MICA_COMPLIANCE_RISK in policy_flags,
            tron_eu_corridor_review=PolicyFlag.TRON_EU_CORRIDOR_REVIEW in policy_flags,
            retention_period_days=retention_days,
        )
