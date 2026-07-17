*** Settings ***
Documentation    Login actions for the ERP user (Login.vue -> POST /auth -> /dashboard).
Resource         ../common_keywords.resource
Resource         ../../locators/login_page_locators.resource

*** Keywords ***
Open Login Page
    Go To Route    ${ROUTES}[LOGIN]
    Wait Until Element Is Visible    ${LOGIN_USERNAME}    ${TIMEOUTS}[DEFAULT]

Fill Login Form
    [Arguments]    ${username}    ${password}
    Input Text Reliably    ${LOGIN_USERNAME}    ${username}
    Input Text Reliably    ${LOGIN_PASSWORD}    ${password}

Submit Login
    Click Element Safe    ${LOGIN_SUBMIT}

Login As
    [Documentation]    Composite UI login. On success the app routes to /dashboard. Retries
    ...    the fill+submit until the URL leaves /login: a single JS click can silently fail
    ...    to register (page re-renders), leaving the browser stuck on /login — seen only
    ...    under a full sequential run (payment suite, 2026-07-16), not in isolation.
    [Arguments]    ${username}    ${password}
    Open Login Page
    Wait Until Keyword Succeeds    3x    2s    Fill And Submit Login Until Dashboard    ${username}    ${password}

Fill And Submit Login Until Dashboard
    [Arguments]    ${username}    ${password}
    Fill Login Form    ${username}    ${password}
    Submit Login
    Wait Until Url Contains Fragment    ${MSG}[LOGIN_DEST]    ${TIMEOUTS}[DEFAULT]

Assert Login Succeeded
    Wait Until Url Contains Fragment    ${MSG}[LOGIN_DEST]

Login As Data User
    [Documentation]    Load a users.json record and log in via the UI; Skip if the account
    ...    has not been provisioned yet (_status != ready).
    [Arguments]    ${user_key}=admin
    ${user}=    Load Test Data    user    ${user_key}
    ${ready}=    Test Data Is Ready    ${user}
    IF    not ${ready}
        Skip    BLOCKED: ERP test account "${user_key}" not provisioned — fill users.json + set _status=ready (docs/QA-ERP-{{MODULE}}-Automation-DataRequest.md §1).
    END
    Login As    ${user}[username]    ${user}[password]
    Assert Login Succeeded
    RETURN    ${user}
