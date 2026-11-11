#!/usr/bin/env python3
"""
Collect Malaysian Ringgit (MYR) exchange rates from the free Frankfurter API
and save them to data/rates.csv.

- First run (no CSV yet): back-fills the last 365 days of history.
- Later runs: fetches everything since the last saved date and appends only
  new rows, so running it twice in a day is harmless.

Uses only the Python standard library, so there is nothing to pip install.
"""
import csv
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://api.frankfurter.dev/v2/rates"
CURRENCIES = ["USD", "SGD", "CNY", "EUR", "GBP", "JPY", "THB", "IDR"]
BACKFILL_DAYS = 365
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "rates.csv"
FIELDS = ["date", "currency", "myr_per_unit"]


def fetch_rates(start: date, end: date) -> list[dict]:
    """Return Frankfurter rows: [{date, base, quote, rate}, ...] (rate = foreign units per 1 MYR)."""
    url = (
        f"{API}?base=MYR&quotes={','.join(CURRENCIES)}"
        f"&from={start.isoformat()}&to={end.isoformat()}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "myr-rate-tracker"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def load_existing() -> dict[tuple[str, str], str]:
    if not DATA_FILE.exists():
        return {}
    with DATA_FILE.open(newline="") as f:
        return {(r["date"], r["currency"]): r["myr_per_unit"] for r in csv.DictReader(f)}


def save(rows: dict[tuple[str, str], str]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        for (d, cur) in sorted(rows):
            writer.writerow([d, cur, rows[(d, cur)]])


def main() -> int:
    rows = load_existing()
    today = date.today()

    if rows:
        last_saved = max(date.fromisoformat(d) for d, _ in rows)
        start = last_saved  # inclusive, duplicates are skipped below
    else:
        start = today - timedelta(days=BACKFILL_DAYS)
        print(f"No data yet, back-filling from {start}")

    try:
        api_rows = fetch_rates(start, today)
    except urllib.error.HTTPError as e:
        print(f"API returned HTTP {e.code}: {e.reason}", file=sys.stderr)
        return 1

    added = 0
    for r in api_rows:
        cur, rate = r.get("quote"), r.get("rate")
        if cur not in CURRENCIES or not rate or rate <= 0:
            continue
        key = (r["date"], cur)
        if key in rows:
            continue
        # API gives "foreign units per 1 MYR"; we store "MYR per 1 foreign unit".
        rows[key] = f"{1 / rate:.8g}"
        added += 1

    save(rows)
    print(f"Added {added} new rows ({len(rows)} total) -> {DATA_FILE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
