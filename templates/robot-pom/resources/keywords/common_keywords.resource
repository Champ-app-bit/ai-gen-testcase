*** Settings ***
Documentation    Common base keywords for the ERP {{MODULE}} suite: browser lifecycle,
...              navigation/settle waits, robust input/click helpers, and SweetAlert2
...              assertions. No page-specific selectors live here. Mirrors the order_v3
...              suite's common layer (same live-verified gotchas: hash router, unreliable
...              native events).
Library          SeleniumLibrary
Library          Collections
Library          String
Library          custom_library.py
Library          db_library.py    ${DB_HOST}    ${DB_USER}    ${DB_PASSWORD}    ${DB_NAME}    ${DB_PORT}
Library          api_library.py    ${API_BASE_URL}    ${API_STATIC_TOKEN}
Variables        ../variables/routes.yaml
Variables        ../variables/timeouts.yaml
Variables        ../variables/messages.yaml
Resource         ../locators/swal_locators.resource

*** Variables ***
# Defaults — overridden by env_dev.yaml at run time.
${BASE_URL}            {{BASE_URL}}
${API_BASE_URL}        {{API_BASE_URL}}
${API_STATIC_TOKEN}    {{API_STATIC_TOKEN}}
${BROWSER}             chrome
${HEADLESS}            ${TRUE}
${ENV}                 dev
${DB_HOST}             ${EMPTY}
${DB_PORT}             3306
${DB_USER}             ${EMPTY}
${DB_PASSWORD}         ${EMPTY}
${DB_NAME}             ${EMPTY}

*** Keywords ***
# ───────────────────────── browser lifecycle ─────────────────────────
Open ERP Browser
    [Documentation]    Open the browser at the ERP site root (headless by default, 1920x1080).
    ${options}=    Build Browser Options
    Open Browser    ${BASE_URL}/    browser=${BROWSER}    options=${options}
    Set Selenium Timeout    ${TIMEOUTS}[DEFAULT]
    Set Selenium Implicit Wait    0
    Register Keyword To Run On Failure    NONE
    Wait For Page Settle

Build Browser Options
    ${opts}=    Set Variable    add_argument("--lang=th-TH");add_argument("--window-size=1920,1080");add_argument("--no-sandbox");add_argument("--disable-dev-shm-usage")
    IF    ${HEADLESS}
        ${opts}=    Set Variable    ${opts};add_argument("--headless=new")
    END
    RETURN    ${opts}

Close ERP Browser
    Close All Browsers

# ───────────────────────── navigation ─────────────────────────
Go To Route
    [Documentation]    Navigate to an SPA route relative to BASE_URL, then wait for settle.
    ...    The FE router is vue-router in HASH mode, so routes go after "/#". A hash-only
    ...    driver.get() does NOT make the router navigate (order_v3 verified live
    ...    2026-07-15), so always Reload Page to boot the SPA at the target route (auth
    ...    persists in storage).
    [Arguments]    ${path}
    Go To    ${BASE_URL}/\#${path}
    Reload Page
    Wait For Page Settle

Wait For Page Settle
    Wait For Condition    return document.readyState == 'complete'    timeout=${TIMEOUTS}[NAVIGATION]

Wait Until Url Contains Fragment
    [Arguments]    ${fragment}    ${timeout}=${TIMEOUTS}[NAVIGATION]
    Wait Until Keyword Succeeds    ${timeout}s    0.5s    Current Url Should Contain    ${fragment}

Current Url Should Contain
    [Arguments]    ${fragment}
    ${url}=    Get Location
    Should Contain    ${url}    ${fragment}

Current Url Should Not Contain
    [Arguments]    ${fragment}
    ${url}=    Get Location
    Should Not Contain    ${url}    ${fragment}

# ───────────────────────── robust input / click ─────────────────────────
Wait Until Any Element Visible
    [Arguments]    ${locator}    ${timeout}=${TIMEOUTS}[DEFAULT]
    Wait Until Keyword Succeeds    ${timeout}s    0.5s    Some Matched Element Is Visible    ${locator}

Some Matched Element Is Visible
    [Arguments]    ${locator}
    ${elements}=    Get WebElements    ${locator}
    FOR    ${el}    IN    @{elements}
        ${visible}=    Run Keyword And Return Status    Element Should Be Visible    ${el}
        IF    ${visible}    RETURN
    END
    Fail    No visible element matched ${locator}

Get First Visible Element
    [Arguments]    ${locator}    ${timeout}=${TIMEOUTS}[DEFAULT]
    Wait Until Any Element Visible    ${locator}    ${timeout}
    ${elements}=    Get WebElements    ${locator}
    FOR    ${el}    IN    @{elements}
        ${visible}=    Run Keyword And Return Status    Element Should Be Visible    ${el}
        IF    ${visible}    RETURN    ${el}
    END
    Fail    No visible element matched ${locator}

Click First Visible Element
    [Arguments]    ${locator}
    Wait Until Keyword Succeeds    3x    0.5s    Click First Visible Element Once    ${locator}

Click First Visible Element Once
    [Arguments]    ${locator}
    ${el}=    Get First Visible Element    ${locator}
    ${ok}=    Run Keyword And Return Status    Click Element    ${el}
    IF    not ${ok}    Execute JavaScript    arguments[0].click();    ARGUMENTS    ${el}

Input Text Reliably
    [Documentation]    Set a field's value via JS + the Vue layer, then verify. Native typing
    ...    is unreliable app-wide (order_v3 verified live 2026-07-15): keystrokes can vanish
    ...    and a native clear can leave the DOM value right while bootstrap-vue's v-model holds
    ...    the OLD text. Emitting the component's model event keeps DOM and Vue in lockstep.
    [Arguments]    ${locator}    ${text}
    Run Keyword And Ignore Error    Wait Until Element Is Visible    ${locator}    ${TIMEOUTS}[DEFAULT]
    ${el}=    Get WebElement    ${locator}
    Execute JavaScript
    ...    const el=arguments[0], text=arguments[1]; el.value=text; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); if (el.__vue__ && el.__vue__.$emit) { el.__vue__.$emit('update', text); el.__vue__.$emit('input', text); }
    ...    ARGUMENTS    ${el}    ${text}
    ${value}=    Get Value    ${locator}
    Should Be Equal    ${value}    ${text}    Input Text Reliably could not set the field value (JS + Vue emit failed)

Click Element Safe
    [Documentation]    Wait for the element then click it via JS. Native WebDriver clicks
    ...    silently no-op on parts of these pages (order_v3 verified live 2026-07-15: the page
    ...    re-renders aggressively, detaching the node the trusted event was aimed at). A JS
    ...    click on the freshly-located node is reliable.
    [Arguments]    ${locator}
    Run Keyword And Ignore Error    Wait Until Element Is Visible    ${locator}    ${TIMEOUTS}[DEFAULT]
    ${el}=    Get WebElement    ${locator}
    Execute JavaScript    arguments[0].click();    ARGUMENTS    ${el}

# ───────────────────────── SweetAlert2 assertions ─────────────────────────
Wait For Swal
    Wait Until Element Is Visible    ${SWAL_POPUP}    ${TIMEOUTS}[DEFAULT]

Assert Swal Contains
    [Arguments]    ${text}
    Wait For Swal
    Wait Until Element Contains    ${SWAL_TEXT}    ${text}    ${TIMEOUTS}[DEFAULT]

Click And Expect
    [Documentation]    JS-click ${locator}, then wait for ${expect} to become visible; if it
    ...    does not, RE-CLICK (up to ${attempts} times). On slow CI machines the app can
    ...    re-render between locating and clicking, silently swallowing the click (order_v3
    ...    lesson on the first GitHub Actions runs).
    [Arguments]    ${locator}    ${expect}    ${attempts}=3    ${wait_each}=6s
    FOR    ${attempt}    IN RANGE    ${attempts}
        Click Element Safe    ${locator}
        ${ok}=    Run Keyword And Return Status    Wait Until Element Is Visible    ${expect}    ${wait_each}
        IF    ${ok}    RETURN
    END
    Wait Until Element Is Visible    ${expect}    ${wait_each}

Confirm Swal
    [Documentation]    Click the SweetAlert2 confirm button ("ตกลง") via JS (native clicks
    ...    silently no-op on this app).
    Click Element Safe    ${SWAL_CONFIRM}

Dismiss Swal
    Click Element Safe    ${SWAL_CANCEL}

Swal Should Not Be Visible
    [Documentation]    No SweetAlert2 popup is present (e.g. FE validation blocked an API call).
    Wait Until Keyword Succeeds    ${TIMEOUTS}[SHORT]s    0.3s    Page Should Not Contain Element    ${SWAL_POPUP}
