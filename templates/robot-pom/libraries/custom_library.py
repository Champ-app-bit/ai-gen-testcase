"""custom_library.py — pure-Python helpers for the ERP {{MODULE}} Robot suite.

  * dataLoader   -> Load Test Data / Load All Test Data (reads variables/test_data/*.json)
  * period rule  -> Hour In Period (mirror of ab_order/model.js:79-86 period bins)
  * amount/date  -> parse helpers for grid/detail assertions

Exposed to Robot via snake_case -> "Space Case".
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    _BANGKOK = ZoneInfo("Asia/Bangkok")
except Exception:  # pragma: no cover
    _BANGKOK = timezone(timedelta(hours=7))

ROBOT_LIBRARY_SCOPE = "GLOBAL"

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "resources", "variables", "test_data")

_ENTITY_FILES = {
    "user": "users.json",
    "users": "users.json",
    "order": "orders.json",
    "orders": "orders.json",
    # ── module-specific: generated per module ──
    # Add the module's own entity file(s) here, e.g. for {{ENTITY}}:
    #   "{{ENTITY}}": "{{ENTITY}}s.json",
    #   "{{ENTITY}}s": "{{ENTITY}}s.json",
    # (payment suite example: "payment"/"payments" -> "payments.json")
}


# ───────────────────────── data loader ─────────────────────────
def _load_json(filename):
    path = os.path.join(_DATA_DIR, filename)
    if not os.path.exists(path):
        raise AssertionError(f"Test data file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_all_test_data(entity):
    key = entity.strip().lower()
    if key not in _ENTITY_FILES:
        raise AssertionError(f"Unknown test-data entity: {entity}")
    return _load_json(_ENTITY_FILES[key])


def load_test_data(entity, key):
    for item in load_all_test_data(entity):
        if item.get("key") == key:
            return item
    raise AssertionError(f'Test data key "{key}" not found in "{entity}" dataset.')


def test_data_is_ready(record):
    """True when a test-data record has been filled in by dev/QA (`_status: ready`)."""
    return str((record or {}).get("_status", "todo")).lower() == "ready"


# ───────────────────────── period bins (ab_order/model.js:79-86) ─────────────────────────
# period 1=07-11, 2=12-15, 3=16-19, 4=20-23 (HOUR(expected_delivery_time)).
_PERIOD_BINS = {
    "1": range(7, 12),
    "2": range(12, 16),
    "3": range(16, 20),
    "4": range(20, 24),
}


def hour_in_period(hour, period):
    """Does an integer hour fall in the given period bin? (BVA oracle for delivery-window tests)."""
    return int(hour) in _PERIOD_BINS.get(str(period), [])


def hours_covered_by_any_period():
    """Return the sorted set of hours (0-23) that any period bin covers — lets a test
    assert 00:00-06:59 is covered by NO period (a real gap in the rule)."""
    covered = set()
    for rng in _PERIOD_BINS.values():
        covered.update(rng)
    return sorted(covered)


# ───────────────────────── date helpers ─────────────────────────
def bangkok_today_iso():
    now = datetime.now(_BANGKOK)
    return date(now.year, now.month, now.day).isoformat()


def days_ago_iso(days):
    now = datetime.now(_BANGKOK)
    return (date(now.year, now.month, now.day) - timedelta(days=int(days))).isoformat()


# ───────────────────────── numeric / string ─────────────────────────
def parse_amount(text):
    """Parse the first numeric value out of a grid cell like '1,599' / '฿1,599.00'."""
    if text is None:
        return None
    cleaned = re.sub(r"[฿\s,]|THB", "", str(text).replace("−", "-"))
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    return float(match.group(0)) if match else None


def extract_order_code(text):
    """Pull an 'O-#########' order code out of a label; fall back to trimmed text."""
    match = re.search(r"O-\d+", text or "")
    return match.group(0) if match else (text or "").strip()


# ── module-specific: generated per module ──
# Pure-Python oracles that mirror the module's FE/BE rules go here (keep each one a
# small, documented function with a file:line evidence pointer). Payment suite examples:
#
#   def extract_payment_code(text):
#       """Pull a 'P-#########' payment code out of a grid cell; fall back to trimmed text."""
#       match = re.search(r"P-\d+", text or "")
#       return match.group(0) if match else (text or "").strip()
#
#   def paid_cap(amount):
#       """form.payment.vue:305-323 — the inclusive max payable: ceil(amount * 1.03)."""
#       return math.ceil(float(amount) * 1.03)
#
#   def expected_remain(amount, paid):
#       """Mirror of the FE remain rule ('' when paid is rejected, else the remainder)."""
#       ...

_ = math  # placeholder-body module: math is used by generated oracles (e.g. paid_cap)
