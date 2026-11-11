#!/usr/bin/env python3
"""
Check data/rates.csv against the rules in alerts.json and send one email
listing every alert that fired.

Rules (alerts.json):
  daily_move_percent  -> alert when any currency moves at least this much vs the previous day
  levels              -> alert when a currency goes above/below a price, in the SAME units as
                         the dashboard cards (RM per 1 USD, RM per 100 JPY, RM per 1000 IDR ...)

Level alerts fire once per crossing: you get one email when USD goes above 4.30,
and another only after it drops back below and crosses again.
State is kept in data/alert_state.json, which the workflow commits.

Email settings come from environment variables (GitHub Secrets):
  GMAIL_USER          your Gmail address
  GMAIL_APP_PASSWORD  16-character Google App Password (NOT your normal password)
  ALERT_TO            optional, where to send alerts (defaults to GMAIL_USER)
"""
import csv
import json
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RATES_FILE = ROOT / "data" / "rates.csv"
STATE_FILE = ROOT / "data" / "alert_state.json"
RULES_FILE = ROOT / "alerts.json"

# Same display units as the dashboard
UNITS = {"JPY": 100, "THB": 100, "IDR": 1000}


def unit(cur: str) -> int:
    return UNITS.get(cur, 1)


def load_rates() -> dict[str, list[tuple[str, float]]]:
    """currency -> [(date, RM per display unit), ...] sorted by date."""
    out: dict[str, list[tuple[str, float]]] = {}
    with RATES_FILE.open(newline="") as f:
        for r in csv.DictReader(f):
            cur = r["currency"]
            out.setdefault(cur, []).append((r["date"], float(r["myr_per_unit"]) * unit(cur)))
    for v in out.values():
        v.sort()
    return out


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def rule_key(rule: dict) -> str:
    direction = "above" if "above" in rule else "below"
    return f"{rule['currency']} {direction} {rule[direction]}"


def check(rates, rules, state, latest: str) -> list[str]:
    alerts: list[str] = []
    active = set(state.get("active_levels", []))

    # 1) Price levels, once per crossing (listed first so they lead the email subject)
    still_active = set()
    for rule in rules.get("levels", []):
        cur = rule["currency"]
        if cur not in rates:
            print(f"Warning: no data for {cur}, skipping rule {rule}")
            continue
        d, value = rates[cur][-1]
        key = rule_key(rule)
        hit = value > rule["above"] if "above" in rule else value < rule["below"]
        if hit:
            still_active.add(key)
            if key not in active:
                alerts.append(f"{key}: now RM {value:.4f} per {unit(cur)} {cur} (as of {d})")
    state["active_levels"] = sorted(still_active)

    # 2) Big daily moves, only for currencies that have data for the newest date
    threshold = rules.get("daily_move_percent")
    if threshold:
        for cur, series in sorted(rates.items()):
            if len(series) < 2 or series[-1][0] != latest:
                continue
            (_, prev), (d1, last) = series[-2], series[-1]
            change = (last - prev) / prev * 100
            if abs(change) >= threshold:
                ringgit = "weakened" if change > 0 else "strengthened"
                alerts.append(
                    f"{cur} moved {change:+.2f}% on {d1}: RM {prev:.4f} -> RM {last:.4f} "
                    f"per {unit(cur)} {cur} (ringgit {ringgit})"
                )

    return alerts


def dashboard_url() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")  # e.g. "CasperNg-2004/myr-rate-tracker"
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner.lower()}.github.io/{name}/"
    return ""


def send_email(alerts: list[str]) -> None:
    user = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not password:
        print("GMAIL_USER / GMAIL_APP_PASSWORD not set; skipping email.")
        return
    to = os.environ.get("ALERT_TO") or user

    msg = EmailMessage()
    first = alerts[0].split(":")[0]
    more = f" (+{len(alerts) - 1} more)" if len(alerts) > 1 else ""
    msg["Subject"] = f"MYR alert: {first}{more}"
    msg["From"] = user
    msg["To"] = to

    url = dashboard_url()
    body = "MYR exchange rate alerts\n\n" + "\n".join(f"- {a}" for a in alerts)
    if url:
        body += f"\n\nDashboard: {url}"
    body += "\n\nEdit alert rules in alerts.json in your repo."
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
    print(f"Email sent to {to}")


def main() -> int:
    if not RATES_FILE.exists():
        print("No rates.csv yet; nothing to check.")
        return 0

    rates = load_rates()
    rules = load_json(RULES_FILE, {})
    state = load_json(STATE_FILE, {})

    latest = max(series[-1][0] for series in rates.values())
    if state.get("last_checked_date") == latest:
        print(f"Already checked {latest}; no new data.")
        return 0

    alerts = check(rates, rules, state, latest)
    state["last_checked_date"] = latest

    if alerts:
        print("Alerts:\n" + "\n".join(f"  - {a}" for a in alerts))
        send_email(alerts)
    else:
        print(f"No alerts for {latest}.")

    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
