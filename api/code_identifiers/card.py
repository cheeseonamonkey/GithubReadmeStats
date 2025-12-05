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
    strip_patterns: Sequence[re.Pattern[str]]  # Remove before extraction
    identifier_patterns: Sequence[re.Pattern[str]]  # Extract from these only
    keywords: frozenset[str]


# Common patterns to strip
STRIP_COMMENTS = [
    re.compile(r'/\*.*?\*/', re.DOTALL),
    re.compile(r'//.*?$', re.MULTILINE),
    re.compile(r'#.*?$', re.MULTILINE),
]
STRIP_STRINGS = [
    re.compile(r'"""[\s\S]*?"""'),
    re.compile(r"'''[\s\S]*?'''"),
    re.compile(r'"(?:[^"\\]|\\.)*"'),
    re.compile(r"'(?:[^'\\]|\\.)*'"),
    re.compile(r'`(?:[^`\\]|\\.)*`'),
]
STRIP_ANNOTATIONS = [re.compile(r'^\s*@\w+.*$', re.MULTILINE)]


LANGUAGE_CONFIGS: Sequence[LanguageConfig] = (
    LanguageConfig(
        key="python",
        display_name="Python",
        color="#3572A5",
        extensions=(".py",),
        strip_patterns=(
            *STRIP_STRINGS, *STRIP_COMMENTS,
            re.compile(r'^(?:from|import)\s+.*$', re.MULTILINE),
        ),
        identifier_patterns=(
            re.compile(r'^\s*def\s+([a-z_][a-z0-9_]*)\s*\(', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*async\s+def\s+([a-z_][a-z0-9_]*)\s*\(', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*class\s+([a-z_][a-z0-9_]*)', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^[ \t]*([a-z_][a-z0-9_]*)\s*=', re.MULTILINE),
            re.compile(r'\bself\.([a-z_][a-z0-9_]*)\s*=', re.IGNORECASE),
        ),
        keywords=frozenset({
            "and", "as", "assert", "async", "await", "break", "class", "continue",
            "def", "del", "elif", "else", "except", "finally", "for", "from",
            "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
            "or", "pass", "raise", "return", "try", "while", "with", "yield",
            "true", "false", "none", "self", "cls",
        }),
    ),
    LanguageConfig(
        key="javascript",
        display_name="JavaScript",
        color="#f1e05a",
        extensions=(".js", ".jsx"),
        strip_patterns=(
            *STRIP_STRINGS, *STRIP_COMMENTS,
            re.compile(r'^import\s+.*?[;\n]', re.MULTILINE),
            re.compile(r'^export\s+(?:default\s+)?(?=class|function)', re.MULTILINE),
        ),
        identifier_patterns=(
            re.compile(r'\b(?:const|let|var)\s+([a-z_$][a-z0-9_$]*)\s*=', re.IGNORECASE),
            re.compile(r'\bfunction\s+([a-z_$][a-z0-9_$]*)\s*\(', re.IGNORECASE),
            re.compile(r'\bclass\s+([a-z_$][a-z0-9_$]*)', re.IGNORECASE),
            re.compile(r'(?:^|[;{])\s*(?:async\s+)?([a-z_$][a-z0-9_$]*)\s*\([^)]*?\)\s*{', re.MULTILINE | re.IGNORECASE),
        ),
        keywords=frozenset({
            "break", "case", "catch", "class", "const", "continue", "debugger",
            "default", "delete", "do", "else", "export", "extends", "finally",
            "for", "function", "if", "import", "in", "instanceof", "let", "new",
            "return", "super", "switch", "this", "throw", "try", "typeof", "var",
            "void", "while", "with", "yield", "async", "await", "true", "false",
            "null", "undefined",
        }),
    ),
    LanguageConfig(
        key="typescript",
        display_name="TypeScript",
        color="#2b7489",
        extensions=(".ts", ".tsx"),
        strip_patterns=(
            *STRIP_STRINGS, *STRIP_COMMENTS,
            re.compile(r'^import\s+.*?[;\n]', re.MULTILINE),
            re.compile(r'^export\s+(?:default\s+)?(?=class|function|interface|type)', re.MULTILINE),
        ),
        identifier_patterns=(
            re.compile(r'\b(?:const|let|var)\s+([a-z_$][a-z0-9_$]*)\s*[=:]', re.IGNORECASE),
            re.compile(r'\bfunction\s+([a-z_$][a-z0-9_$]*)\s*[<(]', re.IGNORECASE),
            re.compile(r'\bclass\s+([a-z_$][a-z0-9_$]*)', re.IGNORECASE),
            re.compile(r'\b(?:interface|type|enum)\s+([a-z_$][a-z0-9_$]*)', re.IGNORECASE),
            re.compile(r'(?:^|[;{])\s*(?:public\s+|private\s+|protected\s+)?(?:async\s+)?([a-z_$][a-z0-9_$]*)\s*\([^)]*?\)\s*{', re.MULTILINE | re.IGNORECASE),
        ),
        keywords=frozenset({
            "abstract", "any", "as", "async", "await", "boolean", "break", "case",
            "catch", "class", "const", "constructor", "continue", "declare", "default",
            "delete", "do", "else", "enum", "export", "extends", "false", "finally",
            "for", "from", "function", "if", "implements", "import", "in", "interface",
            "is", "keyof", "let", "module", "namespace", "new", "null", "number",
            "object", "of", "private", "protected", "public", "readonly", "return",
            "static", "string", "super", "switch", "this", "throw", "true", "try",
            "type", "typeof", "undefined", "var", "void", "while", "with", "yield",
        }),
    ),
    LanguageConfig(
        key="java",
        display_name="Java",
        color="#b07219",
        extensions=(".java",),
        strip_patterns=(
            *STRIP_STRINGS, *STRIP_COMMENTS, *STRIP_ANNOTATIONS,
            re.compile(r'^import\s+.*?;', re.MULTILINE),
            re.compile(r'^package\s+.*?;', re.MULTILINE),
        ),
        identifier_patterns=(
            re.compile(r'\bclass\s+([A-Za-z_][A-Za-z0-9_]*)'),
            re.compile(r'\b(?:interface|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)'),
            re.compile(r'\b([A-Za-z_][\w<>\[\]]*?)\s+([a-z_][a-z0-9_]*)\s*\(', re.IGNORECASE),
            re.compile(r'\b([A-Za-z_][\w<>\[\]]*?)\s+([a-z_][a-z0-9_]*)\s*[=;]', re.IGNORECASE),
        ),
        keywords=frozenset({
            "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
            "class", "continue", "default", "do", "double", "else", "enum", "extends",
            "final", "finally", "float", "for", "if", "implements", "import",
            "instanceof", "int", "interface", "long", "native", "new", "null",
            "package", "private", "protected", "public", "return", "short", "static",
            "super", "switch", "synchronized", "this", "throw", "throws", "transient",
            "try", "void", "volatile", "while", "var", "string", "true", "false",
        }),
    ),
    LanguageConfig(
        key="kotlin",
        display_name="Kotlin",
        color="#A97BFF",
        extensions=(".kt", ".kts"),
        strip_patterns=(
            *STRIP_STRINGS, *STRIP_COMMENTS, *STRIP_ANNOTATIONS,
            re.compile(r'^import\s+.*$', re.MULTILINE),
            re.compile(r'^package\s+.*$', re.MULTILINE),
        ),
        identifier_patterns=(
            re.compile(r'\bfun\s+([a-z_][a-z0-9_]*)\s*[<(]', re.IGNORECASE),
            re.compile(r'\b(?:val|var)\s+([a-z_][a-z0-9_]*)'),
            re.compile(r'\b(?:class|object|interface)\s+([A-Za-z_][A-Za-z0-9_]*)'),
        ),
        keywords=frozenset({
            "as", "break", "by", "class", "companion", "const", "constructor",
            "continue", "do", "else", "enum", "false", "for", "fun", "if", "import",
            "in", "interface", "is", "null", "object", "package", "private",
            "protected", "public", "return", "sealed", "super", "this", "throw",
            "true", "try", "typealias", "val", "var", "when", "while",
        }),
    ),
    LanguageConfig(
        key="csharp",
        display_name="C#",
        color="#178600",
        extensions=(".cs",),
        strip_patterns=(
            *STRIP_STRINGS, *STRIP_COMMENTS, *STRIP_ANNOTATIONS,
            re.compile(r'^using\s+.*?;', re.MULTILINE),
            re.compile(r'^namespace\s+.*$', re.MULTILINE),
        ),
        identifier_patterns=(
            re.compile(r'\b(?:class|struct|record|interface)\s+([A-Za-z_][A-Za-z0-9_]*)'),
            re.compile(r'\b([A-Za-z_][\w<>\[\],?]*)\s+([a-z_][a-z0-9_]*)\s*\(', re.IGNORECASE),
            re.compile(r'\b([A-Za-z_][\w<>\[\],?]*)\s+([a-z_][a-z0-9_]*)\s*[=;]', re.IGNORECASE),
            re.compile(r'\b([A-Za-z_][\w<>\[\],?]*)\s+([A-Z][A-Za-z0-9_]*)\s*{\s*get', re.IGNORECASE),
        ),
        keywords=frozenset({
            "abstract", "as", "base", "bool", "break", "byte", "case", "catch",
            "char", "class", "const", "continue", "decimal", "default", "delegate",
            "do", "double", "else", "enum", "event", "explicit", "extern", "false",
            "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit",
            "in", "int", "interface", "internal", "is", "lock", "long", "namespace",
            "new", "null", "object", "operator", "out", "override", "params",
            "private", "protected", "public", "readonly", "ref", "return", "sbyte",
            "sealed", "short", "sizeof", "static", "string", "struct", "switch",
            "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked",
            "unsafe", "ushort", "using", "var", "virtual", "void", "volatile", "while",
        }),
    ),
    LanguageConfig(
        key="go",
        display_name="Go",
        color="#00ADD8",
        extensions=(".go",),
        strip_patterns=(
            *STRIP_STRINGS, *STRIP_COMMENTS,
            re.compile(r'^import\s+(?:\([\s\S]*?\)|".*?")', re.MULTILINE),
            re.compile(r'^package\s+\w+', re.MULTILINE),
        ),
        identifier_patterns=(
            re.compile(r'\bfunc\s+(?:\([^)]+\)\s*)?([a-z_][a-z0-9_]*)\s*\(', re.IGNORECASE),
            re.compile(r'\b(?:var|const)\s+([a-z_][a-z0-9_]*)'),
            re.compile(r'([a-z_][a-z0-9_]*)\s*:='),
            re.compile(r'^\s*type\s+([A-Z][A-Za-z0-9_]*)', re.MULTILINE),
        ),
        keywords=frozenset({
            "break", "case", "chan", "const", "continue", "default", "defer", "else",
            "fallthrough", "for", "func", "go", "goto", "if", "import", "interface",
            "map", "package", "range", "return", "select", "struct", "switch", "type",
            "var", "nil", "true", "false", "err",
        }),
    ),
    LanguageConfig(
        key="ruby",
        display_name="Ruby",
        color="#701516",
        extensions=(".rb",),
        strip_patterns=(*STRIP_STRINGS, *STRIP_COMMENTS,),
        identifier_patterns=(
            re.compile(r'^\s*def\s+([a-z_][a-z0-9_!?]*)', re.MULTILINE),
            re.compile(r'@([a-z_][a-z0-9_]*)'),
            re.compile(r'^\s*(?:class|module)\s+([A-Z][A-Za-z0-9_:]*)', re.MULTILINE),
        ),
        keywords=frozenset({
            "alias", "and", "begin", "break", "case", "class", "def", "do", "else",
            "elsif", "end", "ensure", "false", "for", "if", "in", "module", "next",
            "nil", "not", "or", "redo", "rescue", "retry", "return", "self", "super",
            "then", "true", "undef", "unless", "until", "when", "while", "yield",
        }),
    ),
    LanguageConfig(
        key="php",
        display_name="PHP",
        color="#4F5D95",
        extensions=(".php",),
        strip_patterns=(
            *STRIP_STRINGS, *STRIP_COMMENTS,
            re.compile(r'^use\s+.*?;', re.MULTILINE),
            re.compile(r'^namespace\s+.*?;', re.MULTILINE),
        ),
        identifier_patterns=(
            re.compile(r'\bfunction\s+([a-z_][a-z0-9_]*)\s*\(', re.IGNORECASE),
            re.compile(r'\$([a-z_][a-z0-9_]*)'),
            re.compile(r'^\s*(?:class|interface|trait)\s+([A-Za-z_][A-Za-z0-9_]*)', re.MULTILINE),
        ),
        keywords=frozenset({
            "abstract", "and", "array", "as", "break", "callable", "case", "catch",
            "class", "clone", "const", "continue", "declare", "default", "die", "do",
            "echo", "else", "elseif", "empty", "endfor", "endforeach", "endif",
            "endswitch", "endwhile", "eval", "exit", "extends", "final", "finally",
            "for", "foreach", "function", "global", "goto", "if", "implements",
            "include", "instanceof", "insteadof", "interface", "isset", "list",
            "namespace", "new", "or", "print", "private", "protected", "public",
            "require", "return", "static", "switch", "throw", "trait", "try", "unset",
            "use", "var", "while", "xor", "yield", "this", "self",
        }),
    ),
    LanguageConfig(
        key="swift",
        display_name="Swift",
        color="#F05138",
        extensions=(".swift",),
        strip_patterns=(
            *STRIP_STRINGS, *STRIP_COMMENTS, *STRIP_ANNOTATIONS,
            re.compile(r'^import\s+\w+', re.MULTILINE),
        ),
        identifier_patterns=(
            re.compile(r'\bfunc\s+([a-z_][a-z0-9_]*)\s*[<(]', re.IGNORECASE),
            re.compile(r'\b(?:let|var)\s+([a-z_][a-z0-9_]*)'),
            re.compile(r'^\s*(?:class|struct|enum|protocol)\s+([A-Za-z_][A-Za-z0-9_]*)', re.MULTILINE),
        ),
        keywords=frozenset({
            "as", "break", "case", "catch", "class", "continue", "defer", "deinit",
            "do", "else", "enum", "extension", "fallthrough", "false", "for", "func",
            "guard", "if", "import", "in", "init", "inout", "internal", "let", "nil",
            "open", "operator", "private", "protocol", "public", "repeat", "return",
            "self", "static", "struct", "subscript", "switch", "throw", "throws",
            "true", "try", "typealias", "var", "where", "while",
        }),
    ),
)

EXTENSION_TO_LANG = {ext: cfg.key for cfg in LANGUAGE_CONFIGS for ext in cfg.extensions}
LANGUAGE_COLORS = {cfg.key: cfg.color for cfg in LANGUAGE_CONFIGS}
LANGUAGE_NAMES = {cfg.key: cfg.display_name for cfg in LANGUAGE_CONFIGS}
LANG_MAP = {cfg.key: cfg for cfg in LANGUAGE_CONFIGS}

SKIP_PATH_PARTS = frozenset({
    "__pycache__", "node_modules", "dist", "build", "vendor", "coverage",
    "site-packages", ".git", "out", "target", "bin", "obj", "packages",
    "test", "tests", "__tests__", "fixtures", "mocks", "spec",
})


class CodeIdentifiersCard(GitHubCardBase):
    MAX_WORKERS = 8

    def __init__(self, username: str, query_params: dict, width: int = 400, header_height: int = 40):
        super().__init__(username, query_params)
        self.card_width = width
        self.header_height = header_height
        self.file_timeout = 3

    def _extract(self, code: str, lang_key: str) -> List[str]:
        config = LANG_MAP.get(lang_key)
        if not config:
            return []
        # Strip noise first
        for pattern in config.strip_patterns:
            code = pattern.sub(' ', code)
        # Extract only from declaration patterns
        names = [
            name
            for name in self._iter_identifier_matches(config.identifier_patterns, code)
            if 2 < len(name) < 30 and name.lower() not in config.keywords
        ]
        return names

    def _should_skip(self, path: str) -> bool:
        return any(p.lower() in SKIP_PATH_PARTS for p in path.split("/"))

    @staticmethod
    def _iter_identifier_matches(patterns: Iterable[re.Pattern[str]], code: str) -> Iterable[str]:
        for pattern in patterns:
            for match in pattern.findall(code):
                yield match[-1] if isinstance(match, tuple) else match

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
                return EXTENSION_TO_LANG[ext], resp.read().decode("utf-8", errors="ignore")

        def fetch_repo(repo: str):
            results, files_scanned, lang_counts = [], 0, CounterType()
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
                    futures = {file_ex.submit(fetch_file, repo, path, ext): ext for path, ext in files}
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

        scored = [
            {"name": n, "count": sum(lc.values()), "lang": lc.most_common(1)[0][0]}
            for n, lc in id_langs.items()
        ]
        scored.sort(key=lambda x: x["count"], reverse=True)
        return {
            "items": scored[:10],
            "language_files": lang_file_counts,
            "repo_count": len(repo_names),
            "file_count": total_files,
        }

    def _fetch_all_repos(self):
        page, repos = 1, []
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

    def process(self):
        if not self.user:
            return self._render_error("Missing ?username= parameter")
        try:
            data = self.fetch_data()
            body, height = self.render_body(data)
            return self._render_frame(f"{self.user}'s Top Identifiers", body, height)
        except Exception:
            import traceback
            return self._render_error(traceback.format_exc())

    def render_body(self, stats):
        items = stats.get("items", [])
        language_counts = stats.get("language_files", CounterType())
        repo_count = stats.get("repo_count", 0)
        file_count = stats.get("file_count", 0)

        bar_h, row_h, bar_w = 12, 20, 200
        svg = []

        if not items:
            svg.append(f'<text x="{self.padding}" y="20" class="stat-value">No identifiers found.</text>')
            body_height = 40
        else:
            max_count = max(s["count"] for s in items)
            for i, item in enumerate(items):
                y = 10 + i * row_h
                w = (item["count"] / max_count) * bar_w
                color = LANGUAGE_COLORS.get(item["lang"], "#58a6ff")
                svg.append(f'''
                    <g transform="translate({self.padding},{y})">
                        <text x="0" y="{bar_h-2}" class="stat-name">{escape_xml(item['name'])}</text>
                        <rect x="110" y="0" width="{bar_w}" height="{bar_h}" rx="3" fill="#21262d"/>
                        <rect x="110" y="0" width="{max(w,2):.2f}" height="{bar_h}" rx="3" fill="{color}"/>
                        <text x="{110+bar_w+10}" y="{bar_h-2}" class="stat-value">{item['count']}</text>
                    </g>''')
            body_height = len(items) * row_h + 10

        legend_svg, legend_height = self._render_legend(language_counts, y_offset=body_height + 10)
        svg.append(legend_svg)

        meta_y = body_height + legend_height + 25
        svg.append(f'<text x="{self.padding}" y="{meta_y}" class="stat-value">{repo_count} repos • {file_count} files scanned</text>')
        return "\n".join(svg), meta_y + 10

    def _render_legend(self, language_counts: CounterType[str], y_offset: int):
        if not language_counts:
            return "", 0
        items = language_counts.most_common()
        col_width, items_per_row = 140, max(1, (self.card_width - 2 * self.padding) // 140)
        rows = (len(items) + items_per_row - 1) // items_per_row
        svg_parts = [f'<text x="{self.padding}" y="{y_offset}" class="stat-name">Legend</text>']

        for idx, (lang_key, count) in enumerate(items):
            x = self.padding + (idx % items_per_row) * col_width
            y = y_offset + 12 + (idx // items_per_row) * 18
            color = LANGUAGE_COLORS.get(lang_key, "#58a6ff")
            svg_parts.append(f'''
                <g transform="translate({x},{y})">
                    <rect x="0" y="-10" width="12" height="12" rx="2" fill="{color}"/>
                    <text x="18" y="0" class="stat-value">{escape_xml(LANGUAGE_NAMES.get(lang_key, lang_key))} ({count})</text>
                </g>''')
        return "\n".join(svg_parts), rows * 18 + 18


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
