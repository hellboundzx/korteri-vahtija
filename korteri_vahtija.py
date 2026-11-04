#!/usr/bin/env python3
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
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "et-EE,et;q=0.9,en;q=0.8",
}


def load_state():
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            if isinstance(data, dict):
                return {k: set(v) for k, v in data.items()}
        except Exception:
            pass
    return {}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps({k: sorted(v) for k, v in state.items()}, indent=0)
    )


def fetch_listings(session, site, url):
    r = session.get(url, headers=HEADERS, timeout=30)
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
    state = load_state()
    session = requests.Session()
    for site, url in SEARCH_URLS.items():
        if not url:
            print(f"[{site}] link puudub, jätan vahele")
            continue
        try:
            listings = fetch_listings(session, site, url)
        except Exception as e:
            print(f"[{site}] viga: {e}", file=sys.stderr)
            continue
        print(f"[{site}] leitud {len(listings)} linki")
        if not listings:
            continue
        first_run = site not in state
        seen = state.get(site, set())
        new = 0
        for link, title in listings.items():
            if link not in seen:
                seen.add(link)
                new += 1
                if not first_run:
                    notify(f"Uus korter ({site})", f"{title}\n{link}".strip())
        state[site] = seen
        print(f"[{site}] " + ("esimene käivitus, salvestasin" if first_run else f"uusi: {new}"))
    save_state(state)


if __name__ == "__main__":
    main()
