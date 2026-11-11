"""
Shared helpers for collect.py and alerts.py.

config.json is the single place that lists which currencies are tracked and
which display unit each uses (e.g. RM per 100 JPY). The dashboard reads the
same file, so adding a currency there updates everything.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.json"
RATES_FILE = ROOT / "data" / "rates.csv"


class ConfigError(Exception):
    """Raised when config.json or alerts.json is invalid. Message lists every problem."""


def read_json(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise ConfigError(f"{path.name} not found")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path.name} is not valid JSON (line {e.lineno}, column {e.colno}): {e.msg}")


def load_currencies() -> dict[str, dict]:
    """Return {"USD": {"name": "US Dollar", "unit": 1}, ...} after validating config.json."""
    cfg = read_json(CONFIG_FILE)
    currencies = cfg.get("currencies") if isinstance(cfg, dict) else None
    if not isinstance(currencies, dict) or not currencies:
        raise ConfigError('config.json must contain a non-empty "currencies" object')

    errors = []
    for code, info in currencies.items():
        where = f'config.json currency "{code}"'
        if not re.fullmatch(r"[A-Z]{3}", code):
            errors.append(f"{where}: code must be 3 capital letters, like USD")
        if not isinstance(info, dict):
            errors.append(f"{where}: must be an object with name and unit")
            continue
        if not isinstance(info.get("name"), str) or not info["name"].strip():
            errors.append(f'{where}: "name" must be text')
        unit = info.get("unit", 1)
        if not isinstance(unit, int) or isinstance(unit, bool) or unit <= 0:
            errors.append(f'{where}: "unit" must be a positive whole number, like 1 or 100')
    if errors:
        raise ConfigError("\n".join(errors))
    return currencies


def fail(err: ConfigError) -> int:
    print("Configuration problem:", file=sys.stderr)
    for line in str(err).splitlines():
        print(f"  - {line}", file=sys.stderr)
    return 1
