"""
google_plugin.py

Real, live-fetching plugin for Google Maps business listings.

Google Maps results are rendered with JavaScript, so plain requests.get()
won't see them -- this uses Selenium to actually load the page in a
headless Chrome browser, scroll the results panel to load more cards,
then hand the rendered HTML to parse().

NOTE ON SELECTORS: Google Maps' CSS class names are auto-generated and
DO change over time (e.g. "Nv2PK", "qBF1Pd" below). If parse() suddenly
returns empty results, that's almost always the fix needed: open Maps
in a real browser, right-click a result -> Inspect, and update the
selectors in parse() to match.
"""

import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

from .base import BasePlugin


class GooglePlugin(BasePlugin):
    name = "google"
    output_file = os.path.join(
        os.path.dirname(__file__), "..", "output", "google_businesses.csv"
    )

    def fetch(self, query: str, location: str = "") -> str:
        search_term = f"{query} {location}".strip()
        url = f"https://www.google.com/maps/search/{search_term.replace(' ', '+')}"

        driver = self._make_driver()
        try:
            driver.get(url)
            time.sleep(4)  # let the initial results render

            self._scroll_results_panel(driver, pause=2.0, max_scrolls=6)

            return driver.page_source
        finally:
            driver.quit()

    def _make_driver(self):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,1600")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def _scroll_results_panel(self, driver, pause: float, max_scrolls: int):
        """Google Maps lazy-loads more result cards as you scroll the
        left-hand results panel, not the whole page."""
        try:
            panel = driver.find_element(By.CSS_SELECTOR, 'div[role="feed"]')
        except Exception:
            return  # panel not found -- likely a layout change, skip scrolling

        for _ in range(max_scrolls):
            driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight", panel
            )
            time.sleep(pause)

    def parse(self, raw: str) -> list[dict]:
        """The callback hook: turns the rendered Maps HTML into business dicts."""
        soup = BeautifulSoup(raw, "html.parser")
        records = []

        # Nv2PK is (as of writing) Google Maps' result-card container class.
        for card in soup.select("div.Nv2PK"):
            name_el = card.select_one(".qBF1Pd")
            rating_el = card.select_one("span.MW4etd")
            reviews_el = card.select_one("span.UY7F9")

            # Address/category/phone all sit in generic "W4Efsd" rows with
            # no unique class, separated by "·" -- pull them out as text.
            detail_rows = card.select("div.W4Efsd > span")
            detail_text = " ".join(el.get_text(" ", strip=True) for el in detail_rows)

            records.append({
                "name": name_el.get_text(strip=True) if name_el else "",
                "rating": rating_el.get_text(strip=True) if rating_el else "",
                "reviews": reviews_el.get_text(strip=True).strip("()") if reviews_el else "",
                "details": detail_text,  # raw text containing category/address/phone
            })

        return records


# ---------------------------------------------------------------------------
# RECOMMENDED ALTERNATIVE: the official Google Places API is far more
# reliable than scraping (no selector breakage, no blocking) if you can
# get an API key (free tier available):
#
#   def fetch(self, query, location=""):
#       import requests, os
#       params = {
#           "query": f"{query} {location}",
#           "key": os.environ["GOOGLE_PLACES_API_KEY"],
#       }
#       r = requests.get(
#           "https://maps.googleapis.com/maps/api/place/textsearch/json",
#           params=params, timeout=10,
#       )
#       return r.text  # then parse() would do: json.loads(raw)["results"]
# ---------------------------------------------------------------------------
