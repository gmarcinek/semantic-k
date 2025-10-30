from abc import ABC, abstractmethod
from typing import Optional


class BasePlugin(ABC):
    """Base plugin interface for topic-specific augmentations.

    Plugins can provide additional context or direct answers for a given prompt.
    """

    topic: str
    name: str

    @abstractmethod
    def prepare_context(self, prompt: str) -> Optional[str]:
        """Optionally return additional context to inject for the LLM.

        Return None if no context is available.
        """

    def can_handle(self, prompt: str) -> bool:
        """Whether plugin likely can help for this prompt (default True)."""
        return True

