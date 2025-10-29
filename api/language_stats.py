from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, urllib.request, os

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

def fetch_languages(username):
    req = urllib.request.Request(
        f"https://api.github.com/users/{username}/repos?per_page=100",
        headers=HEADERS
    )
    repos = json.loads(urllib.request.urlopen(req).read())

    langs = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        r = urllib.request.Request(
            f"https://api.github.com/repos/{username}/{repo['name']}/languages",
            headers=HEADERS
        )
        for lang, bytes_ in json.loads(urllib.request.urlopen(r).read()).items():
            langs[lang] = langs.get(lang, 0) + bytes_

    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda x: x[1], reverse=True)[:5]
    return [(l, round(b / total * 100, 1)) for l, b in top]

def generate_svg(username, languages):
    colors = {
        "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#2b7489",
        "Java": "#b07219", "C++": "#f34b7d", "C": "#555555",
        "Go": "#00ADD8", "Rust": "#dea584", "Ruby": "#701516", "PHP": "#4F5D95"
    }
    svg = [f'<svg width="300" height="200" xmlns="http://www.w3.org/2000/svg">',
           '<rect width="300" height="200" fill="#0d1117" rx="4"/>',
           f'<text x="10" y="25" fill="#c9d1d9" font-family="sans-serif" font-size="14" font-weight="bold">'
           f"{username}'s Top Languages</text>"]
    y = 50
    for lang, pct in languages:
        color = colors.get(lang, "#8b949e")
        svg.append(f'<rect x="10" y="{y}" width="{pct*2.5}" height="18" fill="{color}" rx="2"/>'
                   f'<text x="15" y="{y+13}" fill="#c9d1d9" font-family="monospace" font-size="11">'
                   f"{lang} {pct}%</text>")
        y += 28
    svg.append('</svg>')
    return "\n".join(svg)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        username = parse_qs(urlparse(self.path).query).get("username", [""])[0]
        if not username:
            self.send_error(400, "Missing username parameter")
            return
        try:
            langs = fetch_languages(username)
            svg = generate_svg(username, langs)
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Cache-Control", "max-age=3600")
            self.end_headers()
            self.wfile.write(svg.encode())
        except Exception as e:
            self.send_error(500, str(e))
