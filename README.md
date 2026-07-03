# AI Test-Case Generator

เครื่องมือกลางช่วย **คิดเทสเคสด้วย AI จาก codebase จริง** — สำหรับทีมที่ยังไม่มี Tester

ป้อนคำอธิบายฟีเจอร์เป็นภาษาไทย → เครื่องมือจะ **clone repo จาก git remote สด**
→ คัดโค้ดที่เกี่ยวข้อง → ให้ Gemini อ่านโค้ดแล้วออกแบบเทสเคสตามเทคนิค QA มาตรฐาน
(EP / BVA / Decision Table / State Transition / Pairwise) **พร้อมอ้างอิง source จากโค้ด**

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
# Gemini API key (ฟรี https://aistudio.google.com/apikey)
export GEMINI_API_KEY=<your-key>
```

> PAT ส่งผ่าน HTTP header ตอน git ทำงาน **ไม่ถูกฝังใน URL**

## วิธีใช้

```bash
# พื้นฐาน (โปรเจกต์ wnw)
python3 testgen.py "ระบบใส่คูปองส่วนลด ยอดขั้นต่ำ 500 บาท ใช้ได้ครั้งเดียวต่อคน"

# เจาะเฉพาะ repo / โฟลเดอร์ + ออกทั้ง md และ csv
python3 testgen.py "ล็อกอินด้วยอีเมล/รหัสผ่าน" --repos frontend --path src/app/auth --format both

# ทดสอบการคัดไฟล์ก่อน (ไม่เรียก AI generate — ประหยัดโควตา)
python3 testgen.py "คูปองส่วนลด" --dry-run --keywords coupon,discount,promo,checkout

# ดึงโค้ด repo ล่าสุด
python3 testgen.py "..." --refresh
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
| `--refresh` | re-fetch repo ล่าสุด | off |
| `--dry-run` | แค่ clone + โชว์ไฟล์ที่คัด ไม่เรียก AI | off |
| `--out` | โฟลเดอร์ output | `./output` |

### env
| ตัวแปร | ความหมาย | ดีฟอลต์ |
|---|---|---|
| `GEMINI_API_KEY` | คีย์ Gemini (จำเป็นตอน generate) | — |
| `AZURE_DEVOPS_PAT` | PAT เข้า private repo (Code Read) | — |
| `AI_MODEL` | รุ่นตอน generate (อ่านโค้ด) | `gemini-2.5-pro` |
| `AI_TERMS_MODEL` | รุ่นตอนดึงคำค้น | `gemini-2.5-flash` |
| `TESTGEN_CACHE` | ที่เก็บ repo ที่ clone | `~/.cache/ai-gen-testcase` |

## ไหลการทำงาน
1. อ่าน `projects/<name>.yaml`
2. clone/refresh repo (shallow, auth ผ่าน header) ลง cache
3. **หาคำค้น** — AI แปลงฟีเจอร์ไทย → keyword อังกฤษที่น่าจะอยู่ในโค้ด
4. **คัดไฟล์** — grep + จัดอันดับความเกี่ยว (คุมด้วย `max_files` / `max_total_chars`)
5. **generate** — Gemini อ่านโค้ด → สรุปกติกา → ออกเทสเคส + source
6. เขียน `output/<project>-<slug>-testcases.md` (+ csv)

## เพิ่มเว็บใหม่
ก๊อป `projects/wnw.yaml` เป็น `projects/<ชื่อเว็บ>.yaml` แล้วแก้ `repos` / `domain` / `signal_dirs`
จากนั้น `python3 testgen.py "..." --project <ชื่อเว็บ>`

## ความปลอดภัย
- โค้ดที่คัดมา (เฉพาะส่วนเกี่ยวฟีเจอร์) จะถูกส่งไป Gemini เพื่อวิเคราะห์ — เป็นเรื่องปกติของการ ground
  แต่ควรรู้ไว้ ถ้ามีโค้ด sensitive ให้ใช้ `--path` จำกัดขอบเขต
- ไฟล์ `.env*`, `*.lock`, secret ถูก ignore อัตโนมัติ
- PAT ไม่ถูกฝังใน URL / ไม่ถูก commit (`.gitignore` กัน `.env`)

## ข้อจำกัดปัจจุบัน (Phase 1)
- ยังไม่วิเคราะห์ gap เทียบกับเทสที่มี (แผน Phase 2)
- ยังไม่สร้างไฟล์ `.robot` ให้เลย (แผน Phase 3)
- คัดไฟล์แบบ keyword ranking (ยังไม่ใช่ semantic/agentic) — เพียงพอสำหรับส่วนใหญ่
