"""
base.py

Defines the contract every website plugin must follow.

The key idea your instructor is asking for:
    - Each website (google, facebook, ...) gets its own plugin class.
    - The spider/CLI doesn't know HOW to parse Google vs Facebook HTML.
      It just knows: "call this plugin's parse() callback on the response
      I fetched, and it'll hand me back clean business records."
    - parse() is the "callback hook" -- it's the function that gets called
      back once the raw page data is available, and it's the ONLY part
      that differs between plugins.
"""

from abc import ABC, abstractmethod
import csv
import os


class BasePlugin(ABC):
    # Short identifier used on the CLI, e.g. "python scraper.py google"
    name: str = ""

    # Where this plugin's scraped businesses get written
    output_file: str = ""

    @abstractmethod
    def fetch(self, query: str, location: str = "") -> str:
        """
        Retrieve the raw HTML/JSON for this website.
        Returns raw text content (HTML string, JSON string, etc).
        """
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw: str) -> list[dict]:
        """
        THE CALLBACK HOOK.

        Takes raw content from fetch() and returns a list of normalized
        business dicts, e.g.:
            [{"name": "...", "address": "...", "phone": "...", "rating": "..."}]

        This is the only method that needs to change per website -- the
        rest of the pipeline (fetch -> parse -> save) is identical.
        """
        raise NotImplementedError

    def save(self, records: list[dict], output_path: str | None = None) -> None:
        """Write parsed records to CSV. Uses self.output_file unless
        output_path overrides it (e.g. a filename the user typed in)."""
        path = output_path or self.output_file
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        if not records:
            # Still create an (empty, headerless) file so the run is visible
            open(path, "w").close()
            return

        # Union of keys across all records, in first-seen order, so it
        # doesn't break if one record has an extra/missing field.
        fieldnames = list(dict.fromkeys(k for r in records for k in r.keys()))

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

    def run(self, query: str, location: str = "", output_path: str | None = None) -> list[dict]:
        """
        The pipeline every plugin runs through:
            fetch (get raw page) -> parse (callback hook) -> save (write file)
        """
        raw = self.fetch(query, location)
        records = self.parse(raw)          # <-- callback hook fires here
        for r in records:
            r.setdefault("source", self.name)
        self.save(records, output_path=output_path)
        return records

    def fetch_and_parse(self, query: str, location: str = "") -> list[dict]:
        """Just fetch+parse without saving -- used when the caller wants to
        run several queries (e.g. multiple business types) and combine
        all the records into one file itself."""
        raw = self.fetch(query, location)
        records = self.parse(raw)
        for r in records:
            r.setdefault("source", self.name)
        return records
