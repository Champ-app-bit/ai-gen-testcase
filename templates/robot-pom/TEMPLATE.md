# robot-pom template — manifest

Proven Robot Framework POM suite skeleton, extracted from the ERP automation suites
(`erp_order_v3_robot` → `erp_payment_robot` → `erp_delivery_robot`; primary source =
payment, which carries the latest fixes: login retry wrapper, factored-out
`swal_locators.resource`, `_delete_each` cleanup helper). The `/gen-automation`
command copies this folder to `<module>_robot/` and substitutes the tokens below.

## Placeholder tokens

All tokens are double-curly `{{TOKEN}}`. After substitution, `grep -r "{{" <suite>/`
MUST return nothing.

| Token | Meaning | Example (payment) |
|---|---|---|
| `{{MODULE}}` | module slug: folder names, appSlug, workflow name, docs | `payment` |
| `{{ENTITY}}` | primary entity of the module (test-data file names, skip messages) | `payment` |
| `{{TC_PREFIX}}` | test-case id prefix (`TC-<PREFIX>-NN`) | `PAY` |
| `{{API_PREFIX}}` | BE mount path of the module app | `/ab_payment` |
| `{{ROUTE}}` | FE (hash-router) route of the module list page | `/payment` |
| `{{BASE_URL}}` | FE base URL (staging) | `https://staging.example.com` |
| `{{API_BASE_URL}}` | BE REST base URL (staging) | `https://erp-api.example.com` |
| `{{API_STATIC_TOKEN}}` | X-Authorization static token (util/config.js apiToken) | `eyJ...` |
| `{{CRON_MINUTE}}` | cron minute for the daily CI run — STAGGER per module so suites do not run simultaneously against staging (order_v3=00, payment=15, delivery=30, ...) | `15` |

## Scaffold steps

1. Copy this folder to the target repo as `<module>_robot/` (drop `TEMPLATE.md`).
2. Substitute every token above in every file (filenames contain no tokens; contents do).
3. Verify: `grep -r "{{" <module>_robot/` must return **nothing**.
4. Move `workflows/e2e.yml` to repo-root `.github/workflows/erp-<module>-e2e.yml`.
   If the repo does not already have `.github/workflows/teams-announce.yml`, copy
   `workflows/teams-announce.yml` there as-is. Then **delete `workflows/` from the suite**.
5. Rename `docs/DataRequest.md` → `docs/QA-ERP-<module>-Automation-DataRequest.md`.
6. Generate the per-module files (next section), then `robot --dryrun --pythonpath libraries
   --variablefile resources/variables/env_dev.yaml tests` must pass.
7. Create real test data from the examples: copy `users.json.example` → `users.json`
   (git-ignored; CI regenerates it via `scripts/write_users_json.py`) and
   `orders.json.example` → `orders.json` (fill `factory_template.code`, set `_status: ready`).

## Files GENERATED FRESH per module (not in the template)

| File(s) | Convention (one line) |
|---|---|
| `resources/locators/<module>_list_locators.resource`, `<module>_form_locators.resource`, ... | one locator file per page; variable prefix per page (e.g. `${PAYL_*}` list / `${PAYF_*}` form) + raw `*_XP` composition variables for XPath fragments reused inside the file |
| `resources/keywords/page_keywords/<module>_list_keywords.resource`, `<module>_form_keywords.resource`, ... | page keywords wrap ONE page each and import their locators; layering is strict common → page → feature (page keywords never import feature keywords) |
| `resources/keywords/feature_keywords/<module>_feature_keywords.resource` | cross-page business flows only; imports page keywords; this is what `app_imports.robot` exposes to tests |
| `tests/<group>/TC-<PREFIX>-NN_slug.robot` | ONE test case per file; groups = area folders (`list_search`, `form_paid`, `api_create`, `perm`, ...); no `[Template]` usage — spell assertions out |
| `resources/variables/test_data/<entity>s.json` | seed records with `key`/`_status`/`_note` shape; every record gated by `Test Data Is Ready`; `orders.json` with `factory_template` is ALWAYS required (the factory mints on orders even for non-order modules) |
| module sections in `custom_library.py`, `cleanup_minted.py`, `suite_helpers.resource`, `routes.yaml`, `messages.yaml` | fill the `# ── module-specific: generated per module ──` blocks (oracles, MINTED marker + delete chain, module setups/gates/factory, module routes/messages) |

**Tag taxonomy** (Force Tags + [Tags]): `feature:<module>` · `group:<area>` ·
`level:ui|api|unit` · `priority:high|medium|low` · `positive`/`negative` · `security` ·
`TC-<PREFIX>-NN` · `known-bug` (real failure reported to dev — CI runs
`--skiponfailure known-bug`) · `flag:confirm-spec` (assertion awaiting BA/PO confirmation) ·
`mutating-email` (sends real mail — excluded unless a mail harness exists).

## Required GitHub secrets

| Secret | Required | Used for |
|---|---|---|
| `ERP_ADMIN_USER` / `ERP_ADMIN_PASS` | yes | full-permission account: all UI/API tests, factory, cleanup |
| `ERP_RO_USER` / `ERP_RO_PASS` | yes | readonly account (view but no insert/update) — perm tests |
| `ERP_NOVIEW_USER` / `ERP_NOVIEW_PASS` | optional | account without module view — redirect test (skip if absent) |
| `TEAMS_WEBHOOK_URL` | optional | MS Teams result card (step self-skips if absent) |

## Security invariants

- Real `users.json` is git-ignored and NEVER shipped — only `users.json.example`.
- No real staging URLs or API tokens anywhere in the template: they are `{{BASE_URL}}`,
  `{{API_BASE_URL}}`, `{{API_STATIC_TOKEN}}` and get filled at scaffold time.
