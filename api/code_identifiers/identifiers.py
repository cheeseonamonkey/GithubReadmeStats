from http.server import BaseHTTPRequestHandler
from github_cards.code_identifiers import _respond_with_card


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _respond_with_card(self)
