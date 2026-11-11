# MYR Exchange Rate Tracker

A live dashboard for Malaysian Ringgit (MYR) exchange rates, plus a dataset that grows by itself every day.

**Live dashboard:** https://casperng-2004.github.io/daily-rate-tracker/

## How it works

| Part | What it does |
|---|---|
| `scripts/collect.py` | Fetches MYR rates (USD, SGD, CNY, EUR, GBP, JPY, THB, IDR) from the [Frankfurter API](https://frankfurter.dev) and appends new days to `data/rates.csv`. On the first run it back-fills one year of history. |
| `.github/workflows/collect.yml` | A GitHub Actions job that runs the script every day at 09:17 Malaysia time and commits the updated CSV. |
| `index.html` | A dashboard on GitHub Pages: live rate cards (refreshed every 5 minutes), a history chart with 1M/3M/6M/1Y ranges, high/low/average stats, and a currency converter. |

There's no server and no API key, and it costs nothing to run.

## Tech

Python (standard library only) · GitHub Actions · GitHub Pages · Chart.js · vanilla JavaScript

## Data

`data/rates.csv` has the columns `date, currency, myr_per_unit`, where `myr_per_unit` is how many ringgit one unit of the foreign currency costs. Rates are mid-market reference rates, so they are not suitable for trading.
