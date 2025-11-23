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
import base64

class CodeIdentifiersCard(GitHubCardBase):
    MAX_WORKERS = 5
    EXTENSIONS = {'.py': 'python', '.js': 'js', '.ts': 'js', '.jsx': 'js', '.tsx': 'js', 
                  '.java': 'generic', '.go': 'generic', '.rs': 'generic', '.rb': 'generic'}
    
    def __init__(self, username, query_params, width=350, header_height=40):
        super().__init__(username, query_params)
        self.card_width = width
        self.header_height = header_height
    
    def fetch_data(self):
        try:
            repos_url = f"https://api.github.com/users/{self.user}/repos?per_page=10&type=owner&sort=updated"
            repos = self._make_request(repos_url)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"GitHub API Error: {e.code}")
        
        all_identifiers = []
        repo_names = [r['name'] for r in repos if not r.get('fork')][:3]
        
        def fetch_repo_code(repo_name):
            try:
                tree_url = f"https://api.github.com/repos/{self.user}/{repo_name}/git/trees/HEAD?recursive=1"
                tree = self._make_request(tree_url)
                identifiers = []
                
                for item in tree.get('tree', [])[:80]:
                    ext = next((e for e in self.EXTENSIONS if item['path'].endswith(e)), None)
                    if not ext or item['size'] > 100000:
                        continue
                    
                    try:
                        raw_url = f"https://raw.githubusercontent.com/{self.user}/{repo_name}/HEAD/{item['path']}"
                        req = urllib.request.Request(raw_url, headers={"User-Agent": "GitHub-Stats"})
                        with urllib.request.urlopen(req) as resp:
                            content = resp.read().decode('utf-8', errors='ignore')
                        identifiers.extend(self._extract_identifiers(content, ext))
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
        return [{'name': name, 'count': count} for name, count in counts.most_common(6)]
    
    def _extract_identifiers(self, code, ext_type):
        identifiers = []
        
        if ext_type == 'python':
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                        identifiers.append(node.name)
                    elif isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                identifiers.append(target.id)
            except:
                identifiers = re.findall(r'\b([a-z_][a-z0-9_]*)\b', code.lower())
        
        elif ext_type == 'js':
            patterns = [r'(?:function|const|let|var|class)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)',
                       r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*[:=]\s*(?:function|async|\(|=>)']
            for pattern in patterns:
                identifiers.extend(re.findall(pattern, code))
        
        else:
            identifiers = re.findall(r'\b([a-z_][a-z0-9_]{2,})\b', code.lower())
        
        return [i for i in identifiers if len(i) > 2 and not i.isupper() and i not in 
                {'function', 'class', 'const', 'let', 'var', 'return', 'import', 'export'}]
    
    def render_body(self, stats):
        if not stats:
            return '<text x="20" y="60" class="stat-value">No code found.</text>', 40
        
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
        
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, max-age=0")
        self.end_headers()
        self.wfile.write(card.process().encode())
