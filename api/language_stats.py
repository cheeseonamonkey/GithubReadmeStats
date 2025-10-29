import os
import json
import urllib.request
from urllib.parse import parse_qs
import traceback

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

def fetch_languages(user):
    try:
        req = urllib.request.Request(
            f"https://api.github.com/users/{user}/repos?per_page=100",
            headers=HEADERS
        )
        with urllib.request.urlopen(req) as resp:
            repos = json.load(resp)
    except Exception as e:
        raise RuntimeError(f"Error fetching repos: {e}")

    langs = {}
    for repo in repos:
        if repo.get("fork"): 
            continue
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{user}/{repo['name']}/languages",
                headers=HEADERS
            )
            with urllib.request.urlopen(req) as resp:
                data = json.load(resp)
            for lang, bytes_ in data.items():
                langs[lang] = langs.get(lang, 0) + bytes_
        except Exception as e:
            raise RuntimeError(f"Error fetching languages for {repo['name']}: {e}")

    total = sum(langs.values()) or 1
    return [(l, round(b / total * 100, 1)) for l, b in sorted(langs.items(), key=lambda x: x[1], reverse=True)[:5]]


def generate_svg(user, langs=None, error=None):
    colors = {
        "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#2b7489",
        "Java": "#b07219", "C++": "#f34b7d", "C": "#555555",
        "Go": "#00ADD8", "Rust": "#dea584", "Ruby": "#701516", "PHP": "#4F5D95"
    }

    svg = ['<svg width="300" height="200" xmlns="http://www.w3.org/2000/svg">',
           '<rect width="300" height="200" fill="#0d1117" rx="4"/>']

    if error:
        svg.append(f'<text x="10" y="25" fill="#ff5555" font-family="sans-serif" font-size="12" font-weight="bold">'
                   f"Error for {user}</text>")
        lines = error.splitlines()
        y = 45
        for line in lines:
            if y > 180:
                break
            svg.append(f'<text x="10" y="{y}" fill="#ffbbbb" font-family="monospace" font-size="10">{line}</text>')
            y += 14
    else:
        svg.append(f'<text x="10" y="25" fill="#c9d1d9" font-family="sans-serif" font-size="14" font-weight="bold">'
                   f"{user}'s Top Languages</text>")
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


# Vercel serverless entrypoint
def handler(request, response):
    query = parse_qs(request.url.split("?", 1)[1]) if "?" in request.url else {}
    user = query.get("username", [""])[0]

    response.set_header("Content-Type", "image/svg+xml; charset=utf-8")

    if not user:
        svg = generate_svg("Unknown", error="Missing username parameter")
        response.status = 400
        response.send(svg)
        return

    try:
        langs = fetch_languages(user)
        svg = generate_svg(user, langs=langs)
        response.status = 200
        response.send(svg)
    except Exception:
        error_msg = traceback.format_exc()
        svg = generate_svg(user, error=error_msg)
        response.status = 500
        response.send(svg)
