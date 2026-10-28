#!/usr/bin/env python3
"""Local citation server: fetches Google Scholar citation count on startup and serves it."""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from google_scholar_crawler.main import fetch_author

SCHOLAR_ID = os.environ.get("GOOGLE_SCHOLAR_ID", "oPK92GMAAAAJ")
PORT = 5001
citations = 0


def cached_citations():
    path = Path(__file__).parent / "google-scholar-stats/gs_data_shieldsio.json"
    try:
        with path.open(encoding="utf-8") as infile:
            return int(json.load(infile)["message"])
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        return 0


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"citations": citations}).encode())

    def log_message(self, *args):
        pass  # suppress request logs


def main():
    global citations

    print(f"Fetching citations for {SCHOLAR_ID}...")
    try:
        author = fetch_author(SCHOLAR_ID, os.environ.get("SCRAPER_API_KEY"))
        citations = author["citedby"]
        print(f"Citations: {citations}")
    except RuntimeError as error:
        citations = cached_citations()
        print(f"Fetch failed ({error}), using cached value: {citations}")

    print(f"Citation server running at http://localhost:{PORT}")
    HTTPServer(("", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
