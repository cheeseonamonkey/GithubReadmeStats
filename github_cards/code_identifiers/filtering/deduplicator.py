"""Smart deduplication for identifiers."""

from __future__ import annotations
from typing import Counter as CounterType

from .normalizer import normalize_identifier, prefer_type_over_instance, are_similar


class SmartDeduplicator:
    """
    Handles intelligent deduplication of identifiers.

    Features:
    - Normalizes identifiers for grouping
    - Prefers types (PascalCase) over instances (camelCase)
    - Groups similar identifiers with affixes stripped
    """

    def __init__(self):
        # Maps normalized form to best display name
        self.display_names: dict[str, str] = {}
        # Maps normalized form to language counts
        self.id_langs: dict[str, CounterType[str]] = {}

    def add(self, identifier: str, lang: str) -> None:
        """
        Add an identifier occurrence.

        Args:
            identifier: The identifier name as it appears in code
            lang: The language key
        """
        normalized = normalize_identifier(identifier)

        # Initialize if first occurrence
        if normalized not in self.id_langs:
            self.id_langs[normalized] = CounterType()
            self.display_names[normalized] = identifier
        else:
            # Update display name if new name is preferred
            current = self.display_names[normalized]
            preferred = prefer_type_over_instance(identifier, current)
            self.display_names[normalized] = preferred

        # Update language count
        self.id_langs[normalized][lang] += 1

    def get_results(self) -> tuple[dict[str, CounterType[str]], dict[str, str]]:
        """
        Get the deduplicated results.

        Returns:
            Tuple of (id_langs, display_names) where:
            - id_langs: Maps normalized identifier to language counts
            - display_names: Maps normalized identifier to best display name
        """
        return self.id_langs, self.display_names


__all__ = ["SmartDeduplicator"]
