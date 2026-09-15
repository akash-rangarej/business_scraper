"""
sulekha_plugin.py

Real, live-fetching plugin for business listings on Sulekha.

Sulekha's category/city search pages are mostly server-rendered HTML,
so this uses a plain requests.get() rather than Selenium -- lighter
weight, and works as long as Sulekha doesn't add JS-gating later. If
you find results come back empty, switch to the Selenium pattern used
in google_plugin.py / justdial_plugin.py instead.

NOTE ON SELECTORS: Sulekha uses Tailwind utility classes rather than
semantic ones (no ".compname"/".bizname" -- those never existed). This
parse() instead keys off: the card's distinctive Tailwind class combo,
the <h3> tag for the name, the semantic <address> tag, the tel: link
for phone, and the "Sulekha Score" badge for rating. If Sulekha changes
its markup, re-inspect a real card and update the selectors below.
"""

import os
import requests
from bs4 import BeautifulSoup

from .base import BasePlugin


class SulekhaPlugin(BasePlugin):
    name = "sulekha"
    output_file = os.path.join(
        os.path.dirname(__file__), "..", "output", "sulekha_businesses.csv"
    )

    def fetch(self, query: str, location: str = "") -> str:
        # Sulekha's URL pattern is /<category>/<city>, e.g. /restaurants/bangalore
        category = query.strip().lower().replace(" ", "-")
        city = (location or "india").strip().lower().replace(" ", "-")
        url = f"https://www.sulekha.com/{category}/{city}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            if response.status_code == 404:
                print(f"[sulekha] no listings found for '{query}' in '{location}' (page doesn't exist) -- skipping")
            else:
                print(f"[sulekha] request failed for '{query}' in '{location}': HTTP {response.status_code} -- skipping")
            return ""
        except requests.exceptions.RequestException as e:
            print(f"[sulekha] network error fetching '{query}' in '{location}': {e} -- skipping")
            return ""

        return response.text


    def parse(self, raw: str) -> list[dict]:
        """The callback hook: turns Sulekha's search results HTML into business dicts."""
        soup = BeautifulSoup(raw, "html.parser")
        records = []

        # Each result card is this Tailwind div combo -- no semantic class
        # names exist on Sulekha, so we key off this specific set instead.
        for card in soup.select("div.rounded-lg.border.shadow-sm.bg-white.h-full"):
            name_el = card.select_one("h3")
            address_el = card.select_one("address")
            phone_el = card.select_one('a[href^="tel:"]')
            rating_el = card.select_one("span.font-bold.text-orange-500")
            category_el = card.select_one("span.bg-gray-100")

            phone = ""
            if phone_el and phone_el.get("href"):
                # Pull the number straight from the href (tel:08069874927)
                # rather than the link text, which also includes icon alt text.
                phone = phone_el["href"].split(":", 1)[-1].strip()

            records.append({
                "name": name_el.get_text(strip=True) if name_el else "",
                "address": address_el.get_text(strip=True) if address_el else "",
                "phone": phone,
                "rating": rating_el.get_text(strip=True) if rating_el else "",
                "category": category_el.get_text(strip=True) if category_el else "",
            })

        return records