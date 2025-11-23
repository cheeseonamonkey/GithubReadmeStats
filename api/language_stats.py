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
# 1. THE ABSTRACT BASE CLASS (STYLING ENGINE)
# ==========================================
class GitHubCardBase:
    # Color Themes (Easy to swap)
    THEMES = {
        "default": {
            "bg_gradient": ["#141321", "#1e1c30"], # Dark Violet/Black
            "title": "#a9fef7",
            "text": "#c9d1d9",
            "icon": "#a9fef7",
            "border": "#2c2b3b"
        },
        "light": {
            "bg_gradient": ["#ffffff", "#f5f5f5"],
            "title": "#2f80ed",
            "text": "#434d58",
            "icon": "#2f80ed",
            "border": "#e4e2e2"
        }
    }

    def __init__(self, username, query_params):
        self.user = username
        self.params = query_params
        self.theme = self.THEMES.get(query_params.get("theme", ["default"])[0], self.THEMES["default"])
        
        # Dimensions
        self.card_width = 400 # Wider for the grid layout
        self.padding = 25
        
    def _make_request(self, url):
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)

    def _get_css(self):
        """Returns the CSS block with animations and theme colors."""
        return f"""
        <style>
            .header {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: {self.theme['title']}; }}
            .stat-text {{ font: 600 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: {self.theme['text']}; }}
            .sub-text {{ font: 400 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: {self.theme['text']}; opacity: 0.7; }}
            
            /* Animations */
            @keyframes fadein {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
            .anim-delay-1 {{ animation: fadein 0.6s ease-in-out forwards; }}
            .anim-delay-2 {{ animation: fadein 0.7s ease-in-out 0.2s forwards; opacity: 0; }}
            .anim-delay-3 {{ animation: fadein 0.8s ease-in-out 0.4s forwards; opacity: 0; }}
        </style>
        """

    def _render_frame(self, title, body_content, content_height):
        total_height = content_height + (self.padding * 2) + 20 # +20 for header space
        
        # Gradient Definition
        grad_id = "grad1"
        bg_rect = f"""
        <defs>
            <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:{self.theme['bg_gradient'][0]};stop-opacity:1" />
                <stop offset="100%" style="stop-color:{self.theme['bg_gradient'][1]};stop-opacity:1" />
            </linearGradient>
        </defs>
        <rect width="{self.card_width}" height="{total_height}" fill="url(#{grad_id})" rx="10" stroke="{self.theme['border']}" stroke-width="1"/>
        """

        return f"""
        <svg width="{self.card_width}" height="{total_height}" viewBox="0 0 {self.card_width} {total_height}" xmlns="http://www.w3.org/2000/svg">
            {self._get_css()}
            {bg_rect}
            
            <g transform="translate({self.padding}, 35)">
                <text x="0" y="0" class="header">{escape_xml(title)}</text>
            </g>

            <g transform="translate({self.padding}, 60)">
                {body_content}
            </g>
        </svg>
        """

    def _render_error(self, error_msg):
        # Simplified error view
        return f'<svg width="400" height="100" xmlns="http://www.w3.org/2000/svg"><text x="10" y="20" fill="red">Error: {escape_xml(error_msg)}</text></svg>'

    def fetch_data(self):
        raise NotImplementedError

    def render_body(self, data):
        raise NotImplementedError

    def process(self):
        if not self.user: return self._render_error("Missing ?username=")
        try:
            data = self.fetch_data()
            body, height = self.render_body(data)
            return self._render_frame(f"{self.user}'s Top Languages", body, height)
        except Exception:
            return self._render_error(traceback.format_exc())


# ==========================================
# 2. THE TOP LANGUAGES CARD (MODERN GRID LAYOUT)
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
        # Same Logic as before, just kept clean here
        try:
            repos_url = f"https://api.github.com/users/{self.user}/repos?per_page=100&type=owner"
            repos = self._make_request(repos_url)
        except urllib.error.HTTPError as e: raise RuntimeError(f"API Error: {e.code}")

        repo_names = [r['name'] for r in repos if not r.get('fork')]
        lang_stats = {}

        def fetch_repo_lang(user, repo):
            try: return self._make_request(f"https://api.github.com/repos/{user}/{repo}/languages")
            except: return {}

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_repo = {executor.submit(fetch_repo_lang, self.user, name): name for name in repo_names}
            for future in as_completed(future_to_repo):
                data = future.result()
                for lang, count in data.items():
                    lang_stats[lang] = lang_stats.get(lang, 0) + count

        if not lang_stats: return []

        total_bytes = sum(lang_stats.values())
        sorted_langs = sorted(lang_stats.items(), key=lambda x: x[1], reverse=True)[:8] # Top 8 now
        
        return [{
            "name": lang,
            "fmt_bytes": format_bytes(count),
            "percent": round((count / total_bytes) * 100, 1),
            "color": self.LANG_COLORS.get(lang, "#8b949e")
        } for lang, count in sorted_langs]

    def render_body(self, stats):
        if not stats: return '<text class="stat-text">No data</text>', 50

        # Constants for layout
        progress_bar_width = 350
        progress_bar_height = 10
        col_gap = 20
        row_height = 25
        
        svg_parts = []
        
        # 1. The Master Progress Bar (Multi-colored)
        # ------------------------------------------
        current_x = 0
        bars_svg = []
        
        for lang in stats:
            width = (lang['percent'] / 100) * progress_bar_width
            # Ensure very small percentages are at least visible or skipped if too small
            if width < 2: continue 
            
            bars_svg.append(f'<rect x="{current_x}" y="0" width="{width}" height="{progress_bar_height}" fill="{lang["color"]}" />')
            current_x += width

        # Mask/Container for the progress bar to give it rounded corners
        svg_parts.append(f'''
        <g class="anim-delay-1">
            <mask id="bar-mask"><rect x="0" y="0" width="{progress_bar_width}" height="{progress_bar_height}" rx="5" fill="white" /></mask>
            <g mask="url(#bar-mask)">
                <rect x="0" y="0" width="{progress_bar_width}" height="{progress_bar_height}" fill="#333" />
                {''.join(bars_svg)}
            </g>
        </g>
        ''')

        # 2. The Language Grid (2 Columns)
        # --------------------------------
        y_offset = 30 # Start below progress bar
        
        for i, lang in enumerate(stats):
            col = i % 2 # 0 for left, 1 for right
            row = i // 2
            
            x_pos = 0 if col == 0 else (progress_bar_width / 2) + col_gap
            y_pos = y_offset + (row * row_height)
            
            # Label generation
            label_text = f"{lang['name']}"
            percent_text = f"{lang['percent']}%"

            svg_parts.append(f'''
            <g transform="translate({x_pos}, {y_pos})" class="anim-delay-2">
                <circle cx="5" cy="6" r="5" fill="{lang['color']}" />
                
                <text x="15" y="10" class="stat-text">{escape_xml(label_text)}</text>
                
                <text x="{(progress_bar_width/2) - 10}" y="10" class="sub-text" text-anchor="end">{percent_text}</text>
            </g>
            ''')

        # Calculate final height needed
        rows_count = (len(stats) + 1) // 2
        total_content_height = 30 + (rows_count * row_height)
        
        return "\n".join(svg_parts), total_content_height

# ==========================================
# 3. HANDLER
# ==========================================
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query) if "?" in self.path else {}
        user = query.get("username", [""])[0]
        
        # Instantiate and process
        card = TopLanguagesCard(user, query)
        svg_content = card.process()

        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, max-age=0")
        self.end_headers()
        self.wfile.write(svg_content.encode())
