# code_identifiers/card.py

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Counter as CounterType, Iterable, List, Sequence
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler
import urllib.request

from ..github_base import GitHubCardBase, HEADERS, escape_xml


@dataclass(frozen=True)
class LanguageConfig:
    key: str
    display_name: str
    color: str
    extensions: Sequence[str]
    identifier_patterns: Sequence[re.Pattern[str]]
    keywords: frozenset[str]


class IdentifierExtractor:
    IDENTIFIER_RE = re.compile(r"\b[_A-Za-z][_A-Za-z0-9]{1,39}\b")

    def __init__(self, language_configs: Sequence[LanguageConfig]):
        self._languages = {cfg.key: cfg for cfg in language_configs}

    def extract(self, code: str, lang_key: str) -> List[str]:
        config = self._languages.get(lang_key)
        if not config:
            return []

        names: List[str] = []
        for pattern in config.identifier_patterns:
            names.extend(self._normalize_matches(pattern.findall(code)))

        names.extend(self.IDENTIFIER_RE.findall(code))
        return [name for name in names if self._is_identifier(name, config)]

    @staticmethod
    def _normalize_matches(matches: Iterable[object]) -> List[str]:
        normalized = []
        for item in matches:
            if isinstance(item, tuple):
                normalized.append(str(item[-1]))
            else:
                normalized.append(str(item))
        return normalized

    def _is_identifier(self, name: str, config: LanguageConfig) -> bool:
        if not (2 < len(name) < 40):
            return False
        if name.isupper():
            return False

        lowered = name.lower()
        return lowered not in GLOBAL_SKIP and lowered not in config.keywords


LANGUAGE_CONFIGS: Sequence[LanguageConfig] = (
    LanguageConfig(
        key="python",
        display_name="Python",
        color="#3572A5",
        extensions=(".py",),
        identifier_patterns=(
            re.compile(r"^\s*def\s+([a-z_][a-zA-Z0-9_]*)\s*\(", re.MULTILINE),
            re.compile(r"^[ \t]*([a-z_][a-zA-Z0-9_]*)\s*(?::\s*\w+)?\s*=", re.MULTILINE),
        ),
        keywords=frozenset(
            {
                "and",
                "as",
                "assert",
                "break",
                "class",
                "continue",
                "def",
                "del",
                "elif",
                "else",
                "except",
                "finally",
                "for",
                "from",
                "global",
                "if",
                "import",
                "in",
                "is",
                "lambda",
                "len",
                "list",
                "nonlocal",
                "not",
                "or",
                "pass",
                "print",
                "raise",
                "range",
                "return",
                "set",
                "try",
                "while",
                "with",
                "yield",
                "dict",
                "tuple",
            }
        ),
    ),
    LanguageConfig(
        key="javascript",
        display_name="JavaScript",
        color="#f1e05a",
        extensions=(".js", ".jsx"),
        identifier_patterns=(
            re.compile(r"\b(?:const|let|var)\s+([a-z_$][a-zA-Z0-9_$]*)\s*[=;]"),
            re.compile(r"\bfunction\s+([a-zA-Z_$][\w$]*)\s*\("),
        ),
        keywords=frozenset(
            {
                "break",
                "case",
                "catch",
                "class",
                "const",
                "continue",
                "debugger",
                "default",
                "delete",
                "do",
                "else",
                "export",
                "extends",
                "finally",
                "for",
                "function",
                "if",
                "import",
                "in",
                "instanceof",
                "let",
                "new",
                "return",
                "super",
                "switch",
                "this",
                "throw",
                "try",
                "typeof",
                "var",
                "void",
                "while",
                "with",
                "yield",
                "date",
                "math",
                "promise",
                "object",
                "string",
                "number",
                "array",
                "boolean",
                "error",
                "set",
                "map",
                "now",
            }
        ),
    ),
    LanguageConfig(
        key="typescript",
        display_name="TypeScript",
        color="#2b7489",
        extensions=(".ts", ".tsx"),
        identifier_patterns=(
            re.compile(r"\b(?:const|let|var)\s+([a-z_$][a-zA-Z0-9_$]*)\s*[=;:]"),
            re.compile(r"\bfunction\s+([a-zA-Z_$][\w$]*)\s*\("),
        ),
        keywords=frozenset(
            {
                "abstract",
                "any",
                "as",
                "asserts",
                "async",
                "await",
                "boolean",
                "break",
                "case",
                "catch",
                "class",
                "const",
                "constructor",
                "continue",
                "declare",
                "default",
                "delete",
                "do",
                "else",
                "enum",
                "export",
                "extends",
                "false",
                "finally",
                "for",
                "from",
                "function",
                "get",
                "if",
                "implements",
                "import",
                "in",
                "infer",
                "instanceof",
                "interface",
                "is",
                "keyof",
                "let",
                "module",
                "namespace",
                "new",
                "null",
                "number",
                "object",
                "of",
                "package",
                "private",
                "protected",
                "public",
                "readonly",
                "require",
                "return",
                "set",
                "static",
                "string",
                "super",
                "switch",
                "symbol",
                "this",
                "throw",
                "true",
                "try",
                "type",
                "typeof",
                "undefined",
                "unique",
                "unknown",
                "var",
                "void",
                "while",
                "with",
                "yield",
                "date",
                "math",
                "promise",
                "object",
                "string",
                "number",
                "array",
                "boolean",
                "error",
                "set",
                "map",
                "now",
            }
        ),
    ),
    LanguageConfig(
        key="java",
        display_name="Java",
        color="#b07219",
        extensions=(".java",),
        identifier_patterns=(
            re.compile(
                r"\b(?:public|private|protected|static|final|abstract|sealed|synchronized|native|\s)+(?:[A-Za-z_][\w<>\[\]]*\s+)+([a-z_][A-Za-z0-9_]*)\s*\("
            ),
            re.compile(r"\b(?:final\s+)?(?:[A-Za-z_][\w<>\[\]]*)\s+([a-z_][A-Za-z0-9_]*)\s*(?:=|;)"),
        ),
        keywords=frozenset(
            {
                "abstract",
                "assert",
                "boolean",
                "break",
                "byte",
                "case",
                "catch",
                "char",
                "class",
                "continue",
                "default",
                "do",
                "double",
                "else",
                "enum",
                "extends",
                "final",
                "finally",
                "float",
                "for",
                "if",
                "implements",
                "import",
                "instanceof",
                "int",
                "interface",
                "long",
                "native",
                "new",
                "null",
                "package",
                "private",
                "protected",
                "public",
                "return",
                "short",
                "static",
                "strictfp",
                "super",
                "switch",
                "synchronized",
                "this",
                "throw",
                "throws",
                "transient",
                "try",
                "void",
                "volatile",
                "while",
            }
        ),
    ),
    LanguageConfig(
        key="kotlin",
        display_name="Kotlin",
        color="#A97BFF",
        extensions=(".kt", ".kts"),
        identifier_patterns=(
            re.compile(r"\bfun\s+([a-zA-Z_][\w]*)\s*\("),
            re.compile(r"\b(?:val|var)\s+([a-zA-Z_][\w]*)"),
        ),
        keywords=frozenset(
            {
                "as",
                "break",
                "by",
                "class",
                "companion",
                "const",
                "constructor",
                "continue",
                "do",
                "else",
                "enum",
                "false",
                "for",
                "fun",
                "if",
                "import",
                "in",
                "interface",
                "is",
                "null",
                "object",
                "package",
                "private",
                "protected",
                "public",
                "return",
                "sealed",
                "super",
                "this",
                "throw",
                "true",
                "try",
                "typealias",
                "val",
                "var",
                "when",
                "while",
            }
        ),
    ),
    LanguageConfig(
        key="c#",
        display_name="C#",
        color="#178600",
        extensions=(".cs",),
        identifier_patterns=(
            re.compile(r"\b(?:public|private|protected|internal|static|readonly|sealed|async|virtual|override|partial|new|const|unsafe)\s+(?:[A-Za-z_][\w<>\[\],?]*\s+)+([a-z_][A-Za-z0-9_]*)\s*\("),
            re.compile(r"\b(?:var|dynamic|[A-Za-z_][\w<>\[\],?]*)\s+([a-z_][A-Za-z0-9_]*)\s*(?:=|;)"),
        ),
        keywords=frozenset(
            {
                "abstract",
                "as",
                "base",
                "bool",
                "break",
                "byte",
                "case",
                "catch",
                "char",
                "checked",
                "class",
                "const",
                "continue",
                "decimal",
                "default",
                "delegate",
                "do",
                "double",
                "else",
                "enum",
                "event",
                "explicit",
                "extern",
                "false",
                "finally",
                "fixed",
                "float",
                "for",
                "foreach",
                "goto",
                "if",
                "implicit",
                "in",
                "int",
                "interface",
                "internal",
                "is",
                "lock",
                "long",
                "namespace",
                "new",
                "null",
                "object",
                "operator",
                "out",
                "override",
                "params",
                "private",
                "protected",
                "public",
                "readonly",
                "ref",
                "return",
                "sbyte",
                "sealed",
                "short",
                "sizeof",
                "stackalloc",
                "static",
                "string",
                "struct",
                "switch",
                "this",
                "throw",
                "true",
                "try",
                "typeof",
                "uint",
                "ulong",
                "unchecked",
                "unsafe",
                "ushort",
                "using",
                "virtual",
                "void",
                "volatile",
                "while",
            }
        ),
    ),
    LanguageConfig(
        key="go",
        display_name="Go",
        color="#00ADD8",
        extensions=(".go",),
        identifier_patterns=(
            re.compile(r"\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
            re.compile(r"\b(?:var|const)\s+([a-z_][A-Za-z0-9_]*)"),
        ),
        keywords=frozenset(
            {
                "break",
                "case",
                "chan",
                "const",
                "continue",
                "default",
                "defer",
                "else",
                "fallthrough",
                "for",
                "func",
                "go",
                "goto",
                "if",
                "import",
                "interface",
                "map",
                "package",
                "range",
                "return",
                "select",
                "struct",
                "switch",
                "type",
                "var",
            }
        ),
    ),
    LanguageConfig(
        key="c++",
        display_name="C++",
        color="#f34b7d",
        extensions=(".cpp", ".cc", ".hpp"),
        identifier_patterns=(
            re.compile(r"\b(?:int|float|double|char|bool|auto|long|short|unsigned|std::\w+)\s+([a-z_][A-Za-z0-9_]*)\s*(?:=|;)", re.MULTILINE),
            re.compile(r"\b([a-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{"),
        ),
        keywords=frozenset(
            {
                "alignas",
                "alignof",
                "and",
                "asm",
                "auto",
                "bitand",
                "bitor",
                "bool",
                "break",
                "case",
                "catch",
                "char",
                "class",
                "compl",
                "const",
                "constexpr",
                "continue",
                "decltype",
                "default",
                "delete",
                "do",
                "double",
                "dynamic_cast",
                "else",
                "enum",
                "explicit",
                "export",
                "extern",
                "false",
                "float",
                "for",
                "friend",
                "goto",
                "if",
                "inline",
                "int",
                "long",
                "mutable",
                "namespace",
                "new",
                "noexcept",
                "not",
                "nullptr",
                "operator",
                "or",
                "private",
                "protected",
                "public",
                "register",
                "reinterpret_cast",
                "return",
                "short",
                "signed",
                "sizeof",
                "static",
                "static_cast",
                "struct",
                "switch",
                "template",
                "this",
                "throw",
                "true",
                "try",
                "typedef",
                "typeid",
                "typename",
                "union",
                "unsigned",
                "using",
                "virtual",
                "void",
                "volatile",
                "wchar_t",
                "while",
                "xor",
            }
        ),
    ),
    LanguageConfig(
        key="c",
        display_name="C",
        color="#555555",
        extensions=(".c", ".h"),
        identifier_patterns=(
            re.compile(r"\b(?:int|float|double|char|bool|long|short|unsigned|struct\s+\w+)\s+([a-z_][A-Za-z0-9_]*)\s*(?:=|;)", re.MULTILINE),
            re.compile(r"\b([a-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{"),
        ),
        keywords=frozenset(
            {
                "auto",
                "break",
                "case",
                "char",
                "const",
                "continue",
                "default",
                "do",
                "double",
                "else",
                "enum",
                "extern",
                "float",
                "for",
                "goto",
                "if",
                "inline",
                "int",
                "long",
                "register",
                "return",
                "short",
                "signed",
                "sizeof",
                "static",
                "struct",
                "switch",
                "typedef",
                "union",
                "unsigned",
                "void",
                "volatile",
                "while",
            }
        ),
    ),
    LanguageConfig(
        key="ruby",
        display_name="Ruby",
        color="#701516",
        extensions=(".rb",),
        identifier_patterns=(
            re.compile(r"^\s*def\s+([a-zA-Z_][\w]*)", re.MULTILINE),
            re.compile(r"@([a-zA-Z_][\w]*)"),
        ),
        keywords=frozenset(
            {
                "__FILE__",
                "__LINE__",
                "BEGIN",
                "END",
                "alias",
                "and",
                "begin",
                "break",
                "case",
                "class",
                "def",
                "defined?",
                "do",
                "else",
                "elsif",
                "end",
                "ensure",
                "false",
                "for",
                "if",
                "in",
                "module",
                "next",
                "nil",
                "not",
                "or",
                "redo",
                "rescue",
                "retry",
                "return",
                "self",
                "super",
                "then",
                "true",
                "undef",
                "unless",
                "until",
                "when",
                "while",
                "yield",
            }
        ),
    ),
    LanguageConfig(
        key="php",
        display_name="PHP",
        color="#4F5D95",
        extensions=(".php",),
        identifier_patterns=(
            re.compile(r"\bfunction\s+([a-zA-Z_][\w]*)\s*\("),
            re.compile(r"\$([a-zA-Z_][\w]*)"),
        ),
        keywords=frozenset(
            {
                "abstract",
                "and",
                "array",
                "as",
                "break",
                "callable",
                "case",
                "catch",
                "class",
                "clone",
                "const",
                "continue",
                "declare",
                "default",
                "die",
                "do",
                "echo",
                "else",
                "elseif",
                "empty",
                "endfor",
                "endforeach",
                "endif",
                "endswitch",
                "endwhile",
                "eval",
                "exit",
                "extends",
                "final",
                "finally",
                "for",
                "foreach",
                "function",
                "global",
                "goto",
                "if",
                "implements",
                "include",
                "include_once",
                "instanceof",
                "insteadof",
                "interface",
                "isset",
                "list",
                "namespace",
                "new",
                "or",
                "print",
                "private",
                "protected",
                "public",
                "require",
                "require_once",
                "return",
                "static",
                "switch",
                "throw",
                "trait",
                "try",
                "unset",
                "use",
                "var",
                "while",
                "xor",
                "yield",
            }
        ),
    ),
    LanguageConfig(
        key="swift",
        display_name="Swift",
        color="#F05138",
        extensions=(".swift",),
        identifier_patterns=(
            re.compile(r"\bfunc\s+([a-zA-Z_][\w]*)\s*\("),
            re.compile(r"\b(?:let|var)\s+([a-zA-Z_][\w]*)"),
        ),
        keywords=frozenset(
            {
                "as",
                "associatedtype",
                "break",
                "case",
                "catch",
                "class",
                "continue",
                "defer",
                "deinit",
                "do",
                "else",
                "enum",
                "extension",
                "fallthrough",
                "false",
                "for",
                "func",
                "guard",
                "if",
                "import",
                "in",
                "init",
                "inout",
                "internal",
                "let",
                "nil",
                "open",
                "operator",
                "private",
                "protocol",
                "public",
                "repeat",
                "return",
                "self",
                "static",
                "struct",
                "subscript",
                "switch",
                "throw",
                "throws",
                "true",
                "try",
                "typealias",
                "var",
                "where",
                "while",
                "associatedtype",
            }
        ),
    ),
)

EXTENSION_TO_LANG = {
    ext: cfg.key for cfg in LANGUAGE_CONFIGS for ext in cfg.extensions
}
LANGUAGE_COLORS = {cfg.key: cfg.color for cfg in LANGUAGE_CONFIGS}
LANGUAGE_NAMES = {cfg.key: cfg.display_name for cfg in LANGUAGE_CONFIGS}

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
    }
)

GLOBAL_SKIP = frozenset(
    {
        "i",
        "j",
        "k",
        "x",
        "y",
        "z",
        "e",
        "t",
        "a",
        "b",
        "c",
        "d",
        "f",
        "g",
        "h",
        "id",
        "el",
        "err",
        "fn",
        "cb",
        "fs",
        "os",
        "db",
        "api",
        "app",
        "env",
        "ctx",
        "req",
        "res",
        "self",
        "cls",
        "args",
        "kwargs",
        "this",
        "true",
        "false",
        "null",
        "none",
        "undefined",
        "console",
        "module",
        "exports",
        "main",
        "init",
    }
)


class CodeIdentifiersCard(GitHubCardBase):
    MAX_WORKERS = 8

    def __init__(self, username: str, query_params: dict, width: int = 400, header_height: int = 40):
        super().__init__(username, query_params)
        self.card_width = width
        self.header_height = header_height
        self.file_timeout = 3
        self.extractor = IdentifierExtractor(LANGUAGE_CONFIGS)

    def fetch_data(self):
        repos = self._fetch_all_repos()
        repo_names = [r["name"] for r in repos if not r.get("fork")]

        id_langs: dict[str, CounterType[str]] = {}
        lang_file_counts: CounterType[str] = CounterType()
        total_files = 0

        def fetch_file(repo: str, path: str, ext: str):
            req = urllib.request.Request(
                f"https://raw.githubusercontent.com/{self.user}/{repo}/HEAD/{path}", headers=HEADERS
            )
            with urllib.request.urlopen(req, timeout=self.file_timeout) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
            lang_key = EXTENSION_TO_LANG[ext]
            return lang_key, content

        def fetch_repo(repo: str):
            results: list[tuple[str, str]] = []
            files_scanned = 0
            lang_counts: CounterType[str] = CounterType()
            try:
                tree = self._make_request(
                    f"https://api.github.com/repos/{self.user}/{repo}/git/trees/HEAD?recursive=1"
                )
                files = [
                    (f["path"], ext)
                    for f in tree.get("tree", [])
                    if f.get("type") == "blob" and f.get("size", 0) < 100000 and not self._should_skip(f.get("path", ""))
                    for ext in [next((e for e in EXTENSION_TO_LANG if f["path"].endswith(e)), None)]
                    if ext
                ]

                if not files:
                    return results, files_scanned, lang_counts

                with ThreadPoolExecutor(max_workers=min(6, len(files))) as file_ex:
                    futures = {file_ex.submit(fetch_file, repo, path, ext): (path, ext) for path, ext in files}
                    for future in as_completed(futures):
                        try:
                            lang_key, content = future.result()
                        except Exception:
                            continue
                        files_scanned += 1
                        lang_counts[lang_key] += 1
                        results.extend((name, lang_key) for name in self._extract(content, lang_key))
            except Exception:
                pass
            return results, files_scanned, lang_counts

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as ex:
            for future in as_completed([ex.submit(fetch_repo, r) for r in repo_names]):
                items, file_count, lang_counts = future.result()
                total_files += file_count
                lang_file_counts.update(lang_counts)
                for name, lang in items:
                    id_langs.setdefault(name, CounterType())[lang] += 1

        scored = []
        for name, lang_counts in id_langs.items():
            total = sum(lang_counts.values())
            dominant = lang_counts.most_common(1)[0][0]
            scored.append({"name": name, "count": total, "lang": dominant})

        scored.sort(key=lambda x: x["count"], reverse=True)
        return {
            "items": scored[:10],
            "language_files": lang_file_counts,
            "repo_count": len(repo_names),
            "file_count": total_files,
        }

    def _fetch_all_repos(self):
        page = 1
        repos = []
        while True:
            batch = self._make_request(
                f"https://api.github.com/users/{self.user}/repos?per_page=100&type=owner&sort=updated&page={page}"
            )
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return repos

    def _extract(self, code: str, lang_key: str):
        return self.extractor.extract(code, lang_key)

    def process(self):
        if not self.user:
            return self._render_error("Missing ?username= parameter")
        try:
            data = self.fetch_data()
            title = f"{self.user}'s Top Identifiers"
            body, height = self.render_body(data)
            return self._render_frame(title, body, height)
        except Exception:
            import traceback
            return self._render_error(traceback.format_exc())

    def render_body(self, stats):
        items = stats.get("items") if isinstance(stats, dict) else []
        language_counts = stats.get("language_files", CounterType()) if isinstance(stats, dict) else CounterType()
        repo_count = stats.get("repo_count", 0) if isinstance(stats, dict) else 0
        file_count = stats.get("file_count", 0) if isinstance(stats, dict) else 0

        bar_h, row_h, bar_w = 12, 20, 200
        svg: list[str] = []

        if not items:
            svg.append(f'<text x="{self.padding}" y="20" class="stat-value">No identifiers found.</text>')
            body_height = 40
        else:
            max_count = max(s["count"] for s in items)
            for i, item in enumerate(items):
                y = 10 + i * row_h
                w = (item["count"] / max_count) * bar_w
                color = self._color_for_lang(item["lang"])

                svg.append(
                    f"""
                    <g transform=\"translate({self.padding},{y})\">
                        <text x=\"0\" y=\"{bar_h-2}\" class=\"stat-name\">{escape_xml(item['name'])}</text>
                        <rect x=\"110\" y=\"0\" width=\"{bar_w}\" height=\"{bar_h}\" rx=\"3\" fill=\"#21262d\"/>
                        <rect x=\"110\" y=\"0\" width=\"{max(w,2):.2f}\" height=\"{bar_h}\" rx=\"3\" fill=\"{color}\"/>
                        <text x=\"{110+bar_w+10}\" y=\"{bar_h-2}\" class=\"stat-value\">{item['count']}</text>
                    </g>"""
                )

            body_height = len(items) * row_h + 10

        legend_svg, legend_height = self._render_legend(language_counts, y_offset=body_height + 10)
        svg.append(legend_svg)

        meta_y = body_height + legend_height + 25
        svg.append(
            f'<text x="{self.padding}" y="{meta_y}" class="stat-value">{repo_count} repos • {file_count} files scanned</text>'
        )

        total_height = meta_y + 10
        return "\n".join(svg), total_height

    def _color_for_lang(self, lang_key: str):
        return LANGUAGE_COLORS.get(lang_key, "#58a6ff")

    def _should_skip(self, path: str):
        parts = [p.lower() for p in path.split("/") if p]
        return any(part in SKIP_PATH_PARTS for part in parts)

    def _render_legend(self, language_counts: CounterType[str], y_offset: int):
        if not language_counts:
            return "", 0

        items = language_counts.most_common()
        col_width = 140
        items_per_row = max(1, (self.card_width - (2 * self.padding)) // col_width)
        rows = (len(items) + items_per_row - 1) // items_per_row
        svg_parts = [f'<text x="{self.padding}" y="{y_offset}" class="stat-name">Legend</text>']

        for idx, (lang_key, count) in enumerate(items):
            col = idx % items_per_row
            row = idx // items_per_row
            x = self.padding + (col * col_width)
            y = y_offset + 12 + row * 18
            color = self._color_for_lang(lang_key)
            lang_name = LANGUAGE_NAMES.get(lang_key, lang_key)
            svg_parts.append(
                f"""
                <g transform=\"translate({x},{y})\">
                    <rect x=\"0\" y=\"-10\" width=\"12\" height=\"12\" rx=\"2\" fill=\"{color}\" />
                    <text x=\"18\" y=\"0\" class=\"stat-value\">{escape_xml(lang_name)} ({count})</text>
                </g>"""
            )

        height = rows * 18 + 18
        return "\n".join(svg_parts), height


def _respond_with_card(handler: BaseHTTPRequestHandler):
    query = parse_qs(urlparse(handler.path).query) if "?" in handler.path else {}
    card = CodeIdentifiersCard(query.get("username", [""])[0], query)
    svg = card.process()
    handler.send_response(200)
    handler.send_header("Content-Type", "image/svg+xml; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache, max-age=0")
    handler.end_headers()
    handler.wfile.write(svg.encode())


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _respond_with_card(self)
