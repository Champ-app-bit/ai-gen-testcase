"""db_library.py — MySQL verification helpers for the ERP ab_order suite.

Unlike the WNW project (which had no DB access and shipped a stub), the ERP app is
backed by MySQL and several order-list rules can ONLY be proven at the row level:
  * soft delete           -> `deleted` becomes NOT NULL, row disappears from the list
  * cancel                -> status_order=7 + cancel_remark/cancel_id populated
  * toggle Bill bug        -> ts_billed can be SET but never cleared (model.js:961 uses `=`)
  * refund                 -> status_order=6, price capped at total
  * created_since cap      -> orders older than the window are excluded

Connection is OPTIONAL and OFF by default. Provide DB_* variables (see env_dev.yaml)
to enable it; otherwise `Require Db` raises a clear skip-worthy error so DB-backed
assertions are gated exactly like WNW gated its missing test data — never silently
passing.

Driver: pymysql (pure-python, no build step). Add `pymysql` to requirements.txt.
"""

from __future__ import annotations

ROBOT_LIBRARY_SCOPE = "GLOBAL"

_NO_DRIVER = (
    "pymysql is not installed — run `pip install pymysql` (see requirements.txt) "
    "before using DB verification keywords."
)
_NOT_CONFIGURED = (
    "DB access is not configured — set DB_HOST/DB_USER/DB_PASSWORD/DB_NAME in a "
    "variable file (env_dev.yaml) to enable row-level verification. "
    "See docs/QA-ERP-order_v3-Automation-DataRequest.md."
)

try:
    import pymysql  # noqa: F401

    _HAS_DRIVER = True
except Exception:
    _HAS_DRIVER = False


class db_library:
    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self, host="", user="", password="", name="", port=3306):
        self.cfg = dict(host=host, user=user, password=password, name=name, port=int(port))
        self._conn = None

    # ───────────────────────── lifecycle ─────────────────────────
    def require_db(self):
        """Fail with a skip-worthy message unless a real DB connection is available.
        Call at suite setup for DB-backed suites so they Skip cleanly when unconfigured."""
        if not _HAS_DRIVER:
            raise AssertionError(_NO_DRIVER)
        if not (self.cfg["host"] and self.cfg["name"]):
            raise AssertionError(_NOT_CONFIGURED)

    def connect_to_app_db(self):
        self.require_db()
        import pymysql
        from pymysql.cursors import DictCursor

        self._conn = pymysql.connect(
            host=self.cfg["host"],
            user=self.cfg["user"],
            password=self.cfg["password"],
            database=self.cfg["name"],
            port=self.cfg["port"],
            cursorclass=DictCursor,
            autocommit=True,
        )
        return True

    def disconnect_from_app_db(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _cursor(self):
        if not self._conn:
            self.connect_to_app_db()
        return self._conn.cursor()

    # ───────────────────────── queries ─────────────────────────
    def query_one(self, sql, *params):
        """Run a parameterized SELECT and return the first row (dict) or None."""
        with self._cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def get_order_field(self, order_id, field):
        """Return a single column value for an ab_order row (None if row missing)."""
        row = self.query_one(f"SELECT `{field}` AS v FROM ab_order WHERE id=%s", order_id)
        return row["v"] if row else None

    def order_status_should_be(self, order_id, expected):
        actual = self.get_order_field(order_id, "status_order")
        assert str(actual) == str(expected), (
            f"ab_order.id={order_id} status_order={actual}, expected {expected}"
        )

    def order_should_be_soft_deleted(self, order_id):
        deleted = self.get_order_field(order_id, "deleted")
        assert deleted is not None, f"ab_order.id={order_id} deleted IS NULL (not soft-deleted)"

    def order_should_not_be_soft_deleted(self, order_id):
        deleted = self.get_order_field(order_id, "deleted")
        assert deleted is None, f"ab_order.id={order_id} deleted={deleted} (expected NULL)"

    def order_field_should_be_null(self, order_id, field):
        v = self.get_order_field(order_id, field)
        assert v is None, f"ab_order.id={order_id} {field}={v}, expected NULL"

    def order_field_should_not_be_null(self, order_id, field):
        v = self.get_order_field(order_id, field)
        assert v is not None, f"ab_order.id={order_id} {field} IS NULL, expected a value"

    def find_order_id_by_status(self, status_order, extra_where=""):
        """Return the newest non-deleted order id at a given status_order (or None).
        `extra_where` is a trusted, test-authored fragment (e.g. 'AND ts_billed IS NULL')."""
        where = "deleted IS NULL AND status_order=%s"
        if extra_where:
            where += f" {extra_where}"
        row = self.query_one(
            f"SELECT id FROM ab_order WHERE {where} ORDER BY id DESC LIMIT 1", status_order
        )
        return row["id"] if row else None
