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
    EXTENSIONS = {
        '.py': ('python', '#3572A5'),
        '.js': ('javascript', '#f1e05a'),
        '.ts': ('typescript', '#2b7489'),
        '.jsx': ('javascript', '#f1e05a'),
        '.tsx': ('typescript', '#2b7489'),
    }
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
        self.extract_type = set(query_params.get('extract', ['classes,variables'])[0].split(','))
    
    def fetch_data(self):
        repos = self._make_request(f"https://api.github.com/users/{self.user}/repos?per_page=100&type=owner&sort=updated")
        repo_names = [r['name'] for r in repos if not r.get('fork')][:20]
        
        # {identifier: {lang: count}}
        id_langs = {}
        
        def fetch_repo(repo):
            results = []
            try:
                tree = self._make_request(f"https://api.github.com/repos/{self.user}/{repo}/git/trees/HEAD?recursive=1")
                files = [(f['path'], ext) for f in tree.get('tree', []) 
                         if f.get('type') == 'blob' and f.get('size', 0) < 100000
                         for ext in [next((e for e in self.EXTENSIONS if f['path'].endswith(e)), None)] if ext][:200]
                
                for path, ext in files:
                    try:
                        req = urllib.request.Request(
                            f"https://raw.githubusercontent.com/{self.user}/{repo}/HEAD/{path}",
                            headers={"User-Agent": "GitHub-Stats"})
                        with urllib.request.urlopen(req, timeout=3) as resp:
                            content = resp.read().decode('utf-8', errors='ignore')
                        lang, _ = self.EXTENSIONS[ext]
                        results.extend((name, lang) for name in self._extract(content, lang))
                    except: pass
            except: pass
            return results
        
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as ex:
            for future in as_completed([ex.submit(fetch_repo, r) for r in repo_names]):
                for name, lang in future.result():
                    id_langs.setdefault(name, Counter())[lang] += 1
        
        if not id_langs:
            return []
        
        # Aggregate: pick dominant language per identifier
        scored = []
        for name, lang_counts in id_langs.items():
            total = sum(lang_counts.values())
            dominant = lang_counts.most_common(1)[0][0]
            scored.append({'name': name, 'count': total, 'lang': dominant})
        
        scored.sort(key=lambda x: x['count'], reverse=True)
        return scored[:10]
    
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
        if not stats:
            return '<text x="20" y="60" class="stat-value">No identifiers found.</text>', 40
        
        bar_h, row_h, bar_w = 12, 20, 200
        svg, max_count = [], max(s['count'] for s in stats)
        
        for i, item in enumerate(stats):
            y = 10 + i * row_h
            w = (item['count'] / max_count) * bar_w
            color = self.EXTENSIONS.get(f".{'py' if item['lang']=='python' else 'ts' if item['lang']=='typescript' else 'js'}", ('', '#58a6ff'))[1]
            
            svg.append(f'''<g transform="translate({self.padding},{y})">
                <text x="0" y="{bar_h-2}" class="stat-name">{escape_xml(item['name'])}</text>
                <rect x="110" y="0" width="{bar_w}" height="{bar_h}" rx="3" fill="#21262d"/>
                <rect x="110" y="0" width="{max(w,2)}" height="{bar_h}" rx="3" fill="{color}"/>
                <text x="{110+bar_w+10}" y="{bar_h-2}" class="stat-value">{item['count']}</text>
            </g>''')
        
        return "\n".join(svg), len(stats) * row_h + 10

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query) if "?" in self.path else {}
        svg = CodeIdentifiersCard(query.get("username", [""])[0], query).process()
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, max-age=0")
        self.end_headers()
        self.wfile.write(svg.encode())
