"""
facebook_plugin.py

Real, live-fetching plugin for Facebook business Pages -- via the
official Graph API, NOT HTML scraping.

Why not scrape Facebook directly like the Google plugin does:
    - Facebook Pages require a logged-in session to render most content,
      so a plain (or even Selenium) fetch just hits a login wall.
    - Facebook's Terms of Service explicitly prohibit automated scraping
      of the site. Logging in with a real/fake account to scrape around
      that wall is a ToS violation, not just a technical workaround --
      that's the one piece I won't build for you.
    - The Graph API is Facebook's own supported way to get this data,
      and it's what any real production tool would use anyway.

Setup to get a token (free):
    1. Go to https://developers.facebook.com/apps and create an app
       (type: "Business").
    2. In the app dashboard, go to Tools -> Graph API Explorer.
    3. Select your app, then generate a User or Page access token with
       the `pages_read_engagement` / `public_profile` permissions.
    4. Set it as an environment variable:
           export FB_ACCESS_TOKEN="your_token_here"

Note: Facebook's Page Search endpoint has gotten more restricted over
the years -- many app review tiers only let you fetch Pages you manage,
not search all public Pages by keyword. If `/pages/search` returns a
permissions error for your app, that's Facebook's App Review gating it,
not a bug in this code -- you'd request the relevant permission in your
app's dashboard.
"""

import os
import json
import requests

from .base import BasePlugin

GRAPH_API_VERSION = "v19.0"


class FacebookPlugin(BasePlugin):
    name = "facebook"
    output_file = os.path.join(
        os.path.dirname(__file__), "..", "output", "facebook_businesses.csv"
    )

    def fetch(self, query: str, location: str = "") -> str:
        token = os.environ.get("FB_ACCESS_TOKEN")
        if not token:
            raise RuntimeError(
                "FB_ACCESS_TOKEN environment variable not set. See the "
                "docstring at the top of facebook_plugin.py for how to get one."
            )

        search_term = f"{query} {location}".strip()
        url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/pages/search"
        params = {
            "q": search_term,
            "fields": "name,category,location,phone,fan_count,link",
            "access_token": token,
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.text

    def parse(self, raw: str) -> list[dict]:
        """The callback hook: Graph API returns JSON, not HTML, so this
        just reshapes it -- no CSS selectors needed."""
        payload = json.loads(raw)
        records = []

        for page in payload.get("data", []):
            location = page.get("location", {}) or {}
            address_parts = [
                location.get("street", ""),
                location.get("city", ""),
                location.get("country", ""),
            ]
            records.append({
                "name": page.get("name", ""),
                "address": ", ".join(p for p in address_parts if p),
                "phone": page.get("phone", ""),
                "likes": page.get("fan_count", ""),
                "category": page.get("category", ""),
                "url": page.get("link", ""),
            })

        return records
