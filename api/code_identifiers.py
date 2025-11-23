# code_identifiers.py

from .github_base import GitHubCardBase, escape_xml
import json
import urllib.request
import urllib.error
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
import ast
import re
from collections import Counter

class CodeIdentifiersCard(GitHubCardBase):
    MAX_WORKERS = 5
    EXTENSIONS = {'.py': 'python', '.js': 'javascript', '.ts': 'javascript', '.jsx': 'javascript', '.tsx': 'javascript'}
    # Common names to skip
    SKIP_NAMES = {'self', 'cls', 'args', 'kwargs', 'init', 'str', 'repr', 'del', 'main', 
                  'function', 'class', 'const', 'let', 'var', 'return', 'import', 'export', 
                  'default', 'async', 'await', 'this', 'super', 'prototype', 'constructor',
                  'undefined', 'null', 'true', 'false', 'i', 'j', 'k', 'x', 'y', 'z', 'e', 'err'}
    
    def __init__(self, username, query_params, width=350, header_height=40):
        super().__init__(username, query_params)
        self.card_width = width
        self.header_height = header_height
        self.extract_type = query_params.get('extract', ['classes,variables'])[0]
    
    def fetch_data(self):
        try:
            repos_url = f"https://api.github.com/users/{self.user}/repos?per_page=30&type=owner&sort=updated"
            repos = self._make_request(repos_url)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"GitHub API Error: {e.code}")
        
        all_identifiers = []
        repo_names = [r['name'] for r in repos if not r.get('fork')][:15]
        
        def fetch_repo_code(repo_name):
            try:
                tree_url = f"https://api.github.com/repos/{self.user}/{repo_name}/git/trees/HEAD?recursive=1"
                tree = self._make_request(tree_url)
                identifiers = []
                
                for item in tree.get('tree', [])[:200]:
                    if item.get('type') != 'blob':
                        continue
                    ext = next((e for e in self.EXTENSIONS if item['path'].endswith(e)), None)
                    if not ext or item.get('size', 0) > 100000:
                        continue
                    
                    try:
                        raw_url = f"https://raw.githubusercontent.com/{self.user}/{repo_name}/HEAD/{item['path']}"
                        req = urllib.request.Request(raw_url, headers={"User-Agent": "GitHub-Stats"})
                        with urllib.request.urlopen(req, timeout=3) as resp:
                            content = resp.read().decode('utf-8', errors='ignore')
                        identifiers.extend(self._extract_identifiers(content, self.EXTENSIONS[ext]))
                    except:
                        pass
                
                return identifiers
            except:
                return []
        
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_repo_code, name): name for name in repo_names}
            for future in as_completed(futures):
                all_identifiers.extend(future.result())
        
        if not all_identifiers:
            return []
        
        counts = Counter(all_identifiers)
        return [{'name': name, 'count': count} for name, count in counts.most_common(8)]
    
    def _extract_identifiers(self, code, lang):
        identifiers = []
        types = self.extract_type.split(',')
        
        if lang == 'python':
            try:
                tree = ast.parse(code)
                # Get module-level assignments only
                for node in tree.body:
                    if 'classes' in types and isinstance(node, ast.ClassDef):
                        if not node.name.startswith('_') and len(node.name) > 1:
                            identifiers.append(node.name)
                    elif 'variables' in types and isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                name = target.id
                                # Only module-level, non-private, reasonable length
                                if not name.startswith('_') and 1 < len(name) < 30 and name not in self.SKIP_NAMES:
                                    identifiers.append(name)
            except:
                pass
        
        elif lang == 'javascript':
            # Class declarations
            if 'classes' in types:
                class_matches = re.findall(r'\bclass\s+([A-Z][a-zA-Z0-9_]*)', code)
                identifiers.extend([m for m in class_matches if m not in self.SKIP_NAMES])
            
            # Variable declarations (const/let/var)
            if 'variables' in types:
                var_matches = re.findall(r'\b(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=', code)
                identifiers.extend([m for m in var_matches 
                                  if m not in self.SKIP_NAMES and 1 < len(m) < 30])
        
        return identifiers
    
    def process(self):
        if not self.user:
            return self._render_error("Missing ?username= parameter")
        try:
            data = self.fetch_data()
            body, height = self.render_body(data)
            return self._render_frame(f"{self.user}'s Favorite Names", body, height)
        except Exception:
            import traceback
            return self._render_error(traceback.format_exc())
    
    def render_body(self, stats):
        if not stats:
            return '<text x="20" y="60" class="stat-value">No identifiers found.</text>', 40
        
        bar_height, row_height = 12, 20
        bar_width_max, y_offset = 200, 10
        svg_parts = []
        max_count = max(s['count'] for s in stats)
        
        for i, item in enumerate(stats):
            y = y_offset + (i * row_height)
            bar_width = (item['count'] / max_count) * bar_width_max
            
            svg_parts.append(f'''
            <g transform="translate({self.padding}, {y})">
                <text x="0" y="{bar_height - 2}" class="stat-name">{escape_xml(item['name'])}</text>
                <rect x="100" y="0" width="{bar_width_max}" height="{bar_height}" rx="3" fill="#21262d" />
                <rect x="100" y="0" width="{max(bar_width, 2)}" height="{bar_height}" rx="3" fill="#58a6ff" />
                <text x="{100 + bar_width_max + 10}" y="{bar_height - 2}" class="stat-value">{item['count']}</text>
            </g>
            ''')
        
        return "\n".join(svg_parts), len(stats) * row_height + y_offset

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query) if "?" in self.path else {}
        user = query.get("username", [""])[0]
        card = CodeIdentifiersCard(user, query)
        svg = card.process()
        
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, max-age=0")
        self.end_headers()
        self.wfile.write(svg.encode())
