*** Settings ***
Documentation    Shared suite setup/helpers for the ERP {{MODULE}} tests. Each TC lives in its
...              own .robot file and reuses these to avoid duplicating login/data plumbing.
Resource         ../imports/app_imports.robot

*** Keywords ***
# ── generic UI suite setup ──
Setup Login As User
    [Documentation]    beforeEach for redirect/permission tests: log in as a named account
    ...    WITHOUT navigating to {{ROUTE}} (the test drives the direct-URL navigation itself
    ...    to observe the redirect). Skips if the account is not provisioned.
    [Arguments]    ${user_key}
    Open ERP Browser
    Login As Data User    ${user_key}

# ── API suite setup ──
Setup Api As Admin
    [Documentation]    beforeEach for authed API tests: log in via /auth and store the token.
    ...    Skips if the admin account is not provisioned.
    ${user}=    Load Test Data    user    admin
    ${ready}=    Test Data Is Ready    ${user}
    IF    not ${ready}
        Skip    BLOCKED: ERP admin account not provisioned — fill users.json (docs §1).
    END
    API Login    ${user}[username]    ${user}[password]
    RETURN    ${user}

Ensure Api Session
    [Documentation]    Log in to the API as admin when no bearer is stored (api_library is
    ...    GLOBAL scope, so the token persists across suites — but auth tests call Clear Auth).
    ${has}=    Has Bearer
    IF    not ${has}
        Setup Api As Admin
    END

# ── data gates ──
Require User Account
    [Documentation]    Skip a test until a named users.json account is provisioned.
    [Arguments]    ${user_key}
    ${u}=    Load Test Data    user    ${user_key}
    ${ready}=    Test Data Is Ready    ${u}
    IF    not ${ready}
        Skip    BLOCKED: account "${user_key}" not provisioned — fill users.json + set _status=ready (docs §1).
    END
    RETURN    ${u}

# ── order-id resolver (no seed needed: tests that just need SOME real order) ──
Resolve Any Order Id
    [Documentation]    Return the newest order id via GET /ab_order?limit=1 (cached per run).
    ...    For tests that need a real order_id but not a specific one. Skips if the list is
    ...    empty on staging.
    Ensure Api Session
    ${cached}=    Get Variable Value    \${ANY_ORDER_ID}    ${NONE}
    IF    $cached is not None    RETURN    ${cached}
    ${resp}=    API Get    ${ROUTES}[API_ORDER_LIST]?orderBy=id&ascDesc=desc&limit=1&page=1
    ${id}=    Evaluate    ((($resp['json'] or {}).get('data') or {}).get('data') or [{}])[0].get('id')
    IF    $id is None    Skip    BLOCKED: no orders returned by /ab_order on staging — cannot resolve a real order id.
    Set Global Variable    ${ANY_ORDER_ID}    ${id}
    RETURN    ${id}

# ── order factory (rerun-safe: mint disposable data per test, cleaned up after) ──
# Every disposable order logs a `MINTED order=..` marker that scripts/cleanup_minted.py
# soft-deletes after the run. A module factory that creates child records on top of
# the minted order should log BOTH ids in one marker (see the generated section below
# and scripts/cleanup_minted.py). Pattern verified live end-to-end 2026-07-16 (payment).

Require Factory Template
    [Documentation]    Gate on the clean template order (orders.json "factory_template") and
    ...    return its numeric id (resolved once per run by code via the list API).
    ${tpl}=    Load Test Data    order    factory_template
    ${ready}=    Test Data Is Ready    ${tpl}
    IF    not ${ready}
        Skip    BLOCKED: factory template order not provided — fill orders.json "factory_template" (docs §5).
    END
    Ensure Api Session
    ${cached}=    Get Variable Value    \${FACTORY_TEMPLATE_ID}    ${NONE}
    IF    $cached is None
        ${id}=    Set Variable    ${tpl}[id]
        IF    $id is None or $id == ''
            ${id}=    Resolve Order Id By Code    ${tpl}[code]
        END
        Set Global Variable    ${FACTORY_TEMPLATE_ID}    ${id}
    END
    RETURN    ${FACTORY_TEMPLATE_ID}

Resolve Order Id By Code
    [Documentation]    Find an order id via GET /ab_order?search=<code> (exact code match).
    [Arguments]    ${code}
    ${resp}=    API Get    ${ROUTES}[API_ORDER_LIST]?search=${code}&orderBy=id&ascDesc=desc&limit=50&page=1
    Should Be Equal As Integers    ${resp}[status]    200    order lookup by code "${code}" failed: HTTP ${resp}[status]
    ${rows}=    Evaluate    (($resp['json'] or {}).get('data') or {}).get('data') or []
    FOR    ${row}    IN    @{rows}
        IF    $row['code'] == $code    RETURN    ${row}[id]
    END
    Fail    order with code "${code}" not found via the list API — check orders.json factory_template

Mint Fresh Order
    [Documentation]    Duplicate the factory template into a disposable order; return {id, code, amount}.
    ...    Logs a MINTED marker so scripts/cleanup_minted.py soft-deletes it after the run.
    ${tpl_id}=    Require Factory Template
    ${resp}=    API Put Json    ${ROUTES}[API_ORDER_DUPLICATE]/${tpl_id}
    Should Be Equal As Integers    ${resp}[status]    200    duplicateOrder failed: ${resp}[text]
    ${new_id}=    Evaluate    (($resp['json'] or {}).get('data') or {}).get('order_id')
    ${new_code}=    Evaluate    (($resp['json'] or {}).get('data') or {}).get('order_code')
    Should Be True    $new_id is not None    duplicateOrder returned no order id: ${resp}[text]
    Log    MINTED order=${new_id}
    ${amount}=    Get Minted Order Amount    ${new_id}
    ${order}=    Create Dictionary    id=${new_id}    code=${new_code}    amount=${amount}
    RETURN    ${order}

Get Minted Order Amount
    [Documentation]    Read the disposable order's total (falls back to 50 if the field is absent).
    [Arguments]    ${order_id}
    ${resp}=    API Get    ${ROUTES}[API_ORDER_LIST]?search=${order_id}&limit=5&page=1
    ${rows}=    Evaluate    (($resp['json'] or {}).get('data') or {}).get('data') or []
    FOR    ${row}    IN    @{rows}
        IF    str($row['id']) == str($order_id)
            ${amt}=    Evaluate    $row.get('total') or $row.get('amount') or 50
            RETURN    ${amt}
        END
    END
    RETURN    ${50}

# ── DB gate ──
Require Db Access
    [Documentation]    Skip a DB-backed test unless DB_* env vars are configured. NOTE the
    ...    MCP mirror is a DIFFERENT database from this staging API — these creds must point
    ...    at the staging DB to be meaningful.
    ${ok}=    Run Keyword And Return Status    Require Db
    IF    not ${ok}
        Skip    BLOCKED: DB access not configured — set DB_HOST/DB_USER/DB_PASSWORD/DB_NAME (docs §3).
    END
    Connect To App Db

# ── module-specific: generated per module ──
# Module UI setups, data gates and factories are GENERATED with the tests. They follow
# these payment-suite shapes (commented examples — copy, rename, adapt):
#
# Setup Payment List As Admin
#     [Documentation]    beforeEach for UI list/action suites: open browser, log in as the
#     ...    provisioned admin, land on the module list route.
#     Open ERP Browser
#     Login As Data User    admin
#     Open Payment List
#
# Require Payment Data
#     [Documentation]    Skip a test until its seed record (payments.json key) is provided.
#     [Arguments]    ${payment_key}
#     ${p}=    Load Test Data    payment    ${payment_key}
#     ${ready}=    Test Data Is Ready    ${p}
#     IF    not ${ready}
#         Skip    BLOCKED: seed payment "${payment_key}" not provided — fill payments.json + set _status=ready (docs §2).
#     END
#     RETURN    ${p}
#
# Mint Fresh Payment        # module factory chaining on Mint Fresh Order
#     [Arguments]    ${status}=2
#     ${order}=    Mint Fresh Order
#     ...POST {{API_PREFIX}} on ${order}[id]...
#     Log    MINTED payment=${pid} order=${order}[id]    # pair marker -> cleanup_minted.py
