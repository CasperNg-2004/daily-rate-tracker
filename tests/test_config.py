import json
from pathlib import Path

import pytest

import alerts
import common

REPO = Path(__file__).resolve().parent.parent


def test_valid_config_loads(project):
    currencies = common.load_currencies()
    assert list(currencies) == ["USD", "SGD", "JPY"]
    assert currencies["JPY"]["unit"] == 100


def test_bad_config_lists_every_problem(project):
    project.write_config({"usd": {"name": "US Dollar", "unit": 0}, "SGD": {"unit": 1}})
    with pytest.raises(common.ConfigError) as err:
        common.load_currencies()
    msg = str(err.value)
    assert "3 capital letters" in msg
    assert '"unit" must be a positive whole number' in msg
    assert '"name" must be text' in msg


def test_empty_config_is_rejected(project):
    project.config.write_text(json.dumps({"currencies": {}}))
    with pytest.raises(common.ConfigError, match="non-empty"):
        common.load_currencies()


def test_broken_json_reports_line_and_column(project):
    project.config.write_text('{"currencies": {"USD": ')
    with pytest.raises(common.ConfigError, match=r"not valid JSON \(line 1, column \d+\)"):
        common.load_currencies()


# The checks below run against the REAL files in the repo, so CI fails
# if someone pushes a broken config.json or alerts.json.


def test_repo_config_json_is_valid(monkeypatch):
    monkeypatch.setattr(common, "CONFIG_FILE", REPO / "config.json")
    assert common.load_currencies()


def test_repo_alerts_json_is_valid(monkeypatch):
    monkeypatch.setattr(common, "CONFIG_FILE", REPO / "config.json")
    codes = list(common.load_currencies())
    rules = common.read_json(REPO / "alerts.json")
    alerts.validate_rules(rules, codes)
