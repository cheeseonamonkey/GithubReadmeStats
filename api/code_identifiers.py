# code_identifiers.py

from .github_base import GitHubCardBase, HEADERS, escape_xml
import urllib.request
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from collections import Counter

class CodeIdentifiersCard(GitHubCardBase):
    MAX_WORKERS = 8
    EXTENSIONS = {
        '.py': ('python', '#3572A5'),
        '.js': ('javascript', '#f1e05a'),
        '.ts': ('typescript', '#2b7489'),
        '.jsx': ('javascript', '#f1e05a'),
        '.tsx': ('typescript', '#2b7489'),
    }
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
    
    def __init__(self, username, query_params, width=400, header_height=40):
        super().__init__(username, query_params)
        self.card_width = width
        self.header_height = header_height
        self.extract_type = self._parse_extract_types(query_params)
        self.file_timeout = 3

    @classmethod
    def _parse_extract_types(cls, query_params):
        """Normalize and validate the extract parameter."""
        raw = query_params.get('extract', ['classes,variables'])[0]
        requested = {part.strip().lower() for part in raw.split(',') if part.strip()}
        valid = {'classes', 'variables'}

        selected = {opt for opt in requested if opt in valid}
        if not selected:
            return valid
        return selected
    
    def fetch_data(self):
        repos = self._make_request(f"https://api.github.com/users/{self.user}/repos?per_page=100&type=owner&sort=updated")
        repo_names = [r['name'] for r in repos if not r.get('fork')][:30]

        # {identifier: {lang: count}}
        id_langs = {}
        lang_file_counts = Counter()
        total_files = 0
        
        def fetch_file(repo, path, ext):
            req = urllib.request.Request(
                f"https://raw.githubusercontent.com/{self.user}/{repo}/HEAD/{path}",
                headers=HEADERS)
            with urllib.request.urlopen(req, timeout=self.file_timeout) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
            lang, _ = self.EXTENSIONS[ext]
            return lang, content

        def fetch_repo(repo):
            results = []
            files_scanned = 0
            lang_counts = Counter()
            try:
                tree = self._make_request(f"https://api.github.com/repos/{self.user}/{repo}/git/trees/HEAD?recursive=1")
                files = [(f['path'], ext) for f in tree.get('tree', [])
                         if f.get('type') == 'blob' and f.get('size', 0) < 100000 and not self._should_skip(f.get('path', ''))
                         for ext in [next((e for e in self.EXTENSIONS if f['path'].endswith(e)), None)] if ext]

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
            if 'classes' in self.extract_type:
                names.extend(self.PY_CLASS.findall(code))
            if 'variables' in self.extract_type:
                names.extend(self.PY_VAR.findall(code))
        else:  # javascript/typescript
            if 'classes' in self.extract_type:
                names.extend(self.JS_CLASS.findall(code))
            if 'variables' in self.extract_type:
                names.extend(self.JS_VAR.findall(code))
        
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
                color = self.EXTENSIONS.get(
                    f".{'py' if item['lang']=='python' else 'ts' if item['lang']=='typescript' else 'js'}",
                    ('', '#58a6ff')
                )[1]

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
            color = next((c for (e, (l, c)) in self.EXTENSIONS.items() if l == lang), '#58a6ff')
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
