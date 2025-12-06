"""Stopword lists for filtering out common, non-meaningful identifiers."""

from __future__ import annotations

# Global stopwords - apply to all languages (VERY conservative - recall over precision)
GLOBAL_STOPWORDS = frozenset({
    "main", "system", "uri", "url",
})

# Language-specific stopwords (minimal - only truly meaningless keywords)
LANGUAGE_STOPWORDS = {}

# Substrings to exclude (VERY conservative)
EXCLUDED_SUBSTRINGS = ("system", "override")

__all__ = ["GLOBAL_STOPWORDS", "LANGUAGE_STOPWORDS", "EXCLUDED_SUBSTRINGS"]
