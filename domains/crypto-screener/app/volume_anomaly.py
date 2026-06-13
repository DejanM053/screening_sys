"""Volume anomaly detection (Section 10.3 Step 5) — synthetic/heuristic for now.

Flags sudden large inflows relative to the traced on-chain history. This is
the synthetic-data factor referenced in Section 6.7; a real implementation
would compare against the entity's transaction baseline (factor 2).
"""
from __future__ import annotations

from app.models import HopAnalysis


class VolumeAnomalyDetector:
    @staticmethod
    def detect(amount_usd: float, hop_analysis: HopAnalysis) -> float:
        if amount_usd <= 0:
            return 0.0

        # An inbound amount far larger than anything seen in the traced
        # neighbourhood suggests a sudden, unexplained inflow.
        if hop_analysis.total_value_traced_usd <= 0:
            return 0.0

        ratio = amount_usd / hop_analysis.total_value_traced_usd
        if ratio >= 5.0:
            return 0.8
        if ratio >= 2.0:
            return 0.5
        return 0.0
