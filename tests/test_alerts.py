import pytest

import alerts
import common


@pytest.fixture
def sent(monkeypatch):
    """Capture emails instead of sending them."""
    messages = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def login(self, user, password):
            pass

        def send_message(self, msg):
            messages.append(msg)

    monkeypatch.setattr(alerts.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setenv("GMAIL_USER", "me@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "test-password")
    monkeypatch.setenv("GITHUB_REPOSITORY", "Someone/myr-rate-tracker")
    return messages


def base_history(project):
    project.write_rates(
        [
            ("2026-11-09", "USD", 4.20),
            ("2026-11-09", "SGD", 3.20),
            ("2026-11-09", "JPY", 0.0270),
            ("2026-11-10", "USD", 4.21),
            ("2026-11-10", "SGD", 3.20),
            ("2026-11-10", "JPY", 0.0271),
        ]
    )


# ---------- price levels ----------


def test_level_alert_fires_once_per_crossing(project, sent):
    base_history(project)
    project.write_rules({"levels": [{"currency": "USD", "above": 4.30}]})

    assert alerts.main() == 0  # 4.21: below the level
    assert sent == []

    project.add_rate("2026-11-11", "USD", 4.35)  # crosses above
    alerts.main()
    assert len(sent) == 1
    assert "USD above 4.3" in sent[0]["Subject"]

    project.add_rate("2026-11-12", "USD", 4.36)  # still above: no repeat
    alerts.main()
    assert len(sent) == 1

    project.add_rate("2026-11-13", "USD", 4.25)  # back below: no email
    alerts.main()
    assert len(sent) == 1

    project.add_rate("2026-11-14", "USD", 4.40)  # crosses again
    alerts.main()
    assert len(sent) == 2


def test_level_uses_dashboard_units(project, sent):
    """JPY rules are in RM per 100 JPY, like the dashboard cards."""
    base_history(project)
    project.write_rules({"levels": [{"currency": "JPY", "above": 2.70}]})  # 0.0271 * 100 = 2.71
    alerts.main()
    assert len(sent) == 1
    assert "per 100 JPY" in sent[0].get_content()


# ---------- daily moves ----------


def test_daily_move_alert(project, sent):
    base_history(project)
    project.write_rules({"daily_move_percent": 1.0})
    project.add_rate("2026-11-11", "USD", 4.30)  # +2.1%
    project.add_rate("2026-11-11", "SGD", 3.21)  # +0.3%, below threshold
    alerts.main()

    body = sent[0].get_content()
    assert "USD moved +2.14%" in body
    assert "ringgit weakened" in body
    assert "SGD" not in body


def test_stale_currency_moves_are_not_repeated(project, sent):
    """A currency with no data for the newest date must not re-send an old move."""
    base_history(project)
    project.write_rules({"daily_move_percent": 0.3})  # JPY moved +0.37% on 11-10
    alerts.main()
    assert "JPY" in sent[0].get_content()

    project.add_rate("2026-11-11", "USD", 4.211)  # only USD has new data, tiny move
    alerts.main()
    assert len(sent) == 1


# ---------- run-once-per-day ----------


def test_same_day_is_only_checked_once(project, sent, capsys):
    base_history(project)
    project.write_rules({"levels": [{"currency": "USD", "above": 1.0}]})
    alerts.main()
    alerts.main()
    assert len(sent) == 1
    assert "Already checked 2026-11-10" in capsys.readouterr().out
    assert project.read_state()["last_checked_date"] == "2026-11-10"


def test_no_rates_file_is_fine(project, sent):
    project.write_rules({"daily_move_percent": 1.0})
    assert alerts.main() == 0
    assert sent == []


# ---------- email ----------


def test_email_contents(project, sent):
    base_history(project)
    project.write_rules({"levels": [{"currency": "USD", "above": 1.0}, {"currency": "SGD", "above": 1.0}]})
    alerts.main()

    msg = sent[0]
    assert msg["Subject"] == "MYR alert: USD above 1.0 (+1 more)"
    assert msg["To"] == "me@example.com"
    assert "https://someone.github.io/myr-rate-tracker/" in msg.get_content()


def test_alert_to_overrides_recipient(project, sent, monkeypatch):
    monkeypatch.setenv("ALERT_TO", "other@example.com")
    base_history(project)
    project.write_rules({"levels": [{"currency": "USD", "above": 1.0}]})
    alerts.main()
    assert sent[0]["To"] == "other@example.com"


def test_missing_secrets_skip_email_without_failing(project, capsys):
    base_history(project)
    project.write_rules({"levels": [{"currency": "USD", "above": 1.0}]})
    assert alerts.main() == 0
    assert "skipping email" in capsys.readouterr().out


# ---------- rule validation ----------

CODES = ["USD", "SGD", "JPY"]


def test_valid_rules_pass_and_codes_are_uppercased():
    rules = alerts.validate_rules(
        {"daily_move_percent": 1, "levels": [{"currency": "usd", "below": 4}]}, CODES
    )
    assert rules["levels"][0]["currency"] == "USD"


@pytest.mark.parametrize(
    "rules, expected",
    [
        ({"extra": 1}, 'unknown setting "extra"'),
        ({"daily_move_percent": "1%"}, '"daily_move_percent" must be a number'),
        ({"daily_move_percent": 0}, '"daily_move_percent" must be a number'),
        ({"levels": {}}, '"levels" must be a list'),
        ({"levels": [{"currency": "USD", "Above": 4.3}]}, 'unknown key "Above"'),
        ({"levels": [{"currency": "XYZ", "above": 4.3}]}, 'currency "XYZ" is not in config.json'),
        ({"levels": [{"above": 4.3}]}, 'missing "currency"'),
        ({"levels": [{"currency": "USD", "above": 4, "below": 3}]}, 'exactly one of "above" or "below"'),
        ({"levels": [{"currency": "USD", "above": -1}]}, "must be a positive number"),
        ({"levels": [{"currency": "USD", "above": True}]}, "must be a positive number"),
        ([], "must be a JSON object"),
    ],
)
def test_invalid_rules_are_explained(rules, expected):
    with pytest.raises(common.ConfigError, match=expected.replace("(", r"\(").replace(")", r"\)")):
        alerts.validate_rules(rules, CODES)


def test_all_rule_errors_reported_together():
    rules = {"levels": [{"currency": "XYZ", "above": 1}, {"currency": "USD", "above": -1}]}
    with pytest.raises(common.ConfigError) as err:
        alerts.validate_rules(rules, CODES)
    assert "rule #1" in str(err.value)
    assert "rule #2" in str(err.value)


def test_invalid_rules_stop_run_without_touching_state(project, sent):
    base_history(project)
    project.write_rules({"levels": [{"currency": "USD", "Above": 1.0}]})
    assert alerts.main() == 1
    assert sent == []
    assert not project.state.exists()
