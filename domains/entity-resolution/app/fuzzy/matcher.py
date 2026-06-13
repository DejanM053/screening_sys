"""Fuzzy and phonetic name matching (CC-02)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler, Levenshtein


@dataclass
class MatchCandidate:
    matched_name: str
    score: float
    list_source: str
    list_entry_id: str
    match_methods_used: List[str] = field(default_factory=list)
    corroboration: bool = False


class FuzzyMatcher:
    """
    Composite fuzzy scorer: Jaro-Winkler + Levenshtein + token_sort_ratio.

    Composite = 0.40 * jaro_winkler + 0.35 * levenshtein + 0.25 * token_sort
    Weights tuned to balance prefix-sensitivity (JW) with edit tolerance (LD)
    and word-order robustness (token sort).
    """

    def score(self, query: str, candidate: str) -> float:
        q, c = query.lower(), candidate.lower()
        jw = JaroWinkler.normalized_similarity(q, c)
        lev = 1.0 - (Levenshtein.distance(q, c) / max(len(q), len(c), 1))
        ts = fuzz.token_sort_ratio(q, c) / 100.0
        return round(0.40 * jw + 0.35 * lev + 0.25 * ts, 4)

    def match_all(self, query: str, candidates: List[str]) -> List[tuple[str, float]]:
        return sorted(
            [(c, self.score(query, c)) for c in candidates],
            key=lambda x: x[1],
            reverse=True,
        )


class PhoneticMatcher:
    """
    Phonetic similarity for English-language name variations.

    Uses double-metaphone to generate phonetic keys, then compares.
    Falls back to fuzzy ratio when phonetic keys are identical (both match)
    or completely different (phonetic tells us nothing).
    """

    def _dm_key(self, name: str) -> tuple[str, str]:
        try:
            import phonetics
            primary = phonetics.dmetaphone(name)[0] or ""
            secondary = phonetics.dmetaphone(name)[1] or ""
            return primary, secondary
        except Exception:
            return "", ""

    def score(self, query: str, candidate: str) -> float:
        q_keys = self._dm_key(query)
        c_keys = self._dm_key(candidate)
        # Check any key combination match
        q_set = {k for k in q_keys if k}
        c_set = {k for k in c_keys if k}
        if q_set & c_set:
            return 1.0
        if not q_set or not c_set:
            return 0.0
        # partial phonetic similarity via string ratio on keys
        best = max(
            fuzz.ratio(qk, ck) for qk in q_set for ck in c_set
        ) / 100.0
        return round(best, 4)

    def same_phonetic_family(self, query: str, candidate: str) -> bool:
        return self.score(query, candidate) >= 0.80
