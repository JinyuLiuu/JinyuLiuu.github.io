import argparse
import json
import os
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

SCHOLAR_URL = (
    "https://scholar.google.com/citations"
    "?user={author_id}&hl=en&pagesize=100"
)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0 Safari/537.36"
)


class ScholarProfileParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.name = ""
        self.citation_values = []
        self.publications = {}
        self._capture = None
        self._buffer = []
        self._publication_id = None
        self._publication_title = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = attributes.get("class", "").split()

        if tag == "div" and attributes.get("id") == "gsc_prf_in":
            self._start_capture("name")
        elif tag == "td" and "gsc_rsb_std" in classes:
            self._start_capture("citation_total")
        elif tag == "a" and "gsc_a_at" in classes:
            query = parse_qs(urlparse(attributes.get("href", "")).query)
            self._publication_id = query.get("citation_for_view", [None])[0]
            self._start_capture("publication_title")
        elif tag == "a" and "gsc_a_ac" in classes:
            self._start_capture("publication_citations")

    def handle_endtag(self, tag):
        if self._capture == "name" and tag == "div":
            self.name = self._finish_capture()
        elif self._capture == "citation_total" and tag == "td":
            value = self._finish_capture()
            if value.isdigit():
                self.citation_values.append(int(value))
        elif self._capture == "publication_title" and tag == "a":
            self._publication_title = self._finish_capture()
        elif self._capture == "publication_citations" and tag == "a":
            value = self._finish_capture()
            self._store_publication(int(value) if value.isdigit() else 0)
        elif tag == "tr" and self._publication_id:
            self._store_publication(0)

    def handle_data(self, data):
        if self._capture:
            self._buffer.append(data)

    def _start_capture(self, capture_type):
        self._capture = capture_type
        self._buffer = []

    def _finish_capture(self):
        value = " ".join("".join(self._buffer).split())
        self._capture = None
        self._buffer = []
        return value

    def _store_publication(self, citations):
        if self._publication_id and self._publication_title:
            self.publications[self._publication_id] = {
                "author_pub_id": self._publication_id,
                "bib": {"title": self._publication_title},
                "num_citations": citations,
            }
        self._publication_id = None
        self._publication_title = None


def fetch_html(url, scraper_api_key=None):
    urls = [url]
    if scraper_api_key:
        urls.append(
            "https://api.scraperapi.com"
            f"?api_key={quote(scraper_api_key)}&url={quote(url, safe='')}"
        )

    last_error = None
    for candidate in urls:
        for attempt in range(3):
            try:
                request = Request(candidate, headers={"User-Agent": USER_AGENT})
                with urlopen(request, timeout=45) as response:
                    return response.read().decode("utf-8")
            except (HTTPError, URLError, TimeoutError) as error:
                last_error = error
                if attempt < 2:
                    time.sleep(2 ** attempt)
    raise RuntimeError(f"Unable to fetch Google Scholar profile: {last_error}")


def fetch_author(author_id, scraper_api_key=None):
    profile_url = SCHOLAR_URL.format(author_id=quote(author_id))
    parser = ScholarProfileParser()
    parser.feed(fetch_html(profile_url, scraper_api_key))

    if not parser.name or not parser.citation_values:
        raise RuntimeError("Google Scholar returned an incomplete profile page")

    return {
        "name": parser.name,
        "citedby": parser.citation_values[0],
        "updated": datetime.now(timezone.utc).isoformat(),
        "publications": parser.publications,
    }


def load_fallback(output_dir, fallback_path):
    candidates = [Path(fallback_path)] if fallback_path else []
    candidates.append(output_dir / "gs_data.json")
    for path in candidates:
        if path.is_file():
            with path.open(encoding="utf-8") as infile:
                return json.load(infile)
    return None


def write_json(path, data):
    with path.open("w", encoding="utf-8") as outfile:
        json.dump(data, outfile, ensure_ascii=False, indent=2)
        outfile.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Directory for the generated citation JSON files",
    )
    args = parser.parse_args()

    author_id = os.environ.get("GOOGLE_SCHOLAR_ID", "oPK92GMAAAAJ")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    previous_author = load_fallback(
        output_dir, os.environ.get("FALLBACK_DATA_PATH")
    )

    try:
        author = fetch_author(author_id, os.environ.get("SCRAPER_API_KEY"))
        print(
            f"Fetched {author['citedby']} citations and "
            f"{len(author['publications'])} publications for {author['name']}."
        )
    except RuntimeError as error:
        if previous_author is None:
            raise
        print(f"Warning: {error}. Keeping the last valid citation data.")
        return

    if previous_author and all(
        author[field] == previous_author.get(field)
        for field in ("name", "citedby", "publications")
    ):
        print("Citation data is unchanged.")
        return

    write_json(output_dir / "gs_data.json", author)
    write_json(
        output_dir / "gs_data_shieldsio.json",
        {
            "schemaVersion": 1,
            "label": "citations",
            "message": str(author["citedby"]),
        },
    )


if __name__ == "__main__":
    main()
