"""
justdial_plugin.py

Real, live-fetching plugin for business listings on JustDial.

JustDial pages are largely server-rendered but paginate/lazy-load more
results as you scroll, and -- important -- they hide phone numbers
behind a "Show Number" click rather than putting them in the raw HTML.

Because the number only appears in a SPECIFIC card after clicking THAT
card's button, this plugin keeps the Selenium driver alive between
fetch() and parse() instead of handing off a frozen HTML snapshot --
parse() walks the live page, clicking each card's button and reading
the result right after, one card at a time.
"""

import os
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)
import undetected_chromedriver as uc

from .base import BasePlugin


class JustdialPlugin(BasePlugin):
    name = "justdial"
    output_file = os.path.join(
        os.path.dirname(__file__), "..", "output", "justdial_businesses.csv"
    )

    def fetch(self, query: str, location: str = "") -> str:
        city = (location or "India").strip().replace(" ", "-")
        category = query.strip().replace(" ", "-")
        url = f"https://www.justdial.com/{city}/{category}"

        driver = self._make_driver()
        print(f"[justdial] navigating to: {url}")
        driver.get(url)

        # Wait for real listing text, not just the shimmer/skeleton placeholder
        try:
            WebDriverWait(driver, 15).until(
                EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".resultbox_title"), "")
            )
        except Exception:
            pass

        time.sleep(2)
        self._scroll_page(driver, pause=1.5, max_scrolls=6)

        # Keep the driver alive -- parse() needs it to click buttons live.
        self._driver = driver
        return driver.page_source  # kept for reference/debugging; parse() won't rely on it

    def _make_driver(self):
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,1600")
        return uc.Chrome(options=options, version_main=152)

    def _scroll_page(self, driver, pause: float, max_scrolls: int):
        """JustDial lazy-loads more result cards as you scroll the page."""
        for _ in range(max_scrolls):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)

    def parse(self, raw: str) -> list[dict]:
        """
        THE CALLBACK HOOK -- but instead of parsing the frozen `raw` HTML
        string, this walks the LIVE page (self._driver, set by fetch()),
        clicking each card's "Show Number" button one at a time and
        reading the revealed number right after, before moving to the
        next card.
        """
        driver = self._driver
        records = []

        cards = driver.find_elements(By.CSS_SELECTOR, "div.resultbox_info")
        print(f"[justdial] found {len(cards)} cards on page")

        for i in range(len(cards)):
            try:
                # Re-fetch the card fresh each loop -- clicking can re-render
                # the DOM and invalidate old element references (stale element).
                cards = driver.find_elements(By.CSS_SELECTOR, "div.resultbox_info")
                card = cards[i]

                name = self._safe_text(card, ".resultbox_title")
                address = self._safe_text(card, ".resultbox_address")
                rating = self._safe_text(card, ".resultbox_overall")

                phone = self._click_and_get_phone(driver, card)

                records.append({
                    "name": name,
                    "address": address,
                    "rating": rating,
                    "phone": phone,
                })
            except (StaleElementReferenceException, IndexError):
                continue  # card disappeared/moved after a click -- skip it

        driver.quit()
        return records

    def _safe_text(self, card, selector: str) -> str:
        try:
            return card.find_element(By.CSS_SELECTOR, selector).text.strip()
        except NoSuchElementException:
            return ""

    def _click_and_get_phone(self, driver, card) -> str:
        """Click THIS card's 'Show Number' button and read the number
        that appears in its place. Best-effort: returns '' rather than
        crashing if the button/number isn't found."""
        try:
            btn = card.find_element(By.CSS_SELECTOR, ".callbutton")
        except NoSuchElementException:
            return ""

        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            btn.click()
        except ElementClickInterceptedException:
            try:
                driver.execute_script("arguments[0].click();", btn)  # fallback: JS click
            except Exception:
                return ""
        except Exception:
            return ""

        time.sleep(3)  # give the AJAX call time to fill in the number

        # After clicking, JustDial typically replaces the button's own text
        # with the number, or adds a sibling element -- try the button text
        # first, then fall back to re-reading the whole card's text.
        try:
            revealed = btn.text.strip()
            if revealed and revealed.lower() != "show number":
                return revealed
        except StaleElementReferenceException:
            pass

        return self._safe_text(card, ".callbutton")