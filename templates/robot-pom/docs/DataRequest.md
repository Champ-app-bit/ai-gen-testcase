# QA ERP {{MODULE}} — Automation Data Request

<!-- Rename this file to QA-ERP-{{MODULE}}-Automation-DataRequest.md when scaffolding. -->

เอกสารนี้รวม "ของที่ยังขาด" เพื่อให้ suite `erp_{{MODULE}}_robot` รันได้เต็มชุด — เทสทุกตัว
"gate-then-skip": พอเติมข้อมูล + set `_status: ready` แล้วมันจะรันเองทันที ไม่ต้องแก้โค้ดเทส.

Baseline ปัจจุบัน (staging, YYYY-MM-DD): <!-- TODO(generated): N เทส — x pass / y fail / z skip -->

---

## §0 — Base URL ของหน้าเว็บ (FE)

- API = `{{API_BASE_URL}}` (→ `API_BASE_URL` ใน `resources/variables/env_dev.yaml`)
- FE = `{{BASE_URL}}` เสิร์ฟ route `{{ROUTE}}` (→ `BASE_URL`)

## §1 — บัญชีผู้ใช้ (`resources/variables/test_data/users.json`)

| key | ต้องการ | ใช้โดย | สถานะ |
|---|---|---|---|
| `admin` | สิทธิ์เต็มบน {{MODULE}} (flag_insert/update, view) | ทุกเทส UI/API | ⛔ todo |
| `readonly` | **มี** view {{MODULE}} แต่ **ไม่มี** flag_insert/flag_update | perm tests | ⛔ todo |
| `noview` | **ไม่มี** สิทธิ์ view appSlug `{{MODULE}}` (optional) | redirect test | ⛔ todo |

CI เขียน users.json จาก secrets: `ERP_ADMIN_USER/PASS`, `ERP_RO_USER/PASS`, `ERP_NOVIEW_USER/PASS`
(ขาดตัวไหน → บัญชีนั้น `_status=todo` → เทสที่ใช้มัน Skip เงียบ ๆ).

## §2 — ข้อมูล seed (`resources/variables/test_data/{{ENTITY}}s.json`)

seed เฉพาะทางที่ factory (§5) สร้างแทนไม่ได้ — ขอเป็นรายตัว:

| key | ต้องการ | ใช้โดย | ทำไม factory แทนไม่ได้ |
|---|---|---|---|
| <!-- TODO(generated) --> | | | |

## §3 — DB access (ตัวเลือก)

`env_dev.yaml` → `DB_HOST/DB_USER/DB_PASSWORD/DB_NAME`. ต้องชี้ที่ **DB ของ staging API** เท่านั้น.
⚠️ MCP mirror ที่ใช้ค้นข้อมูลเป็น **คนละฐาน** — ใช้ยืนยันผลรันไม่ได้.
ใช้โดย: การยืนยันระดับ row (soft-delete / status sync) — ไม่ให้ก็ได้ เทสเหล่านั้นจะ Skip.

## §4 — Harness ที่ยังไม่มี + คำถามเชิงสเปก (flag:confirm-spec)

- <!-- TODO(generated): mail capture / 3rd-party stub / binary download checks ที่เทสต้องการ -->
- 🔴 คำถามที่ BA/PO ต้องยืนยันก่อนล็อก assertion: <!-- TODO(generated) -->

## §5 — Factory + cleanup

`suite_helpers.Mint Fresh Order`: `PUT /ab_order/duplicateOrder` จาก template
(`orders.json` key `factory_template` — **ทุก module ต้องมี** แม้ไม่ใช่ module order เพราะ
ข้อมูลทิ้งได้ของ module ก็ mint บน order ใหม่) → log `MINTED order=..`.
Module factory ต่อยอด mint record ของ module บน order นั้น → log marker คู่.
`scripts/cleanup_minted.py` (CI step "Clean up minted ..." + `if: always()`) soft-delete
ลูกก่อน order, ป้องกัน template id อัตโนมัติ. **Rerun-safe.**

## §6 — Selector ที่ต้องปรับปรุงร่วมกับ dev

- <!-- TODO(generated): จุดที่ต้องขอ data-testid / title ซ้ำ ฯลฯ -->

## §6.5 — รันบน GitHub Actions

Workflow: `.github/workflows/erp-{{MODULE}}-e2e.yml`
- **Secrets ที่ต้องตั้ง**: `ERP_ADMIN_USER/PASS`, `ERP_RO_USER/PASS` (+ `ERP_NOVIEW_USER/PASS`,
  `TEAMS_WEBHOOK_URL` ตามต้องการ) → `scripts/write_users_json.py` สร้าง users.json ตอนรัน
  (ไฟล์จริงถูก .gitignore กันไว้ **ห้าม commit รหัสจริง** — มี users.json.example ให้เครื่องใหม่)
- รันด้วย `--skiponfailure known-bug`: เทสที่จับบั๊กที่แจ้ง dev แล้วขึ้น SKIP แทน FAIL
  → build เขียวโดยไม่ซ่อน failure ใหม่; พอ dev แก้แล้วถอด tag ออก
- `scripts/cleanup_minted.py results/output.xml` รันท้าย job (`if: always()`) — กวาด soft-delete
  ข้อมูลที่ factory mint (ลบทีละ id เพราะ bulk 500, กัน template id ให้อัตโนมัติ)
- `concurrency.group` ล็อกให้รันทีละ job — สองรันพร้อมกันจะกวนข้อมูล staging กันเอง
- ผลเทส (log.html/report.html) upload เป็น artifact `robot-results-{{MODULE}}` เก็บ 14 วัน
