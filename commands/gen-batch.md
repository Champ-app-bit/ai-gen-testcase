---
description: ปล่อยรันทั้ง project — ไล่ทำ module ทีละตัวจนจบ (spec → เทสเคส → automation → verify) resume ได้ ไม่ต้องนั่งเฝ้า
argument-hint: <ชื่อ project> [--limit N] [--modules a,b,c] [--stage-only spec|testcases|automation|verify] [--attended]
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, Task, Agent, AskUserQuestion
---

คุณคือ **orchestrator** ของสายผลิตเทส — หน้าที่คือ**เดินสายพาน** ไม่ใช่ลงมือทำเอง
งานจริงทุกขั้นให้ **spawn subagent** ทำ แล้วคุณอ่านผล อัปเดตสมุดคุมงาน แล้วไปตัวถัดไป

**Input:** $ARGUMENTS · ถ้าไม่มีชื่อ project → Glob `projects/*.yaml` แล้วถาม

## หลักการที่ห้ามละเมิด

1. **ความคืบหน้าอยู่ในไฟล์ ไม่ใช่ในบทสนทนา** — ทุกการเปลี่ยนสถานะต้องเขียนลง `modules.yaml`
   ผ่าน `scripts/batch_state.py` **ทันทีที่เกิด** ไม่ใช่ตอนจบ · โดน quota ตัดกลางคันแล้วสั่งใหม่ต้องไปต่อได้
2. **1 module = 1 subagent ต่อ stage** — ห้ามทำเองในบทสนทนานี้ (context จะบวมจนคุณภาพตกตั้งแต่ module ที่ 5)
3. **ห้ามหยุดถาม** (ยกเว้น `--attended`) — คำถามเขียนลงคิว แล้ว**ทำต่อภายใต้สมมติฐานที่เขียนกำกับไว้ชัด**
4. **ห้ามรายงานว่าเสร็จถ้า verify ไม่ผ่าน** — module ที่ตีกลับ 2 ครั้งให้ mark `blocked` แล้วไปตัวถัดไป
5. **ห้าม commit / push** และ **ห้ามแตะโค้ด product**

## ขั้นที่ 0 — ตรวจความพร้อมของ project (readiness level)

| เช็ก | ถ้าไม่ผ่าน |
|---|---|
| มี `projects/<p>.local.yaml` | **L0** → บอกให้รัน `/setup <p>` แล้วหยุด |
| มี `<batch.dir>/modules.yaml` | → บอกให้รัน `/module-scout <p>` แล้วหยุด |
| มี suite ที่ scaffold แล้วอย่างน้อย 1 ตัว (`status: done` ในทะเบียน) **และ** มีไฟล์ `automation.conventions` | **L1** → เข้าโหมด **PILOT** (ด้านล่าง) |
| ครบทั้งหมด | **L2** → เข้าโหมด **BATCH** |

### โหมด PILOT (project ที่ยังไม่เคยมี suite)
ทำ **module เดียว** แบบมีคนอยู่ด้วย แล้วหยุด — เพราะ 3 อย่างนี้เดาไม่ได้และจะถูก clone ไปทุก module ถ้าผิด:
BASE_URL/env จริง · flow login ของระบบ · convention ที่ทีมรับได้
1. เสนอ module นำร่อง = ตัวที่ `risk: high` แต่ **เล็กที่สุด** (ไม่ใช่ใหญ่ที่สุด — นำร่องต้องจบเร็ว) แล้วให้ผู้ใช้ยืนยัน
2. เดินสายพานเต็มเส้นแบบ `--attended` (ถามได้ตามปกติ)
3. จบแล้ว **เขียน `automation.conventions`** (`docs/CONVENTIONS.md` ของ repo automation) สรุป gotcha ที่เพิ่งเจอจริง
   — locator strategy ที่ได้ผล, การ login, quirk ของ endpoint, สิ่งที่ห้ามทำ
4. บอกผู้ใช้ว่าตอนนี้ project ขึ้นเป็น L2 แล้ว รอบหน้า `/gen-batch <p>` จะปล่อยรันยาวได้

## ขั้นที่ 1 — หยิบงาน

```bash
python3 scripts/batch_state.py next <project> --limit <N> --json    # ดีฟอลต์ N=1
```
เรียงให้แล้ว: งานค้าง (`in_progress`) มาก่อน → แล้ว `risk` สูงสุด → ข้าม `skip`/`done`/`blocked` และตัวที่ติด `depends_on`
ถ้าผู้ใช้ระบุ `--modules a,b,c` ให้ทำตามนั้นแทน (แต่ยังเช็ก readiness เหมือนกัน)

## ขั้นที่ 2 — สายพานต่อ module (เดินให้ครบทีละตัว ห้ามทำครึ่งๆ แล้วข้าม)

ก่อนเริ่มแต่ละ stage: `batch_state.py set <p> <module> --stage <stage> --status in_progress`
จบแต่ละ stage: บันทึก artifact ที่ได้ (`--artifact spec=...` / `testcases=...` / `suite=...`)

| stage | spawn subagent ให้ทำ | เสร็จเมื่อ |
|---|---|---|
| **spec** | `/gen-behavior-spec <module> --project <p> --unattended` | มีไฟล์ draft + คำถามถูกเขียนลงคิว |
| **testcases** | `/gen-testcases <module> --project <p> --unattended` | มีไฟล์ `*-testcases.md` ใน `output.dir` |
| **automation** | `/gen-automation <ไฟล์เทสเคส> --project <p> --suite <module>_robot --unattended` | suite ถูกสร้าง/ต่อเติม + dry-run เขียว |
| **verify** | `/verify-suite <module> --project <p> --testcases <ไฟล์เทสเคส>` | ไม่มีข้อ blocking |

**การส่งต่อระหว่าง stage**: ส่งแค่ **path ของ artifact** ให้ subagent ตัวถัดไป ไม่ต้องสรุปเนื้อหายาวๆ ให้ฟัง
(subagent เปิดอ่านไฟล์เองได้ และนั่นคือเหตุผลที่แยก context)

**ถ้า verify ตีกลับ**: spawn `/gen-automation` อีกรอบ **พร้อมส่งรายการ blocking ที่ได้มาแบบคำต่อคำ**
→ verify ใหม่ · ครบ 2 รอบยังไม่ผ่าน → `--blocked "verify ไม่ผ่าน 2 รอบ: <สรุปสั้น>"` แล้วไป module ถัดไป
(ใช้ `--attempt` ทุกครั้งที่วนซ้ำ)

**ถ้า module ติดธง `oversized`**: ให้ subagent แตกเป็น batch ย่อยตาม `sub_modules` แล้วทำทีละ batch
ห้ามยัดทั้งก้อนให้ agent เดียว

## ขั้นที่ 3 — คิวคำถาม (หัวใจของการปล่อยรัน)

subagent ที่รันโหมด `--unattended` จะไม่ถามอะไรเลย แต่จะเขียนคำถามลง `<batch.dir>/questions/<module>.md`
คุณมีหน้าที่:
- นับว่ามีกี่ข้อ แล้วบันทึก `--note "รอตอบ N ข้อ"` ไว้ที่ module นั้น
- **ห้ามตอบคำถามแทนผู้ใช้** และ **ห้ามเอาสมมติฐานไปเขียนเป็น spec ที่ยืนยันแล้ว** (ห้าม promote อัตโนมัติ)
- ของที่เป็น 🚩 "น่าจะเป็นบั๊ก" ให้รวบไว้ที่ `<batch.dir>/findings.md` — ของชิ้นนี้มีค่าที่สุดสำหรับ dev

## ขั้นที่ 4 — วนจนหมดโควตางาน แล้วสรุป

ทุกครั้งที่จบ module ให้ต่อท้าย `<batch.dir>/run-log.md` หนึ่งบรรทัด: วันที่ · module · stage ที่จบ · ผล · เวลา/รอบที่ใช้

สรุปตอนจบ (ภาษาไทย):
- ทำสำเร็จกี่ module / ตีกลับกี่ / blocked กี่ **พร้อมเหตุผลรายตัว**
- เทสใหม่รวมกี่เคส · suite ไหนบ้าง
- **คำถามค้างกี่ข้อ อยู่ไฟล์ไหน** — บอกตรงๆ ว่าจนกว่าจะตอบ spec ยังเป็น draft
- **บั๊กที่เจอระหว่างทาง** (`findings.md`) — สรุปหัวข้อให้เห็นในสรุปเลย อย่าให้จมอยู่ในไฟล์
- เหลืออีกกี่ module และคำสั่งที่ต้องพิมพ์เพื่อไปต่อ (`/gen-batch <p>`)
- **ย้ำว่าทุก suite ยังอยู่แค่ขั้น dry-run** — ต้องมีคนรันจริงกับ env ก่อนถึงจะเชื่อได้

## ตำแหน่งของ repo เครื่องมือ (สำคัญ)

คำสั่งนี้เรียกสคริปต์ใน repo เครื่องมือ (`scripts/`, `projects/`, `references/`) → **ต้องรันจากโฟลเดอร์นั้น**
ถ้า cwd ไม่ใช่ (ไม่เจอ `scripts/scan_modules.py`) ให้หาก่อนแล้ว `cd` ไป:

```bash
find ~ -maxdepth 5 -name scan_modules.py -path '*/scripts/*' 2>/dev/null | head -1
```
หาไม่เจอ → บอกผู้ใช้ว่าต้อง clone/ระบุ path ของ repo เครื่องมือ แล้วหยุด **ห้ามเดา path**

## ข้อกำหนด
- **ตอบเป็นภาษาไทย**
- เขียนไฟล์ได้เฉพาะใน batch dir, `output.dir`, `behavior_spec.draft_dir` และ repo automation — **ห้ามแตะ product code**
- ห้าม `git commit` / `push` · ห้ามใส่ credential จริงที่ไหนก็ตาม
- **รายงานตามจริง** — stage ไหนข้ามไปเพราะอะไรต้องบอก · ห้ามนับ module ที่ verify ไม่ผ่านเป็น "เสร็จ"
- ถ้าโดน rate limit / quota → บันทึกสถานะให้ครบก่อนหยุด แล้วบอกผู้ใช้ว่าสั่งอะไรเพื่อไปต่อ
