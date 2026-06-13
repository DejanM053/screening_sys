"""Script normalization: Arabic/Russian/Chinese → Latin (CC-02)."""
from __future__ import annotations

import unicodedata
import re
from typing import List

from unidecode import unidecode


class TransliterationNormalizer:
    """
    Normalize names from various scripts to ASCII-safe Latin for comparison.

    Pipeline: script-specific transliteration → NFKD → diacritic strip → lowercase.
    """

    def normalize(self, name: str) -> str:
        """Full normalization pipeline."""
        name = self._transliterate_cyrillic(name)
        name = self._transliterate_arabic(name)
        name = unidecode(name)  # handles Chinese pinyin + remaining diacritics
        name = unicodedata.normalize("NFKD", name)
        name = "".join(c for c in name if not unicodedata.combining(c))
        name = name.lower().strip()
        name = re.sub(r"\s+", " ", name)
        return name

    def normalize_variants(self, name: str) -> List[str]:
        """Return multiple normalization variants to maximise recall."""
        base = self.normalize(name)
        variants = {base}
        # Without punctuation
        variants.add(re.sub(r"[^a-z0-9 ]", "", base))
        return list(variants)

    def _transliterate_cyrillic(self, text: str) -> str:
        try:
            from transliterate import translit, get_available_language_codes
            if "ru" in get_available_language_codes():
                return translit(text, "ru", reversed=True)
        except Exception:
            pass
        return text

    def _transliterate_arabic(self, text: str) -> str:
        # Basic Arabic → Latin mapping; full implementation uses arabic-transliteration lib
        arabic_map = {
            "ا": "a", "ب": "b", "ت": "t", "ث": "th", "ج": "j",
            "ح": "h", "خ": "kh", "د": "d", "ذ": "dh", "ر": "r",
            "ز": "z", "س": "s", "ش": "sh", "ص": "s", "ض": "d",
            "ط": "t", "ظ": "z", "ع": "a", "غ": "gh", "ف": "f",
            "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n",
            "ه": "h", "و": "w", "ي": "y", "ة": "a", "ى": "a",
            "أ": "a", "إ": "i", "آ": "a", "ئ": "y", "ء": "",
        }
        result = []
        for ch in text:
            result.append(arabic_map.get(ch, ch))
        return "".join(result)
