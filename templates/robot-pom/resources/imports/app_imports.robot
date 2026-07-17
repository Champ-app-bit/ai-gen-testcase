*** Settings ***
Documentation    Single import hub for the ERP {{MODULE}} Robot suite. Each test suite does
...              `Resource    ../../resources/keywords/suite_helpers.resource` (which pulls
...              this in) and gets the whole POM stack: SeleniumLibrary + custom/db/api
...              libraries + variable files + login/list page keywords + {{MODULE}}
...              feature keywords.
...
...              Environment values (BASE_URL/API_BASE_URL/DB_*/...) come from a variable
...              file chosen at run time:
...                robot --variablefile resources/variables/env_dev.yaml tests
...              Defaults baked into common_keywords keep a bare `robot` run pointed at dev.

# NOTE: the two {{MODULE}}_* resources below are GENERATED per module together with the
# tests (they do not ship with the template — the template only guarantees this layering:
# common -> page -> feature). Add more page-keyword imports (e.g. a form page) as generated.

# Feature keyword layer (transitively pulls in page keywords, locators, common keywords,
# the Python libraries and the routes/timeouts/messages variable files).
Resource         ../keywords/feature_keywords/{{MODULE}}_feature_keywords.resource

# Page keyword layer.
Resource         ../keywords/page_keywords/login_page_keywords.resource
Resource         ../keywords/page_keywords/{{MODULE}}_list_keywords.resource

*** Keywords ***
Open ERP Site
    [Documentation]    Suite-level setup: open the browser at the ERP root.
    Open ERP Browser

Teardown ERP Site
    [Documentation]    Suite-level teardown: close all browsers.
    Close ERP Browser
