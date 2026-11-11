import csv
import io
import json
import urllib.error
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

import collect


def fake_api_rows(url, rate=0.25):
    """Build a Frankfurter-style response for every weekday in the requested range."""
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    codes = q["quotes"].split(",")
    day, end = date.fromisoformat(q["from"]), date.fromisoformat(q["to"])
    rows = []
    while day <= end:
        if day.weekday() < 5:
            rows += [{"date": day.isoformat(), "base": "MYR", "quote": c, "rate": rate} for c in codes]
        day += timedelta(days=1)
    return rows


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeUrlopen:
    """Replays a plan of failures, then answers like the real API."""

    def __init__(self, plan=(), rate=0.25):
        self.plan = list(plan)
        self.rate = rate
        self.calls = []

    def __call__(self, req, timeout=None):
        self.calls.append(req.full_url)
        step = self.plan.pop(0) if self.plan else "ok"
        if step == "network":
            raise urllib.error.URLError("temporary failure")
        if isinstance(step, int):
            raise urllib.error.HTTPError(req.full_url, step, "error", {}, None)
        return FakeResponse(json.dumps(fake_api_rows(req.full_url, self.rate)).encode())


@pytest.fixture
def api(monkeypatch):
    def install(plan=(), rate=0.25):
        fake = FakeUrlopen(plan, rate)
        monkeypatch.setattr(collect.urllib.request, "urlopen", fake)
        return fake

    return install


def read_rows(project):
    with project.rates.open(newline="") as f:
        return list(csv.DictReader(f))


def test_first_run_backfills_a_year(project, api):
    fake = api()
    assert collect.main() == 0

    assert len(fake.calls) == 1
    start = date.today() - timedelta(days=collect.BACKFILL_DAYS)
    assert f"from={start.isoformat()}" in fake.calls[0]

    rows = read_rows(project)
    assert {r["currency"] for r in rows} == {"USD", "SGD", "JPY"}
    # API rate 0.25 foreign units per MYR -> stored as 4 MYR per unit
    assert all(float(r["myr_per_unit"]) == pytest.approx(4.0) for r in rows)


def test_second_run_adds_no_duplicates(project, api):
    api()
    collect.main()
    first = read_rows(project)

    fake = api()
    collect.main()
    second = read_rows(project)

    assert second == first
    keys = [(r["date"], r["currency"]) for r in second]
    assert len(keys) == len(set(keys))
    # Second run only asks for data from the last saved date onwards
    last_saved = max(r["date"] for r in first)
    assert f"from={last_saved}" in fake.calls[0]


def test_saved_history_is_never_overwritten(project, api, capsys):
    api(rate=0.25)
    collect.main()
    before = read_rows(project)

    api(rate=0.5)  # API now reports different values for the same days
    collect.main()

    assert read_rows(project) == before
    assert "Added 0 new rows" in capsys.readouterr().out


def test_new_currency_gets_backfilled(project, api):
    api()
    collect.main()

    project.write_config(
        {
            "USD": {"name": "US Dollar", "unit": 1},
            "SGD": {"name": "Singapore Dollar", "unit": 1},
            "JPY": {"name": "Japanese Yen", "unit": 100},
            "AUD": {"name": "Australian Dollar", "unit": 1},
        }
    )
    fake = api()
    collect.main()

    start = date.today() - timedelta(days=collect.BACKFILL_DAYS)
    assert f"from={start.isoformat()}" in fake.calls[0]
    rows = read_rows(project)
    usd = sum(r["currency"] == "USD" for r in rows)
    aud = sum(r["currency"] == "AUD" for r in rows)
    assert aud == usd > 0


def test_temporary_errors_are_retried(project, api):
    fake = api(plan=["network", 503])
    assert collect.main() == 0
    assert len(fake.calls) == 3
    assert project.rates.exists()


def test_permanent_error_is_not_retried(project, api):
    fake = api(plan=[400])
    assert collect.main() == 1
    assert len(fake.calls) == 1
    assert not project.rates.exists()


def test_gives_up_after_all_retries(project, api):
    fake = api(plan=["network"] * 10)
    assert collect.main() == 1
    assert len(fake.calls) == collect.RETRIES + 1


def test_invalid_config_stops_before_calling_api(project, api):
    project.write_config({"usd": {"name": "x", "unit": 1}})
    fake = api()
    assert collect.main() == 1
    assert fake.calls == []
