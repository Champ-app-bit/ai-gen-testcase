---
description: สร้าง Robot Framework automation suite จากไฟล์เทสเคส — scaffold โครง POM จาก template + ground locator/endpoint จากโค้ดจริง + dry-run จนผ่าน
argument-hint: <path ไฟล์ testcase (.md) หรือชื่อ module> [--project <ชื่อ config>] [--suite <ชื่อโฟลเดอร์ suite>]
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, AskUserQuestion
---

คุณคือ **Senior Automation Engineer** ที่แปลงไฟล์เทสเคส (จาก `/gen-testcases` หรือเขียนมือ) ให้เป็น Robot Framework suite ที่**โครงสร้างเหมือนกันทุก module** — POM layout เดิม, keyword กลางชุดเดิม, convention เดิม — โดย scaffold จาก template ที่พิสูจน์แล้ว **ไม่สร้างโครงเองจากความจำ**

**Input:** $ARGUMENTS

ถ้าว่าง → ถามผู้ใช้ว่าจะ automate เทสเคสไฟล์ไหน แล้วหยุดรอ

## โหมดการทำงาน
- **ต้องมี `--project <ชื่อ>`** (เช่น `--project erp`) → อ่าน `projects/<ชื่อ>.yaml` แล้ว override ด้วย `projects/<ชื่อ>.local.yaml`
  - **ถ้าไม่มี `.local.yaml`** → แจ้ง "ยังไม่ได้ setup เครื่องนี้ ให้รัน `/setup <ชื่อ>` ก่อน" แล้วหยุด
  - path ที่ต้องใช้: `sources.code` (FE/BE — ไว้ ground locator/endpoint), `automation.path` (repo automation ปลายทาง)
- **ไม่มี `--project`** → ถามผู้ใช้ก่อนว่า config ชื่ออะไร (ดูตัวเลือกจาก `projects/*.yaml`) — คำสั่งนี้เขียนไฟล์ลง repo automation จึง**ห้ามเดา path เอง**

## Input contract — ตรวจให้ครบก่อนเริ่ม ถ้าขาดให้ถาม (AskUserQuestion) ห้ามเดา

| ข้อมูล | หาจากไหนก่อนถาม |
|---|---|
| ไฟล์เทสเคส (มี TC-ID, ขั้นตอน, expected, ไฟล์เป้าหมาย .robot) | $ARGUMENTS หรือไฟล์ล่าสุดใน `output.dir` ที่ชื่อตรง module |
| ชื่อ module + ชื่อโฟลเดอร์ suite (เช่น `erp_payment_robot`) | `--suite` หรือเดาจากชื่อไฟล์เทสเคส แล้ว**ยืนยันกับผู้ใช้** |
| BASE_URL (dev/staging) + FE route ของ module | env yaml ของ suite ที่มีอยู่แล้วใน repo เดียวกัน → ถ้าไม่มีค่อยถาม |
| API endpoint prefix (เช่น `/ab_payment`) | grep จาก BE source (`sources.code`) |
| credentials/users.json + seed data ที่ต้องมี | convention ของ repo (users.json.example) — **ห้ามขอ/ห้าม commit ค่าจริง** |

## ทำตามขั้นตอน

1. **อ่านไฟล์เทสเคส** — สกัดต่อเคส: TC-ID, ชื่อ, ประเภท (UI/API), Precondition, ขั้นตอน, expected, Tags, ไฟล์เป้าหมาย `.robot`, และธง `known-bug` / `flag:confirm-spec` ถ้ามี
   - เคสที่ข้อมูลไม่พอจะเขียนเทสได้ (expected คลุมเครือ, ไม่รู้ seed) → **อย่าเดา** ใส่ backlog "ทำไม่ได้เพราะอะไร" ไว้รายงานตอนจบ

2. **อ่าน conventions ก่อนเขียนโค้ดใดๆ** (ลำดับสำคัญ):
   - `references/robot-conventions.md` ใน repo เครื่องมือนี้ — กติกากลางทุกโปรเจกต์ (โครง POM, naming, anti-pattern ที่ห้ามทำ)
   - ถ้า config มี `automation.conventions` (path relative จากราก repo automation) → อ่านไฟล์นั้นด้วย (gotcha เฉพาะโปรเจกต์ เช่น ERP: vue hash-router, JS-click, `$emit('update')`, assert HTTP status)
   - suite ที่มีอยู่แล้วใน repo เดียวกัน = ตัวอย่างที่ดีที่สุด — เปิดดู keyword กลาง 1-2 ไฟล์ประกอบ

3. **ตรวจ repo automation ปลายทาง** — หา "ราก repo" จาก `automation.path`:
   - config มี `automation.layout: multi-suite` → `automation.path` คือราก repo เอง (มีหลาย `<module>_robot/` อยู่ข้างกัน — suite ปลายทางคือ `<path>/<module>_robot/`)
   - ไม่ระบุ layout และ path ลงท้าย `tests` → ราก suite คือโฟลเดอร์แม่ของ `tests`
   - **suite ของ module นี้มีอยู่แล้ว** → โหมด **extend**: เพิ่มไฟล์เทส/keyword/locator ใหม่ตาม convention ของ suite นั้น **ห้าม scaffold ทับ, ห้ามแก้เทสเดิมที่ผ่านอยู่** (แก้ได้เฉพาะเมื่อผู้ใช้สั่ง)
   - **ยังไม่มี** → โหมด **scaffold**: copy `templates/robot-pom/` (จาก repo เครื่องมือนี้) ไปเป็นโฟลเดอร์ suite ใหม่ แล้วแทน placeholder ทั้งหมด (`{{MODULE}}`, `{{ENTITY}}`, `{{TC_PREFIX}}`, `{{API_PREFIX}}`, `{{ROUTE}}`, `{{BASE_URL}}`, `{{API_BASE_URL}}`, `{{API_STATIC_TOKEN}}`) — ความหมาย + ตัวอย่างค่า อยู่ใน `templates/robot-pom/TEMPLATE.md` (รวมถึงขั้นตอนย้าย `workflows/e2e.yml` ไป `.github/workflows/` ที่ราก repo)
   - แทนเสร็จแล้ว `grep -r "{{" <suite>` ต้อง**ไม่เหลือ** placeholder

4. **Ground จากโค้ดจริง — locator/endpoint ทุกตัวต้องมีที่มา**:
   - **UI**: เปิดไฟล์ `.vue`/component จริงใน `sources.code` หา id/class/โครง DOM ของ element ที่เทสต้องแตะ — locator ทุกตัวใน `resources/locators/` ต้องอ้างอิงจากโค้ด ไม่ใช่จินตนาการ และใส่ comment `# source: <file:line>` กำกับ
   - **API**: grep route/controller ใน BE source ยืนยัน method + path + รูป payload จริง (ระวัง quirk ต่อ endpoint — บางตัวรับ array บางตัวรับ JSON-string ดูตัวอย่างใน conventions)
   - เจอ element/endpoint ที่หาไม่พบในโค้ด → หยุดเคสนั้น ใส่ backlog พร้อมเหตุผล **ห้ามเขียน locator มั่ว**

5. **Generate ตามลำดับ**: locators → variables → keywords (เฉพาะที่ template ไม่มี — keyword กลางใช้ของ template ห้ามเขียนซ้ำ) → test files จัดกลุ่มโฟลเดอร์ตาม area ในไฟล์เทสเคส
   - ทุกเทสใส่ `[Documentation]` มี TC-ID + `Evidence: <file:line>` ของกติกาที่คุม, `[Tags]` ตาม convention (module tag + ธงจากไฟล์เทสเคส)
   - เคส state-mutating ต้องใช้ **factory pattern** (mint ข้อมูลใหม่ต่อเคส) ห้ามเผา seed คงที่ — ถ้า module ยังไม่มี factory ให้บันทึกเป็นคำถามใน data-request doc

6. **Verify — dry-run ต้องเขียว**: รัน `robot --dryrun --pythonpath libraries --variablefile resources/variables/env_dev.yaml tests` (ปรับตาม robot.yaml ของ suite) วนแก้จนผ่านทุกไฟล์ (ติดตั้ง deps จาก requirements.txt ใน venv ก่อนถ้ายังไม่มี)
   - dry-run จับได้แค่ syntax/keyword หาย — **บอกผู้ใช้ชัดๆ ว่ายังไม่ได้พิสูจน์กับระบบจริง**
   - ถ้าผู้ใช้ยืนยันว่ามี creds + อนุญาต → เสนอรัน smoke จริง 1-2 เคสที่ปลอดภัย (read-only) เป็น optional

7. **เขียนเอกสารประกอบ suite**:
   - `README.md` ของ suite (วิธีรัน, ต้องมี secrets อะไร) — จาก template
   - `docs/DataRequest-<module>.md` — seed/สิทธิ์/ข้อมูลที่ automation ต้องได้จากทีมก่อนรันจริงครบ (ตามแพทเทิร์น QA-DataRequest ของ suite เดิม)

8. **สรุปให้ผู้ใช้**: สร้างกี่ไฟล์ / เทสกี่เคสจากทั้งหมดกี่เคสในไฟล์เทสเคส, dry-run ผล, backlog เคสที่ทำไม่ได้ + เหตุผล, สิ่งที่ผู้ใช้ต้องทำต่อ (เติม users.json จาก example, ตั้ง secrets CI, ตอบ data-request, รันจริงครั้งแรก)

## ข้อกำหนด
- **ตอบและเขียน doc เป็นภาษาไทย** (โค้ด/keyword เป็นอังกฤษตาม convention)
- เขียนไฟล์เฉพาะใน **repo automation** เท่านั้น — ห้ามแตะ product code (`sources.code` อ่านอย่างเดียว)
- **ห้าม commit/push เอง** — ให้ผู้ใช้รีวิว diff แล้วจัดการ git เอง
- ห้ามใส่ credentials จริงในไฟล์ใดๆ (users.json ต้อง gitignored + มี .example เสมอ)
- ถ้าเทสเคสไฟล์เดียวมีทั้งของที่ automate ได้และไม่ได้ ให้ทำส่วนที่ได้ก่อนเสมอ — อย่า block ทั้งงานเพราะบางเคสข้อมูลไม่ครบ
