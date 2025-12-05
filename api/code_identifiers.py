# code_identifiers.py

from .github_base import GitHubCardBase, escape_xml
import urllib.request
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from collections import Counter

class CodeIdentifiersCard(GitHubCardBase):
    MAX_WORKERS = 8
    FILE_WORKERS = 6
    MAX_REPOS = 50
    MAX_FILES_PER_REPO = 200
    EXTENSIONS = {
        '.py': ('python', '#3572A5'),
        '.js': ('javascript', '#f1e05a'),
        '.ts': ('typescript', '#2b7489'),
        '.jsx': ('javascript', '#f1e05a'),
        '.tsx': ('typescript', '#2b7489'),
        '.java': ('java', '#b07219'),
        '.kt': ('kotlin', '#A97BFF'),
        '.kts': ('kotlin', '#A97BFF'),
        '.go': ('go', '#00ADD8'),
        '.rb': ('ruby', '#701516'),
        '.php': ('php', '#4F5D95'),
        '.cs': ('csharp', '#178600'),
        '.c': ('c', '#555555'),
        '.cc': ('cpp', '#f34b7d'),
        '.cpp': ('cpp', '#f34b7d'),
    }
    LANGUAGE_COLORS = {v[0]: v[1] for v in EXTENSIONS.values()}
    SKIP_PATH_PARTS = frozenset({
        '__pycache__', 'node_modules', 'dist', 'build', 'vendor', 'coverage', 'site-packages',
        '.git', 'out', 'target'
    })
    SKIP = frozenset({'i','j','k','x','y','z','e','t','a','b','c','d','f','g','h',
                      'id','el','err','fn','cb','fs','os','db','api','app','env',
                      'self','cls','args','kwargs','this','true','false','null',
                      'None','True','False','undefined','console','module','exports'})
    
    # Regex patterns (compiled once)
    PY_CLASS = re.compile(r'\bclass\s+([A-Z][a-zA-Z0-9_]*)')
    PY_VAR = re.compile(r'^[ \t]*([a-z_][a-zA-Z0-9_]*)\s*(?::\s*\w+)?\s*=', re.MULTILINE)
    JS_CLASS = re.compile(r'\bclass\s+([A-Z][a-zA-Z0-9_]*)')
    JS_VAR = re.compile(r'\b(?:const|let|var)\s+([a-z_$][a-zA-Z0-9_$]*)\s*[=;]')
    JAVA_CLASS = re.compile(r'\bclass\s+([A-Z][a-zA-Z0-9_]*)')
    JAVA_VAR = re.compile(r'\b(?:public|protected|private|static|final|transient|volatile|\s)*'
                          r'(?:[A-Za-z_][\w<>\[\]]*\s+)+([a-z_][a-zA-Z0-9_]*)\s*[=;]')
    KOTLIN_CLASS = re.compile(r'\bclass\s+([A-Z][a-zA-Z0-9_]*)')
    KOTLIN_VAR = re.compile(r'\b(?:val|var)\s+([a-z_][a-zA-Z0-9_]*)')
    GO_CLASS = re.compile(r'\btype\s+([A-Z][a-zA-Z0-9_]*)\s+struct\b')
    GO_VAR = re.compile(r'\b(?:var|const)\s+([a-z_][a-zA-Z0-9_]*)')
    RUBY_CLASS = re.compile(r'\bclass\s+([A-Z][a-zA-Z0-9_]*)')
    RUBY_VAR = re.compile(r'^([a-z_][a-zA-Z0-9_]*)\s*=.*$', re.MULTILINE)
    PHP_CLASS = re.compile(r'\bclass\s+([A-Z][a-zA-Z0-9_]*)')
    PHP_VAR = re.compile(r'\$([a-z_][a-zA-Z0-9_]*)\s*[=;]')
    CSHARP_CLASS = re.compile(r'\bclass\s+([A-Z][a-zA-Z0-9_]*)')
    CSHARP_VAR = re.compile(r'\b(?:public|protected|private|static|readonly|const|internal|volatile|\s)*'
                             r'(?:[A-Za-z_][\w<>\[\]]*\s+)+([a-z_][a-zA-Z0-9_]*)\s*[=;]')
    C_STRUCT = re.compile(r'\bstruct\s+([A-Z][a-zA-Z0-9_]*)')
    C_VAR = re.compile(r'\b(?:int|char|float|double|long|short|size_t|auto|bool|unsigned|signed|struct\s+[A-Za-z_][\w]*)\s+([a-z_][a-zA-Z0-9_]*)\s*[=;]')
    CPP_CLASS = re.compile(r'\bclass\s+([A-Z][a-zA-Z0-9_]*)')
    CPP_VAR = re.compile(r'\b(?:int|char|float|double|long|short|auto|bool|unsigned|signed|std::\w+|class\s+[A-Za-z_][\w]*)\s+([a-z_][a-zA-Z0-9_]*)\s*[=;]')
    
    def __init__(self, username, query_params, width=400, header_height=40):
        super().__init__(username, query_params)
        self.card_width = width
        self.header_height = header_height
        self.extract_type = self._parse_extract_types(query_params)

    @classmethod
    def _parse_extract_types(cls, query_params):
        """Normalize and validate the extract parameter."""
        raw = query_params.get('extract', ['types,identifiers'])[0]
        requested = {part.strip().lower() for part in raw.split(',') if part.strip()}

        # Allow legacy names so existing URLs keep working
        alias_map = {
            'classes': 'types',
            'variables': 'identifiers',
        }

        normalized = {alias_map.get(opt, opt) for opt in requested}
        valid = {'types', 'identifiers'}

        selected = {opt for opt in normalized if opt in valid}
        if not selected:
            return valid
        return selected
    
    def _list_repos(self):
        repos = []
        page = 1
        while len(repos) < self.MAX_REPOS:
            page_repos = self._make_request(
                f"https://api.github.com/users/{self.user}/repos?per_page=100&type=owner&sort=updated&page={page}"
            )
            if not page_repos:
                break
            repos.extend(r for r in page_repos if not r.get('fork'))
            if len(page_repos) < 100:
                break
            page += 1

        return [r['name'] for r in repos[: self.MAX_REPOS]]

    def fetch_data(self):
        repo_names = self._list_repos()

        # {identifier: {lang: count}}
        id_langs = {}
        lang_file_counts = Counter()
        total_files = 0
        
        def fetch_file(repo, path, ext):
            try:
                req = urllib.request.Request(
                    f"https://raw.githubusercontent.com/{self.user}/{repo}/HEAD/{path}",
                    headers={"User-Agent": "GitHub-Stats"})
                with urllib.request.urlopen(req, timeout=2.5) as resp:
                    content = resp.read().decode('utf-8', errors='ignore')
                lang, _ = self.EXTENSIONS[ext]
                return lang, self._extract(content, lang)
            except:  # noqa: E722
                return None, []

        def fetch_repo(repo):
            results = []
            files_scanned = 0
            lang_counts = Counter()
            try:
                tree = self._make_request(f"https://api.github.com/repos/{self.user}/{repo}/git/trees/HEAD?recursive=1")
                files = [(f['path'], ext) for f in tree.get('tree', [])
                         if f.get('type') == 'blob' and f.get('size', 0) < 100000 and not self._should_skip(f.get('path', ''))
                         for ext in [next((e for e in self.EXTENSIONS if f['path'].endswith(e)), None)] if ext][: self.MAX_FILES_PER_REPO]

                with ThreadPoolExecutor(max_workers=self.FILE_WORKERS) as fex:
                    futures = [fex.submit(fetch_file, repo, path, ext) for path, ext in files]
                    for future in as_completed(futures):
                        lang, names = future.result()
                        if not lang:
                            continue
                        files_scanned += 1
                        lang_counts[lang] += 1
                        results.extend((name, lang) for name in names)
            except:  # noqa: E722
                pass
            return results, files_scanned, lang_counts

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as ex:
            for future in as_completed([ex.submit(fetch_repo, r) for r in repo_names]):
                items, file_count, lang_counts = future.result()
                total_files += file_count
                lang_file_counts.update(lang_counts)
                for name, lang in items:
                    id_langs.setdefault(name, Counter())[lang] += 1

        # Aggregate: pick dominant language per identifier
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
    
    def _extract(self, code, lang):
        names = []
        if lang == 'python':
            if 'types' in self.extract_type:
                names.extend(self.PY_CLASS.findall(code))
            if 'identifiers' in self.extract_type:
                names.extend(self.PY_VAR.findall(code))
        elif lang in {'javascript', 'typescript'}:
            if 'types' in self.extract_type:
                names.extend(self.JS_CLASS.findall(code))
            if 'identifiers' in self.extract_type:
                names.extend(self.JS_VAR.findall(code))
        elif lang == 'java':
            if 'types' in self.extract_type:
                names.extend(self.JAVA_CLASS.findall(code))
            if 'identifiers' in self.extract_type:
                names.extend(self.JAVA_VAR.findall(code))
        elif lang == 'kotlin':
            if 'types' in self.extract_type:
                names.extend(self.KOTLIN_CLASS.findall(code))
            if 'identifiers' in self.extract_type:
                names.extend(self.KOTLIN_VAR.findall(code))
        elif lang == 'go':
            if 'types' in self.extract_type:
                names.extend(self.GO_CLASS.findall(code))
            if 'identifiers' in self.extract_type:
                names.extend(self.GO_VAR.findall(code))
        elif lang == 'ruby':
            if 'types' in self.extract_type:
                names.extend(self.RUBY_CLASS.findall(code))
            if 'identifiers' in self.extract_type:
                names.extend(self.RUBY_VAR.findall(code))
        elif lang == 'php':
            if 'types' in self.extract_type:
                names.extend(self.PHP_CLASS.findall(code))
            if 'identifiers' in self.extract_type:
                names.extend(self.PHP_VAR.findall(code))
        elif lang == 'csharp':
            if 'types' in self.extract_type:
                names.extend(self.CSHARP_CLASS.findall(code))
            if 'identifiers' in self.extract_type:
                names.extend(self.CSHARP_VAR.findall(code))
        elif lang == 'c':
            if 'types' in self.extract_type:
                names.extend(self.C_STRUCT.findall(code))
            if 'identifiers' in self.extract_type:
                names.extend(self.C_VAR.findall(code))
        elif lang == 'cpp':
            if 'types' in self.extract_type:
                names.extend(self.CPP_CLASS.findall(code))
            if 'identifiers' in self.extract_type:
                names.extend(self.CPP_VAR.findall(code))
        
        return [n for n in names if 2 < len(n) < 40 and n not in self.SKIP and not n.isupper()]
    
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
                color = self.LANGUAGE_COLORS.get(item['lang'], '#58a6ff')

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
        svg.append(
            f'<text x="{self.padding}" y="{meta_y}" class="stat-value">{repo_count} repos • {file_count} files scanned</text>'
        )

        total_height = meta_y + 10
        return "\n".join(svg), total_height

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
            color = self.LANGUAGE_COLORS.get(lang, '#58a6ff')
            svg_parts.append(
                f'<g transform="translate({x},{y})">'
                f'<rect x="0" y="-10" width="12" height="12" rx="2" fill="{color}" />'
                f'<text x="18" y="0" class="stat-value">{escape_xml(lang.title())} ({count})</text>'
                f'</g>'
            )

        height = rows * 18 + 18
        return "\n".join(svg_parts), height

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query) if "?" in self.path else {}
        svg = CodeIdentifiersCard(query.get("username", [""])[0], query).process()
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, max-age=0")
        self.end_headers()
        self.wfile.write(svg.encode())
