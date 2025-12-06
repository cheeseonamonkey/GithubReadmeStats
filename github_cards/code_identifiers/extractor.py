"""Identifier extraction helpers."""

from __future__ import annotations

import re
from typing import Iterable, List

from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.token import Name

from .languages import LANG_MAP, LanguageConfig
from .filtering.stopwords import GLOBAL_STOPWORDS, LANGUAGE_STOPWORDS, EXCLUDED_SUBSTRINGS
from .filtering.normalizer import normalize_identifier as norm_identifier
from .extraction.ast_extractors import PythonASTExtractor


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
        self._ast_extractor = PythonASTExtractor()

    def extract(self, code: str, lang_key: str) -> List[str]:
        config = self._lang_map.get(lang_key)
        if not config:
            return []

        stripped_code = code
        for pattern in config.strip_patterns:
            stripped_code = pattern.sub(" ", stripped_code)

        names = self._collect_candidates(code, stripped_code, lang_key, config)

        if lang_key == "python":
            names = self._filter_python_imports(code, names)

        return self._filter_identifiers(names, config, lang_key)

    def should_skip(self, path: str) -> bool:
        return any(part.lower() in SKIP_PATH_PARTS for part in path.split("/"))

    def _collect_candidates(
        self, code: str, stripped_code: str, lang_key: str, config: LanguageConfig
    ) -> list[str]:
        candidates = []

        # Try AST extraction first (more accurate for supported languages)
        if self._ast_extractor.supports_language(lang_key):
            candidates.extend(self._ast_extractor.extract(code, lang_key))

        # Add results from other extraction methods
        candidates.extend(self._extract_structural_identifiers(code, lang_key))
        candidates.extend(self._iter_identifier_matches(config.identifier_patterns, stripped_code))
        candidates.extend(self._extract_bracket_generics(code))
        candidates.extend(self._extract_with_pygments(code, lang_key))

        # Strip @ prefix from decorators
        return [name.lstrip("@") for name in candidates]

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

    @staticmethod
    def _extract_bracket_generics(code: str) -> Iterable[str]:
        """Capture wrapper and inner types that use square-bracket generics (e.g., Optional[Response])."""

        for match in re.finditer(r"\b([A-Z][A-Za-z0-9_]*)\s*\[", code):
            yield match.group(1)
        for match in re.finditer(r"\[\s*([A-Z][A-Za-z0-9_]*)", code):
            yield match.group(1)

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
        """Normalize identifier using the improved normalization logic."""
        return norm_identifier(name)

    def _filter_identifiers(self, names: list[str], config: LanguageConfig, lang_key: str) -> list[str]:
        filtered: list[str] = []
        seen: set[str] = set()

        # Get language-specific stopwords
        lang_stopwords = LANGUAGE_STOPWORDS.get(lang_key, frozenset())

        for name in names:
            normalized = name.lower()

            if (
                normalized in seen
                or any(sub in normalized for sub in EXCLUDED_SUBSTRINGS)
                or not (2 < len(name) < 30)
                or normalized in config.keywords
                or normalized in GLOBAL_STOPWORDS
                or normalized in lang_stopwords
            ):
                continue

            filtered.append(name)
            seen.add(normalized)

        return filtered

    def _filter_python_imports(self, code: str, names: list[str]) -> list[str]:
        imports, modules = self._python_import_names(code)
        code_without_imports = re.sub(r"^(?:from|import)\s+.*$", " ", code, flags=re.MULTILINE)

        used_names = {
            name
            for name in imports | modules
            if re.search(rf"\b{re.escape(name)}\b", code_without_imports)
        }

        return [name for name in names if name not in imports | modules or name in used_names]

    @staticmethod
    def _python_import_names(code: str) -> tuple[set[str], set[str]]:
        imports: set[str] = set()
        modules: set[str] = set()

        for match in re.finditer(r"^\s*from\s+([\w\.]+)\s+import\s+(.+)$", code, re.MULTILINE):
            modules.update(match.group(1).split("."))
            imports.update(filter(None, re.split(r"\s*,\s*", match.group(2).replace(" as ", ","))))

        for match in re.finditer(r"^\s*import\s+(.+)$", code, re.MULTILINE):
            parts = re.split(r"\s*,\s*", match.group(1))
            for alias in parts:
                clean = alias.split(" as ")[-1].split(".")[0].strip()
                base = alias.split(" as ")[0].split(".")[0].strip()
                imports.update(filter(None, (clean, base)))
                modules.add(base)

        return imports, modules


__all__ = ["IdentifierExtractor", "GLOBAL_STOPWORDS", "SKIP_PATH_PARTS", "EXCLUDED_SUBSTRINGS"]
