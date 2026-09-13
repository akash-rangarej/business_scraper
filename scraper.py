"""
scraper.py

Usage (interactive -- just run it and answer the prompts):
    python scraper.py google
    python scraper.py facebook

Usage (non-interactive, e.g. for scripting/cron):
    python scraper.py google --query "restaurants,malls" --location "Bengaluru" --output my_results.csv

This file has NO knowledge of Google's or Facebook's HTML structure.
It just looks up the requested site name in PLUGINS, and for each
business type the user gives it, runs the fetch -> parse(callback)
pipeline, then combines everything into one CSV the user names.
"""

import argparse
import os
import sys

from plugins.registry import PLUGINS

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def prompt_business_types() -> list[str]:
    raw = input(
        "What type(s) of business are you looking for? "
        "(e.g. restaurants, malls, shops -- separate multiple with commas): "
    ).strip()
    # Split on commas AND the word "and" so "restaurants and malls" also works
    raw = raw.replace(" and ", ",")
    types = [t.strip() for t in raw.split(",") if t.strip()]
    return types or ["restaurants"]


def prompt_location() -> str:
    return input("Which location? (e.g. Bengaluru): ").strip()


def prompt_filename(default_name: str) -> str:
    name = input(f"Save results as (press Enter for default: {default_name}): ").strip()
    name = name or default_name
    if not name.lower().endswith(".csv"):
        name += ".csv"
    return name


def main():
    parser = argparse.ArgumentParser(
        description="Plugin-based business listing scraper (Google / Facebook)"
    )
    parser.add_argument("site", choices=PLUGINS.keys(), help="Which website's plugin to run")
    parser.add_argument(
        "--query", default=None,
        help="Comma-separated business type(s), e.g. 'restaurants,malls'. "
             "If omitted, you'll be prompted interactively.",
    )
    parser.add_argument(
        "--location", default=None,
        help="Location to search in, e.g. 'Bengaluru'. If omitted, prompted interactively.",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output CSV filename. If omitted, prompted interactively.",
    )
    args = parser.parse_args()

    plugin = PLUGINS[args.site]

    # Fall back to interactive prompts for anything not given on the CLI
    business_types = (
        [t.strip() for t in args.query.split(",") if t.strip()]
        if args.query else prompt_business_types()
    )
    location = args.location if args.location is not None else prompt_location()
    default_name = f"{plugin.name}_businesses.csv"
    filename = args.output if args.output else prompt_filename(default_name)
    output_path = os.path.join(OUTPUT_DIR, filename)

    all_records = []
    for business_type in business_types:
        print(f"[{plugin.name}] fetching '{business_type}' in '{location}'...")
        try:
            records = plugin.fetch_and_parse(business_type, location)
        except (NotImplementedError, RuntimeError) as e:
            print(f"[{plugin.name}] {e}", file=sys.stderr)
            sys.exit(1)

        for r in records:
            r.setdefault("business_type", business_type)
        print(f"[{plugin.name}]   -> found {len(records)} results for '{business_type}'")
        all_records.extend(records)

    plugin.save(all_records, output_path=output_path)
    print(f"[{plugin.name}] saved {len(all_records)} businesses -> {output_path}")


if __name__ == "__main__":
    main()
