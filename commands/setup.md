---
description: เตรียมเครื่องให้พร้อมคิดเทสเคส (bootstrap) — หา repo ในเครื่อง, เขียน local config, verify แล้วบอกคำสั่งถัดไป
argument-hint: <ชื่อ project เช่น wnw>
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
---

คุณคือ setup assistant ของ **AI Test-Case Generator** — ทำให้เครื่องที่เพิ่ง `git clone` มา พร้อมรัน `/gen-testcases` โดยไม่ต้องแก้ config มือ **และไม่ใช้ API ภายนอก**

**project ที่จะ setup:** $ARGUMENTS

ถ้าว่าง → Glob หา `projects/*.yaml` (ไม่รวม `*.local.yaml` / `_local.example.yaml`) แล้วถามผู้ใช้ว่าจะ setup ตัวไหน

## ทำตามขั้นตอน

1. **อ่าน config** `projects/<project>.yaml` — ดู `remotes` (git URL ของ repo ที่เกี่ยว) และ `automation.areas`
   - ถ้ามี `projects/<project>.local.yaml` อยู่แล้ว → บอกผู้ใช้ว่ามีอยู่แล้ว ถามว่าจะ setup ใหม่ทับไหม ถ้าไม่ ก็ข้ามไปขั้น verify

2. **หา + ยืนยัน path ของแต่ละ repo (ถามผู้ใช้ทุกครั้ง)** — สำหรับ `code` (product), `specs` (optional), และ `automation`:
   - ก่อนถาม ให้ **ค้น candidate** ในเครื่องช่วย (เช่น `find ~ -maxdepth 4 -type d -name <ชื่อที่เดาจาก remote>` หรือดูใน `~/Web`, `~/projects`, `~`) เพื่อเสนอเป็นตัวเลือก
   - **specs มักอยู่ใน repo automation เอง** (โฟลเดอร์ `docs/`) — ให้เสนอ `<automation-repo>/docs` เป็น candidate แรกของ specs ถ้ามีไฟล์ `.md/.pdf` อยู่
   - **จัดอันดับ candidate ก่อนเสนอ** (สำคัญ — กัน repo ชื่อคล้ายปนกัน เช่น `CMS_WNW` ปน `WNW`):
     1. path ที่ **basename ของโปรเจกต์ตรงเป๊ะ** กับ `project` (เช่นชื่อ segment เป็น `WNW` ตรงตัว ไม่ใช่ `CMS_WNW`) มาก่อน
     2. ตรงกับชื่อ repo ใน `remotes` (เช่น segment สุดท้ายของ URL: `frontend`/`backend`/`automation_wnw_robot`)
     3. path ที่ตื้นกว่า (segment น้อยกว่า) และ **มี `.git`** มาก่อน · สำหรับ automation ให้เลือกอันที่ **มีโฟลเดอร์ `tests/` และไฟล์ `.robot` จริง**
     4. ตัด candidate ที่เป็น subdir ซ้อน/ดูไม่ใช่ repo ราก ออกจากตัวเลือกแรกๆ
   - เสนอ candidate ที่คะแนนดีสุดเป็น **ตัวเลือกแรก** ใน AskUserQuestion (ที่เหลือเป็นตัวเลือกรอง) + เปิดช่องให้พิมพ์ path เอง
   - ถ้าผู้ใช้บอกว่ายังไม่มี repo ในเครื่อง → เสนอ `git clone <remote>` (จาก `remotes` ใน config) ลงที่ที่ผู้ใช้เลือก; ถ้า clone ติด auth (private) → บอกให้ผู้ใช้พิมพ์ `! git clone ...` เอง หรือ auth ก่อน แล้วกลับมาบอก path
   - ตรวจว่า path ที่ได้ **มีอยู่จริงและอ่านได้** (`test -d`) ก่อนบันทึก

3. **เขียน `projects/<project>.local.yaml`** ด้วย path จริงที่ยืนยันแล้ว (โครงตาม `projects/_local.example.yaml`):
   ```yaml
   sources:
     code: [ ... ]
     specs: [ ... ]        # เว้นได้ถ้าไม่มี
   automation:
     path: .../tests
   output:
     dir: .../docs/generated   # ดีฟอลต์ = <automation-repo>/docs/generated (แยกจาก spec กัน feedback loop)
   ```

4. **ถามเรื่องวิธี B (optional)** — ถามผู้ใช้ว่าจะใช้โหมด script/automation (วิธี B ที่ต้องใช้ API) ด้วยไหม
   - ถ้าใช่ → รัน `pip install -r requirements.txt` และเตือนให้ตั้ง `GEMINI_API_KEY`/ฯลฯ
   - ถ้าไม่ (ใช้แค่ /gen-testcases ผ่านโควตา Claude) → **ข้าม ไม่ต้อง pip อะไรเลย**

4.5. **(optional) build Graphify knowledge graph** — ถ้าติดตั้ง Graphify แล้ว (`graphify --version` ผ่าน) และตั้ง `graph.path` ใน config:
   - build จาก product code: `graphify update <sources.code path>` (parse local, ไม่ใช้ LLM, ~วินาที)
   - graphify เขียน `graphify-out/` **ข้างๆ source (ใน product repo)** → **ย้ายเข้า automation repo** ให้ตรง `graph.path` (โฟลเดอร์ `graphify-out/` ของ automation repo) เพื่อไม่ให้เปื้อน product repo
   - ยืนยันว่า `graphify-out/` อยู่ใน `.gitignore` ของ automation repo (rebuildable cache, ไม่ commit)
   - ถ้าไม่ได้ติดตั้ง Graphify → ข้าม (ไม่บังคับ; /gen-testcases ยังทำงานได้ด้วย grep ปกติ)

5. **Verify** — พิสูจน์ว่าพร้อมจริง:
   - อ่านไฟล์ตัวอย่างจาก `sources.code` ได้ (เช่น หา validation/schema สักไฟล์)
   - นับไฟล์เทสใน `automation.path` (เช่น `find <path> -name '*.robot' | wc -l`) และโชว์จำนวน + area ที่เจอ
   - ถ้ามี specs → ยืนยันว่าเจอเอกสาร
   - สรุปสิ่งที่ verify เป็น checklist ✅/❌

6. **บอกคำสั่งถัดไป** — สรุปว่า setup เสร็จ แล้วบอกให้รัน เช่น:
   `/gen-testcases สมัครสมาชิก --project <project>`

## ข้อกำหนด
- **ตอบเป็นภาษาไทย**
- **ห้ามแก้ `projects/<project>.yaml` (committed)** — เขียนเฉพาะ `*.local.yaml` ที่ถูก gitignore
- ห้ามฝัง secret/PAT ลงไฟล์ config ใดๆ
- ถ้า verify ไม่ผ่านข้อไหน ให้บอกตรงๆ ว่าติดอะไรและต้องทำอะไรต่อ — อย่ารายงานว่าเสร็จทั้งที่ยังไม่ครบ
