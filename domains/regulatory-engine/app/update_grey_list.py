"""FATF grey-list update script (Section 9.3 maintenance note).

The FATF grey list ("Increased Monitoring") and black list ("Call to Action")
are reassessed at each plenary (February, June, October). This script applies
a diff to app/config/country_risk_tiers.yaml and is intended to be triggered
by list-sync (CC-07) on its own schedule, or run manually after a plenary.

Usage:
    python -m app.update_grey_list --add-grey NG --remove-grey BG --add-black IR
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from app.country_risk import CONFIG_PATH

TIERS = ("BLACK", "GREY", "HIGH_RISK", "OFFSHORE")


def apply_changes(config_path: Path, additions: dict[str, list[str]], removals: dict[str, list[str]]) -> dict:
    with open(config_path, "r") as fh:
        data = yaml.safe_load(fh)

    for tier, codes in additions.items():
        existing = set(data["tiers"][tier]["countries"])
        existing.update(c.upper() for c in codes)
        data["tiers"][tier]["countries"] = sorted(existing)

    for tier, codes in removals.items():
        existing = set(data["tiers"][tier]["countries"])
        existing.difference_update(c.upper() for c in codes)
        data["tiers"][tier]["countries"] = sorted(existing)

    with open(config_path, "w") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)

    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Update FATF country risk tiers")
    for tier in TIERS:
        parser.add_argument(f"--add-{tier.lower().replace('_', '-')}", action="append", default=[], metavar="CC")
        parser.add_argument(f"--remove-{tier.lower().replace('_', '-')}", action="append", default=[], metavar="CC")
    args = parser.parse_args()

    additions = {tier: getattr(args, f"add_{tier.lower()}") for tier in TIERS}
    removals = {tier: getattr(args, f"remove_{tier.lower()}") for tier in TIERS}

    apply_changes(CONFIG_PATH, additions, removals)
    print(f"Updated {CONFIG_PATH}")


if __name__ == "__main__":
    main()
