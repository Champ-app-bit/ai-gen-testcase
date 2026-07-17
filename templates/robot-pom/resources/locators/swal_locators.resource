*** Settings ***
Documentation    SweetAlert2 popup locators fired by util/alertUtils.js — shared by the
...              common keyword layer (confirm/alert flows on the {{MODULE}} pages).

*** Variables ***
${SWAL_POPUP}          css:.swal2-popup
${SWAL_TEXT}           css:.swal2-html-container, .swal2-content
${SWAL_CONFIRM}        css:.swal2-confirm
${SWAL_CANCEL}         css:.swal2-cancel
${SWAL_ICON_SUCCESS}   css:.swal2-icon.swal2-success
${SWAL_ICON_WARNING}   css:.swal2-icon.swal2-warning
${SWAL_ICON_ERROR}     css:.swal2-icon.swal2-error
