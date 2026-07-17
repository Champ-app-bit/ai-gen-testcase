#!/usr/bin/env python3
"""Write resources/variables/test_data/users.json from environment variables.

CI step: credentials live in GitHub Secrets, never in the repo. An account whose
env vars are missing is written with _status=todo so its tests Skip gracefully
instead of failing with bogus credentials.

Env vars: ERP_ADMIN_USER / ERP_ADMIN_PASS / ERP_RO_USER / ERP_RO_PASS
          ERP_NOVIEW_USER / ERP_NOVIEW_PASS (optional — only needed when the
          module has a no-view-permission redirect test)
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "..", "resources", "variables", "test_data", "users.json")

ACCOUNTS = [
    {
        "key": "admin",
        "user_env": "ERP_ADMIN_USER",
        "pass_env": "ERP_ADMIN_PASS",
        "_note": "Full-permission ERP user (flag_insert/delete/update all true) on {{MODULE}}.",
    },
    {
        "key": "readonly",
        "user_env": "ERP_RO_USER",
        "pass_env": "ERP_RO_PASS",
        "_note": "User WITH {{MODULE}} view but WITHOUT flag_insert/flag_update — perm tests.",
    },
    # OPTIONAL account: keep only if the module has a no-view-permission redirect test.
    # Missing env vars just mean _status=todo, so leaving it here is harmless.
    {
        "key": "noview",
        "user_env": "ERP_NOVIEW_USER",
        "pass_env": "ERP_NOVIEW_PASS",
        "_note": "User with NO view permission on appSlug '{{MODULE}}' — redirect test (optional).",
    },
]


def main() -> None:
    records = []
    for acc in ACCOUNTS:
        username = os.environ.get(acc["user_env"], "").strip()
        password = os.environ.get(acc["pass_env"], "").strip()
        ready = bool(username and password)
        records.append(
            {
                "key": acc["key"],
                "_status": "ready" if ready else "todo",
                "_note": acc["_note"],
                "username": username,
                "password": password,
            }
        )
        state = "ready" if ready else f"todo (missing {acc['user_env']}/{acc['pass_env']})"
        print(f"users.json: {acc['key']} -> {state}")

    with open(TARGET, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"wrote {os.path.normpath(TARGET)}")


if __name__ == "__main__":
    main()
