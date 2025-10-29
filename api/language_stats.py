from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import urllib.request, json, os

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

def fetch_languages(user):
    repos = json.loads(urllib.request.urlopen(
        urllib.request.Request(
            f"https://api.github.com/users/{user}/repos?per_page=100",
            headers=HEADERS
        )
    ).read())

    langs = {}
    for repo in repos:
        if repo.get("fork"): continue
        data = json.loads(urllib.request.urlopen(
            urllib.request.Request(
                f"https://api.github.com/repos/{user}/{repo['name']}/languages",
                headers=HEADERS
            )
        ).read())
        for lang, bytes_ in data.items():
            langs[lang] = langs.get(lang, 0) + bytes_

    total = sum(langs.values()) or 1
    return [(l, round(b / total * 100, 1)) for l, b in sorted(langs.items(), key=lambda x: x[1], reverse=True)[:5]]

def generate_svg(user, langs):
    colors = {
        "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#2b7489",
        "Java": "#b07219", "C++": "#f34b7d", "C": "#555555",
        "Go": "#00ADD8", "Rust": "#dea584", "Ruby": "#701516", "PHP": "#4F5D95"
    }
    svg = [
        '<svg width="300" height="200" xmlns="http://www.w3.org/2000/svg">',
        '<rect width="300" height="200" fill="#0d1117" rx="4"/>',
        f'<text x="10" y="25" fill="#c9d1d9" font-family="sans-serif" font-size="14" font-weight="bold">'
        f"{user}'s Top Languages</text>"
    ]
    y = 50
    for lang, pct in langs:
        color = colors.get(lang, "#8b949e")
        svg.append(
            f'<rect x="10" y="{y}" width="{pct*2.5}" height="18" fill="{color}" rx="2"/>'
            f'<text x="15" y="{y+13}" fill="#c9d1d9" font-family="monospace" font-size="11">'
            f"{lang} {pct}%</text>"
        )
        y += 28
    svg.append('</svg>')
    return "\n".join(svg)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        user = parse_qs(urlparse(self.path).query).get("username", [""])[0]
        if not user:
            self.send_error(400, "Missing username parameter")
            return
        try:
            langs = fetch_languages(user)
            svg = generate_svg(user, langs)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(svg.encode())
        except Exception as e:
            self.send_error(500, str(e))
