#!/usr/bin/env python3
"""
Korteri vahtija (GitHub Actions versioon).
Seaded tulevad GitHubi Secrets kaudu: NTFY_TOPIC, KV_URL, CITY24_URL.
"""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
SEARCH_URLS = {
    "kv.ee": os.environ.get("KV_URL", ""),
    "city24.ee": os.environ.get("CITY24_URL", ""),
}
LISTING_PATTERNS = {
    "kv.ee": r"^/\d{5,}|kv\.ee/\d{5,}",
    "city24.ee": r"/kinnisvara/|/real-estate/",
}
STATE_FILE = Path(__file__).with_name("nahtud.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) KorteriVahtija/1.0"}


def load_seen():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_seen(seen):
    STATE_FILE.write_text(json.dumps(sorted(seen), indent=0))


def fetch_listings(site, url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    pattern = re.compile(LISTING_PATTERNS[site])
    found = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if pattern.search(href):
            full = urljoin(url, href).split("?")[0].split("#")[0]
            title = " ".join(a.get_text(" ", strip=True).split())[:120]
            if full not in found or (title and not found[full]):
                found[full] = title
    return found


def notify(title, link):
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=link.encode("utf-8"),
        headers={"Title": title.encode("utf-8"), "Click": link},
        timeout=30,
    )


def main():
    if not NTFY_TOPIC:
        sys.exit("NTFY_TOPIC puudub")
    first_run = not STATE_FILE.exists()
    seen = load_seen()
    new_count = 0
    for site, url in SEARCH_URLS.items():
        if not url:
            print(f"[{site}] link puudub, jätan vahele")
            continue
        try:
            listings = fetch_listings(site, url)
        except Exception as e:
            print(f"[{site}] viga: {e}", file=sys.stderr)
            continue
        print(f"[{site}] leitud {len(listings)} linki")
        for link, title in listings.items():
            if link not in seen:
                seen.add(link)
                new_count += 1
                if not first_run:
                    notify(f"Uus korter ({site})", f"{title}\n{link}".strip())
    save_seen(seen)
    print("Esimene käivitus, teavitusi ei saadetud." if first_run else f"Uusi: {new_count}")


if __name__ == "__main__":
    main()
