from http.server import BaseHTTPRequestHandler
from .card import _respond_with_card


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _respond_with_card(self)
