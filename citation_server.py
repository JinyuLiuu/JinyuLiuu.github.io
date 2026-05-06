#!/usr/bin/env python3
"""Local citation server: fetches Google Scholar citation count on startup and serves it."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os
from scholarly import scholarly

SCHOLAR_ID = os.environ.get("GOOGLE_SCHOLAR_ID", "oPK92GMAAAAJ")
PORT = 5001

print(f"Fetching citations for {SCHOLAR_ID}...")
try:
    author = scholarly.search_author_id(SCHOLAR_ID)
    scholarly.fill(author, sections=["indices"])
    citations = author.get("citedby", 0)
    print(f"Citations: {citations}")
except Exception as e:
    citations = 83  # fallback to last known value
    print(f"Fetch failed ({e}), using cached value: {citations}")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"citations": citations}).encode())

    def log_message(self, *args):
        pass  # suppress request logs

print(f"Citation server running at http://localhost:{PORT}")
HTTPServer(("", PORT), Handler).serve_forever()
