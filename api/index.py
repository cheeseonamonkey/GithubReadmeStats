# api/index.py

from http.server import BaseHTTPRequestHandler

HTML = """<!DOCTYPE html>
<html><head>
<meta charset=\"utf-8\"><title>GitHub Stats Cards</title>
<style>
body { font-family: system-ui, sans-serif; background: #0d1117; color: #c9d1d9; max-width: 820px; margin: 40px auto; padding: 20px; }
a { color: #58a6ff; } code { background: #21262d; padding: 2px 6px; border-radius: 4px; }
pre { background: #161b22; padding: 16px; border-radius: 6px; overflow-x: auto; }
h1 { border-bottom: 1px solid #30363d; padding-bottom: 10px; }
.endpoint { margin: 20px 0; padding: 16px; background: #161b22; border-radius: 6px; border-left: 3px solid #58a6ff; }
</style>
</head><body>
<h1>GitHub Stats Cards API</h1>
<p>SVG card generator for GitHub profile stats. Embed in READMEs or anywhere that renders images.</p>

<div class=\"endpoint\">
<h3>GET <code>/api/language_stats</code></h3>
<p>Top programming languages by bytes across repos.</p>
<pre>?username=octocat
&amp;mode=percent|bytes|both
&amp;width=350</pre>
</div>

<div class=\"endpoint\">
<h3>GET <code>/api/code_identifiers</code></h3>
<p>Most frequent identifiers across Python, JavaScript/TypeScript, Java, Kotlin, C#, Go, C/C++, PHP, Ruby, and Swift.</p>
<pre>?username=octocat</pre>
</div>

<div class=\"endpoint\">
<h3>GET <code>/api/code_identifiers/identifiers</code></h3>
<p>Alias endpoint for the identifiers card.</p>
<pre>?username=octocat</pre>
</div>

<h3>Example</h3>
<pre>&lt;img src=\"https://your-domain.vercel.app/api/code_identifiers?username=octocat\" /&gt;</pre>

<p><a href=\"https://github.com/your-repo\">Source</a></p>
</body></html>"""

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode())
