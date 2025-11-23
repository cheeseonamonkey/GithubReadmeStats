# language_card.py

import .github_base 
import json
import urllib.request
import urllib.error
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# 2. THE CONCRETE IMPLEMENTATION (Languages)
# ==========================================
class TopLanguagesCard(GitHubCardBase):
    MAX_WORKERS = 10
    # Defined here so it's encapsulated with the Language Card logic
    LANG_COLORS = {
        "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#2b7489",
        "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "C#": "#178600",
        "Go": "#00ADD8", "Rust": "#dea584", "Ruby": "#701516", "PHP": "#4F5D95",
        "HTML": "#e34c26", "CSS": "#563d7c", "Shell": "#89e051", "Swift": "#F05138"
    }

    def fetch_data(self):
        # Implementation is concise, using inherited methods
        try:
            repos_url = f"https://api.github.com/users/{self.user}/repos?per_page=100&type=owner"
            repos = self._make_request(repos_url)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"GitHub API Error: {e.code} {e.reason}")

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
        sorted_langs = sorted(lang_stats.items(), key=lambda x: x[1], reverse=True)[:6] # Top 6
        
        return [{
            "name": lang,
            "fmt_bytes": format_bytes(count),
            "percent": round((count / total_bytes) * 100, 1),
            "color": self.LANG_COLORS.get(lang, "#8b949e")
        } for lang, count in sorted_langs]

    def render_body(self, stats):
        if not stats:
            return '<text x="20" y="60" class="stat-value">No language data found.</text>', 40

        mode = self.params.get("mode", ["percent"])[0].lower()
        
        # --- RESTYLED BAR CHART CONSTANTS ---
        bar_height = 12 
        bar_width_max = 200 # Slightly wider bar
        vertical_margin = 8 # Less vertical space
        row_height = bar_height + vertical_margin 
        
        y_offset_initial = 10 # Start closer to the header
        svg_parts = []

        for i, lang in enumerate(stats):
            y_offset = y_offset_initial + (i * row_height)
            
            # Logic for label
            if mode == "bytes": label = lang['fmt_bytes']
            elif mode == "both": label = f"{lang['percent']}% ({lang['fmt_bytes']})"
            else: label = f"{lang['percent']}%"

            bar_width = (lang['percent'] / 100) * bar_width_max
            
            svg_parts.append(f'''
            <g transform="translate({self.padding}, {y_offset})">
                <text x="0" y="{bar_height - 2}" class="stat-name">{escape_xml(lang['name'])}</text>
                
                <rect x="100" y="0" width="{bar_width_max}" height="{bar_height}" rx="3" fill="#21262d" />
                <rect x="100" y="0" width="{max(bar_width, 2)}" height="{bar_height}" rx="3" fill="{lang['color']}" />
                
                <text x="{100 + bar_width_max + 10}" y="{bar_height - 2}" class="stat-value">{escape_xml(label)}</text>
            </g>
            ''')
            
        # Total height of the content block
        content_height = len(stats) * row_height + y_offset_initial
        return "\n".join(svg_parts), content_height

# ==========================================
# 3. THE HANDLER
# ==========================================
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query) if "?" in self.path else {}
        user = query.get("username", [""])[0]
        card_type = query.get("type", ["languages"])[0] 

        # Route to the correct card implementation
        if card_type == "languages":
            card = TopLanguagesCard(user, query)
        else:
            # Fallback/default logic
            card = TopLanguagesCard(user, query) 

        svg_content = card.process()

        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, max-age=0")
        self.end_headers()
        self.wfile.write(svg_content.encode())
