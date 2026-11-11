# MYR Exchange Rate Tracker

A live dashboard for Malaysian Ringgit (MYR) exchange rates, plus a dataset that grows by itself every day.

**Live dashboard:** https://casperng-2004.github.io/daily-rate-tracker/

## How it works

| Part | What it does |
|---|---|
| `config.json` | The single list of tracked currencies and their display units (e.g. RM per 100 JPY). Used by the scripts and the dashboard, so adding a currency here updates everything. |
| `scripts/collect.py` | Fetches MYR rates from the [Frankfurter API](https://frankfurter.dev) and appends new days to `data/rates.csv`. Back-fills one year of history on the first run, or for a newly added currency, and retries temporary network errors. |
| `scripts/alerts.py` | Checks the rules in `alerts.json` (price levels and big daily moves) and emails you through Gmail. It validates the rules and explains any mistake. |
| `scripts/common.py` | Shared config loading and validation. |
| `.github/workflows/collect.yml` | A GitHub Actions job that runs every day at 09:17 Malaysia time, checks alerts, and commits the new data. It never runs twice at once, still saves the data if the alert step fails, and pulls before pushing to avoid conflicts. |
| `index.html` | A dashboard on GitHub Pages: live rate cards (refreshed every 5 minutes), a history chart with 1M/3M/6M/1Y ranges, high/low/average stats, and a currency converter. |

There's no server and no API key, and it costs nothing to run.

## Tech

Python (standard library only) · GitHub Actions · GitHub Pages · Chart.js · vanilla JavaScript

## Data

`data/rates.csv` has the columns `date, currency, myr_per_unit`, where `myr_per_unit` is how many ringgit one unit of the foreign currency costs. Rates are mid-market reference rates, so they are not suitable for trading.
