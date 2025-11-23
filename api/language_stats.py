import os
import json
import urllib.request
import urllib.error
from urllib.parse import parse_qs, urlparse
import traceback
from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION ---
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {TOKEN}", "User-Agent": "GitHub-Stats-Card"} if TOKEN else {"User-Agent": "GitHub-Stats-Card"}
MAX_WORKERS = 10  # For parallel API calls

# GitHub standard language colors
LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#2b7489",
    "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "C#": "#178600",
    "Go": "#00ADD8", "Rust": "#dea584", "Ruby": "#701516", "PHP": "#4F5D95",
    "HTML": "#e34c26", "CSS": "#563d7c", "Shell": "#89e051", "Swift": "#F05138"
}

# --- UTILITIES ---

def make_request(url):
    """Helper to make HTTP requests using standard library."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)

def format_bytes(size):
    """Converts raw bytes into human readable format (KB, MB)."""
    power = 2**10
    n = 0
    power_labels = {0: '', 1: 'KB', 2: 'MB', 3: 'GB'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.1f} {power_labels.get(n, '')}"

def escape_xml(text):
    """Sanitize text for SVG."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

# --- DATA FETCHING ---

def fetch_repo_languages(user, repo_name):
    """Fetches language data for a single repo."""
    try:
        url = f"https://api.github.com/repos/{user}/{repo_name}/languages"
        return make_request(url)
    except Exception:
        return {}

def get_user_stats(user):
    """
    Fetches repos and aggregates language bytes.
    Uses ThreadPoolExecutor for parallel fetching.
    """
    try:
        # 1. Get list of repos (limit to 100 to avoid rate limits on simple scripts)
        repos_url = f"https://api.github.com/users/{user}/repos?per_page=100&type=owner"
        repos = make_request(repos_url)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub API Error: {e.code} {e.reason}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch repos: {str(e)}")

    lang_stats = {}
    repo_names = [r['name'] for r in repos if not r.get('fork')]

    # 2. Fetch languages in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_repo = {executor.submit(fetch_repo_languages, user, name): name for name in repo_names}
        
        for future in as_completed(future_to_repo):
            data = future.result()
            for lang, bytes_count in data.items():
                lang_stats[lang] = lang_stats.get(lang, 0) + bytes_count

    if not lang_stats:
        return []

    # 3. Calculate percentages and sort
    total_bytes = sum(lang_stats.values())
    sorted_langs = sorted(lang_stats.items(), key=lambda item: item[1], reverse=True)[:6] # Top 6

    result = []
    for lang, count in sorted_langs:
        result.append({
            "name": lang,
            "bytes": count,
            "fmt_bytes": format_bytes(count),
            "percent": round((count / total_bytes) * 100, 1),
            "color": LANG_COLORS.get(lang, "#8b949e")
        })
        
    return result

# --- SVG GENERATION ---

def render_svg(user, stats, mode="percent", error=None):
    """
    Renders the SVG.
    mode options: 'percent', 'bytes', 'both'
    """
    # --- Error State ---
    if error:
        lines = str(error).splitlines()[:5] # Limit error length
        height = 60 + (len(lines) * 20)
        svg_content = [
            f'<svg width="400" height="{height}" xmlns="http://www.w3.org/2000/svg">',
            f'<style>.header {{ font: 600 14px "Segoe UI", Ubuntu, Sans-Serif; fill: #ff5555; }} .text {{ font: 400 12px monospace; fill: #f85149; }}</style>',
            f'<rect width="400" height="{height}" fill="#0d1117" rx="6" stroke="#30363d"/>',
            f'<text x="20" y="30" class="header">Error fetching data for {escape_xml(user)}</text>'
        ]
        y = 60
        for line in lines:
            svg_content.append(f'<text x="20" y="{y}" class="text">{escape_xml(line)}</text>')
            y += 20
        svg_content.append('</svg>')
        return "\n".join(svg_content)

    # --- Success State ---
    card_width = 350
    row_height = 35
    padding = 20
    header_height = 40
    total_height = header_height + (len(stats) * row_height) + padding
    
    svg = [
        f'<svg width="{card_width}" height="{total_height}" viewBox="0 0 {card_width} {total_height}" xmlns="http://www.w3.org/2000/svg">',
        '<style>',
        '.title { font: 600 16px "Segoe UI", Ubuntu, Sans-Serif; fill: #c9d1d9; }',
        '.lang-name { font: 600 13px "Segoe UI", Ubuntu, Sans-Serif; fill: #c9d1d9; }',
        '.stats { font: 400 12px "Segoe UI", Ubuntu, Sans-Serif; fill: #8b949e; }',
        '</style>',
        f'<rect width="{card_width}" height="{total_height}" fill="#0d1117" rx="6" stroke="#30363d" stroke-width="1"/>',
        f'<text x="{padding}" y="30" class="title">{escape_xml(user)}\'s Top Languages</text>'
    ]

    y_offset = 55
    
    for lang in stats:
        # Determine label based on mode
        if mode == "bytes":
            label = lang['fmt_bytes']
        elif mode == "both":
            label = f"{lang['percent']}% ({lang['fmt_bytes']})"
        else: # default to percent
            label = f"{lang['percent']}%"

        # Progress bar calculation
        bar_width_max = 150
        bar_width = (lang['percent'] / 100) * bar_width_max
        
        svg.append(f'''
        <g transform="translate({padding}, {y_offset})">
            <text x="0" y="10" class="lang-name">{escape_xml(lang['name'])}</text>
            
            <rect x="80" y="0" width="{bar_width_max}" height="10" rx="3" fill="#21262d" />
            
            <rect x="80" y="0" width="{max(bar_width, 2)}" height="10" rx="3" fill="{lang['color']}" />
            
            <text x="{90 + bar_width_max}" y="9" class="stats">{escape_xml(label)}</text>
        </g>
        ''')
        y_offset += row_height

    svg.append('</svg>')
    return "\n".join(svg)

# --- SERVER HANDLER ---

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse Query
        query = parse_qs(urlparse(self.path).query) if "?" in self.path else {}
        user = query.get("username", [""])[0]
        mode = query.get("mode", ["percent"])[0].lower() # options: percent, bytes, both
        
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, max-age=0") # GitHub caches heavily, this helps
        self.end_headers()

        if not user:
            svg = render_svg("Unknown", [], error="Missing ?username= parameter")
            self.wfile.write(svg.encode())
            return

        try:
            stats = get_user_stats(user)
            svg = render_svg(user, stats, mode=mode)
            self.wfile.write(svg.encode())
        except Exception:
            # Catch-all for bugs or API limits
            svg = render_svg(user, [], error=traceback.format_exc())
            self.wfile.write(svg.encode())
