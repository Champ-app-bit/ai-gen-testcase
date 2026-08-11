# Demo Runbook — present ระบบ gen test case (0 → automation → GitHub Actions)

> คู่มือเดโมทีละคำสั่ง + บทพูด สำหรับนำเสนอ pipeline
> `/setup` → `/gen-behavior-spec` → `/gen-testcases` → `/gen-automation` → GitHub Actions
>
> **สไลด์:** https://claude.ai/code/artifact/ee3d8b8f-60cd-478a-b4a2-18ca6bfbafd6 (14 สไลด์ · มีโหมดนำเสนอ)
> **หลักการเดโม:** bake ล่วงหน้า — รันสดเฉพาะสิ่งที่เร็ว (< 90 วินาที) และล้มยาก

---

## 0. ข้อมูลเวที

| หัวข้อ | ค่า |
|---|---|
| เวลารวม | ~40 นาที (พูด 25-28 · เดโม 10-12 · Q&A ที่เหลือ) |
| โมดูลที่ใช้เดโม | **`supplier_location`** (ผูกพื้นที่จัดส่ง + ค่าส่ง กับซัพพลายเออร์) — AREA code `SML` |
| ทำไมโมดูลนี้ | มี draft spec อยู่แล้ว แต่ **ยังไม่ promote · ยังไม่มีเทสเคส · ยังไม่มี suite** → เดโม 0→1 ได้จริงทั้ง 3 ขั้น |
| โมดูลสำรอง | `supplier_product` (spec confirmed แล้ว ไม่มี suite) → ถ้า SML มีปัญหา ใช้ตัวนี้เดโมตั้งแต่ `/gen-testcases` |
| suite ที่ใช้โชว์ CI | `erp_supplier_robot` (มี workflow เขียวอยู่แล้วบน GitHub) |

**path ที่ต้องรู้** (ตั้ง alias ไว้ก่อนขึ้นเวทีจะสะดวก)

```bash
export TOOL=~/Web/ai_gen_testcase/ai-gen-testcase              # repo เครื่องมือ (slash commands + template)
export AUTO=~/Web/erp_08_07_2026/erp_automation_script         # repo automation (suite + .github/workflows)
export OUT=~/Web/erp_08_07_2026/erp_test_script                # output: behavior-spec + *-testcases.md
```

---

## 1. ของที่ bake ไว้แล้ว ✅ (รัน pipeline จริงเมื่อ 2026-08-11)

`/gen-behavior-spec`, `/gen-testcases`, `/gen-automation` ใช้เวลาหลายนาทีถึงหลายสิบนาทีต่อคำสั่ง
**ห้ามรันสดบนเวที** — pipeline ถูกรันจริงครบทั้ง 3 ขั้นแล้ว ของอยู่ในเครื่องพร้อมเปิด

### 1.1 ผลลัพธ์จริงที่ได้ (ตัวเลขที่ใช้พูดได้เลย)

| ขั้น | ผลลัพธ์ | ที่อยู่ |
|---|---|---|
| `/gen-behavior-spec promote supplier_location` | spec confirmed **22 ข้อ** (✅ ยืนยันเต็ม 17 · 🟡 บันทึกแบบยังไม่ยืนยัน 5) + ใบ findings **9 รายการ** (P1 1 · P2 3 · P3 5) | `$OUT/behavior-spec/confirmed/supplier-mapping-location.md` · `$OUT/behavior-spec/draft/findings-supplier-mapping-location.md` |
| `/gen-testcases` | กติกา **34 ข้อ** (✅1 / ⚠️1 / ❌32) → **43 เคสใหม่** + เจอบั๊กเพิ่ม **3 ตัว** ตอนคิดเทสเคส | `$OUT/supplier-location-testcases.md` |
| `/gen-automation` | suite ใหม่ **43 ไฟล์เทส** (UI 29 · API 14) + workflow + DataRequest · **`robot --dryrun` 43/43 เขียว** · `known-bug` 7 · `flag:confirm-spec` 5 | `$AUTO/erp_supplier_location_robot/` · `$AUTO/.github/workflows/erp-supplier-location-e2e.yml` |

คำสั่งที่ใช้ (ถ้าจะรันซ้ำกับโมดูลอื่น):

```
/setup erp
/gen-behavior-spec promote supplier_location --project erp
/gen-testcases ผูกพื้นที่จัดส่งและค่าส่งกับซัพพลายเออร์ (supplier_location) --project erp
/gen-automation $OUT/supplier-location-testcases.md --project erp --suite erp_supplier_location_robot
```

### 1.2 ไฟล์ที่จะเปิดโชว์ — คัดไว้ที่ `~/demo-present/` แล้ว

| ไฟล์ | ใช้ตอน |
|---|---|
| `01-draft-spec.md` | สเต็ป 2 — draft ที่ยังมี ❓/🚩 (ดึงจาก git ก่อน promote) |
| `02-confirmed-spec.md` | สเต็ป 2 — หลัง promote: ✅ 17 + 🟡 5 พร้อมเหตุผลว่าทำไมยังไม่ยืนยัน |
| `03-findings-บั๊กที่เจอ.md` | สเต็ป 2 — ใบ findings 9 รายการส่ง dev |
| `04-testcases.md` | สเต็ป 3 — coverage matrix + backlog 43 เคส |
| `05-data-request.md` | สเต็ป 4 — สิ่งที่ต้องขอทีมก่อนรันจริง (ปิดท้ายว่า "งานยังไม่จบ") |

เปิดทั้ง 5 ไฟล์ค้างไว้ใน editor แยก tab เรียงตามเลข (จะไม่ต้องหาไฟล์สดบนเวที)

### 1.3 git — **ยังไม่ commit** (เจตนา: ให้คุณรีวิว diff ก่อน)

`/gen-automation` ไม่ commit ให้เองตามกติกา ⇒ ตอนนี้ของใหม่ทั้งหมดเป็น **untracked**
ซึ่ง**ดีสำหรับเดโม**: `git status --short` โชว์ได้เลยว่า "นี่คือของที่เพิ่ง generate ทั้งหมด"

```bash
cd $AUTO && git status --short      # ?? .github/workflows/erp-supplier-location-e2e.yml · ?? erp_supplier_location_robot/
cd $OUT  && git status --short      # spec confirmed + findings + testcases ใหม่
```

ถ้าอยากได้ branch ไว้สลับ before/after (รีวิว diff แล้ว):

```bash
cd $OUT  && git switch -c demo/after && git add -A && git commit -m "demo: supplier_location spec + testcases"
cd $AUTO && git switch -c demo/after && git add -A && git commit -m "demo: erp_supplier_location_robot suite (43 tests, dryrun 43/43)"
```

### 1.4 ⚠️ ข้อจำกัดที่ต้องรู้ก่อนวางแผนคลิป

**เครื่องนี้ยังรันเทสจริงไม่ได้** — `users.json` ของทุกสูทในเครื่องเป็น `_status: todo` ทั้งหมด
(รหัสจริงอยู่ใน GitHub Secrets เท่านั้น) ⇒ ถ้ารันจริงตอนนี้ทุกเคสจะ **Skip** พร้อมข้อความ
`BLOCKED: ERP test account ... not provisioned`

ทางเลือก (เลือก 1):

| ทาง | ทำอะไร |
|---|---|
| **A (แนะนำ)** | เดโมในเครื่องแค่ `--dryrun` แล้วโชว์ "การรันจริง" จาก **GitHub Actions run เก่าของสูท supplier** (มี log + `report.html` + การ์ด Teams ครบ) |
| B | เติม `users.json` ของสูทใหม่ด้วยบัญชีทดสอบจริง (`_status: ready`) แล้วอัดคลิปรัน API-only 14 เคส — `robot --include level:api` ไม่ต้องเปิดเบราว์เซอร์ เร็วและเสถียรกว่า UI |
| C | เติม users.json แล้วรัน UI 1 เคสอ่านอย่างเดียว (TC-SML-01) อัดคลิปเห็น Chrome ขยับ |

คลิปที่ควรมีไว้กันพลาด: `clip-dryrun.mp4` (20-30 วิ) — อัดจากเครื่องนี้ได้เลย

### 1.5 เตรียม GitHub

- [ ] เปิด `github.com/Tanboon-Org/erp_automation_script/actions` → ยืนยันว่ามี run **เขียว** ล่าสุดของ `erp-supplier-e2e`
- [ ] เปิด run นั้นค้างไว้ 1 tab (โชว์ log + artifact `robot-results-supplier`)
- [ ] เปิดหน้า Settings → Secrets and variables → Actions ค้างไว้ 1 tab (โชว์ว่ามี secrets อะไร — **ค่าไม่โผล่**)
- [ ] screenshot การ์ด Teams ที่เคยเข้ามา (เผื่อ webhook ไม่ยิงตอนเดโม)
- [ ] จด URL ของ run ลงสไลด์ (กันหา tab ไม่ทัน)

---

## 2. T-0 เช้าวันนำเสนอ — checklist 5 นาที

```bash
# 1) slash commands ล่าสุดอยู่ในเครื่อง
cp $TOOL/commands/*.md ~/.claude/commands/ && ls ~/.claude/commands/

# 2) claude ใช้ได้
cd $TOOL && claude --version

# 3) robot ใช้ได้
robot --version                      # ต้องได้ Robot Framework 7.1.1

# 4) dry-run ของ suite ที่ bake ไว้ ผ่านจริง (ซ้อมสิ่งที่จะรันสด — ต้องได้ 43/43)
cd $AUTO/erp_supplier_location_robot
robot --dryrun --pythonpath libraries --variablefile resources/variables/env_dev.yaml tests

# 5) ยืนยันไม่เหลือ placeholder
grep -r "{{" $AUTO/erp_supplier_location_robot/ ; echo "exit=$? (ต้องเป็น 1 = ไม่เจอ)"

# 6) เปิดไฟล์เดโม 5 ไฟล์ค้างไว้
ls ~/demo-present/
```

- [ ] ถ้าจะรันเทสจริง: เติม `users.json` (`_status: ready`) — ตอนนี้ยังเป็น `todo` ทุกบัญชี **ห้าม commit ค่าจริง**
- [ ] staging เปิดได้ (ลองเปิด `https://erp-staging.dev-app-bit.com` ในเบราว์เซอร์)
- [ ] ฟอนต์ terminal ≥ 16pt · theme สว่างพอสำหรับโปรเจกเตอร์
- [ ] ปิด notification ทั้งหมด (Teams/Outlook/Slack) · ปิด tab ที่มีข้อมูลลูกค้า
- [ ] เปิดสไลด์ (artifact) + 4 ไฟล์ + 3 tab GitHub + 2 คลิปวิดีโอ ครบ

---

## 3. เดโมบนเวที — 4 สเต็ป (~11 นาที)

### สเต็ป 1 — `/setup erp` · รันสด · ~90 วินาที

**ทำ:** ในบานขวา (`$TOOL`) เปิด `claude` แล้วพิมพ์

```
/setup erp
```

**บทพูด:**
> "เครื่องใหม่เริ่มจากศูนย์ ผมไม่ต้องแก้ config มือเลย — คำสั่งนี้ไปหา repo ในเครื่องให้ก่อน
> แล้วถามยืนยันทุกตัว จากนั้นเขียน path ลงไฟล์ `erp.local.yaml` ที่ **ไม่ถูก commit**
> เพราะ path ของแต่ละคนไม่เหมือนกัน ส่วนที่ portable อย่าง git remote กับ area mapping
> อยู่ใน `erp.yaml` ที่ commit ร่วมกัน"

**จุดที่ต้องชี้เมื่อมันจบ:** ท้ายผลลัพธ์มี checklist ✅ — อ่านไฟล์โค้ดได้, นับไฟล์ `.robot` ได้ (279 ไฟล์ 5 suites)
> "มันไม่ได้บอกว่าเสร็จเฉยๆ — มัน verify ให้เห็นว่าอ่านของจริงได้"

**ถ้ามันถาม path:** เลือกตัวเลือกแรกที่มันเสนอ (จัดอันดับมาแล้ว) — อย่าพิมพ์เอง จะเสียจังหวะ

---

### สเต็ป 2 — spec: draft → confirmed · เปิดไฟล์ที่ bake ไว้ · ~3 นาที

**ทำ:** เปิด tab `01-draft-spec.md` แล้ว `02-confirmed-spec.md`

**บทพูด:**
> "ERP ไม่มีเอกสาร requirement เลย — grounding เหลือชั้นเดียวคือโค้ด ซึ่งอันตราย
> เพราะถ้าเราถอดโค้ดออกมาเป็น requirement ตรงๆ **บั๊กในโค้ดจะกลายเป็น requirement**
> แล้วเราจะไม่เจอ mismatch อีกเลย สเปกกลายเป็นกระจกสะท้อนโค้ด
>
> วิธีแก้คือทุกข้อถูกติดป้าย 3 แบบ"

ชี้ 3 ป้ายในไฟล์ draft (`01-draft-spec.md`):

| ป้าย | จำนวนในไฟล์นี้ | พูดว่า |
|---|---|---|
| ✅ | 17 ข้อ | "โค้ดชัด ทุกชั้นตรงกัน — เขียนเป็น spec ได้เลย" |
| ❓ | 1 ข้อ (`BS-SML-17` คอลัมน์ `type`) | "พฤติกรรมชัด แต่ 'เจตนา' ไม่ชัด — ต้องถาม dev ก่อน" |
| 🚩 | 4 ข้อ (`BS-SML-18..21`) | "น่าสงสัยว่าเป็นบั๊ก — เขียนเป็น *คำถาม* พร้อมหลักฐาน 2 ฝั่งที่ขัดกัน ห้ามเขียนเป็น spec" |

**แล้วเปิด `02-confirmed-spec.md` เทียบ** — จุดที่ต้องพูดคือกติกาที่ทำให้ pipeline ไม่ค้าง:
> "ใบถามส่ง PO ไปเมื่อวาน ยังไม่มีคำตอบ — แต่งานไม่หยุด กติกาคือ **ไม่ตอบ ≠ บล็อก**:
> บันทึกพฤติกรรมปัจจุบันไว้เป็น spec แล้วติดธง `flag:confirm-spec` ที่เทส
> แลกกับการยอมรับตรงๆ ว่า *ถ้าวันหนึ่งจุดนั้นทำงานผิด เราจะจับไม่ได้* — เขียนไว้ในเอกสารเลยว่าแลกอะไรไป"

**หมัดเด็ดของสเต็ปนี้** — เลื่อนไปที่ `BS-SML-18` ในไฟล์:
> "ระหว่างที่มันอ่านโค้ดโมดูลนี้ มันพิสูจน์ได้ว่า **ราคาแบบ 'กลุ่มพื้นที่' ไม่เคยถูกนำไปคิดเงินเลย**
> — ฟีเจอร์ที่มีหน้าจอให้กรอก มีข้อมูลในตาราง แต่ไม่มีใครเรียกใช้
> อันนี้ไม่ใช่เทสเคส อันนี้คือบั๊กที่เจอก่อนเขียนเทสแม้แต่บรรทัดเดียว"

จากนั้นเปิด `03-findings-บั๊กที่เจอ.md` แวบเดียว:
> "ทุกครั้งที่ promote spec ข้อ 🚩 จะถูกแยกออกเป็นใบ findings ส่งให้ dev — โมดูลนี้ได้ **9 รายการ**
> และรวมทั้งระบบตอนนี้สะสมได้ **43 รายการ · P1 9 รายการ** เช่น แก้แถวของซัพพลายเออร์เจ้าอื่นได้
> (broken access control), `page=0` ทำให้ LIMIT หลุดคืนทุกแถวในตาราง, `full_address` หายเงียบไม่ถูกบันทึก"

---

### สเต็ป 3 — เทสเคส: coverage matrix · เปิดไฟล์ที่ bake ไว้ · ~3 นาที

**ทำ:** เปิด tab `04-testcases.md`

**บทพูด (ชี้ 3 จุด ตามลำดับ — อย่าอ่านตารางทั้งตาราง):**

1. **หัวข้อ "กติกาที่พบในโค้ด/สเปก"**
   > "ทุกกติกามี `file:line` ห้อยท้าย — ตรวจย้อนได้ว่ามันไม่ได้เดา"
2. **Coverage matrix ✅/⚠️/❌**
   > "นี่คือหัวใจ มันไม่ได้ออกเทสเคสลอยๆ — มันไปอ่านเทสที่ automate ไว้แล้วใน repo
   > สกัด TC-ID กับ Evidence ออกมา แล้วเทียบ *ความหมาย* ว่ากติกาข้อไหนมีใครคุมอยู่แล้ว
   > **⚠️ คือช่องที่คนมักคิดไม่ถึง** — เช่นมีเทสฝั่งค่าที่ผิดครบ แต่ไม่เคยมีใครยืนยันว่า 'ค่าขอบที่ถูกต้องพอดี' ผ่านจริง"
3. **ตาราง "🆕 เคสใหม่ที่ยังไม่ถูก automate" — 43 เคส**
   > "output ของขั้นนี้คือ **backlog** ไม่ใช่ลิสต์เทสซ้ำของที่มีแล้ว — ทุกแถวบอกไฟล์ `.robot` เป้าหมาย
   > กับ TC-ID ที่นับต่อจากเลขสูงสุดเดิมของ area นั้นให้เลย
   > กติกา 34 ข้อ ✅1 / ⚠️1 / ❌32 — ตัว ✅ คือกติกาลิสต์ที่ยิง `/ab_supplier` **endpoint เดียวกับหน้า
   > supplier ที่เทสไว้แล้ว** มันจึงตัดออกให้ ไม่เสนอทำซ้ำ"

4. **หัวข้อ "⚠️ ช่องว่างสเปก ↔ โค้ด" — หมัดเด็ดที่สอง**
   > "ระหว่างที่มันอ่านโค้ดเพื่อคิดเทสเคส มันเจอบั๊กเพิ่มอีก **3 ตัวที่ยังไม่มีใน spec** —
   > ตัวที่ชอบสุดคือ **ลบพื้นที่ออกจากตาราง แล้วไปเพิ่มพื้นที่อื่น ตัวที่ลบกลับมาเอง**
   > เพราะ dialog ไม่ล้างรายการที่เลือกไว้หลังกดตกลง (`selected` ค้าง) — ผลคือแถวเดิมถูกลบแล้ว insert ใหม่
   > เสียประวัติไปเงียบๆ · อันนี้ไม่มีใครนึกถึงตอนเขียนเทสด้วยมือ"

**ถ้ามีคนถามเรื่องเทคนิค QA:** ชี้คอลัมน์ "เทคนิค" — EP / BVA / Decision Table / State Transition / Pairwise
มาจาก `references/tester-heuristics.md` ที่เป็น checklist กลางใช้ได้ทุกเว็บ

---

### สเต็ป 4 — suite ที่รันได้ · รัน dry-run สด · ~4 นาที

**ทำ (บานซ้าย `$AUTO`):**

```bash
# 4.1 ของใหม่ทั้งหมดที่ generate ออกมา (ยังไม่ commit)
git status --short

# 4.2 โครง suite (โครงเดียวกับทุก module — 43 ไฟล์เทสจัดกลุ่มตาม area)
find erp_supplier_location_robot -type d | sort
find erp_supplier_location_robot/tests -name '*.robot' | wc -l

# 4.3 ไม่เหลือ placeholder ของ template
grep -r "{{" erp_supplier_location_robot/ ; echo "exit=$? (1 = ไม่เจอ = ดี)"

# 4.4 locator มีที่มาจากโค้ดจริง
grep -n "source:" erp_supplier_location_robot/resources/locators/supplier_location_form_locators.resource | head -5

# 4.5 dry-run สด
cd erp_supplier_location_robot
robot --dryrun --pythonpath libraries --variablefile resources/variables/env_dev.yaml tests
```

> **จุดที่ควรชี้ระหว่าง 4.2:** `tests/` แบ่ง 8 โฟลเดอร์ตาม area (`list_ui`, `form_rounds`,
> `form_locations`, `preview`, `api_read`, `api_crud`, `api_auth`, `perm`) — **1 เคส = 1 ไฟล์**
> ชื่อไฟล์ขึ้นต้นด้วย TC-ID ⇒ ตามรอยจากเทสเคสในเอกสารมาที่โค้ดได้ตรงๆ

**บทพูด (ระหว่าง 4.1):**
> "โครงนี้ไม่ได้ให้ AI คิดเอง — มันก๊อปมาจาก `templates/robot-pom/` ที่ผมสกัดออกมาจาก suite ที่ใช้งานจริง
> ถ้าปล่อยให้ AI สร้างโครงจากความจำ ทุกครั้งจะได้โครงไม่เหมือนกัน แล้ว maintain ไม่ได้
> POM ชั้นนี้ตายตัว: tests → keywords (feature/page/common) → locators แยกไฟล์ต่อหน้า 1 เคส = 1 ไฟล์"

**บทพูด (ระหว่าง 4.3) — นี่คือประโยคทองประโยคที่สอง:**
> "locator ทุกตัวมี comment `# source: file:line` — มันเปิดไฟล์ `.vue` จริงไปอ่าน DOM มา
> ถ้าหา element ในโค้ดไม่เจอ มันจะ **ไม่เขียน locator มั่ว** แต่โยนเคสนั้นเข้า backlog พร้อมเหตุผล"

**บทพูด (ตอน dry-run เขียว 43/43) — พูดข้อจำกัดตรงๆ:**
> "เขียว 43 จาก 43 แต่ผมต้องบอกตามตรงว่า **dry-run จับได้แค่ syntax กับ keyword ที่หาย
> ยังไม่ได้พิสูจน์กับระบบจริง** — ของที่พิสูจน์กับ staging แล้วคือ 5 suite ที่รันอยู่ทุกวันนี้
> สูทใหม่นี้ยังต้องเติมบัญชีทดสอบก่อน แล้วรันจริงครั้งแรก"

ปิดท้ายสเต็ปนี้ด้วย `05-data-request.md`:
> "และนี่คือสิ่งที่ผมส่งกลับไปที่ทีมพร้อมกับ suite — บัญชีที่ต้องขอ, seed ที่ mint เองไม่ได้,
> คำถามสเปก 5 ข้อที่ยังค้าง — **เครื่องมือไม่แกล้งทำเป็นว่าทำได้ทุกอย่าง มันบอกว่าติดอะไรอยู่**"

---

## 4. ส่วน GitHub Actions (~5 นาที)

**ทำ:** สลับไป tab GitHub → หน้า Actions ของ `erp_automation_script`

### 4.1 กดรันสด (แล้วปล่อยให้วิ่งไป)

`Actions` → `erp-supplier-e2e` → `Run workflow` → เลือก branch → `Run workflow`

> "กดรันเองเท่านั้น — `workflow_dispatch` ไม่มี schedule เพราะนโยบายทีมคือไม่รัน E2E อัตโนมัติ
> และมี `concurrency` กันสอง run ชนกันแย่งข้อมูลบน staging"

### 4.2 ระหว่างรอ — เปิด run เก่าที่เขียวไว้ อธิบาย 5 จุดนี้

| # | จุด | พูดว่า |
|---|---|---|
| 1 | **secrets → users.json** | "ไม่มี credential ใน repo เลยแม้แต่ตัวเดียว — CI เอา secrets มาเขียน `users.json` ตอนรันด้วย `scripts/write_users_json.py` ไฟล์จริง gitignored มีแต่ `.example`" |
| 2 | **`--skiponfailure known-bug`** | "เทสที่ fail เพราะบั๊กที่รายงาน dev ไปแล้ว จะกลายเป็น SKIP → build ยังเขียว แต่**ไม่ปิดบัง failure ใหม่** พอ dev แก้เสร็จ เทสจะ fail เตือนเราเอง ให้ไปลบแท็ก" |
| 3 | **factory + cleanup** | "เคสที่เปลี่ยนข้อมูลจะ mint ข้อมูลใหม่ต่อรอบ ไม่เผา seed ตายตัว จบรัน `cleanup_minted.py` ลบทิ้งตาม marker ใน `output.xml` → รันซ้ำได้ไม่ทิ้งขยะบน staging" |
| 4 | **artifact** | "`robot-results-*` เก็บ 14 วัน — โหลด `report.html`/`log.html` ดูย้อนได้" (โหลดโชว์จริง 1 ไฟล์) |
| 5 | **การ์ด Teams** | "แจ้งผลเข้า Teams พร้อมแยกนับ known-bug ออกจาก skip ปกติ และบอกว่า 'ขาดอะไร' — บัญชี/seed/harness/DB ทีมจะรู้ว่าเทสที่ยังปลดล็อกไม่ได้ ติดรออะไรอยู่" (โชว์ screenshot ถ้าการ์ดยังไม่มา) |

> **เกร็ดที่ทำให้ดูมืออาชีพ:** ชี้ว่า step Teams ถูกเขียนให้ล้มเหลวเป็นแค่ warning
> — "notification สะดุด ห้ามทำให้ run ที่เขียวกลายเป็นแดง"

### 4.3 ปลาย present — กลับมาดู run สด

ถ้าเสร็จแล้ว โชว์ผล + การ์ด Teams ที่เพิ่งเข้า · ถ้ายังไม่เสร็จ บอกว่าปกติใช้เวลาเท่าไหร่แล้วเปิด run เก่าปิดท้าย

---

## 5. Plan B — ถ้าอะไรพัง

| อาการ | ทำอะไร |
|---|---|
| เน็ตห้องประชุมล่ม | เดโมทั้งหมดเป็น local ได้ ยกเว้นส่วน GitHub → ใช้ screenshot + คลิปที่อัดไว้ เล่าจบได้ครบ |
| `claude` login หลุด / โควตาหมด | ข้ามสเต็ป 1 (รันสด) → เปิดผล `/setup` ที่ screenshot ไว้ แล้วไปสเต็ป 2 ต่อ (ทุกอย่างเป็นไฟล์ที่ bake แล้ว) |
| `robot --dryrun` แดงบนเวที | อย่าแก้สด — เปิด `clip-dryrun.mp4` แล้วพูดว่า "เมื่อคืนเขียว เดี๋ยวตามดูให้" (ห้ามเสียเวลา debug หน้าคนดู) |
| staging ล่ม | ไม่กระทบเลย — dry-run ไม่แตะ staging และคลิปอัดไว้แล้ว |
| GitHub Actions run แดง | ใช้เป็นโอกาส: เปิด `log.html` แล้วโชว์ว่ารายงานบอกอะไร → "นี่คือสิ่งที่ทีมจะได้รับตอนของพัง" |
| เวลาเหลือน้อย 10 นาที | ตัดสเต็ป 1 และ 4.2 ข้อ 3-5 → เหลือ: spec ✅❓🚩 → coverage matrix → dry-run เขียว → run บน Actions |

---

## 6. คำถามที่จะถูกถาม — คำตอบสั้น

| คำถาม | ตอบ |
|---|---|
| "AI มั่วไหม / เชื่อได้แค่ไหน" | ทุกกติกาและ locator มี `file:line`; หาในโค้ดไม่เจอ → เข้า backlog ไม่เขียนมั่ว; output เป็น**ร่าง** มีคนรีวิวก่อนใช้เสมอ |
| "ค่าใช้จ่ายเท่าไหร่" | วิธีหลักใช้โควตา Claude Pro/Max ไม่คิดต่อ token · โหมด script + Gemini API มีไว้เผื่องานที่ต้องรันไม่โต้ตอบ |
| "เอา Tester ออกได้เลยไหม" | ไม่ — มันเร่งการ "คิดให้ครบ" และทำงานซ้ำๆ แทน แต่คนยังเป็นผู้ตัดสิน (human-in-the-loop) |
| "ใช้กับเว็บอื่นได้ไหม" | ได้ — ก๊อป `projects/wnw.yaml` เป็น `projects/<เว็บ>.yaml` แก้ `remotes` + `automation.areas` แล้ว `/setup <เว็บ>`; `references/` เป็นกลางกับทุก stack |
| "ทำไมไม่ให้ AI เขียนโครง suite เอง" | โครงจากความจำ AI ไม่เหมือนกันทุกครั้ง → maintain ไม่ได้ จึง scaffold จาก template ที่พิสูจน์แล้ว + `references/robot-conventions.md` |
| "ครอบคลุมระบบไปแล้วเท่าไหร่" | FE มี 48 โมดูล — มี spec 8 (confirmed 3 + draft 5) ยังไม่มีเลย 40 · automate แล้ว 5 suites / 279 ไฟล์เทส · `behavior-spec/COVERAGE.md` จัดลำดับว่าควรทำโมดูลไหนก่อน (ชั้น A = แตะเงิน/ข้อมูลลูกค้า) |
| "ถ้าโค้ดเปลี่ยน spec จะเก่าไหม" | เก่าได้ — ต้อง re-run `/gen-behavior-spec` ของโมดูลนั้น; แต่ `Evidence: file:line` ในเทสทำให้ตามได้ว่าเทสไหนอ้างโค้ดจุดที่เปลี่ยน |
| "ทำไมไม่ให้ CI รันอัตโนมัติทุกคืน" | นโยบายทีม — E2E ยิง staging จริงและเปลี่ยนข้อมูล; ถ้าจะเปิด schedule ต้อง stagger นาทีต่อ suite ไม่ให้แย่งข้อมูลกัน (มีตัวอย่าง comment ไว้ใน workflow แล้ว) |

---

## 7. ภาคผนวก — คำสั่งทั้งหมดแบบ copy-paste

```bash
# ── ติดตั้ง (เครื่องใหม่) ─────────────────────────────────────────
git clone <tool-repo> && cd ai-gen-testcase
cp commands/*.md ~/.claude/commands/

# ── pipeline เต็ม (ในหน้าต่าง claude) ─────────────────────────────
# /setup erp
# /gen-behavior-spec <module> --project erp          ← ร่าง spec
# /gen-behavior-spec promote <module> --project erp  ← ยืนยัน + แยก findings
# /gen-testcases <คำอธิบายฟีเจอร์ไทย> --project erp   ← coverage gap + backlog
# /gen-automation <ไฟล์ testcase> --project erp --suite <module>_robot

# ── verify suite ที่ได้ ───────────────────────────────────────────
cd $AUTO/<module>_robot
grep -r "{{" .                      # ต้องไม่เจอ placeholder
robot --dryrun --pythonpath libraries --variablefile resources/variables/env_dev.yaml tests

# ── รันจริงในเครื่อง ──────────────────────────────────────────────
pip install -r requirements.txt
robot --pythonpath libraries --variablefile resources/variables/env_dev.yaml \
      --skiponfailure known-bug --outputdir results tests
# เฉพาะ API (ไม่เปิดเบราว์เซอร์ เร็วกว่ามาก — เหมาะกับเดโม)
robot --pythonpath libraries --variablefile resources/variables/env_dev.yaml \
      --include level:api --outputdir results tests

# ── ขึ้น CI ──────────────────────────────────────────────────────
# 1) workflow อยู่ที่ .github/workflows/erp-<module>-e2e.yml แล้ว (ย้ายโดย /gen-automation)
# 2) ตั้ง repository secrets: ERP_ADMIN_USER/PASS, ERP_RO_USER/PASS,
#    ERP_NOVIEW_USER/PASS (optional), TEAMS_WEBHOOK_URL (optional)
# 3) Actions → erp-<module>-e2e → Run workflow
```

**ห้ามลืม:** `/gen-automation` ไม่ commit ให้เอง — ต้องรีวิว diff แล้ว commit เอง · `users.json` จริงต้องไม่ถูก commit

---

## 8. ลิงก์

- สไลด์ (artifact): https://claude.ai/code/artifact/ee3d8b8f-60cd-478a-b4a2-18ca6bfbafd6
  — กด **▶ โหมดนำเสนอ** เพื่อดูสไลด์ทีละหน้า (ลูกศร ←/→ หรือ Space เปลี่ยนหน้า · Esc ออก) · ปุ่ม **◐ ธีม** สลับสว่าง/มืดให้เข้ากับโปรเจกเตอร์
- automation repo: https://github.com/Tanboon-Org/erp_automation_script
- ความครอบคลุม spec ปัจจุบัน: `$OUT/behavior-spec/COVERAGE.md`
- กติกากลาง automation: `$TOOL/references/robot-conventions.md`
