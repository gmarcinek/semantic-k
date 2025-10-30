"""Search query builder for Wikipedia.

Provides lightweight heuristics to convert a natural-language prompt
into effective Wikipedia search queries. Avoids LLM usage for speed
and reliability.
"""

import re
from typing import List


POLISH_DIACRITICS = set("ąćęłńóśżźĄĆĘŁŃÓŚŻŹ")


class SearchQueryBuilder:
    """Heuristic builder for Wikipedia search queries."""

    @staticmethod
    def detect_language(prompt: str, default: str = "en") -> str:
        """Detect likely language based on simple heuristics.

        Returns 'pl' if Polish diacritics are present, otherwise default.
        """
        if any(ch in POLISH_DIACRITICS for ch in prompt):
            return "pl"
        return default

    @staticmethod
    def build_candidates(prompt: str) -> List[str]:
        """Build candidate queries from a natural-language prompt.

        Strategy:
        - Prefer quoted phrases ("...") if present
        - Prefer entity forms like "X (Y)" and also "X Y"
        - Strip trailing conversational tails and punctuation
        - Always include a compacted version of the prompt and the original
        """
        candidates: List[str] = []
        p = prompt.strip()

        # 1) Extract quoted phrases as high-signal queries
        quotes = re.findall(r'"([^"]+)"', p)
        for q in quotes:
            q = SearchQueryBuilder._clean(q)
            if q and q not in candidates:
                candidates.append(q)

        # 2) Extract entity with qualifier: X (Y)
        m = re.search(r"([^\(]+)\(([^\)]+)\)", p)
        if m:
            x = SearchQueryBuilder._clean(m.group(1))
            y = SearchQueryBuilder._clean(m.group(2))
            if x and y:
                xy_paren = f"{x} ({y})".strip()
                if xy_paren and xy_paren not in candidates:
                    candidates.append(xy_paren)
                xy_space = f"{x} {y}".strip()
                if xy_space and xy_space not in candidates:
                    candidates.append(xy_space)

        # 3) Remove common tails after separators like '-', ':', '?'
        p_core = re.split(r"\s[-–—:]\s|\?\s*", p, maxsplit=1)[0]
        p_core = SearchQueryBuilder._clean(p_core)
        if p_core and p_core not in candidates:
            candidates.append(p_core)

        # 4) Minimal keyword compaction: remove stop tails in PL/EN
        compact = SearchQueryBuilder._compact_keywords(p)
        if compact and compact not in candidates:
            candidates.append(compact)

        # 5) Fallback to original (last priority)
        if p not in candidates:
            candidates.append(p)

        return [c for c in candidates if c]

    @staticmethod
    def _clean(text: str) -> str:
        text = text.strip()
        # Remove enclosing quotes and excessive punctuation
        text = text.strip('"\'\'\u201c\u201d')
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _compact_keywords(text: str) -> str:
        """Remove common conversational tails and question fluff in PL/EN."""
        t = text.lower()
        # Remove typical Polish/English tails
        tails = [
            "co o niej wiesz", "co o nim wiesz", "co o tym wiesz",
            "co o niej możesz powiedzieć", "co o nim możesz powiedzieć",
            "what do you know about it", "tell me about", "what do you know about",
        ]
        for tail in tails:
            t = t.replace(tail, "")
        # Strip punctuation
        t = re.sub(r"[\?\!\.]", "", t)
        # Collapse whitespace and title-case important-looking tokens
        t = re.sub(r"\s+", " ", t).strip()
        # Return original casing of words except we keep spaces normalized
        # Use simple heuristic: keep original characters for non-lowercase detection
        return SearchQueryBuilder._clean(t)

