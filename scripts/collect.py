#!/usr/bin/env python3
"""
Collect Malaysian Ringgit (MYR) exchange rates from the free Frankfurter API
and save them to data/rates.csv.

- Currencies come from config.json.
- First run, or a newly added currency: back-fills the last 365 days.
- Later runs: fetches everything since the last saved date and appends only
  new rows, so running it twice in a day is harmless.
- Temporary network/server errors are retried a few times before giving up.

Uses only the Python standard library, so there is nothing to pip install.
"""

import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

from common import RATES_FILE, ConfigError, fail, load_currencies

API = "https://api.frankfurter.dev/v2/rates"
BACKFILL_DAYS = 365
FIELDS = ["date", "currency", "myr_per_unit"]

RETRIES = 3  # extra attempts after the first one
RETRY_WAIT_SECONDS = 5  # waits 5s, 10s, 20s between attempts
RETRY_HTTP_CODES = {429, 500, 502, 503, 504}


def fetch_json(url: str):
    """GET a URL and parse JSON, retrying temporary failures."""
    req = urllib.request.Request(url, headers={"User-Agent": "myr-rate-tracker"})
    for attempt in range(RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_HTTP_CODES or attempt == RETRIES:
                raise
            reason = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == RETRIES:
                raise
            reason = str(getattr(e, "reason", e))
        wait = RETRY_WAIT_SECONDS * 2**attempt
        print(f"Attempt {attempt + 1} failed ({reason}); retrying in {wait}s...")
        time.sleep(wait)


def fetch_rates(codes: list[str], start: date, end: date) -> list[dict]:
    """Return Frankfurter rows: [{date, base, quote, rate}, ...] (rate = foreign units per 1 MYR)."""
    url = f"{API}?base=MYR&quotes={','.join(codes)}&from={start.isoformat()}&to={end.isoformat()}"
    return fetch_json(url)


def load_existing() -> dict[tuple[str, str], str]:
    if not RATES_FILE.exists():
        return {}
    with RATES_FILE.open(newline="") as f:
        return {(r["date"], r["currency"]): r["myr_per_unit"] for r in csv.DictReader(f)}


def save(rows: dict[tuple[str, str], str]) -> None:
    RATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RATES_FILE.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        for d, cur in sorted(rows):
            writer.writerow([d, cur, rows[(d, cur)]])


def main() -> int:
    try:
        codes = list(load_currencies())
    except ConfigError as e:
        return fail(e)

    rows = load_existing()
    today = date.today()
    saved_codes = {cur for _, cur in rows}
    new_codes = [c for c in codes if c not in saved_codes]

    if not rows or new_codes:
        start = today - timedelta(days=BACKFILL_DAYS)
        print(f"Back-filling from {start} for: {', '.join(new_codes)}")
    else:
        start = max(date.fromisoformat(d) for d, _ in rows)  # inclusive; duplicates skipped

    try:
        api_rows = fetch_rates(codes, start, today)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        print(f"Could not reach the exchange-rate API: {e}", file=sys.stderr)
        return 1

    added = 0
    for r in api_rows:
        cur, rate = r.get("quote"), r.get("rate")
        if cur not in codes or not rate or rate <= 0:
            continue
        key = (r["date"], cur)
        if key in rows:
            continue
        # API gives "foreign units per 1 MYR"; we store "MYR per 1 foreign unit".
        rows[key] = f"{1 / rate:.8g}"
        added += 1

    returned = {r.get("quote") for r in api_rows}
    missing = [c for c in codes if c not in returned]
    if missing:
        print(f"Warning: API returned no data for {', '.join(missing)} (check the codes in config.json)")

    save(rows)
    print(f"Added {added} new rows ({len(rows)} total) -> {RATES_FILE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
