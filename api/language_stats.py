import os
import json
import urllib.request
import urllib.error
from urllib.parse import parse_qs, urlparse
import traceback
from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- SHARED CONFIG ---
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {TOKEN}", "User-Agent": "GitHub-Stats-Card"} if TOKEN else {"User-Agent": "GitHub-Stats-Card"}

# --- UTILITIES ---
def escape_xml(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def format_bytes(size):
    power = 2**10
    n = 0
    power_labels = {0: '', 1: 'KB', 2: 'MB', 3: 'GB'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.1f} {power_labels.get(n, '')}"

# ==========================================
# 1. THE ABSTRACT BASE CLASS
# ==========================================
class GitHubCardBase:
    def __init__(self, username, query_params):
        self.user = username
        self.params = query_params
        # Default styling constants
        self.card_width = 350
        self.padding = 20
        self.header_height = 40
        
    def _make_request(self, url):
        """Shared HTTP handler with Authentication."""
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)

    def _render_error(self, error_msg):
        """Standardized error card."""
        lines = str(error_msg).splitlines()[:5]
        height = 60 + (len(lines) * 20)
        return f"""
        <svg width="400" height="{height}" xmlns="http://www.w3.org/2000/svg">
            <style>.header {{ font: 600 14px "Segoe UI", Ubuntu, Sans-Serif; fill: #ff5555; }} .text {{ font: 400 12px monospace; fill: #f85149; }}</style>
            <rect width="400" height="{height}" fill="#0d1117" rx="6" stroke="#30363d"/>
            <text x="20" y="30" class="header">Error: {escape_xml(self.user)}</text>
            {''.join([f'<text x="20" y="{60 + i*20}" class="text">{escape_xml(line)}</text>' for i, line in enumerate(lines)])}
        </svg>
        """

    def _render_frame(self, title, body_content, content_height):
        """Wraps specific content in the standard card design."""
        total_height = self.header_height + content_height + self.padding
        
        return f"""
        <svg width="{self.card_width}" height="{total_height}" viewBox="0 0 {self.card_width} {total_height}" xmlns="http://www.w3.org/2000/svg">
            <style>
                .title {{ font: 600 16px "Segoe UI", Ubuntu, Sans-Serif; fill: #c9d1d9; }}
                .lang-name {{ font: 600 13px "Segoe UI", Ubuntu, Sans-Serif; fill: #c9d1d9; }}
                .stats {{ font: 400 12px "Segoe UI", Ubuntu, Sans-Serif; fill: #8b949e; }}
            </style>
            <rect width="{self.card_width}" height="{total_height}" fill="#0d1117" rx="6" stroke="#30363d" stroke-width="1"/>
            <text x="{self.padding}" y="30" class="title">{escape_xml(title)}</text>
            {body_content}
        </svg>
        """

    def fetch_data(self):
        """Override this method to fetch data from GitHub."""
        raise NotImplementedError

    def render_body(self, data):
        """Override this method to generate SVG body content. Returns (svg_str, height_int)."""
        raise NotImplementedError

    def process(self):
        """Main execution flow."""
        if not self.user:
            return self._render_error("Missing ?username= parameter")
        try:
            data = self.fetch_data()
            body, height = self.render_body(data)
            return self._render_frame(f"{self.user}'s Stats", body, height)
        except Exception:
            return self._render_error(traceback.format_exc())

# ==========================================
# 2. THE CONCRETE IMPLEMENTATION (Languages)
# ==========================================
class TopLanguagesCard(GitHubCardBase):
    MAX_WORKERS = 10
    LANG_COLORS = {
        "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#2b7489",
        "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "C#": "#178600",
        "Go": "#00ADD8", "Rust": "#dea584", "Ruby": "#701516", "PHP": "#4F5D95",
        "HTML": "#e34c26", "CSS": "#563d7c", "Shell": "#89e051", "Swift": "#F05138"
    }

    def fetch_data(self):
        # 1. Fetch Repos
        try:
            repos_url = f"https://api.github.com/users/{self.user}/repos?per_page=100&type=owner"
            repos = self._make_request(repos_url)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"GitHub API Error: {e.code} {e.reason}")

        repo_names = [r['name'] for r in repos if not r.get('fork')]
        lang_stats = {}

        # 2. Helper for Threading
        def fetch_repo_lang(user, repo):
            try:
                return self._make_request(f"https://api.github.com/repos/{user}/{repo}/languages")
            except: return {}

        # 3. Parallel Fetch
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_repo = {executor.submit(fetch_repo_lang, self.user, name): name for name in repo_names}
            for future in as_completed(future_to_repo):
                data = future.result()
                for lang, count in data.items():
                    lang_stats[lang] = lang_stats.get(lang, 0) + count

        if not lang_stats: return []

        # 4. Process Logic
        total_bytes = sum(lang_stats.values())
        sorted_langs = sorted(lang_stats.items(), key=lambda x: x[1], reverse=True)[:6]
        
        return [{
            "name": lang,
            "fmt_bytes": format_bytes(count),
            "percent": round((count / total_bytes) * 100, 1),
            "color": self.LANG_COLORS.get(lang, "#8b949e")
        } for lang, count in sorted_langs]

    def render_body(self, stats):
        if not stats:
            return '<text x="20" y="60" class="stats">No language data found.</text>', 40

        mode = self.params.get("mode", ["percent"])[0].lower()
        row_height = 35
        y_offset = 55
        svg_parts = []

        for lang in stats:
            # Logic for label
            if mode == "bytes": label = lang['fmt_bytes']
            elif mode == "both": label = f"{lang['percent']}% ({lang['fmt_bytes']})"
            else: label = f"{lang['percent']}%"

            bar_width = (lang['percent'] / 100) * 150
            
            svg_parts.append(f'''
            <g transform="translate({self.padding}, {y_offset})">
                <text x="0" y="10" class="lang-name">{escape_xml(lang['name'])}</text>
                <rect x="80" y="0" width="150" height="10" rx="3" fill="#21262d" />
                <rect x="80" y="0" width="{max(bar_width, 2)}" height="10" rx="3" fill="{lang['color']}" />
                <text x="240" y="9" class="stats">{escape_xml(label)}</text>
            </g>
            ''')
            y_offset += row_height
            
        return "\n".join(svg_parts), (len(stats) * row_height)

# ==========================================
# 3. THE HANDLER
# ==========================================
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query) if "?" in self.path else {}
        user = query.get("username", [""])[0]
        card_type = query.get("type", ["languages"])[0] # Allow switching types

        # Route to the correct card implementation
        if card_type == "languages":
            card = TopLanguagesCard(user, query)
        else:
            # Example of how you would extend this:
            # card = UserOverviewCard(user, query)
            card = TopLanguagesCard(user, query) # Default fallback

        svg_content = card.process()

        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, max-age=0")
        self.end_headers()
        self.wfile.write(svg_content.encode())
