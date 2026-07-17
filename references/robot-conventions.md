# Robot Framework Automation Conventions (POM) — กติกากลางทุกโปรเจกต์

> ไฟล์นี้เป็น "กติกากลาง" ที่ `/gen-automation` ต้องอ่านก่อนสร้าง suite ใหม่ทุกครั้ง
> **ห้ามใส่ค่า/กติกาเฉพาะเว็บใดเว็บหนึ่ง** — gotcha เฉพาะโปรเจกต์ให้เขียนไว้ในไฟล์ conventions
> ของ repo automation นั้นๆ แล้วชี้ผ่าน `automation.conventions` ใน `projects/<name>.yaml`

## 1. โครงสร้าง suite (POM layout)

หนึ่ง module = หนึ่งโฟลเดอร์ suite (`<module>_robot/`) โครงตายตัวตาม `templates/robot-pom/`:

```
<module>_robot/
  libraries/            # Python: api_library, db_library, custom_library
  resources/
    imports/            # app_imports.robot — จุดรวม import ทั้งหมดของ UI tests
    keywords/
      common_keywords.resource      # helper กลางระดับ browser/dialog (app-agnostic)
      suite_helpers.resource        # suite setup/teardown, data gate, factory
      page_keywords/                # interaction ราย "หน้า" (1 หน้า = 1 ไฟล์)
      feature_keywords/             # business flow ที่ร้อย page keywords เข้าด้วยกัน
    locators/           # 1 หน้า = 1 ไฟล์ locator (แยกจาก keyword เสมอ)
    variables/          # env_dev.yaml, routes.yaml, timeouts.yaml, messages.yaml
      test_data/        # users.json (gitignored + มี .example), <entity>.json
  scripts/              # write_users_json.py, cleanup_minted.py
  docs/                 # DataRequest doc + เอกสารประกอบ suite
  tests/<group>/        # เทสจริง จัดกลุ่มเป็นโฟลเดอร์ตาม area
```

**Layering — ห้ามข้ามชั้น:** tests → (suite_helpers / feature / page keywords) → common keywords → SeleniumLibrary/libraries. เทสห้ามเรียก `Click Element` / xpath ตรงๆ — ต้องผ่าน keyword ที่มีชื่อสื่อความหมายเสมอ

## 2. Locators

- **prefix ต่อหน้า**: locator ทุกตัวในไฟล์เดียวกันขึ้นต้นด้วย prefix เดียวกัน (เช่น `OL_*` = order list, `DLG_*` = dialog, `SWAL_*` = SweetAlert) — อ่านชื่อแล้วรู้ทันทีว่าอยู่หน้าไหน
- **คู่ตัวแปร composition**: ถ้า keyword ต้องประกอบ xpath ต่อ (เช่น เจาะ row ที่ n) ให้มี 2 ตัวแปรคู่กัน:
  ```robot
  ${XX_ROWS_XP}    //table[...]/tbody/tr[...]      # ไม่มี strategy prefix — ไว้ประกอบต่อ
  ${XX_ROWS}       xpath=${XX_ROWS_XP}             # ไว้ใช้ตรงๆ
  ```
  **ห้ามฝังตัวแปรที่มี prefix ลงใน xpath อื่น** — `xpath=(${XX_ROWS})[1]` จะกลายเป็น `(xpath=//...)` = InvalidSelector
- **ทุก locator ต้องมีที่มาจากโค้ดจริง** — ใส่ comment `# source: <file:line>` กำกับ ห้ามเดา DOM
- element ที่ระบุด้วย attribute ข้อความ (title/aria-label/ข้อความปุ่ม) ให้ประกาศข้อความนั้นเป็นตัวแปรค่าคงที่ แล้วให้ชั้น keyword ประกอบ selector เอง

## 3. Keywords

- **common** = ของกลางที่ไม่รู้จัก business (open/close browser, wait/settle, click-safe, input-reliably, dialog helpers) — มากับ template **ห้ามเขียนซ้ำ/ห้ามแก้** ถ้าไม่จำเป็น
- **page** = interaction ของหน้าเดียว (`Open X List`, `Search Xs`, `Get Row Count`, `Wait For Grid Settle`) — import common + locator ของหน้าตัวเองเท่านั้น
- **feature** = business flow ที่ผู้อ่านเทสเข้าใจได้ทันที (ร้อยหลาย page เข้าด้วยกัน)
- **suite_helpers** = suite setup/teardown, `Require * Data` (data gate), factory keywords
- keyword ที่รอ grid/list โหลด ต้องเผื่อ "แถวเก่าค้าง" หลัง action: settle ก่อน (sleep สั้นตามที่ template กำหนด) แล้วค่อย assert สถานะ loading/rows — ห้ามใช้ sleep ยาวลอยๆ แทน explicit wait

## 4. ไฟล์เทส

- **1 เทสเคส = 1 ไฟล์**: `tests/<group>/TC-<PREFIX>-NN_slug.robot` จัดโฟลเดอร์ตาม area (`list_filter/`, `crud/`, `perm/`, `api_*/` ฯลฯ)
- ทุกไฟล์ต้องมี:
  - `[Documentation]` อธิบายว่าเทสคุมกติกาอะไร + **`Evidence: <file:line>`** ชี้โค้ด/สเปกที่กติกามาจาก
  - `Suite Setup` / `Suite Teardown` ผ่าน keyword ใน suite_helpers (ห้ามเปิด browser เองในเทส)
  - `Force Tags` ตาม taxonomy ข้อ 5
- **ไม่ใช้ `[Template]`** (data-driven ให้แตกเป็นเคสแยง) — ตรงกับของเดิมทั้ง repo
- เทสต้องรันซ้ำได้ (rerun-safe) และ**ไม่พึ่งลำดับ/ผลของเทสอื่น**
- เทสล้วน API ไม่ต้องเปิด browser — import `api_library.py` + routes ตรงๆ

## 5. Tag taxonomy (ตายตัว)

| tag | ค่า | ความหมาย |
|---|---|---|
| `TC-<PREFIX>-NN` | — | TC-ID ตรงกับไฟล์เทสเคสต้นทาง |
| `feature:<module>` | — | module ของ suite |
| `group:<name>` | — | ตรงชื่อโฟลเดอร์กลุ่ม |
| `level:` | `ui` `api` `unit` `integration` | ชั้นที่ทดสอบ |
| `priority:` | `high` `medium` `low` | ความสำคัญ |
| `positive` / `negative` | — | ทิศของเคส |
| `security` | — | เคสสิทธิ์/ความปลอดภัย |
| `known-bug` | — | expected คือพฤติกรรมที่ถูก แต่ระบบยังบั๊ก — CI รัน `--skiponfailure known-bug` ให้ build เขียวแต่เห็นเป็น SKIP · **เอา tag ออกเมื่อ dev แก้แล้ว** |
| `flag:confirm-spec` | — | expected ยังรอ BA/PO ยืนยัน |
| `mutating-email` (หรือ side-effect อื่น) | — | เคสมี side effect จริงนอกระบบ — ต้องเลือกใส่/ตัดตอนรันได้ |

**หลัก known-bug:** เขียนเทส assert พฤติกรรม*ที่ถูกต้อง*เสมอ (ไม่ใช่ assert บั๊ก) แล้วติด tag — เทสจะกลายเป็น regression test อัตโนมัติวันที่บั๊กถูกแก้

## 6. Test data + factory pattern

- test_data เป็น json: แต่ละ record มี `key`, `_status` (`todo`/`ready`), `_note` — เทสที่ต้องใช้ data ที่ยัง `todo` ให้ **Skip พร้อมเหตุผล ไม่ใช่ Fail** (data gate ใน suite_helpers)
- `users.json` (creds จริง) **gitignored เสมอ** — commit เฉพาะ `users.json.example`; CI สร้างไฟล์จริงจาก secrets ผ่าน `scripts/write_users_json.py`
- **เคสที่เปลี่ยน state ห้ามเผา seed คงที่** — ต้อง mint ข้อมูลใหม่ต่อเคสผ่าน factory keyword (duplicate จาก record แม่แบบที่ pristine) แล้ว log marker `MINTED <entity>=<id>` ให้ `scripts/cleanup_minted.py` ตามลบจาก output.xml หลังรัน
- record แม่แบบของ factory ต้อง**ห้ามมีเทสไหนไปแก้** — cleanup script ต้อง protect id นี้เสมอ

## 7. ลำดับการ verify (บันไดความเชื่อมั่น)

1. `robot --dryrun` — จับ syntax/keyword หาย **ยังไม่พิสูจน์อะไรกับระบบจริง**
2. smoke เคส read-only กับ env จริง — พิสูจน์ locator/route/auth
3. full run — ต้องมี creds + seed ครบ (ดู DataRequest doc)

รายงานผลต้องบอกเสมอว่าอยู่บันไดขั้นไหน — "dry-run ผ่าน" ≠ "เทสใช้งานได้"

## 8. CI (GitHub Actions)

- 1 suite = 1 workflow (`erp-<module>-e2e.yml` ที่ราก repo, ใช้ `defaults.run.working-directory`)
- cron **เหลื่อมเวลากันระหว่าง suite** (กันแย่ง data) + `concurrency` group ต่อ suite
- ขั้นตอนตายตัว: setup python → pip install → write users.json จาก secrets → robot รัน `--skiponfailure known-bug` → cleanup minted (`if: always()`) → upload artifact → Teams notify (ไม่มี webhook = ข้ามเงียบๆ ห้าม fail build)
- secrets ขาด → เทสที่ต้องใช้ Skip เอง (data gate) — build ยังเขียว

## 9. เอกสารประกอบ (ต้องมีคู่ suite เสมอ)

- `README.md` ของ suite — วิธีรัน local, task ใน robot.yaml, secrets ที่ต้องตั้ง
- `docs/<DataRequest>.md` — บัญชี/seed/สิทธิ์/DB access ที่ทีมต้องเตรียมก่อนรันครบ + คำถาม `flag:confirm-spec` ทั้งหมดรอ BA ตอบ
