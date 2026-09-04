# Onboarding — AI Test-Case Generator

เพิ่ง `git clone` repo นี้มา? ทำ 4 ขั้นนี้แล้วคิดเทสเคสได้เลย — **ใช้โควตา Claude ไม่ต้องมี API key**

## สิ่งที่ต้องมีก่อน
- **Claude Code** (CLI) + บัญชี Claude Pro/Max
- **repo ของเว็บที่จะทดสอบ** clone ไว้ในเครื่อง (product code) และ **repo automation** (ถ้ามี) — ถ้ายังไม่มี `/setup` จะช่วย clone ให้
- *(optional)* **Graphify** — code knowledge graph ที่ `/gen-behavior-spec` / `/gen-testcases` ใช้ไล่สาย `page → api → controller` ก่อน grep
  ```bash
  pip3 install --user graphifyy   # ⚠️ ชื่อ package สะกด y สองตัว · ลงครั้งเดียวต่อเครื่อง ใช้ได้ทุก project
  graphify --version              # ถ้า command not found: export PATH="$HOME/.local/bin:$PATH"
  ```
  ไม่ลงก็ทำงานได้ครบ — คำสั่งจะถอยไปใช้ grep เอง (คุ้มเมื่อทำโมดูลใหญ่ที่เรียกข้ามไฟล์หลายชั้น)

## 4 ขั้นตอน

```bash
# 1) ติดตั้ง slash command (ครั้งเดียว)
cd ai-gen-testcase
cp commands/*.md ~/.claude/commands/

# 2) เปิด Claude Code ในโฟลเดอร์นี้
claude
```
```
# 3) setup เครื่อง — Claude จะถาม path ของ repo แต่ละตัว แล้วเขียน config ให้ (ไม่ commit)
/setup wnw

# 4) คิดเทสเคส (3-way grounded: code + spec + เทสที่ automate แล้ว)
/gen-testcases สมัครสมาชิก --project wnw
```

ผลลัพธ์เขียนที่ `docs/generated/` เป็น **coverage matrix + เฉพาะเคสใหม่ที่ยังไม่ถูก automate** (backlog ว่าต้องทำอะไรต่อ) — เป็นร่าง รีวิวก่อนนำไปเขียนเทสจริง

## หลักการ
- **`/setup <project>`** — bootstrap: หา repo ในเครื่อง (ถามทุกครั้ง) → เขียน `projects/<project>.local.yaml` (path เฉพาะเครื่อง, gitignore) → verify
- **`/gen-testcases <ฟีเจอร์> --project <project>`** — อ่าน code + spec + เทสที่มี → เทียบ coverage → ออกเฉพาะเคสใหม่
- **เพิ่มเว็บใหม่**: ก๊อป `projects/wnw.yaml` เป็น `projects/<เว็บ>.yaml` แก้ `remotes` + `automation.areas` แล้ว `/setup <เว็บ>`

## ทำไมต้อง `/setup`
`projects/*.yaml` เก็บแค่ส่วน portable (git remote + area mapping) — **path จริงของ repo ต่างกันทุกเครื่อง** จึงแยกไปไฟล์ `*.local.yaml` ที่ `/setup` สร้างให้ per-machine (ไม่ถูก commit)

## โหมด script + API (optional — วิธี B)
ถ้าต้องรันแบบไม่โต้ตอบ/CI ด้วย Gemini/Claude API: `pip install -r requirements.txt` แล้วดู `README.md` หัวข้อ "วิธีใช้ (Quick Start วิธี B)"
