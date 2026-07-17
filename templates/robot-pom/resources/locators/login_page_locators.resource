*** Settings ***
Documentation    Locators for the ERP login page (erp-frontend-2026/src/views/Pages/Login.vue).
...              username/password base-inputs + a "Sign in" submit; success routes to /dashboard.

*** Variables ***
${LOGIN_USERNAME}    xpath=//input[@placeholder='Username']
${LOGIN_PASSWORD}    xpath=//input[@placeholder='Password']
${LOGIN_SUBMIT}      xpath=//button[normalize-space()='Sign in']
