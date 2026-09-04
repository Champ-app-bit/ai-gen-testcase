# AI Test-Case Generator

เครื่องมือกลางช่วย **คิดเทสเคสด้วย AI จาก codebase จริง** — สำหรับทีมที่ยังไม่มี Tester

ป้อนคำอธิบายฟีเจอร์เป็นภาษาไทย → เครื่องมือจะ **clone repo จาก git remote สด**
→ คัดโค้ดที่เกี่ยวข้อง (+ สเปก/requirement ถ้าเปิด RAG) → ให้ AI อ่านแล้วออกแบบเทสเคสตามเทคนิค QA มาตรฐาน
(EP / BVA / Decision Table / State Transition / Pairwise) **พร้อมอ้างอิง source จากโค้ด**
รองรับหลายเจ้า (Gemini / Claude / OpenAI / local) ผ่าน litellm

> ผลลัพธ์เป็น **ร่าง** ไว้ให้คนรีวิวก่อนนำไปเขียนเป็นเทสจริง (human-in-the-loop)
> ใช้กับเว็บไหนก็ได้

## 2 วิธีใช้งาน

### วิธี A (แนะนำ) — Claude Code + Claude Pro ✨ ไม่เปลือง API

**จำคำสั่งเดียวพอ: `/testgen`** — มันดูสถานะเองว่า project นี้อยู่ขั้นไหน แล้วพาไปขั้นถัดไปให้

```bash
# ติดตั้งครั้งเดียว (global — ใช้ได้ทุก repo)
git clone <repo นี้> && cd ai-gen-testcase
pip3 install --user graphifyy
cp commands/*.md ~/.claude/commands/

# เปิด claude แล้วพิมพ์:
/testgen                          # ดูว่ามี project อะไรบ้าง แต่ละตัวไปถึงไหนแล้ว
/testgen ~/Web/myproject          # เพิ่ม project ใหม่ — ชี้แค่ path ที่เหลือมันทำเอง
/testgen myproject                # ไปต่อจากจุดที่ค้างไว้
```

**project ใหม่ไม่ต้องเขียน config เอง** — `scripts/bootstrap_project.py` ตรวจ stack จาก marker file
(NestJS · Next App/Pages · Vue 2/3 · Laravel รวม monorepo · Express · Django · Spring)
แล้วเขียน `include_ext` / `ignore_dirs` / `signal_dirs` / `discovery` ให้เอง โดย**ทดสอบ glob กับดิสก์จริงก่อนเขียน**
พร้อมตรวจเคสที่คนมักพลาด: marker อยู่ในลูก (monorepo) และ prefix ร่วมของชื่อโฟลเดอร์ (`ab_customer` → `customer`)

> ทดสอบย้อนกลับกับ 3 โปรเจกต์ที่เคยเขียน config ด้วยมือ (Vue2+Express · NestJS+Next · Next+Laravel monorepo)
> — bootstrap เดา `discovery` ออกมาตรงกับที่คนเขียนทั้งสามตัว

คำสั่งย่อยยังเรียกตรงได้ถ้าอยากคุมเอง:

| คำสั่ง | ทำอะไร |
|---|---|
| `/setup <p>` | ผูก path บนเครื่องนี้ (สร้าง config ให้ถ้ายังไม่มี) |
| `/module-scout <p>` | ออกทะเบียน module + AREA code + อันดับความเสี่ยง |
| `/gen-behavior-spec <m> --project <p>` | ร่างสเปกจากโค้ด (ทุกข้อ tag ✅/❓/🚩) |
| `/gen-testcases <ฟีเจอร์> --project <p>` | ออกแบบเทสเคส (3-way grounding) |
| `/gen-automation <ไฟล์> --project <p>` | สร้าง Robot suite |
| `/verify-suite <m> --project <p>` | ตรวจว่า suite ที่ได้ไม่ได้มั่ว |
| `/gen-batch <p>` | ปล่อยรันทั้ง project ทีละ module |

### วิธี B — สคริปต์ Python + Gemini API (automation / clone จาก Azure)
เหมาะเมื่อต้องการดึง repo จาก git remote อัตโนมัติ หรือรันแบบไม่โต้ตอบ — ดูรายละเอียดด้านล่าง

## Behavior Spec — reverse-engineer เอกสารพฤติกรรมจากโค้ด (`/gen-behavior-spec`)
เว็บที่ไม่มีเอกสาร requirement ทำให้ 3-way grounding เหลือแค่โค้ดชั้นเดียว — คำสั่งนี้ให้ AI อ่านโค้ด+กราฟ
แล้วร่าง **"draft behavior spec"** ต่อ module เพื่อเป็น ground ชั้นที่ 2 (spec) ที่อิสระจากโค้ด

> **กับดักที่ต้องระวัง:** ถ้า reverse-engineer แล้วเขียนเป็น requirement ตรงๆ **บั๊กในโค้ดจะกลายเป็น requirement**
> แล้วจะหา mismatch ไม่เจออีก — เพราะ spec กลายเป็นกระจกสะท้อนโค้ด

วิธีแก้: แยก **descriptive** ("โค้ดทำอะไร" — reverse ได้ 100%) ออกจาก **prescriptive** ("ควรทำอะไร" — โค้ดบอกไม่ได้)
ทุกข้อจึงถูก tag 3 แบบ และต้องให้ user ยืนยันก่อนจึงกลายเป็น spec จริง:

| tag | ความหมาย | เขียนเป็น spec ได้เลยไหม |
|---|---|---|
| ✅ | พฤติกรรมชัด ทุกชั้นสอดคล้อง | ได้ |
| ❓ | พฤติกรรมชัดแต่ "เจตนา" ไม่ชัด | ต้องถาม user ก่อน |
| 🚩 | น่าสงสัย/อาจเป็นบั๊ก (เขียนเป็น *คำถาม* + evidence 2 ฝั่งที่ขัดกัน) | ห้าม — โยนเป็นคำถาม |

```bash
# ติดตั้งครั้งเดียว (global)
cp commands/gen-behavior-spec.md ~/.claude/commands/

# 1) ร่าง draft spec ของ module → เขียนลง behavior_spec.draft_dir
/gen-behavior-spec reset-password --project wnw

# 2) เปิดไฟล์ draft ตอบตาราง "คำถามถึง user" (ทุกข้อ ❓/🚩)
#    3) promote → ข้อที่ยืนยันเป็น ✅, ข้อที่เป็นบั๊กแยกไป findings-<module>.md, ย้ายไป confirmed_dir
/gen-behavior-spec promote reset-password --project wnw
```

**Flow:** draft (ทุกข้อ tag + file:line) → user ตอบคำถาม → promote → spec ที่ confirmed แล้วถูก `/gen-testcases`
อ่านเป็น ground #2 อัตโนมัติ (มันข้าม `draft_dir` เสมอเพื่อกัน feedback loop). ตั้ง path ใน `projects/<name>.local.yaml`:

```yaml
behavior_spec:
  draft_dir:     /path/to/automation-repo/docs/behavior-spec/draft      # /gen-testcases ห้ามอ่าน
  confirmed_dir: /path/to/automation-repo/docs/behavior-spec/confirmed  # นับเป็น spec
```

## สร้าง automation suite จากเทสเคส (`/gen-automation`)

ขั้นสุดท้ายของ pipeline: แปลงไฟล์เทสเคส (จาก `/gen-testcases` หรือเขียนมือ) เป็น **Robot Framework
suite ที่รันได้จริง** โดย scaffold โครง POM จาก `templates/robot-pom/` (skeleton ที่สกัดจาก suite
ที่ใช้งานจริง — ไม่ให้ AI สร้างโครงจากความจำ) แล้ว ground locator/endpoint จากโค้ดจริงทุกตัว

```bash
# ติดตั้งครั้งเดียว (global)
cp commands/gen-automation.md ~/.claude/commands/

# ใช้งาน (ต้อง /setup <project> ก่อน — คำสั่งต้องรู้ path repo automation)
/gen-automation docs/generated/payment-testcases.md --project erp
```

สิ่งที่ได้: suite ใหม่ `<module>_robot/` (หรือเทสเพิ่มใน suite เดิม) + CI workflow + DataRequest doc
— จบที่ `robot --dryrun` เขียว แล้วรายงานว่าเคสไหน automate ไม่ได้เพราะขาดข้อมูลอะไร

สิ่งที่คำสั่งอ่านเป็น ground:
- `templates/robot-pom/` — skeleton + `TEMPLATE.md` (placeholder + ไฟล์ไหน copy/generate)
- `references/robot-conventions.md` — กติกากลาง (POM layering, locator naming, tag taxonomy, factory pattern)
- `automation.conventions` ใน `projects/<name>.yaml` — gotcha เฉพาะโปรเจกต์ (อยู่ใน repo automation เอง)

**Flow เต็มของ pipeline:** `/setup` → `/gen-behavior-spec` (ร่าง+ยืนยัน spec) → `/gen-testcases`
(backlog เคสที่ยังไม่ automate) → `/gen-automation` (แปลง backlog เป็น suite ที่รันได้)

## ทะเบียน module — รู้ว่า "ทั้งเว็บมีอะไรบ้าง ทำอะไรก่อน" (`/module-scout`)

ปัญหาเวลาเอาเครื่องมือนี้ไปใช้จริง: 1 เว็บมี 30–70 module ต้องมานั่งเปิดดูเองว่ามีอะไร แล้วไล่ทำทีละตัว
`/module-scout` สแกนให้ครบทั้งโปรเจกต์ในครั้งเดียว แล้วออก **ทะเบียนงาน** ที่มีสถานะติดตามได้

```bash
cp commands/module-scout.md ~/.claude/commands/     # ติดตั้งครั้งเดียว
/module-scout inventory                             # ในหน้าต่าง claude
```

ได้ `<repo automation>/docs/batch/modules.yaml` + `modules.md`:
ทุก module พร้อม **AREA code** (prefix ของ TC-ID, ไม่ชนกัน), **อันดับความเสี่ยง** พร้อมเหตุผลที่เป็นตัวเลขจริง,
จำนวน endpoint แยก verb, suite ที่ scaffold แล้ว (นับ `.robot` บนดิสก์ → `status: done`) และธง
`oversized` / `wip_signals` / `unclear_mutation` / `unpaired`

**ทำงานกับ stack ไหนก็ได้** — ความรู้ว่า "module อยู่ตรงไหน" อยู่ใน `discovery:` ของ `projects/<project>.yaml`
ครั้งแรกคำสั่งจะเดาจาก `references/module-discovery.md` แล้วให้คุณยืนยัน จากนั้นบันทึกไว้ใช้ตลอด:

```yaml
discovery:                                    # ตัวอย่าง: NestJS + Next.js
  modules:
    - { side: be, root_match: backend,  glob: "src/modules/*",     name_from: dirname }
    - { side: fe, root_match: frontend, glob: "src/app/modules/*", name_from: dirname }
  pair_by: name                               # name | route | manual
  exclude: [shared, common]
```

ส่วนที่เป็น "งานนับ" ทำโดย `scripts/scan_modules.py` (deterministic ไม่ใช้ AI ไม่เปลืองโควตา — รันซ้ำได้ตลอด
**merge ไม่ทับ** `status`/`area`/`suite`/note ที่คุณแก้ไว้) ส่วนที่ต้องใช้วิจารณญาณ — ชื่อ module ที่โกหก,
module ที่ยังไม่เสร็จ, การแตก sub-module, การเชื่อม FE↔BE ที่ชื่อไม่ตรง — เป็นหน้าที่ของ agent

> เกณฑ์คะแนน + ที่มาของสูตร (ทำไมต้องเป็นความหนาแน่น × พื้นที่ผิว mutation แล้วจัดอันดับเทียบกันเอง)
> อยู่ใน `references/module-discovery.md` §5

## ปล่อยรันทั้ง project (`/gen-batch`) + ตัวตรวจ (`/verify-suite`)

`/gen-batch <project>` = **สั่งทีเดียว ไล่ทำทีละ module จนจบ** โดยไม่ต้องนั่งเฝ้า
มันไม่ได้ทำงานเองในบทสนทนาเดียว แต่ **spawn subagent 1 ตัวต่อ module ต่อ stage** แล้วเดินสายพาน:

```
spec → testcases → automation → verify → done      (ต่อ 1 module)
 └ /gen-behavior-spec  └ /gen-testcases  └ /gen-automation  └ /verify-suite
```

**3 อย่างที่ทำให้ปล่อยรันได้จริง:**

| กลไก | แก้ปัญหาอะไร |
|---|---|
| **สมุดคุมงานอยู่ในไฟล์** (`modules.yaml` + `scripts/batch_state.py`) | โดน quota ตัดกลางทาง / ปิดเครื่อง → สั่ง `/gen-batch <p>` ใหม่ ไปต่อจากเดิม ไม่ทำซ้ำ |
| **คิวคำถาม** (`--unattended`) | agent ห้ามหยุดถาม — เขียนคำถาม + สมมติฐานที่ใช้ไปก่อนลง `questions/<module>.md` แล้วทำต่อ · คนตอบครั้งเดียวตอนจบแทนถูกขัด 300 ครั้ง |
| **readiness level** | project ที่ยังไม่เคยมี suite (L1) จะถูกบังคับทำ **PILOT 1 module แบบมีคนเฝ้า** ก่อน แล้ว freeze convention — ไม่งั้นได้ 30 suite ที่ผิดเหมือนกันหมด |

```bash
cp commands/gen-batch.md commands/verify-suite.md ~/.claude/commands/

/gen-batch erp --limit 3          # ทำ 3 module ที่เสี่ยงสุดที่ยังไม่ได้ทำ
/verify-suite payment --project erp --testcases <ไฟล์ .md>   # ตรวจ suite เดี่ยวๆ
python3 scripts/batch_state.py report erp                    # ดูว่าทำถึงไหนแล้ว
```

**`/verify-suite` = ตัวปฏิปักษ์** ตั้งสมมติฐานว่า *"suite นี้ยังพิสูจน์อะไรไม่ได้จนกว่าจะพิสูจน์ได้"*
`scripts/verify_suite.py` ตรวจส่วนที่ฟันธงได้: placeholder ค้าง · TC-ID ซ้ำ/prefix ปนกัน ·
`Evidence: file:line` **ที่ชี้ไฟล์และบรรทัดที่มีอยู่จริง** · locator ที่มีที่มา · **เทส stub ที่ dry-run เขียวแต่ไม่ได้ assert อะไร** ·
1 เคส/ไฟล์ · creds หลุด · **เคสที่หายไปเทียบกับไฟล์เทสเคสต้นทาง**
ส่วนที่ต้องใช้ตา — locator ชี้ element ถูกตัวไหม, oracle false-pass ไหม — เป็นงานของ agent

> ⚠️ `--dryrun` เขียว = ขั้นที่ 1 ของบันไดความเชื่อมั่นเท่านั้น (`references/robot-conventions.md` §7)
> **ยังไม่ได้พิสูจน์กับระบบจริง** — ทุกสรุปของ batch จะย้ำข้อนี้เสมอ

## คลัง QA heuristics (ground เพิ่ม — ใช้ได้ทุกเว็บ)
`references/` เก็บความรู้ QA ที่ **เป็นกลางกับทุกเว็บ/ทุก stack** ให้ `/gen-testcases` และ `/gen-behavior-spec` อ่านเป็น checklist กันตกหล่น (ไม่เรียก API — เป็นแค่ไฟล์อ่าน):
- `references/tester-heuristics.md` — เทคนิค (EP/BVA/Decision Table/State Transition/Pairwise) + มุม cross-cutting (validation parity, authz matrix, concurrency, error/enumeration, rate limit, security)
- `references/domain-patterns.md` — แพทเทิร์นตามชนิดฟีเจอร์ทั่วไป (auth, token/link flow, checkout/coupon, payment, upload, search/pagination, webhook, i18n, consent ฯลฯ)

> ไฟล์กลางนี้ **ห้ามใส่ค่า/กติกาเฉพาะเว็บใด** — ถ้าเว็บไหนต้องการ heuristic เพิ่มเป็นพิเศษ ให้ทำไฟล์แยกแล้วชี้ผ่าน `heuristics.extra` ใน `*.local.yaml` (optional)

## ทำไมต้อง ground ด้วยโค้ดจริง
AI อ่านโค้ดแล้วเจอกติกาที่คนมักคิดเทสไม่ครบ: ค่า validation จริง (`min=500` → ทดสอบ 499/500/501),
business rule (logic คูปอง/ค่าส่ง → decision table), enum/สถานะ, ข้อความ error จริง
— แล้วออกเทสเคสที่ตรงระบบ ไม่ใช่เดา

## ติดตั้ง

```bash
# วิธี A (slash command) — ไม่ต้องติดตั้งอะไรเลยนอกจากก๊อป command
cp commands/*.md ~/.claude/commands/

# วิธี B (สคริปต์ python + API) เท่านั้นที่ต้อง:
pip install -r requirements.txt
```

### (optional) Graphify — ground #0 code knowledge graph

```bash
pip3 install --user graphifyy   # ⚠️ package สะกด y สองตัว (คำสั่งที่ได้ชื่อ graphify)
graphify --version              # command not found → export PATH="$HOME/.local/bin:$PATH"
```

**ลงครั้งเดียวต่อเครื่อง ใช้ได้ทุก project** · ไม่ต้องมี API key (`graphify update` เป็น AST parse ล้วน ไม่เรียก LLM)
· ที่มา: [safishamsi/graphify](https://github.com/safishamsi/graphify) (MIT, third-party)

| ใครใช้ | ใช้ทำอะไร |
|---|---|
| `/setup` | **สร้าง** กราฟ (`graphify update <sources.code>`) แล้วย้าย `graphify-out/` เข้า repo automation ตาม `graph.path` ใน `*.local.yaml` |
| `/gen-behavior-spec` · `/gen-testcases` | **อ่าน** กราฟ (`graphify explain` / `graphify path`) เพื่อไล่สาย `page → component → api → controller` ก่อน grep — กันหลง endpoint / กันตกหล่น |

**ไม่ติดตั้งก็ใช้งานได้ครบ** — `/setup` ข้ามขั้นนี้เงียบๆ และคำสั่ง gen ถอยไปใช้ grep/Glob แทน
คุ้มกับโมดูลใหญ่ที่เรียกข้ามไฟล์หลายชั้น · โมดูล CRUD เล็กๆ grep ตรงๆ ก็พอ

> `graphify-out/` ถูก gitignore (cache ที่ rebuild ได้ + เก่าทันทีที่โค้ดเปลี่ยน) ⇒ **เครื่องใหม่ต้อง build เอง** (~30 วิ ต่อ repo)
> และต้องรัน `graphify update` ซ้ำทุกครั้งที่ pull โค้ดใหม่ ไม่งั้นกราฟจะชี้ไป node ที่ย้าย/หายไปแล้ว

## ตั้ง credential (ครั้งเดียว)

```bash
# Azure DevOps PAT — scope: Code (Read)  (สร้างที่ Azure DevOps → User settings → Personal access tokens)
export AZURE_DEVOPS_PAT=<your-pat>
# key ของเจ้าที่จะใช้ — เลือกเจ้าเดียวก็พอ (ผ่าน litellm รองรับหลายเจ้า)
export GEMINI_API_KEY=<your-key>       # ฟรี https://aistudio.google.com/apikey
# export ANTHROPIC_API_KEY=<your-key>  # ถ้าจะใช้ Claude: AI_MODEL=anthropic/claude-sonnet-4-5
# export OPENAI_API_KEY=<your-key>     # ถ้าจะใช้ GPT: AI_MODEL=gpt-4o
```

> รันผ่าน **litellm** — เปลี่ยนเจ้าได้แค่ตั้ง `AI_MODEL` (เช่น `gemini/gemini-2.5-pro`, `anthropic/claude-sonnet-4-5`, `gpt-4o`, `ollama/llama3` สำหรับ local) + ตั้ง key ของเจ้านั้น
> PAT ส่งผ่าน HTTP header ตอน git ทำงาน **ไม่ถูกฝังใน URL**

## วิธีใช้ (Quick Start วิธี B)

**ทำตามลำดับนี้ (ครั้งแรก):**

```bash
# 1) ติดตั้ง (ครั้งเดียว)
cd ai-gen-testcase
pip install -r requirements.txt

# 2) ตั้ง credential (ครั้งเดียวต่อ terminal — ดูหัวข้อ "ตั้ง credential" ข้างบน)
export AZURE_DEVOPS_PAT=<pat>
export GEMINI_API_KEY=<key>

# 3) ลองดูก่อนว่าคัดไฟล์ถูกไหม (ไม่เรียก AI = ไม่เปลืองโควตา) — แนะนำทำก่อนเสมอ
python3 testgen.py "ระบบใส่คูปองส่วนลด ยอดขั้นต่ำ 500 บาท" --dry-run --keywords coupon,discount,checkout

# 4) พอใจแล้ว รันจริง (เอา --dry-run ออก)
python3 testgen.py "ระบบใส่คูปองส่วนลด ยอดขั้นต่ำ 500 บาท ใช้ได้ครั้งเดียวต่อคน"

# 5) เปิดผลลัพธ์ที่ output/wnw-...-testcases.md แล้ว *รีวิวก่อนใช้* (ผลเป็นร่างเสมอ)
```

**ตัวอย่างอื่นๆ:**
```bash
# เจาะเฉพาะ repo / โฟลเดอร์ + ออกทั้ง md และ csv
python3 testgen.py "ล็อกอินด้วยอีเมล/รหัสผ่าน" --repos frontend --path src/app/auth --format both

# ground ด้วยโค้ด + สเปก (dual grounding — ดูหัวข้อด้านล่าง)
python3 testgen.py "คูปองส่วนลด"          # อ่าน spec จาก docs/ ที่ตั้งใน config

# ดึงโค้ด repo ล่าสุด + re-index เอกสาร
python3 testgen.py "..." --refresh

# กำหนดจำนวนเคสขั้นต่ำ
python3 testgen.py "..." --count 12
```

### ตัวเลือก
| ตัวเลือก | ความหมาย | ดีฟอลต์ |
|---|---|---|
| `feature` | คำอธิบายฟีเจอร์ (ไทย) | จำเป็น |
| `--project` | config ใน `projects/` | `wnw` |
| `--repos` | เลือก repo บางตัว คั่นด้วย `,` | ทั้งหมดใน config |
| `--path` | จำกัดไฟล์ใต้ subpath | — |
| `--keywords` | คำค้นเพิ่ม (อังกฤษ) คั่นด้วย `,` | — |
| `--prefix` | prefix ของ TC-ID | อิง feature |
| `--count` | จำนวนเคสขั้นต่ำ | `8` |
| `--format` | `md` / `csv` / `both` | `md` |
| `--refresh` | re-fetch repo ล่าสุด + re-index เอกสาร | off |
| `--docs` | override path โฟลเดอร์เอกสาร spec (RAG) | อิง config |
| `--no-docs` | ปิด RAG เอกสาร ใช้เฉพาะโค้ด | off |
| `--top-k` | จำนวน chunk เอกสารที่ดึงมา ground | `6` |
| `--dry-run` | แค่ clone + โชว์ไฟล์/เอกสารที่คัด ไม่เรียก AI | off |
| `--out` | โฟลเดอร์ output | `./output` |

### env
| ตัวแปร | ความหมาย | ดีฟอลต์ |
|---|---|---|
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / … | key ของผู้ให้บริการ AI (ต้องมีตัวใดตัวหนึ่งตรงกับ `AI_MODEL`) | — |
| `AZURE_DEVOPS_PAT` | PAT เข้า private repo (Code Read) | — |
| `AI_MODEL` | รุ่นตอน generate (อ่านโค้ด) — ชื่อแบบ litellm | `gemini/gemini-2.5-pro` |
| `AI_TERMS_MODEL` | รุ่นตอนดึงคำค้น | `gemini/gemini-2.5-flash` |
| `AI_EMBED_MODEL` | รุ่น embedding ตอน RAG เอกสาร | `gemini/text-embedding-004` |
| `TESTGEN_CACHE` | ที่เก็บ repo ที่ clone + vector เอกสาร | `~/.cache/ai-gen-testcase` |

## Dual grounding — ground ด้วยโค้ด + สเปก (optional)
นอกจากโค้ด สามารถป้อน **requirement/spec** (PDF/md/txt) มา ground คู่กันได้ — AI จะ **เทียบสเปกกับโค้ด**
แล้วหา *ช่องว่าง* (กติกาในสเปกที่โค้ดยังไม่ทำ / โค้ดทำต่างจากสเปก) ซึ่งมักเป็นเทสเคส (และบั๊ก) ที่มีค่าที่สุด

```yaml
# ใน projects/<name>.yaml — comment ออก = ปิด (ใช้เฉพาะโค้ด เหมือนเดิม)
docs:
  path: ./docs/wnw          # โฟลเดอร์เก็บ requirement
  ext: [.pdf, .md, .txt]
```
```bash
python3 testgen.py "คูปองส่วนลด"                    # ใช้ docs จาก config
python3 testgen.py "คูปองส่วนลด" --docs ./specs      # override path
python3 testgen.py "คูปองส่วนลด" --no-docs           # ปิด RAG ใช้เฉพาะโค้ด
python3 testgen.py "คูปองส่วนลด" --refresh --top-k 8 # re-index เอกสาร + ดึง 8 chunk
```
> เอกสารถูก embed ครั้งเดียวแล้ว cache (re-embed เฉพาะ chunk ใหม่/`--refresh`) — คุมต้นทุน
> ผลลัพธ์เพิ่มหัวข้อ **"⚠️ ช่องว่างระหว่างสเปกกับโค้ด"** ให้รีวิว

## ไหลการทำงาน
1. อ่าน `projects/<name>.yaml`
2. clone/refresh repo (shallow, auth ผ่าน header) ลง cache
3. **หาคำค้น** — AI แปลงฟีเจอร์ไทย → keyword อังกฤษที่น่าจะอยู่ในโค้ด
4. **คัดไฟล์** — grep + จัดอันดับความเกี่ยว (คุมด้วย `max_files` / `max_total_chars`)
5. **RAG เอกสาร** (ถ้าตั้ง `docs`) — embed spec → ดึง chunk ที่เกี่ยวกับฟีเจอร์
6. **generate** — AI อ่านโค้ด + สเปก → สรุปกติกา → หา gap → ออกเทสเคส + source
7. เขียน `output/<project>-<slug>-testcases.md` (+ csv)

## เพิ่มเว็บใหม่
ก๊อป `projects/wnw.yaml` เป็น `projects/<ชื่อเว็บ>.yaml` แล้วแก้ `repos` / `domain` / `signal_dirs`
จากนั้น `python3 testgen.py "..." --project <ชื่อเว็บ>`

## ความปลอดภัย
- โค้ดที่คัดมา (เฉพาะส่วนเกี่ยวฟีเจอร์) จะถูกส่งไป AI เพื่อวิเคราะห์ — เป็นเรื่องปกติของการ ground
  แต่ควรรู้ไว้ ถ้ามีโค้ด sensitive ให้ใช้ `--path` จำกัดขอบเขต
- เอกสาร spec (ถ้าเปิด RAG) ถูกส่งไป AI ตอน generate และไป embedding provider ตอน index — เช่นเดียวกับโค้ด
  ถ้าเอกสาร sensitive ให้ระวัง / จำกัดไฟล์ใน `docs.path`
- ไฟล์ `.env*`, `*.lock`, secret ถูก ignore อัตโนมัติ
- PAT ไม่ถูกฝังใน URL / ไม่ถูก commit (`.gitignore` กัน `.env`)

## ข้อจำกัดปัจจุบัน
- คัดไฟล์**โค้ด**แบบ keyword ranking (ยังไม่ใช่ semantic/agentic) — เพียงพอสำหรับส่วนใหญ่
- RAG ใช้กับ**เอกสาร**เท่านั้น (โค้ดยังใช้ grep — เหมาะกว่าสำหรับโครงสร้างโค้ด)
- ยังไม่ทำ traceability matrix (req→case) และยังไม่ pull Azure Work Item/Wiki (แผนถัดไป)
- สร้างไฟล์เทสรันได้แล้วผ่าน `/gen-automation` (Robot Framework เท่านั้น — Playwright/pytest ยังไม่รองรับ)
