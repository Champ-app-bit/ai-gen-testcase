# ERP {{MODULE}} — Robot Framework E2E

Automation สำหรับเมนู **{{MODULE}}** (`{{ROUTE}}`) ของ ERP — API + UI ยิงจริงบน staging.
โครง POM เดียวกับ `erp_order_v3_robot` / `erp_payment_robot` (libraries + resources/{imports,locators,keywords,variables} + tests แยกตาม area, 1 เคส/ไฟล์).

## รันในเครื่อง

```bash
pip install -r requirements.txt
# ทั้งชุด (UI ต้องมี Chrome; Selenium Manager ดึง driver ให้เอง)
robot --pythonpath libraries --variablefile resources/variables/env_dev.yaml --skiponfailure known-bug --outputdir results tests
# เฉพาะ API (ไม่ต้องเปิดเบราว์เซอร์)
robot --pythonpath libraries --variablefile resources/variables/env_dev.yaml --include level:api --outputdir results tests
```

หรือผ่าน `robot.yaml` profiles: `Dev` / `Api` / `Ui` / `Confirm Spec`.

## Baseline (staging, YYYY-MM-DD)

<!-- TODO(generated): N เทส — x pass / y fail / z skip (a known-bug + b blocked รอ seed/บัญชี/DB/harness) -->
เขียว = "ระบบยังตรงตามที่บันทึกไว้ ไม่มี regression" ไม่ใช่ "ไม่มีบั๊ก" — ดู known-bug/🔴 ด้านล่าง.

**Rerun-safe ผ่าน factory:** เคส state-changing ไม่พึ่ง seed ตายตัว — แต่ละรัน factory
(`Mint Fresh Order` + module factory ใน `suite_helpers.resource`) duplicate order template
เป็นข้อมูลทิ้งได้ แล้ว log marker `MINTED ...`. จบรัน step "Clean up minted ..." 
(`scripts/cleanup_minted.py`) soft-delete ทั้งหมด → รันซ้ำได้ไม่ทิ้งขยะ.

## สิ่งที่รันจริงแล้ว (pass)

<!-- TODO(generated): สรุปกลุ่มเทสที่ pass จริง พร้อม TC id -->

## 🐞 known-bug (fail จริง → CI SKIP ด้วย `--skiponfailure known-bug`)

<!-- TODO(generated): รายการ TC ที่ติดแท็ก known-bug + อาการ + สาเหตุ (file:line) -->
พอ dev แก้แล้ว เทสจะ fail เตือนเอง → ลบแท็ก `known-bug`. การ์ด Teams แยกนับ known-bug ให้แล้ว.

## 🔴 ต้องยืนยัน dev/PO (flag:confirm-spec)

<!-- TODO(generated): รายการ TC ที่ต้องยืนยันสเปกก่อนล็อก assertion -->
ดู `docs/QA-ERP-{{MODULE}}-Automation-DataRequest.md`.

## ปลดล็อกเทสที่ SKIP

ทุกตัว gate-then-skip. เติม `users.json` / test data แล้ว set `_status: ready` → รันเอง.
รายละเอียดครบใน `docs/QA-ERP-{{MODULE}}-Automation-DataRequest.md` (§1 บัญชี · §2 seed · §3 DB · §4 harness · §5 factory).

## CI

`.github/workflows/erp-{{MODULE}}-e2e.yml` — **กดรันมือเท่านั้น** (workflow_dispatch — นโยบายทีม ไม่รันอัตโนมัติ), ubuntu-latest.
Secrets: `ERP_ADMIN_USER/PASS`, `ERP_RO_USER/PASS`, `ERP_NOVIEW_USER/PASS` (optional), `TEAMS_WEBHOOK_URL` (optional).
Teams card แยกนับ known-bug ออกจาก skip ปกติ.

## Gotchas (สืบทอดจาก order_v3/payment — ยืนยันสดบน staging)

- Deployed API คืน HTTP status จริง (401/500/400/250/203) — assert บน HTTP status ไม่ใช่ `status.code`.
- FE router = HASH mode (`/#{{ROUTE}}`) → `Go To Route` append `/#` + Reload.
- Native WebDriver events ไม่น่าเชื่อถือ → ใช้ `Click Element Safe` (JS) + `Input Text Reliably` (JS + Vue emit).
- `base-input` **ไม่** ส่ง `name` ลง DOM → locator ฟอร์มยึด label เป็นหลัก.
- Robot ตัวแปร case-insensitive → อย่าตั้ง local `${msg}` ทับ dict `${MSG}`.
- filter dropdown: ตัวเลือกว่างตอน mount, ต้องเปิด dropdown (@show) ให้ render ก่อนติ๊ก.
