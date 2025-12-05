# code_identifiers/card.py

from __future__ import annotations

from ..github_base import GitHubCardBase, HEADERS, escape_xml
import urllib.request
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from collections import Counter
from typing import Iterable, List, Set


class CodeIdentifiersCard(GitHubCardBase):
    MAX_WORKERS = 8

    LANGUAGE_EXTENSIONS = {
        '.py': ('python', '#3572A5'),
        '.js': ('javascript', '#f1e05a'),
        '.jsx': ('javascript', '#f1e05a'),
        '.ts': ('typescript', '#2b7489'),
        '.tsx': ('typescript', '#2b7489'),
        '.java': ('java', '#b07219'),
        '.kt': ('kotlin', '#A97BFF'),
        '.kts': ('kotlin', '#A97BFF'),
        '.cs': ('c#', '#178600'),
        '.go': ('go', '#00ADD8'),
        '.cpp': ('c++', '#f34b7d'),
        '.cc': ('c++', '#f34b7d'),
        '.c': ('c', '#555555'),
        '.h': ('c', '#555555'),
        '.hpp': ('c++', '#f34b7d'),
        '.rb': ('ruby', '#701516'),
        '.php': ('php', '#4F5D95'),
        '.swift': ('swift', '#F05138'),
    }

    LANGUAGE_PATTERNS = {
        'python': {
            'types': [re.compile(r'\bclass\s+([A-Z][a-zA-Z0-9_]*)')],
            'identifiers': [
                re.compile(r'^\s*def\s+([a-z_][a-zA-Z0-9_]*)\s*\(', re.MULTILINE),
                re.compile(r'^[ \t]*([a-z_][a-zA-Z0-9_]*)\s*(?::\s*\w+)?\s*=', re.MULTILINE),
            ],
        },
        'javascript': {
            'types': [
                re.compile(r'\bclass\s+([A-Z][a-zA-Z0-9_$]*)'),
                re.compile(r'\binterface\s+([A-Z][a-zA-Z0-9_$]*)'),
                re.compile(r'\btype\s+([A-Z][a-zA-Z0-9_$]*)\s*='),
            ],
            'identifiers': [
                re.compile(r'\b(?:const|let|var)\s+([a-z_$][a-zA-Z0-9_$]*)\s*[=;]'),
                re.compile(r'\bfunction\s+([a-zA-Z_$][\w$]*)\s*\('),
            ],
        },
        'typescript': {
            'types': [
                re.compile(r'\bclass\s+([A-Z][a-zA-Z0-9_$]*)'),
                re.compile(r'\binterface\s+([A-Z][a-zA-Z0-9_$]*)'),
                re.compile(r'\btype\s+([A-Z][a-zA-Z0-9_$]*)\s*='),
            ],
            'identifiers': [
                re.compile(r'\b(?:const|let|var)\s+([a-z_$][a-zA-Z0-9_$]*)\s*[=;:]'),
                re.compile(r'\bfunction\s+([a-zA-Z_$][\w$]*)\s*\('),
            ],
        },
        'java': {
            'types': [re.compile(r'\b(class|interface|enum)\s+([A-Z][A-Za-z0-9_]*)')],
            'identifiers': [
                re.compile(r'\b(?:public|private|protected|static|final|abstract|sealed|synchronized|native|\s)+(?:(?:[A-Za-z_][\w<>\[\]]*)\s+)+([a-z_][A-Za-z0-9_]*)\s*\('),
                re.compile(r'\b(?:final\s+)?(?:[A-Za-z_][\w<>\[\]]*)\s+([a-z_][A-Za-z0-9_]*)\s*(?:=|;)'),
            ],
        },
        'kotlin': {
            'types': [
                re.compile(r'\b(?:data\s+)?class\s+([A-Z][A-Za-z0-9_]*)'),
                re.compile(r'\binterface\s+([A-Z][A-Za-z0-9_]*)'),
                re.compile(r'\bobject\s+([A-Z][A-Za-z0-9_]*)'),
            ],
            'identifiers': [
                re.compile(r'\bfun\s+([a-zA-Z_][\w]*)\s*\('),
                re.compile(r'\b(?:val|var)\s+([a-zA-Z_][\w]*)'),
            ],
        },
        'c#': {
            'types': [
                re.compile(r'\b(class|interface|record|struct)\s+([A-Z][A-Za-z0-9_]*)'),
            ],
            'identifiers': [
                re.compile(r'\b(?:public|private|protected|internal|static|readonly|sealed|async|virtual|override|partial|new|const|unsafe)\s+(?:[A-Za-z_][\w<>\[\],?]*\s+)+([a-z_][A-Za-z0-9_]*)\s*\('),
                re.compile(r'\b(?:var|dynamic|[A-Za-z_][\w<>\[\],?]*)\s+([a-z_][A-Za-z0-9_]*)\s*(?:=|;)'),
            ],
        },
        'go': {
            'types': [re.compile(r'\btype\s+([A-Z][A-Za-z0-9_]*)\s+(?:struct|interface)')],
            'identifiers': [
                re.compile(r'\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)\s*\('),
                re.compile(r'\b(?:var|const)\s+([a-z_][A-Za-z0-9_]*)'),
            ],
        },
        'c++': {
            'types': [re.compile(r'\b(class|struct)\s+([A-Z][A-Za-z0-9_]*)')],
            'identifiers': [
                re.compile(r'\b(?:int|float|double|char|bool|auto|long|short|unsigned|std::\w+)\s+([a-z_][A-Za-z0-9_]*)\s*(?:=|;)'),
                re.compile(r'\b([a-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{'),
            ],
        },
        'c': {
            'types': [re.compile(r'\bstruct\s+([A-Z][A-Za-z0-9_]*)')],
            'identifiers': [
                re.compile(r'\b(?:int|float|double|char|bool|long|short|unsigned|struct\s+\w+)\s+([a-z_][A-Za-z0-9_]*)\s*(?:=|;)'),
                re.compile(r'\b([a-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{'),
            ],
        },
        'ruby': {
            'types': [re.compile(r'\bclass\s+([A-Z][A-Za-z0-9_]*)')],
            'identifiers': [
                re.compile(r'^\s*def\s+([a-zA-Z_][\w]*)', re.MULTILINE),
                re.compile(r'@([a-zA-Z_][\w]*)'),
            ],
        },
        'php': {
            'types': [re.compile(r'\bclass\s+([A-Z][A-Za-z0-9_]*)')],
            'identifiers': [
                re.compile(r'\bfunction\s+([a-zA-Z_][\w]*)\s*\('),
                re.compile(r'\$([a-zA-Z_][\w]*)'),
            ],
        },
        'swift': {
            'types': [
                re.compile(r'\b(class|struct|enum)\s+([A-Z][A-Za-z0-9_]*)'),
            ],
            'identifiers': [
                re.compile(r'\bfunc\s+([a-zA-Z_][\w]*)\s*\('),
                re.compile(r'\b(?:let|var)\s+([a-zA-Z_][\w]*)'),
            ],
        },
    }

    SKIP_PATH_PARTS = frozenset({
        '__pycache__', 'node_modules', 'dist', 'build', 'vendor', 'coverage', 'site-packages',
        '.git', 'out', 'target'
    })
    SKIP = frozenset({'i','j','k','x','y','z','e','t','a','b','c','d','f','g','h',
                      'id','el','err','fn','cb','fs','os','db','api','app','env','ctx','req','res',
                      'self','cls','args','kwargs','this','true','false','null',
                      'None','True','False','undefined','console','module','exports','main','init'})

    def __init__(self, username, query_params, width=400, header_height=40, forced_filters: Set[str] | None = None):
        super().__init__(username, query_params)
        self.card_width = width
        self.header_height = header_height
        self.extract_filters = forced_filters or self._parse_filters(query_params)
        self.file_timeout = 3

    @classmethod
    def _parse_filters(cls, query_params):
        """Normalize and validate the filter parameter (types|identifiers)."""
        raw = query_params.get('filter') or query_params.get('extract') or ['types,identifiers']
        raw_value = raw[0] if isinstance(raw, list) else str(raw)
        requested = {part.strip().lower() for part in raw_value.split(',') if part.strip()}
        valid = {'types', 'identifiers'}

        selected = {opt for opt in requested if opt in valid}
        if not selected:
            return valid
        return selected

    def fetch_data(self):
        repos = self._fetch_all_repos()
        repo_names = [r['name'] for r in repos if not r.get('fork')]

        id_langs = {}
        lang_file_counts = Counter()
        total_files = 0

        def fetch_file(repo, path, ext):
            req = urllib.request.Request(
                f"https://raw.githubusercontent.com/{self.user}/{repo}/HEAD/{path}",
                headers=HEADERS)
            with urllib.request.urlopen(req, timeout=self.file_timeout) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
            lang, _ = self.LANGUAGE_EXTENSIONS[ext]
            return lang, content

        def fetch_repo(repo):
            results = []
            files_scanned = 0
            lang_counts = Counter()
            try:
                tree = self._make_request(f"https://api.github.com/repos/{self.user}/{repo}/git/trees/HEAD?recursive=1")
                files = [
                    (f['path'], ext)
                    for f in tree.get('tree', [])
                    if f.get('type') == 'blob' and f.get('size', 0) < 100000 and not self._should_skip(f.get('path', ''))
                    for ext in [next((e for e in self.LANGUAGE_EXTENSIONS if f['path'].endswith(e)), None)] if ext
                ]

                if not files:
                    return results, files_scanned, lang_counts

                with ThreadPoolExecutor(max_workers=min(6, len(files))) as file_ex:
                    futures = {file_ex.submit(fetch_file, repo, path, ext): (path, ext) for path, ext in files}
                    for future in as_completed(futures):
                        try:
                            lang, content = future.result()
                        except Exception:
                            continue
                        files_scanned += 1
                        lang_counts[lang] += 1
                        results.extend((name, lang) for name in self._extract(content, lang))
            except Exception:
                pass
            return results, files_scanned, lang_counts

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as ex:
            for future in as_completed([ex.submit(fetch_repo, r) for r in repo_names]):
                items, file_count, lang_counts = future.result()
                total_files += file_count
                lang_file_counts.update(lang_counts)
                for name, lang in items:
                    id_langs.setdefault(name, Counter())[lang] += 1

        scored = []
        for name, lang_counts in id_langs.items():
            total = sum(lang_counts.values())
            dominant = lang_counts.most_common(1)[0][0]
            scored.append({'name': name, 'count': total, 'lang': dominant})

        scored.sort(key=lambda x: x['count'], reverse=True)
        return {
            'items': scored[:10],
            'language_files': lang_file_counts,
            'repo_count': len(repo_names),
            'file_count': total_files,
        }

    def _fetch_all_repos(self):
        page = 1
        repos = []
        while True:
            batch = self._make_request(
                f"https://api.github.com/users/{self.user}/repos?per_page=100&type=owner&sort=updated&page={page}")
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return repos

    def _extract(self, code: str, lang: str):
        patterns = self.LANGUAGE_PATTERNS.get(lang, {})
        names: List[str] = []
        for category in self.extract_filters:
            for pattern in patterns.get(category, []):
                names.extend(self._normalize_matches(pattern.findall(code)))
        return [n for n in names if 2 < len(n) < 40 and n not in self.SKIP and not n.isupper()]

    @staticmethod
    def _normalize_matches(matches: Iterable):
        normalized = []
        for item in matches:
            if isinstance(item, tuple):
                normalized.append(item[-1])
            else:
                normalized.append(item)
        return normalized

    def process(self):
        if not self.user:
            return self._render_error("Missing ?username= parameter")
        try:
            data = self.fetch_data()
            title_filter = '/'.join(sorted(self.extract_filters)).title()
            body, height = self.render_body(data)
            return self._render_frame(f"{self.user}'s Top {title_filter}", body, height)
        except Exception:
            import traceback
            return self._render_error(traceback.format_exc())

    def render_body(self, stats):
        items = stats.get('items') if isinstance(stats, dict) else []
        language_counts = stats.get('language_files', Counter()) if isinstance(stats, dict) else Counter()
        repo_count = stats.get('repo_count', 0) if isinstance(stats, dict) else 0
        file_count = stats.get('file_count', 0) if isinstance(stats, dict) else 0

        bar_h, row_h, bar_w = 12, 20, 200
        svg = []

        if not items:
            svg.append(f'<text x="{self.padding}" y="20" class="stat-value">No identifiers found.</text>')
            body_height = 40
        else:
            max_count = max(s['count'] for s in items)
            for i, item in enumerate(items):
                y = 10 + i * row_h
                w = (item['count'] / max_count) * bar_w
                color = self._color_for_lang(item['lang'])

                svg.append(f'''<g transform="translate({self.padding},{y})">
                    <text x="0" y="{bar_h-2}" class="stat-name">{escape_xml(item['name'])}</text>
                    <rect x="110" y="0" width="{bar_w}" height="{bar_h}" rx="3" fill="#21262d"/>
                    <rect x="110" y="0" width="{max(w,2)}" height="{bar_h}" rx="3" fill="{color}"/>
                    <text x="{110+bar_w+10}" y="{bar_h-2}" class="stat-value">{item['count']}</text>
                </g>''')

            body_height = len(items) * row_h + 10

        legend_svg, legend_height = self._render_legend(language_counts, y_offset=body_height + 10)
        svg.append(legend_svg)

        meta_y = body_height + legend_height + 25
        svg.append(f'<text x="{self.padding}" y="{meta_y}" class="stat-value">{repo_count} repos • {file_count} files scanned</text>')

        total_height = meta_y + 10
        return "\n".join(svg), total_height

    def _color_for_lang(self, lang):
        for ext, (name, color) in self.LANGUAGE_EXTENSIONS.items():
            if name == lang:
                return color
        return '#58a6ff'

    def _should_skip(self, path):
        parts = [p.lower() for p in path.split('/') if p]
        return any(part in self.SKIP_PATH_PARTS for part in parts)

    def _render_legend(self, language_counts, y_offset):
        if not language_counts:
            return '', 0

        items = language_counts.most_common()
        col_width = 140
        items_per_row = max(1, (self.card_width - (2 * self.padding)) // col_width)
        rows = (len(items) + items_per_row - 1) // items_per_row
        svg_parts = [f'<text x="{self.padding}" y="{y_offset}" class="stat-name">Legend</text>']

        for idx, (lang, count) in enumerate(items):
            col = idx % items_per_row
            row = idx // items_per_row
            x = self.padding + (col * col_width)
            y = y_offset + 12 + row * 18
            color = self._color_for_lang(lang)
            svg_parts.append(
                f'<g transform="translate({x},{y})">'
                f'<rect x="0" y="-10" width="12" height="12" rx="2" fill="{color}" />'
                f'<text x="18" y="0" class="stat-value">{escape_xml(lang.title())} ({count})</text>'
                f'</g>'
            )

        height = rows * 18 + 18
        return "\n".join(svg_parts), height


def _respond_with_card(handler: BaseHTTPRequestHandler, forced_filters=None):
    query = parse_qs(urlparse(handler.path).query) if "?" in handler.path else {}
    card = CodeIdentifiersCard(query.get("username", [""])[0], query, forced_filters=forced_filters)
    svg = card.process()
    handler.send_response(200)
    handler.send_header("Content-Type", "image/svg+xml; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache, max-age=0")
    handler.end_headers()
    handler.wfile.write(svg.encode())


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _respond_with_card(self)
