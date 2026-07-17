#!/usr/bin/env python3
"""Soft-delete the disposable records + orders the suite minted during a run.

Usage: python scripts/cleanup_minted.py <output.xml> [<output.xml> ...]

The factory (Mint Fresh Order / module factory in suite_helpers.resource) logs a
marker line for every disposable record it creates. This script collects those ids
from output.xml and soft-deletes them, dropping the factory template's own order
id as a safety net.

Gotchas encoded here (verified live 2026-07-16 on the payment suite):
  * delete accepts ONLY a single-element JSON array per call — {"id": [n]}.
    A multi-id array 500s (BE builds an invalid SQL log string first), so one
    id per request.
Credentials come from ERP_ADMIN_USER / ERP_ADMIN_PASS (falls back to the local
users.json for developer machines). Never fails the build: cleanup problems are
reported but exit code stays 0 so test results still upload.
"""
from __future__ import annotations

import json
import os
import re
import sys
import warnings

import requests

warnings.filterwarnings("ignore")
try:
    requests.packages.urllib3.disable_warnings()
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
API_BASE = os.environ.get("ERP_API_BASE", "{{API_BASE_URL}}")
STATIC_TOKEN = os.environ.get("ERP_STATIC_TOKEN", "{{API_STATIC_TOKEN}}")

# ── module-specific: generated per module ──
# Marker regex. The base factory (Mint Fresh Order) logs `MINTED order=<oid>`.
# A module factory that mints child records on top of the order should log BOTH ids
# in one marker and extend the regex + the delete chain in main(). Payment example:
#   MINTED_RE = re.compile(r"MINTED payment=(\d+) order=(\d+)")
#   (then delete the payments FIRST — they reference the orders — see main())
MINTED_RE = re.compile(r"MINTED order=(\d+)")


def load_credentials():
    user = os.environ.get("ERP_ADMIN_USER", "").strip()
    pw = os.environ.get("ERP_ADMIN_PASS", "").strip()
    if user and pw:
        return user, pw
    users_path = os.path.join(ROOT, "resources", "variables", "test_data", "users.json")
    try:
        with open(users_path, encoding="utf-8") as fh:
            for rec in json.load(fh):
                if rec.get("key") == "admin" and rec.get("username"):
                    return rec["username"], rec["password"]
    except OSError:
        pass
    return "", ""


def template_order_id(headers):
    """Resolve the factory template's order id by code so it can never be deleted."""
    orders_path = os.path.join(ROOT, "resources", "variables", "test_data", "orders.json")
    try:
        with open(orders_path, encoding="utf-8") as fh:
            code = next(
                (r.get("code") for r in json.load(fh) if r.get("key") == "factory_template"),
                None,
            )
    except OSError:
        return None
    if not code:
        return None
    resp = requests.get(
        f"{API_BASE}/ab_order",
        params={"search": code, "orderBy": "id", "ascDesc": "desc", "limit": 50, "page": 1},
        headers=headers,
        timeout=30,
        verify=False,
    )
    rows = ((resp.json() or {}).get("data") or {}).get("data") or []
    for row in rows:
        if row.get("code") == code:
            return int(row["id"])
    return None


def _delete_each(path, ids, headers, label):
    ok, failed = 0, []
    for _id in sorted(ids):
        resp = requests.post(
            f"{API_BASE}{path}",
            json={"id": [_id]},
            headers=headers,
            timeout=30,
            verify=False,
        )
        if resp.status_code == 200:
            ok += 1
        else:
            failed.append((_id, resp.status_code))
    print(f"cleanup: soft-deleted {ok}/{len(ids)} minted {label}")
    for _id, status in failed:
        print(f"cleanup: WARNING — could not delete {label[:-1]} {_id} (HTTP {status})")


def main():
    xml_paths = [p for p in sys.argv[1:] if os.path.exists(p)]
    if not xml_paths:
        print("cleanup: no output.xml found — nothing to do")
        return

    order_ids = set()
    for path in xml_paths:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for oid in MINTED_RE.findall(fh.read()):
                order_ids.add(int(oid))
    if not order_ids:
        print("cleanup: no minted ids in the run — nothing to do")
        return

    user, pw = load_credentials()
    if not user:
        print(f"cleanup: WARNING — no admin credentials; {len(order_ids)} orders left behind")
        return

    login = requests.post(
        f"{API_BASE}/auth",
        json={"username": user, "password": pw},
        headers={"X-Authorization": STATIC_TOKEN},
        timeout=30,
        verify=False,
    )
    bearer = ((login.json() or {}).get("data") or {}).get("accessToken")
    if not bearer:
        print(f"cleanup: WARNING — API login failed ({login.status_code}); minted data left behind")
        return
    headers = {"X-Authorization": STATIC_TOKEN, "Authorization": bearer}

    protected = template_order_id(headers)
    if protected in order_ids:
        order_ids.discard(protected)
        print(f"cleanup: protected factory template order id {protected}")

    # ── module-specific: generated per module ──
    # Delete CHILD records first (they reference the orders), then the orders.
    # Payment example (with the two-group MINTED_RE above):
    #   _delete_each("{{API_PREFIX}}/delete", payment_ids, headers, "payments")
    #   _delete_each("/ab_order/delete", order_ids, headers, "orders")
    _delete_each("/ab_order/delete", order_ids, headers, "orders")


if __name__ == "__main__":
    main()
