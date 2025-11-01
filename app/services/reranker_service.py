"""
LLM-based Reranker Service
Uses GPT-4o mini to rerank Wikipedia search results based on relevance to user query
"""

from typing import List, Dict, Optional
import logging
from app.services.llm_service import LLMService
from app.utils.colored_logger import get_plugin_logger
from pydantic import BaseModel

logger = logging.getLogger(__name__)
plugin_logger = get_plugin_logger(__name__, 'reranker')


class RankedResult(BaseModel):
    """Model for ranked search result"""
    pageid: int
    title: str
    snippet: str
    relevance_score: float
    reasoning: str


class RerankerService:
    """Service for reranking Wikipedia search results using LLM"""

    def __init__(self, llm_service: LLMService):
        """
        Initialize reranker service

        Args:
            llm_service: LLM service for making API calls
        """
        self.llm_service = llm_service

    async def rerank_results(
        self,
        query: str,
        search_results: List[Dict[str, str]],
        top_n: int = 5,
        model: str = "gpt-4o-mini"
    ) -> List[RankedResult]:
        """
        Rerank Wikipedia search results based on relevance to query

        Args:
            query: User's search query
            search_results: List of Wikipedia search results
            top_n: Number of top results to return after reranking
            model: Model to use for reranking (default: gpt-4o-mini)

        Returns:
            List of reranked results with relevance scores
        """
        if not search_results:
            return []

        # Prepare search results for LLM evaluation
        results_text = self._format_results_for_evaluation(search_results)

        # Create reranking prompt
        reranking_prompt = self._create_reranking_prompt(query, results_text)

        try:
            # Call LLM to evaluate relevance using structured completion
            messages = [
                {"role": "system", "content": (
                    "You are an expert at evaluating Wikipedia search result relevance. "
                    "Respond ONLY with a valid JSON object matching the requested fields."
                )},
                {"role": "user", "content": reranking_prompt}
            ]

            response = await self.llm_service.generate_structured_completion(
                messages=messages,
                model_config={
                    "provider": "openai",
                    "model_id": model,
                    "api_key_env": "OPENAI_API_KEY"
                },
                temperature=0.2
            )

            # Parse LLM response
            ranked_data = response.get("ranked_results", [])

            # Merge scores with original results
            ranked_results = self._merge_scores_with_results(
                search_results,
                ranked_data
            )

            # Sort by relevance score (descending) and return top_n
            ranked_results.sort(key=lambda x: x.relevance_score, reverse=True)
            top_results = ranked_results[:top_n]

            # Log reranking results
            plugin_logger.info(f"🔄 Reranked {len(search_results)} results, returning top {len(top_results)}:")
            for i, result in enumerate(top_results, 1):
                plugin_logger.info(f"  [{i}] {result.title} (score: {result.relevance_score:.2f})")
                plugin_logger.info(f"      💡 {result.reasoning}")

            return top_results

        except Exception as e:
            logger.error(f"Reranking error: {e}")
            # Fallback: return original results without reranking
            return [
                RankedResult(
                    pageid=result.get("pageid", 0),
                    title=result.get("title", ""),
                    snippet=result.get("snippet", ""),
                    relevance_score=1.0 - (i * 0.1),  # Simple descending score
                    reasoning="Reranking failed, using original order"
                )
                for i, result in enumerate(search_results[:top_n])
            ]

    def _format_results_for_evaluation(
        self,
        search_results: List[Dict[str, str]]
    ) -> str:
        """
        Format search results for LLM evaluation

        Args:
            search_results: List of search results

        Returns:
            Formatted string of results
        """
        formatted = []
        for i, result in enumerate(search_results, 1):
            formatted.append(
                f"Result {i}:\n"
                f"  Page ID: {result.get('pageid', 'N/A')}\n"
                f"  Title: {result.get('title', 'N/A')}\n"
                f"  Snippet: {result.get('snippet', 'N/A')}\n"
            )
        return "\n".join(formatted)

    def _create_reranking_prompt(self, query: str, results_text: str) -> str:
        """
        Create prompt for LLM reranking

        Args:
            query: User's search query
            results_text: Formatted search results

        Returns:
            Reranking prompt
        """
        return f"""You are an expert at evaluating Wikipedia search result relevance.

User Query: "{query}"

Search Results:
{results_text}

Task: Evaluate each search result's relevance to the user's query. For each result:
1. Assign a relevance score from 0.0 (completely irrelevant) to 1.0 (perfectly relevant)
2. Provide brief reasoning for the score

Consider:
- How well the title matches the query intent
- How relevant the snippet content is to answering the query
- Whether the result provides direct information or tangential information
- Topic alignment and specificity

Return a JSON object with the key "ranked_results" containing ALL results provided above, each as an object with fields: pageid (number), relevance_score (number between 0 and 1), reasoning (string)."""

    def _merge_scores_with_results(
        self,
        original_results: List[Dict[str, str]],
        scored_results: List[Dict]
    ) -> List[RankedResult]:
        """
        Merge LLM scores with original search results

        Args:
            original_results: Original Wikipedia search results
            scored_results: LLM-scored results

        Returns:
            List of RankedResult objects
        """
        # Create lookup dictionary for scores
        score_lookup = {
            int(item["pageid"]): {
                "relevance_score": item["relevance_score"],
                "reasoning": item["reasoning"]
            }
            for item in scored_results
        }

        # Merge scores with original results
        ranked = []
        for result in original_results:
            pageid = result.get("pageid", 0)
            score_data = score_lookup.get(
                pageid,
                {"relevance_score": 0.5, "reasoning": "No score provided"}
            )

            ranked.append(RankedResult(
                pageid=pageid,
                title=result.get("title", ""),
                snippet=result.get("snippet", ""),
                relevance_score=score_data["relevance_score"],
                reasoning=score_data["reasoning"]
            ))

        return ranked
