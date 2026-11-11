# MYR Exchange Rate Tracker

[![CI](https://github.com/CasperNg-2004/daily-rate-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/CasperNg-2004/daily-rate-tracker/actions/workflows/ci.yml)

A live dashboard for Malaysian Ringgit (MYR) exchange rates, a **hidden fee checker** that shows how much banks and money changers really charge, a dataset that grows by itself every day, and email alerts when rates cross levels you choose.

**Live dashboard:** https://casperng-2004.github.io/daily-rate-tracker/

## How it works

| Part | What it does |
|---|---|
| `config.json` | The single list of tracked currencies and their display units (e.g. RM per 100 JPY). Used by the scripts and the dashboard, so adding a currency here updates everything. |
| `scripts/collect.py` | Fetches MYR rates from the [Frankfurter API](https://frankfurter.dev) and appends new days to `data/rates.csv`. Back-fills one year of history on the first run, or for a newly added currency, and retries temporary network errors. |
| `scripts/alerts.py` | Checks the rules in `alerts.json` (price levels and big daily moves) and emails you through Gmail. It validates the rules and explains any mistake. |
| `scripts/common.py` | Shared config loading and validation. |
| `index.html` | A dashboard: live rate cards (refreshed every 5 minutes), a history chart with 1M/3M/6M/1Y ranges, high/low/average stats, and a currency converter. |
| `fees.html` + `fees.js` | **Hidden fee checker.** Enter a quoted rate (plus any fixed fee) or what's on a receipt, and see the markup against the real mid-market rate in % and RM, with a rating. Works for buying or selling, uses the saved history for past dates, and spots reversed quotes like "1 MYR = 0.2465 USD". |
| `data.js`, `style.css` | Shared data loading and styles for both pages. |

There's no server and no API key, and it costs nothing to run.

## Automation (GitHub Actions)

| Workflow | When it runs | What it does |
|---|---|---|
| `ci.yml` | Every push and pull request | **CI:** lints the Python code (ruff), checks formatting, and runs the Python tests (pytest) and JavaScript tests (`node --test`). **CD:** on `main`, deploys the site only if every check passes. |
| `collect.yml` | Daily at 09:17 Malaysia time | Collects new rates, sends alerts, commits the data, then redeploys the dashboard. Never runs twice at once, saves the data even if alerts fail, and pulls before pushing. |
| `deploy.yml` | Called by the two above | Publishes only the website files (pages, styles, browser JavaScript, `config.json`, `data/`) to GitHub Pages. |

## Tests

**Python (37 tests)** cover the collector (back-fill, no duplicates, saved history never overwritten, retry and give-up behaviour), the alerts (once-per-crossing, no stale alerts, units, email contents, rule validation), and the real `config.json` and `alerts.json`, so a broken config fails CI before it reaches the live site.

**JavaScript (29 tests)** cover the fee maths: buying and selling, fixed fees, per-100 units (JPY), receipt mode, rating bands, reversed-quote detection, rejecting impossible inputs, and finding the rate for a past date.

Run them locally:

```bash
pip install -r requirements-dev.txt
pytest          # Python tests
ruff check .    # lint
ruff format .   # auto-format
node --test     # JavaScript tests (Node 22+, no install needed)

python -m http.server   # then open http://localhost:8000 to try the site
```

## Tech

Python (standard library only) · JavaScript (ES modules, no framework) · pytest · node:test · ruff · GitHub Actions (CI/CD, scheduled jobs) · GitHub Pages · Chart.js · vanilla JavaScript

## Data

`data/rates.csv` has the columns `date, currency, myr_per_unit`, where `myr_per_unit` is how many ringgit one unit of the foreign currency costs. Rates are mid-market reference rates, so they are not suitable for trading.
