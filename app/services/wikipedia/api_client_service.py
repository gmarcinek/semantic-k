"""Wikipedia API client service for low-level HTTP interactions."""
import aiohttp
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class WikipediaApiClientService:
    """Low-level Wikipedia API client for HTTP requests."""

    def __init__(self, language: str = "pl"):
        """Initialize Wikipedia API client.

        Args:
            language: Wikipedia language code (e.g., 'pl', 'en')
        """
        self.language = language
        self.base_url = f"https://{language}.wikipedia.org/w/api.php"
        self._headers = {
            "User-Agent": "semantic-k/1.0 (Wikipedia Q&A; contact: local)",
            "Accept": "application/json"
        }

    async def _make_request(
        self,
        params: Dict[str, Any],
        url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request to Wikipedia API.

        Args:
            params: Request parameters
            url: Optional custom URL (defaults to base_url)

        Returns:
            JSON response or None on error
        """
        request_url = url or self.base_url

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(request_url, params=params, headers=self._headers) as response:
                    if not self._validate_response(response):
                        text = await response.text()
                        logger.error(f"Wikipedia API HTTP {response.status}: {text[:200]}")
                        return None

                    content_type = response.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type:
                        text = await response.text()
                        logger.error(f"Wikipedia API non-JSON ({content_type}): {text[:200]}")
                        return None

                    return await response.json()
        except Exception as e:
            logger.error(f"Wikipedia API request error: {e}")
            return None

    async def make_rest_request(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Make request to Wikipedia REST API.

        Args:
            endpoint: REST API endpoint path

        Returns:
            JSON response or None on error
        """
        url = f"https://{self.language}.wikipedia.org/api/rest_v1/{endpoint}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._headers) as resp:
                    if resp.status != 200:
                        return None
                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type:
                        return None
                    return await resp.json()
        except Exception:
            return None

    @staticmethod
    def _validate_response(response) -> bool:
        """Validate HTTP response status.

        Args:
            response: HTTP response object

        Returns:
            True if response is valid
        """
        return response.status == 200

    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags from text.

        Args:
            text: Text containing HTML tags

        Returns:
            Cleaned text
        """
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers.

        Returns:
            Dictionary of headers
        """
        return self._headers.copy()
