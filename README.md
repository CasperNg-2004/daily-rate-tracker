# MYR Exchange Rate Tracker

[![CI](https://github.com/CasperNg-2004/myr-rate-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/CasperNg-2004/myr-rate-tracker/actions/workflows/ci.yml)

A live dashboard for Malaysian Ringgit (MYR) exchange rates, plus a dataset that grows by itself every day and email alerts when rates cross levels you choose.

**Live dashboard:** https://casperng-2004.github.io/daily-rate-tracker/

## How it works

| Part | What it does |
|---|---|
| `config.json` | The single list of tracked currencies and their display units (e.g. RM per 100 JPY). Used by the scripts and the dashboard, so adding a currency here updates everything. |
| `scripts/collect.py` | Fetches MYR rates from the [Frankfurter API](https://frankfurter.dev) and appends new days to `data/rates.csv`. Back-fills one year of history on the first run, or for a newly added currency, and retries temporary network errors. |
| `scripts/alerts.py` | Checks the rules in `alerts.json` (price levels and big daily moves) and emails you through Gmail. It validates the rules and explains any mistake. |
| `scripts/common.py` | Shared config loading and validation. |
| `index.html` | A dashboard: live rate cards (refreshed every 5 minutes), a history chart with 1M/3M/6M/1Y ranges, high/low/average stats, and a currency converter. |

There's no server and no API key, and it costs nothing to run.

## Automation (GitHub Actions)

| Workflow | When it runs | What it does |
|---|---|---|
| `ci.yml` | Every push and pull request | **CI:** lints the code (ruff), checks formatting, and runs the test suite (pytest). **CD:** on `main`, deploys the dashboard only if every check passes. |
| `collect.yml` | Daily at 09:17 Malaysia time | Collects new rates, sends alerts, commits the data, then redeploys the dashboard. Never runs twice at once, saves the data even if alerts fail, and pulls before pushing. |
| `deploy.yml` | Called by the two above | Publishes only `index.html`, `config.json` and `data/` to GitHub Pages. |

## Tests

37 tests cover the collector (back-fill, no duplicates, saved history never overwritten, retry and give-up behaviour), the alerts (once-per-crossing, no stale alerts, units, email contents, rule validation), and the real `config.json` and `alerts.json`, so a broken config fails CI before it reaches the live site.

Run them locally:

```bash
pip install -r requirements-dev.txt
pytest          # run the tests
ruff check .    # lint
ruff format .   # auto-format
```

## Tech

Python (standard library only) · pytest · ruff · GitHub Actions (CI/CD, scheduled jobs) · GitHub Pages · Chart.js · vanilla JavaScript

## Data

`data/rates.csv` has the columns `date, currency, myr_per_unit`, where `myr_per_unit` is how many ringgit one unit of the foreign currency costs. Rates are mid-market reference rates, so they are not suitable for trading.
