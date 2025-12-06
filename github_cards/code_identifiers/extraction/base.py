"""Base extractor interface for identifier extraction."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List


class BaseExtractor(ABC):
    """
    Abstract base class for identifier extractors.

    Extractors implement different strategies for extracting identifiers
    from source code (AST parsing, regex patterns, lexer analysis, etc.).
    """

    @abstractmethod
    def extract(self, code: str, lang_key: str) -> List[str]:
        """
        Extract identifiers from source code.

        Args:
            code: The source code to extract from
            lang_key: Language key (e.g., 'python', 'javascript')

        Returns:
            List of extracted identifier names
        """
        pass

    def supports_language(self, lang_key: str) -> bool:
        """
        Check if this extractor supports a given language.

        Args:
            lang_key: Language key to check

        Returns:
            True if the language is supported, False otherwise
        """
        return True  # By default, assume all languages supported


class CompositeExtractor(BaseExtractor):
    """
    Composite extractor that combines results from multiple extractors.

    Uses the Composite pattern to aggregate identifiers from different
    extraction strategies.
    """

    def __init__(self, extractors: List[BaseExtractor] | None = None):
        """
        Initialize the composite extractor.

        Args:
            extractors: List of extractors to compose
        """
        self.extractors = extractors or []

    def add_extractor(self, extractor: BaseExtractor) -> None:
        """Add an extractor to the composition."""
        self.extractors.append(extractor)

    def extract(self, code: str, lang_key: str) -> List[str]:
        """
        Extract identifiers using all available extractors.

        Args:
            code: The source code to extract from
            lang_key: Language key

        Returns:
            Combined list of identifiers from all extractors
        """
        results = []
        for extractor in self.extractors:
            if extractor.supports_language(lang_key):
                results.extend(extractor.extract(code, lang_key))
        return results


__all__ = ["BaseExtractor", "CompositeExtractor"]
