"""Response strategy service for determining how to respond to user queries."""
import logging
from typing import Dict, List, Optional, Tuple
from app.models import WikipediaMetadata, WikipediaSource

logger = logging.getLogger(__name__)


class ResponseStrategy:
    """Represents a response strategy."""

    PERFECT_MATCH = "perfect_match"
    HIGH_RELEVANCE = "high_relevance"
    NO_RESULTS = "no_results"
    LOW_RELEVANCE = "low_relevance"


class ResponseStrategyService:
    """Service for determining response strategy based on Wikipedia results."""

    def __init__(self, config_service):
        """Initialize response strategy service.

        Args:
            config_service: Configuration service
        """
        self.config_service = config_service

    def determine_strategy(
        self,
        wikipedia_metadata: Optional[WikipediaMetadata]
    ) -> Tuple[str, List[WikipediaSource], List[WikipediaSource]]:
        """Determine response strategy based on Wikipedia metadata.

        Args:
            wikipedia_metadata: Wikipedia metadata with sources

        Returns:
            Tuple of (strategy, top_answer_sources, perfect_sources)
        """
        if not wikipedia_metadata or not getattr(wikipedia_metadata, 'sources', None):
            return ResponseStrategy.NO_RESULTS, [], []

        sources = wikipedia_metadata.sources
        thr_cfg = self.config_service.config.get('wikipedia', {}).get('thresholds', {})
        answer_thr = float(thr_cfg.get('answer', 0.8))
        perfect_thr = float(thr_cfg.get('perfect', 0.98))

        top_answer = [s for s in sources if (s.relevance_score or 0) >= answer_thr]
        perfect = [s for s in sources if (s.relevance_score or 0) >= perfect_thr]

        if perfect:
            return ResponseStrategy.PERFECT_MATCH, top_answer, perfect
        elif top_answer:
            return ResponseStrategy.HIGH_RELEVANCE, top_answer, []
        else:
            return ResponseStrategy.LOW_RELEVANCE, [], []

    def build_perfect_match_prompt(self, title: str) -> str:
        """Build prompt for perfect match response.

        Args:
            title: Article title

        Returns:
            Prompt text
        """
        return (
            "Na Wikipedii jest artykuł, który opisuje to dokładnie. "
            f"Napisz wprost: Na Wikipedii jest artykuł '{title}', który opisuje to dokładnie. "
            "Przygotuj kompletną odpowiedź bazując na artykule (z kontekstu), dodaj 1–2 krótkie cytaty i link. "
            "Wspomnij o obrazie, jeśli dostępny, i podaj URL obrazu. "
            "Sformatuj odpowiedź jako prosty HTML (użyj <p>, <ul>, <li>, <a>, <blockquote>). "
            "Jeśli w kontekście jest linia 'Image: <URL>', możesz dodać <figure><img src=...><figcaption>."
        )

    def build_perfect_match_prompt_with_user_query(self, prompt: str, title: str) -> str:
        """Build prompt for perfect match response including user query.

        Args:
            prompt: User's original prompt
            title: Article title

        Returns:
            Prompt text
        """
        return (
            f"{prompt}\n\n"
            "Na Wikipedii jest artykuł, który opisuje to dokładnie. "
            f"Napisz wprost: Na Wikipedii jest artykuł '{title}', który opisuje to dokładnie. "
            "Przygotuj odpowiedź bazując na treści artykułu (z kontekstu systemowego), dodaj 1–2 krótkie cytaty w bloku cytatu i podaj link. "
            "Jeśli jest obraz/miniatura, wspomnij o nim i podaj URL obrazu. "
            "Zachowaj zwięzłość i nie wymyślaj faktów. "
            "Sformatuj odpowiedź jako prosty HTML (użyj <p>, <ul>, <li>, <a>, <blockquote>). "
            "Jeśli w kontekście jest linia 'Image: <URL>', możesz dodać <figure><img src=...><figcaption> z podpisem."
        )

    def build_high_relevance_prompt(self, top_answer: List[WikipediaSource]) -> str:
        """Build prompt for high relevance response.

        Args:
            top_answer: List of high-relevance sources

        Returns:
            Prompt text
        """
        cite_lines = "\n".join([
            f"- {s.title} ({s.url}) [~{int(round((s.relevance_score or 0)*100))}%]"
            for s in top_answer[:3]
        ])
        return (
            "Podsumuj odpowiedź bazując na wynikach z Wikipedii (patrz kontekst systemowy). "
            "W treści wpleć odniesienia do źródeł, a na końcu wypisz je w formie listy. "
            "Sformatuj odpowiedź jako prosty HTML (użyj <p>, <ul>, <li>, <a>, <blockquote>).\n"
            f"{cite_lines}"
        )

    def build_high_relevance_prompt_with_context(self, top_answer: List[WikipediaSource]) -> str:
        """Build prompt for high relevance response with Wikipedia context.

        Args:
            top_answer: List of high-relevance sources

        Returns:
            Prompt text
        """
        cite_lines = "\n".join([
            f"- {s.title} ({s.url}) [~{int(round((s.relevance_score or 0)*100))}%]"
            for s in top_answer[:3]
        ])
        return (
            "Based on the Wikipedia results above, provide a complete answer to the user's question. "
            "UWZGLĘDNIJ w treści odwołania do tych wysokotrafnych źródeł. "
            "Sformatuj odpowiedź jako prosty HTML (użyj <p>, <ul>, <li>, <a>, <blockquote>).\n"
            f"{cite_lines}\n"
        )

    def build_no_results_prompt(self) -> str:
        """Build prompt for no results response.

        Returns:
            Prompt text
        """
        return (
            "Sformatuj odpowiedź jako prosty HTML. "
            "<p>Nie znaleziono wiarygodnych wyników w Wikipedii dla tego zapytania.</p> "
            "<p>Zaproponuj alternatywne zapytania:</p><ul><li>…</li><li>…</li><li>…</li></ul>"
        )

    def build_low_relevance_prompt(self) -> str:
        """Build prompt for low relevance response.

        Returns:
            Prompt text
        """
        return "Based on the Wikipedia results above, provide a complete answer to the user's question."
