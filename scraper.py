"""Scrape Samsung phone specifications from GSMArena into SQLite."""
import sys
import time
import requests
from bs4 import BeautifulSoup
import database

BASE = "https://www.gsmarena.com/"
LISTING_FIRST = BASE + "samsung-phones-9.php"
LISTING_PAGE = BASE + "samsung-phones-f-9-0-p{page}.php"
MAX_LISTING_PAGES = 8

PHONES = [
    "Samsung Galaxy S21 5G",
    "Samsung Galaxy S21 Ultra 5G",
    "Samsung Galaxy S22 5G",
    "Samsung Galaxy S22 Ultra 5G",
    "Samsung Galaxy S23",
    "Samsung Galaxy S23 Ultra",
    "Samsung Galaxy S24",
    "Samsung Galaxy S24 Ultra",
    "Samsung Galaxy Z Flip5",
    "Samsung Galaxy Z Fold5",
    "Samsung Galaxy A54",
    "Samsung Galaxy A34",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_DELAY = 5  # seconds between requests; GSMArena rate-limits aggressively


def fetch(url, retries=3):
    for attempt in range(retries):
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 429:
            wait = 30 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.text
    raise RuntimeError(f"Still rate-limited after {retries} attempts: {url}")


def build_phone_index(targets):
    """Crawl the Samsung listing pages until every target phone URL is found.

    GSMArena's search endpoint sits behind a bot check, but the plain listing
    pages do not, so URL discovery goes through the listing instead.
    """
    wanted = {t.lower().replace("samsung ", "") for t in targets}
    index = {}
    for page in range(1, MAX_LISTING_PAGES + 1):
        url = LISTING_FIRST if page == 1 else LISTING_PAGE.format(page=page)
        soup = BeautifulSoup(fetch(url), "html.parser")
        for a in soup.select("div.makers ul li a"):
            title = a.get_text(" ", strip=True).lower()
            if title in wanted and title not in index:
                index[title] = BASE + a["href"]
        print(f"  listing page {page}: {len(index)}/{len(wanted)} targets found")
        if len(index) == len(wanted):
            break
        time.sleep(REQUEST_DELAY)
    return index


def parse_specs(html):
    """Return (name, image_url, [(category, spec_name, spec_value), ...])."""
    soup = BeautifulSoup(html, "html.parser")
    name = soup.select_one("h1.specs-phone-name-title").get_text(strip=True)
    img = soup.select_one("div.specs-photo-main img")
    image_url = img["src"] if img else None

    specs = []
    for table in soup.select("div#specs-list table"):
        th = table.select_one("th")
        category = th.get_text(strip=True) if th else "Other"
        for row in table.select("tr"):
            ttl, nfo = row.select_one("td.ttl"), row.select_one("td.nfo")
            if not nfo:
                continue
            spec_name = ttl.get_text(" ", strip=True) if ttl else ""
            spec_value = nfo.get_text(" ", strip=True)
            if spec_value:
                specs.append((category, spec_name or "Info", spec_value))
    return name, image_url, specs


def main():
    database.init_db()
    only = sys.argv[1:] or None
    targets = [p for p in PHONES if not only or any(o.lower() in p.lower() for o in only)]
    print("Building URL index from listing pages...")
    index = build_phone_index(targets)
    for name in targets:
        print(f"Scraping {name}...")
        url = index.get(name.lower().replace("samsung ", ""))
        if not url:
            print(f"  NOT FOUND in listing: {name}")
            continue
        try:
            time.sleep(REQUEST_DELAY)
            full_name, image_url, specs = parse_specs(fetch(url))
            database.save_phone(full_name, url, image_url, specs)
            print(f"  saved '{full_name}' with {len(specs)} spec rows")
        except Exception as e:
            print(f"  FAILED: {e}")
        time.sleep(REQUEST_DELAY)
    print(f"Done. {len(database.list_phones())} phones in database.")


if __name__ == "__main__":
    main()
