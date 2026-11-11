"""
Shared test fixtures.

`project` builds a throw-away copy of the repo layout in a temp folder and
points every script at it, so tests never touch the real data files.
"""

import json

import pytest

import alerts
import collect
import common

TEST_CURRENCIES = {
    "USD": {"name": "US Dollar", "unit": 1},
    "SGD": {"name": "Singapore Dollar", "unit": 1},
    "JPY": {"name": "Japanese Yen", "unit": 100},
}


class Project:
    def __init__(self, root):
        self.root = root
        self.config = root / "config.json"
        self.rules = root / "alerts.json"
        self.rates = root / "data" / "rates.csv"
        self.state = root / "data" / "alert_state.json"

    def write_config(self, currencies=None):
        self.config.write_text(json.dumps({"currencies": currencies or TEST_CURRENCIES}))

    def write_rules(self, rules):
        self.rules.write_text(rules if isinstance(rules, str) else json.dumps(rules))

    def write_rates(self, rows):
        """rows: [(date, currency, myr_per_unit), ...]"""
        self.rates.parent.mkdir(parents=True, exist_ok=True)
        lines = ["date,currency,myr_per_unit"] + [f"{d},{c},{v}" for d, c, v in rows]
        self.rates.write_text("\n".join(lines) + "\n")

    def add_rate(self, d, cur, value):
        with self.rates.open("a") as f:
            f.write(f"{d},{cur},{value}\n")

    def read_state(self):
        return json.loads(self.state.read_text())


@pytest.fixture
def project(tmp_path, monkeypatch):
    p = Project(tmp_path)
    p.write_config()

    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "CONFIG_FILE", p.config)
    monkeypatch.setattr(common, "RATES_FILE", p.rates)
    monkeypatch.setattr(collect, "RATES_FILE", p.rates)
    monkeypatch.setattr(alerts, "RATES_FILE", p.rates)
    monkeypatch.setattr(alerts, "STATE_FILE", p.state)
    monkeypatch.setattr(alerts, "RULES_FILE", p.rules)
    monkeypatch.setattr(alerts, "UNITS", {})
    monkeypatch.setattr(collect, "RETRY_WAIT_SECONDS", 0)

    # Never send real email from tests
    for var in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "ALERT_TO", "GITHUB_REPOSITORY"):
        monkeypatch.delenv(var, raising=False)
    return p
