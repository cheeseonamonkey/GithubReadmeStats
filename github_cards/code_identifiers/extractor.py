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
from .extraction.tree_sitter_extractor import TreeSitterExtractor


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
        self._tree_sitter_extractor = TreeSitterExtractor()

    def extract(self, code: str, lang_key: str) -> List[str]:
        config = self._lang_map.get(lang_key)
        if not config:
            return []

        stripped_code = code
        for pattern in config.strip_patterns:
            stripped_code = pattern.sub(" ", stripped_code)

        names = self._collect_candidates(code, stripped_code, lang_key, config)

        # Filter imports for all supported languages
        names = self._filter_imports(code, names, lang_key)

        return self._filter_identifiers(names, config, lang_key)

    def should_skip(self, path: str) -> bool:
        return any(part.lower() in SKIP_PATH_PARTS for part in path.split("/"))

    def _collect_candidates(
        self, code: str, stripped_code: str, lang_key: str, config: LanguageConfig
    ) -> list[str]:
        candidates = []

        # Try tree-sitter first for JS/TS/Java/Go (most accurate)
        if self._tree_sitter_extractor.supports_language(lang_key):
            candidates.extend(self._tree_sitter_extractor.extract(code, lang_key))
        # Then try Python AST extractor
        elif self._ast_extractor.supports_language(lang_key):
            candidates.extend(self._ast_extractor.extract(code, lang_key))

        # Add results from other extraction methods (regex patterns)
        candidates.extend(self._extract_structural_identifiers(code, lang_key))
        candidates.extend(self._iter_identifier_matches(config.identifier_patterns, stripped_code))
        candidates.extend(self._extract_bracket_generics(code))
        candidates.extend(self._extract_destructuring(code, lang_key))
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

            # Python constants (SCREAMING_SNAKE_CASE)
            names.extend(match.group(1) for match in re.finditer(r"^\s+([A-Z][A-Z0-9_]{2,})\s*=", code, re.MULTILINE))

        # JavaScript/TypeScript specific patterns
        if lang_key in ("javascript", "typescript"):
            # Getters and setters
            names.extend(match.group(1) for match in re.finditer(r"\b(?:get|set)\s+([a-z_$][a-z0-9_$]*)\s*\(", code, re.IGNORECASE))
            # Enum members (TypeScript)
            if lang_key == "typescript":
                for enum_match in re.finditer(r"\benum\s+\w+\s*\{([^}]+)\}", code):
                    enum_body = enum_match.group(1)
                    # Extract enum member names
                    names.extend(match.group(1) for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|,|})", enum_body))

        # C# properties
        if lang_key == "csharp":
            # public string Name { get; set; }
            names.extend(match.group(1) for match in re.finditer(
                r"(?:public|private|protected|internal)\s+\w+\s+([A-Z][A-Za-z0-9_]*)\s*\{", code
            ))

        # Java enums and records
        if lang_key == "java":
            # Enum constants
            for enum_match in re.finditer(r"\benum\s+\w+\s*\{([^}]+)\}", code):
                enum_body = enum_match.group(1)
                names.extend(match.group(1) for match in re.finditer(r"([A-Z_][A-Z0-9_]*)\s*(?:\(|,|})", enum_body))
            # Record components
            for record_match in re.finditer(r"\brecord\s+\w+\s*\(([^)]+)\)", code):
                params = record_match.group(1)
                names.extend(match.group(1) for match in re.finditer(r"(\w+)\s*(?:,|\))", params))

        # Go constants and struct fields
        if lang_key == "go":
            # const NAME = value
            names.extend(match.group(1) for match in re.finditer(r"\bconst\s+([A-Z][A-Za-z0-9_]*)\s*=", code))
            # Struct fields (exported ones starting with capital)
            names.extend(match.group(1) for match in re.finditer(r"^\s+([A-Z][A-Za-z0-9_]*)\s+\w+", code, re.MULTILINE))

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

    def _extract_destructuring(self, code: str, lang_key: str) -> Iterable[str]:
        """Extract identifiers from destructuring patterns."""
        if lang_key in ("javascript", "typescript"):
            # Object destructuring: const { a, b: renamed } = obj
            for match in re.finditer(r"(?:const|let|var)\s*\{([^}]+)\}\s*=", code):
                parts = match.group(1).split(",")
                for part in parts:
                    # Handle renaming: "original: renamed" - we want "renamed"
                    if ":" in part:
                        name = part.split(":")[-1].strip()
                    else:
                        name = part.strip()
                    # Skip spread operator and quoted keys
                    if name and not name.startswith(("...", '"', "'", "[")):
                        # Clean up any remaining syntax
                        clean = re.match(r"([a-z_$][a-z0-9_$]*)", name, re.IGNORECASE)
                        if clean:
                            yield clean.group(1)

            # Array destructuring: const [a, b] = arr
            for match in re.finditer(r"(?:const|let|var)\s*\[([^\]]+)\]\s*=", code):
                parts = match.group(1).split(",")
                for part in parts:
                    name = part.strip()
                    # Skip spread operator
                    if name and not name.startswith("..."):
                        clean = re.match(r"([a-z_$][a-z0-9_$]*)", name, re.IGNORECASE)
                        if clean:
                            yield clean.group(1)

        elif lang_key == "python":
            # Tuple unpacking: a, b = value (already handled by AST, but add pattern for completeness)
            for match in re.finditer(r"^\s*(\w+(?:\s*,\s*\w+)+)\s*=", code, re.MULTILINE):
                names = match.group(1).split(",")
                for name in names:
                    clean = name.strip()
                    if clean and re.match(r"[a-z_][a-z0-9_]*$", clean, re.IGNORECASE):
                        yield clean

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

    def _filter_imports(self, code: str, names: list[str], lang_key: str) -> list[str]:
        """Filter import-only names for supported languages."""
        if lang_key == "python":
            return self._filter_python_imports(code, names)
        elif lang_key in ("javascript", "typescript"):
            return self._filter_js_imports(code, names)
        elif lang_key == "java":
            return self._filter_java_imports(code, names)
        elif lang_key == "go":
            return self._filter_go_imports(code, names)
        return names

    def _filter_python_imports(self, code: str, names: list[str]) -> list[str]:
        imports, modules = self._python_import_names(code)
        code_without_imports = re.sub(r"^(?:from|import)\s+.*$", " ", code, flags=re.MULTILINE)

        used_names = {
            name
            for name in imports | modules
            if re.search(rf"\b{re.escape(name)}\b", code_without_imports)
        }

        return [name for name in names if name not in imports | modules or name in used_names]

    def _filter_js_imports(self, code: str, names: list[str]) -> list[str]:
        """Filter JavaScript/TypeScript imports."""
        imported_names = set()

        # Named imports: import { foo, bar } from 'module'
        for match in re.finditer(r"import\s*\{([^}]+)\}\s*from", code):
            parts = match.group(1).split(",")
            for part in parts:
                # Handle "foo as bar" - we want "bar"
                if " as " in part:
                    name = part.split(" as ")[-1].strip()
                else:
                    name = part.strip()
                if name:
                    imported_names.add(name)

        # Default imports: import foo from 'module'
        for match in re.finditer(r"import\s+([a-z_$][a-z0-9_$]*)\s+from", code, re.IGNORECASE):
            imported_names.add(match.group(1))

        # Namespace imports: import * as foo from 'module'
        for match in re.finditer(r"import\s+\*\s+as\s+([a-z_$][a-z0-9_$]*)", code, re.IGNORECASE):
            imported_names.add(match.group(1))

        if not imported_names:
            return names

        # Remove import statements and check if imported names are used
        code_without_imports = re.sub(r"^import\s+.*?[;\n]", " ", code, flags=re.MULTILINE)

        used_names = {
            name
            for name in imported_names
            if re.search(rf"\b{re.escape(name)}\b", code_without_imports)
        }

        return [name for name in names if name not in imported_names or name in used_names]

    def _filter_java_imports(self, code: str, names: list[str]) -> list[str]:
        """Filter Java imports."""
        imported_names = set()

        # import com.example.ClassName;
        for match in re.finditer(r"^import\s+(?:static\s+)?[\w.]+\.(\w+)\s*;", code, re.MULTILINE):
            imported_names.add(match.group(1))

        if not imported_names:
            return names

        code_without_imports = re.sub(r"^import\s+.*?;", " ", code, flags=re.MULTILINE)

        used_names = {
            name
            for name in imported_names
            if re.search(rf"\b{re.escape(name)}\b", code_without_imports)
        }

        return [name for name in names if name not in imported_names or name in used_names]

    def _filter_go_imports(self, code: str, names: list[str]) -> list[str]:
        """Filter Go imports."""
        imported_names = set()

        # import "package/name" - extract last part
        for match in re.finditer(r'import\s+"[\w/]+/(\w+)"', code):
            imported_names.add(match.group(1))

        # import alias "package"
        for match in re.finditer(r'import\s+(\w+)\s+"[\w/]+"', code):
            imported_names.add(match.group(1))

        if not imported_names:
            return names

        code_without_imports = re.sub(r'import\s+(?:\w+\s+)?"[\w/]+"', " ", code)
        code_without_imports = re.sub(r"import\s*\([^)]+\)", " ", code_without_imports)

        used_names = {
            name
            for name in imported_names
            if re.search(rf"\b{re.escape(name)}\b", code_without_imports)
        }

        return [name for name in names if name not in imported_names or name in used_names]

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
