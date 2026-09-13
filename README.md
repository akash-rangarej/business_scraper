# Plugin-Based Business Listing Scraper

Scrapes business listings from multiple sources (Google, Facebook) using a
plugin architecture, and writes each source's results to its own output file.

## How it works

```
scraper.py            <-- CLI entry point (interactive prompts + optional flags)
plugins/
  base.py             <-- BasePlugin: fetch() -> parse() -> save() pipeline
  registry.py          <-- THE DICTIONARY: {"google": GooglePlugin(), "facebook": FacebookPlugin()}
  google_plugin.py     <-- Google-specific fetch + parse (callback hook)
  facebook_plugin.py   <-- Facebook-specific fetch + parse (callback hook)
output/               <-- google_businesses.csv / facebook_businesses.csv land here
```

The **callback hook** is `parse()`. `scraper.py` and `base.py` never know
anything about Google's or Facebook's markup -- they just call
`plugin.run()`, which internally does:

1. `fetch()`  — get raw HTML/JSON for that site
2. `parse()`  — **the callback** — turn raw content into a list of business dicts
3. `save()`   — write that site's own JSON file

Because each site's dictionary value is a self-contained plugin object,
adding a third source (e.g. Yelp) means writing one new plugin file and
adding one line to `registry.py` — nothing else changes.

## Setup

```bash
pip install -r requirements.txt
```

## Run

**Interactive (recommended)** — just run it and answer the prompts:

```bash
python scraper.py google
```

```
What type(s) of business are you looking for? (e.g. restaurants, malls, shops -- separate multiple with commas): restaurants and malls
Which location? (e.g. Bengaluru): Bengaluru
Save results as (press Enter for default: google_businesses.csv): bengaluru_results.csv
```

You can list several business types at once ("restaurants, malls, shops" or
"restaurants and malls and shops") — the scraper runs a separate search for
each one and combines all the results into the single CSV file you named,
with a `business_type` column showing which search each row came from.

**Non-interactive** (for scripting) — pass everything as flags and it skips the prompts:

```bash
python scraper.py google --query "restaurants,malls" --location "Bengaluru" --output bengaluru_results.csv
python scraper.py facebook --query "coffee shops" --location "Bengaluru" --output fb_coffee.csv
```

Either way, results land in `output/<the filename you chose>.csv`.

## Live fetching — how each plugin actually gets real data

**Google (`plugins/google_plugin.py`)** — uses Selenium to load Google Maps
in headless Chrome (needed because results are JS-rendered), scrolls the
results panel to load more cards, then parses the rendered HTML. This is
real, working scraping of public data — no login required.

```bash
pip install -r requirements.txt
python scraper.py google --query "coffee shops" --location "Bengaluru"
```

The first run downloads a matching ChromeDriver automatically via
`webdriver-manager`. If Google changes its result-card class names
(`Nv2PK`, `qBF1Pd`, etc. — these do shift periodically), `parse()` in
that file is the only place you need to update: inspect a result in a
real browser and adjust the selectors.

**Facebook (`plugins/facebook_plugin.py`)** — uses the official
**Graph API** rather than scraping Facebook's HTML. I didn't build a
login-wall-bypassing scraper for Facebook on purpose: Facebook Pages
require an authenticated session to render content, and Facebook's
Terms of Service explicitly prohibit automated scraping of the site —
logging in around that wall would be a ToS violation, not just a
technical workaround. The Graph API is Facebook's own sanctioned way to
get this data, and is what a real/production tool would use anyway.

To use it:
1. Create a free app at https://developers.facebook.com/apps
2. Generate an access token via Graph API Explorer (see the docstring
   at the top of `facebook_plugin.py` for exact steps)
3. `export FB_ACCESS_TOKEN="your_token_here"`
4. `python scraper.py facebook --query "coffee shops" --location "Bengaluru"`

Facebook's Page Search endpoint is permission-gated for some app tiers —
if you get a permissions error, that's Facebook's App Review restricting
your app, not a bug in the code.

## Extending with a new site

```python
# plugins/yelp_plugin.py
from .base import BasePlugin

class YelpPlugin(BasePlugin):
    name = "yelp"
    output_file = "output/yelp_businesses.json"

    def fetch(self, query, location=""):
        ...

    def parse(self, raw):
        ...  # the callback hook
```

Then in `plugins/registry.py`:

```python
from .yelp_plugin import YelpPlugin

PLUGINS = {
    "google": GooglePlugin(),
    "facebook": FacebookPlugin(),
    "yelp": YelpPlugin(),
}
```
