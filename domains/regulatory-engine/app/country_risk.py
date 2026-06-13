"""CountryRiskClassifier — FATF-based country risk tiers (Section 9.3)."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import yaml

from app.models import CountryRiskResult, CountryRiskTier

CONFIG_PATH = Path(__file__).parent / "config" / "country_risk_tiers.yaml"


class CountryRiskClassifier:
    """Loads FATF country risk tiers from YAML and classifies countries.

    The YAML file is a living configuration, re-assessed every FATF plenary
    (Feb/Jun/Oct). See app/update_grey_list.py for the update workflow.
    """

    def __init__(self, config_path: Path = CONFIG_PATH):
        self._config_path = config_path
        self._country_to_tier: Dict[str, CountryRiskTier] = {}
        self._tier_info: Dict[CountryRiskTier, dict] = {}
        self._load()

    def _load(self) -> None:
        with open(self._config_path, "r") as fh:
            data = yaml.safe_load(fh)

        for tier_name, tier_cfg in data["tiers"].items():
            tier = CountryRiskTier(tier_name)
            self._tier_info[tier] = {
                "score_multiplier": tier_cfg["score_multiplier"],
                "auto_block": tier_cfg["auto_block"],
                "description": tier_cfg["description"],
            }
            for country in tier_cfg.get("countries", []):
                self._country_to_tier[country.upper()] = tier

    def reload(self) -> None:
        """Reload the YAML config (call after the grey-list update script runs)."""
        self._country_to_tier.clear()
        self._tier_info.clear()
        self._load()

    def classify(self, country_code: str) -> CountryRiskResult:
        country_code = (country_code or "").upper()
        tier = self._country_to_tier.get(country_code, CountryRiskTier.STANDARD)
        info = self._tier_info[tier]
        return CountryRiskResult(
            country=country_code,
            tier=tier,
            score_multiplier=info["score_multiplier"],
            auto_block=info["auto_block"],
            description=info["description"],
        )

    def worst_of(self, *country_codes: str) -> CountryRiskResult:
        """Return the highest-risk classification among the given countries."""
        results = [self.classify(c) for c in country_codes if c]
        if not results:
            return self.classify("")
        return max(results, key=lambda r: (r.auto_block, r.score_multiplier))
