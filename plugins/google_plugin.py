"""
google_plugin.py

Real, live-fetching plugin for Google Maps business listings.

Google Maps results are rendered with JavaScript, so plain requests.get()
won't see them -- this uses Selenium to actually load the page in a
headless Chrome browser, scroll the results panel to load more cards,
then extract data.

IMPORTANT: clicking a card REPLACES the results list with a detail
panel (Google Maps doesn't keep both visible) -- so parse() clicks a
card, reads its detail panel (address, phone), then clicks "Back" to
restore the list before moving to the next card. Skipping the "Back"
click would mean every card after the first fails to be found.

NOTE ON SELECTORS: Google Maps' CSS class names are auto-generated and
DO change over time. If parse() suddenly returns empty results, open
Maps in a real browser, right-click a result -> Inspect, and update
the selectors below to match.
"""

import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)
from webdriver_manager.chrome import ChromeDriverManager

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
        driver.get(url)
        time.sleep(4)  # let the initial results render

        self._scroll_results_panel(driver, pause=2.0, max_scrolls=6)

        # Keep the driver alive -- parse() needs it to click into cards live.
        self._driver = driver
        return driver.page_source  # kept for reference/debugging only

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
        """
        THE CALLBACK HOOK -- walks the LIVE page (self._driver, set by
        fetch()). For each card: read name/rating/reviews from the list
        view, click into it to read address/phone from the detail
        panel, then click "Back" to restore the list before the next card.
        """
        driver = self._driver
        records = []

        cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK")
        card_count = len(cards)
        print(f"[google] found {card_count} cards on page")

        for i in range(card_count):
            try:
                # Re-fetch the list fresh each loop -- after clicking
                # "Back", these are new DOM elements, not the same ones.
                cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK")
                card = cards[i]

                name = self._safe_text(card, ".qBF1Pd")
                if not name:
                    # Fallback: the card's link has the name as aria-label
                    try:
                        name = card.find_element(By.CSS_SELECTOR, "a.hfpxzc").get_attribute("aria-label") or ""
                    except NoSuchElementException:
                        name = ""

                rating = self._safe_text(card, "span.MW4etd")
                reviews = self._safe_text(card, "span.UY7F9").strip("()")

                address, phone = self._open_details_and_read(driver, card)

                records.append({
                    "name": name,
                    "rating": rating,
                    "reviews": reviews,
                    "address": address,
                    "phone": phone,
                })
            except (StaleElementReferenceException, IndexError):
                continue  # card disappeared/moved -- skip it

        return records

    def _safe_text(self, card, selector: str) -> str:
        try:
            return card.find_element(By.CSS_SELECTOR, selector).text.strip()
        except NoSuchElementException:
            return ""

    def _open_details_and_read(self, driver, card) -> tuple[str, str]:
        """Click into THIS card's detail panel, read address + phone,
        then click Back to restore the results list. Best-effort:
        returns ('', '') for whichever field isn't found rather than
        crashing, and always tries to go Back even if reading fails."""
        address, phone = "", ""
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
            card.click()
            time.sleep(1.5)  # let the detail panel start rendering

            address = self._wait_for_field(driver, 'button[data-item-id="address"] .Io6YTe', timeout=4)
            phone = self._wait_for_field(driver, 'button[data-item-id^="phone:"] .Io6YTe', timeout=4)
        except Exception:
            pass
        finally:
            self._go_back(driver)

        return address, phone

    def _wait_for_field(self, driver, selector: str, timeout: float) -> str:
        """Poll briefly for a detail-panel field to appear, since it
        loads asynchronously after the click."""
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                el = driver.find_element(By.CSS_SELECTOR, selector)
                text = el.text.strip()
                if text:
                    return text
            except NoSuchElementException:
                pass
            time.sleep(0.3)
        return ""

    def _go_back(self, driver):
        """Click the detail panel's Back arrow to restore the results
        list. Best-effort -- if this fails, subsequent cards just won't
        be found and the loop moves on rather than crashing."""
        try:
            back_btn = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Back"]')
            back_btn.click()
            time.sleep(1.0)  # let the list panel re-render
        except NoSuchElementException:
            pass