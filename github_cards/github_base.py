# github_base.py

import os
import json
import urllib.request
import urllib.error
import traceback

# --- SHARED CONFIG ---
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {TOKEN}", "User-Agent": "GitHub-Stats-Card"} if TOKEN else {"User-Agent": "GitHub-Stats-Card"}

# --- UTILITIES ---
def escape_xml(text):
    """Sanitize text for SVG output."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def format_bytes(size):
    """Converts raw bytes into human readable format (KB, MB)."""
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
                .stat-name {{ font: 600 13px "Segoe UI", Ubuntu, Sans-Serif; fill: #c9d1d9; }}
                .stat-value {{ font: 400 12px "Segoe UI", Ubuntu, Sans-Serif; fill: #8b949e; }}
            </style>
            <rect width="{self.card_width}" height="{total_height}" fill="#0d1117" rx="6" stroke="#30363d" stroke-width="1"/>
            <text x="{self.padding}" y="30" class="title">{escape_xml(title)}</text>
            <g transform="translate(0, {self.header_height - 10})">
            {body_content}
            </g>
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
            # The 'render_body' now just returns the SVG content and the height of that content
            body, height = self.render_body(data)
            # The frame method handles wrapping the body and calculating the full card height
            return self._render_frame(f"{self.user}'s Top Languages", body, height)
        except Exception:
            return self._render_error(traceback.format_exc())
