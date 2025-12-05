"""Identifier extraction helpers."""

from __future__ import annotations

import re
from typing import Iterable, List

from .languages import LANG_MAP, LanguageConfig


SKIP_PATH_PARTS = frozenset(
    {
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        "vendor",
        "coverage",
        "site-packages",
        ".git",
        "out",
        "target",
        "bin",
        "obj",
        "packages",
        "test",
        "tests",
        "__tests__",
        "fixtures",
        "mocks",
        "spec",
    }
)


GLOBAL_STOPWORDS = frozenset(
    {
        "item",
        "items",
        "main",
        "row",
        "rows",
        "system",
        "uri",
        "url",
        "view",
    }
)


class IdentifierExtractor:
    """Extract identifiers from code snippets for supported languages."""

    def __init__(self):
        self._lang_map: dict[str, LanguageConfig] = LANG_MAP

    def extract(self, code: str, lang_key: str) -> List[str]:
        config = self._lang_map.get(lang_key)
        if not config:
            return []

        for pattern in config.strip_patterns:
            code = pattern.sub(" ", code)

        names = [
            name
            for name in self._iter_identifier_matches(config.identifier_patterns, code)
            if 2 < len(name) < 30
            and name.lower() not in config.keywords
            and name.lower() not in GLOBAL_STOPWORDS
        ]
        return list(dict.fromkeys(names))

    def should_skip(self, path: str) -> bool:
        return any(part.lower() in SKIP_PATH_PARTS for part in path.split("/"))

    @staticmethod
    def _iter_identifier_matches(patterns: Iterable[re.Pattern[str]], code: str) -> Iterable[str]:
        for pattern in patterns:
            for match in pattern.findall(code):
                yield match[-1] if isinstance(match, tuple) else match


__all__ = ["IdentifierExtractor", "GLOBAL_STOPWORDS", "SKIP_PATH_PARTS"]
