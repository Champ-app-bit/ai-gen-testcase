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
ใช้ slash command `/gen-testcases` — Claude อ่านโค้ดใน repo ปัจจุบันเอง (agentic) แล้วออกเทสเคส
โดยใช้โควตา **Claude Pro/Max ของคุณ ไม่คิดเงินต่อ token** เหมาะกับงาน on-demand ที่คนนั่งรันเอง

```bash
# ติดตั้งครั้งเดียว (global — ใช้ได้ทุก repo)
cp commands/gen-testcases.md ~/.claude/commands/

# ใช้งาน: เข้า repo เว็บไหนก็ได้ แล้วเปิด Claude Code
cd <repo เว็บที่จะทดสอบ>
claude
# ในหน้าต่าง claude พิมพ์:
/gen-testcases ระบบใส่คูปองส่วนลด ยอดขั้นต่ำ 500 บาท ใช้ได้ครั้งเดียวต่อคน
```
Claude จะ grep/อ่านโค้ดที่เกี่ยว → สรุปกติกา → เขียนเทสเคสลง `docs/generated/` พร้อมอ้าง `file:line`

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
pip install -r requirements.txt
```

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
- ยังไม่สร้างไฟล์เทสรันได้ (`.robot`/Playwright/pytest)
