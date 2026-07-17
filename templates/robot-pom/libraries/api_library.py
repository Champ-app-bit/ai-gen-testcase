"""api_library — thin Robot Framework wrapper over `requests` for ERP ab_order API tests.

Mirrors the WNW POM's api_library but adds ERP authentication: the ERP backend
mounts every app folder at /<feature> (server.js:41), so ab_order lives at
`${API_BASE_URL}/ab_order` and auth at `${API_BASE_URL}/auth`.

Auth model (erp-api-2025/app/auth/controller.js:56-66, middleware/authenMiddleware.js:7-13):
  POST /auth {username,password} -> {status, data:{token, accessToken:"Bearer <jwt>", ...}}
  Protected endpoints require BOTH headers, exactly like the FE httpServices.getHeader():
    Authorization:   "Bearer <jwt>"      (authenMiddleware splits on space, takes [1])
    X-Authorization: <static api token>  (Config.apiToken)

Every keyword returns a Robot-friendly dict: {status, json, text}.

Usage (Robot):
    Library    api_library.py    ${API_BASE_URL}    ${API_STATIC_TOKEN}
    ${token}=  API Login    ${USER}[username]    ${USER}[password]
    ${resp}=   API Get    /ab_order?orderBy=id&ascDesc=desc&limit=10
    Should Be Equal As Integers    ${resp}[status]    200
"""

import json
import warnings

import requests

warnings.filterwarnings("ignore")
try:
    requests.packages.urllib3.disable_warnings()
except Exception:
    pass


class api_library:
    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self, base_url="{{API_BASE_URL}}", static_token=""):
        # static_token = Config.apiToken (X-Authorization). Defaults to the value baked
        # into util/config.js; override from a variable file if it rotates.
        self.base_url = base_url.rstrip("/")
        self.static_token = static_token or "{{API_STATIC_TOKEN}}"
        self._bearer = None  # "Bearer <jwt>" captured after API Login

    # ───────────────────────── internals ─────────────────────────
    def _url(self, path):
        if path.startswith("http"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _headers(self, authed=True):
        headers = {"X-Authorization": self.static_token}
        if authed and self._bearer:
            headers["Authorization"] = self._bearer
        return headers

    def _as_payload(self, payload):
        """Robot passes inline `{"k": v}` as a STRING — parse it to a real dict so
        requests serializes an object, not a quoted JSON string. Accepts dict/None too."""
        if payload is None or payload == "":
            return {}
        if isinstance(payload, str):
            return json.loads(payload)
        return payload

    def _wrap(self, resp):
        try:
            body = resp.json()
        except ValueError:
            body = {}
        return {"status": resp.status_code, "json": body, "text": resp.text}

    # ───────────────────────── auth ─────────────────────────
    def api_login(self, username, password):
        """POST /auth; store the Bearer token for later authed calls; return the token.

        Raises AssertionError if the backend does not return an accessToken (so a
        credential/typo problem fails loudly instead of silently running unauthed)."""
        resp = requests.post(
            self._url("/auth"),
            json={"username": username, "password": password},
            headers={"X-Authorization": self.static_token},
            timeout=30,
            verify=False,
        )
        data = (resp.json() or {}).get("data") if resp.headers.get("content-type", "").startswith("application/json") else None
        access = (data or {}).get("accessToken") if data else None
        if not access:
            raise AssertionError(
                f"API Login failed for '{username}': no accessToken in response "
                f"(status={resp.status_code}, body={resp.text[:300]})"
            )
        self._bearer = access
        return access

    def set_bearer_token(self, bearer):
        """Inject a raw 'Bearer <jwt>' string (e.g. reused from a UI session)."""
        self._bearer = bearer

    def clear_auth(self):
        """Drop the stored token so the next call is unauthenticated (auth tests)."""
        self._bearer = None

    def has_bearer(self):
        """True when a bearer token is currently stored. Lets `Ensure Api Session`
        self-heal after an auth test calls Clear Auth (the library is GLOBAL scope,
        so a cleared token would otherwise 401 every later factory call)."""
        return bool(self._bearer)

    # ───────────────────────── verbs ─────────────────────────
    def api_get(self, path, authed=True, timeout=30):
        resp = requests.get(self._url(path), headers=self._headers(authed), timeout=float(timeout), verify=False)
        return self._wrap(resp)

    def api_post_json(self, path, payload=None, authed=True, timeout=30):
        resp = requests.post(
            self._url(path), json=self._as_payload(payload), headers=self._headers(authed), timeout=float(timeout), verify=False
        )
        return self._wrap(resp)

    def api_put_json(self, path, payload=None, authed=True, timeout=30):
        resp = requests.put(
            self._url(path), json=self._as_payload(payload), headers=self._headers(authed), timeout=float(timeout), verify=False
        )
        return self._wrap(resp)
