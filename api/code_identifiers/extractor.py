"""Identifier extraction helpers."""

from __future__ import annotations

import re
from typing import Iterable, List

from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.token import Name

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


GLOBAL_STOPWORDS = frozenset({"main", "system", "uri", "url"})


PYGMENTS_LEXERS = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "java": "java",
    "kotlin": "kotlin",
    "csharp": "csharp",
    "go": "go",
    "ruby": "ruby",
    "php": "php",
    "swift": "swift",
}


class IdentifierExtractor:
    """Extract identifiers from code snippets for supported languages."""

    def __init__(self):
        self._lang_map: dict[str, LanguageConfig] = LANG_MAP

    def extract(self, code: str, lang_key: str) -> List[str]:
        config = self._lang_map.get(lang_key)
        if not config:
            return []

        stripped_code = code
        for pattern in config.strip_patterns:
            stripped_code = pattern.sub(" ", stripped_code)

        names = [
            name.lstrip("@")
            for name in self._extract_structural_identifiers(code, lang_key)
            + list(self._iter_identifier_matches(config.identifier_patterns, stripped_code))
            + list(self._extract_with_pygments(code, lang_key))
        ]

        if lang_key == "python":
            imports = self._python_import_names(code)
            names = [name for name in names if name not in imports]
        filtered = [
            name
            for name in names
            if 2 < len(name) < 30
            and name.lower() not in config.keywords
            and name.lower() not in GLOBAL_STOPWORDS
        ]
        return list(dict.fromkeys(filtered))

    def should_skip(self, path: str) -> bool:
        return any(part.lower() in SKIP_PATH_PARTS for part in path.split("/"))

    @staticmethod
    def _iter_identifier_matches(patterns: Iterable[re.Pattern[str]], code: str) -> Iterable[str]:
        for pattern in patterns:
            for match in pattern.findall(code):
                yield match[-1] if isinstance(match, tuple) else match

    def _extract_structural_identifiers(self, code: str, lang_key: str) -> Iterable[str]:
        names: list[str] = []
        if lang_key == "python":
            for match in re.finditer(r"^\s*def\s+[a-z_][a-z0-9_]*\s*\(([^)]*)\)", code, re.MULTILINE | re.IGNORECASE):
                names.extend(re.findall(r"[a-z_][a-z0-9_]*", match.group(1), re.IGNORECASE))

            for match in re.finditer(
                r"for\s+([a-z_][a-z0-9_]*(?:\s*,\s*[a-z_][a-z0-9_]*)*)\s+in\s",
                code,
                re.IGNORECASE,
            ):
                names.extend(re.split(r"\s*,\s*", match.group(1)))

            names.extend(match.group(1) for match in re.finditer(r"@([A-Za-z_][A-Za-z0-9_]*)", code))
            names.extend(match.group(1).split(".")[0] for match in re.finditer(r"->\s*([A-Za-z_][A-Za-z0-9_\.]*)", code))
            names.extend(match.group(1) for match in re.finditer(r"[\(,:]\s*([A-Z][A-Za-z0-9_]*)(?:\s*[\[\]\)=]|\s*\n)", code))

        # Cross-language helpers to capture annotations, attributes, generics, and base types
        names.extend(match.group(1) for match in re.finditer(r"@([A-Za-z_][A-Za-z0-9_]*)", code))
        names.extend(match.group(1) for match in re.finditer(r"\[\s*([A-Z][A-Za-z0-9_]*)\s*\]", code))
        names.extend(match.group(1) for match in re.finditer(r"\b([A-Z][A-Za-z0-9_]*)\s*<", code))
        names.extend(match.group(1) for match in re.finditer(r"<\s*([A-Z][A-Za-z0-9_]*)", code))
        names.extend(match.group(1) for match in re.finditer(r"\bnew\s+([A-Z][A-Za-z0-9_]*)", code))
        names.extend(
            match.group(1)
            for match in re.finditer(
                r"class\s+[A-Za-z_][A-Za-z0-9_]*\s*(?::\s*|implements\s+|extends\s+)([A-Z][A-Za-z0-9_]*)",
                code,
            )
        )
        return names

    def _extract_with_pygments(self, code: str, lang_key: str) -> Iterable[str]:
        lexer_name = PYGMENTS_LEXERS.get(lang_key)
        if not lexer_name:
            return []

        try:
            lexer = get_lexer_by_name(lexer_name)
        except Exception:
            return []

        try:
            for tok_type, tok in lex(code, lexer):
                if tok_type in Name and tok.strip():
                    yield tok.strip()
        except Exception:
            return []

    @staticmethod
    def normalize_identifier(name: str) -> str:
        spaced = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
        collapsed = re.sub(r"[^a-zA-Z0-9]+", "_", spaced)
        return collapsed.lower().strip("_") or name.lower()

    @staticmethod
    def _python_import_names(code: str) -> set[str]:
        imports: set[str] = set()

        for match in re.finditer(r"^\s*from\s+[\w\.]+\s+import\s+(.+)$", code, re.MULTILINE):
            imports.update(filter(None, re.split(r"\s*,\s*", match.group(1).replace(" as ", ","))))

        for match in re.finditer(r"^\s*import\s+(.+)$", code, re.MULTILINE):
            parts = re.split(r"\s*,\s*", match.group(1))
            for alias in parts:
                clean = alias.split(" as ")[-1].split(".")[0].strip()
                base = alias.split(" as ")[0].split(".")[0].strip()
                imports.update(filter(None, (clean, base)))

        return imports


__all__ = ["IdentifierExtractor", "GLOBAL_STOPWORDS", "SKIP_PATH_PARTS"]
