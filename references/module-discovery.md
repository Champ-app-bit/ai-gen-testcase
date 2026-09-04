# Module Discovery — คลังความรู้ "module ของ stack นี้อยู่ตรงไหน"

ใช้โดย `/module-scout` เป็น **prior** ตอนเดาโครงของ project ที่ยังไม่เคย scout
เป้าหมาย: เดาถูกตั้งแต่ครั้งแรกให้มากที่สุด → คนแค่กดยืนยัน ไม่ต้องพิมพ์ glob เอง

> ผลการเดาจะถูกเขียนกลับลง `projects/<project>.yaml` เป็น `discovery:` block
> ครั้งต่อไป scout อ่าน block นั้นตรงๆ ไม่เดาซ้ำ (deterministic)

---

## 1. ตรวจ stack ก่อน (marker file ที่ราก code root แต่ละอัน)

| marker | stack | หมายเหตุ |
|---|---|---|
| `nest-cli.json` / `@nestjs/core` ใน package.json | **NestJS** | module = โฟลเดอร์ที่มี `*.module.ts` |
| `next.config.*` | **Next.js** | ดูต่อว่า App Router (`src/app/`) หรือ Pages (`src/pages/`) |
| `vue.config.js` + `vue@^2` | **Vue 2** | มักมี `src/apps/` หรือ `src/views/` |
| `vite.config.*` + `vue@^3` | **Vue 3** | `src/views/` / `src/modules/` |
| `artisan` + `composer.json` | **Laravel** | module = Controller (หรือ `Modules/` ถ้าใช้ nwidart) |
| `package.json` + `express` (ไม่มี nest) | **Express** | โครงอิสระ — ดูโฟลเดอร์ที่มี `routes.js`/`controller.js` คู่กัน |
| `manage.py` | **Django** | module = app ใน `INSTALLED_APPS` |
| `pom.xml` / `build.gradle` | **Spring** | module = package ใต้ `controller/` |

⚠️ **code root ซ้อนชั้นได้** — เช่น inventory ใช้ `frontend/frontend/` (ซ้อน 1 ชั้น)
ให้ยึด path ที่อยู่ใน `sources.code` เป็นราก แล้ว glob ต่อจากนั้นเสมอ

---

## 2. Prior ต่อ stack (glob ตั้งต้น)

| stack | glob (relative จาก code root) | `name_from` | หมายเหตุ |
|---|---|---|---|
| NestJS | `src/modules/*` · `src/*/` ที่มี `*.module.ts` | dirname | 1 โฟลเดอร์ = 1 module ชัดสุดในบรรดา stack ทั้งหมด |
| Next App Router (แบบมี modules) | `src/app/modules/*` | dirname | โครงแบบ "หน้าจอตามโดเมน" |
| Next App Router (แบบ route ล้วน) | `src/app/*` | dirname | ⚠️ ปนหน้า content เยอะ — ดู §4 |
| Next Pages Router | `src/pages/*` | dirname/basename | ข้าม `_app`, `_document`, `api/` แยกต่างหาก |
| Vue 2 (ERP-style) | `src/apps/*` | dirname | ใต้ module มักมี `view/*.vue` |
| Vue 3 | `src/views/*` · `src/modules/*` | dirname | |
| Express (โครง 1 โฟลเดอร์/โดเมน) | `app/*` · `src/modules/*` ที่มี `routes.js` | dirname | มัก prefix ชื่อ เช่น `ab_payment` → ตัดด้วย `strip_prefix` |
| Laravel (ธรรมดา) | `app/Http/Controllers/*Controller.php` | basename | `strip_suffix: Controller.php` |
| Laravel monorepo | `*/app/Http/Controllers/*Controller.php` | basename | หลาย app (web/erp/backoffice) → ใส่ชื่อ app ไว้ใน `side` เช่น `be:web` |
| Laravel nwidart | `Modules/*` | dirname | |
| Django | `*/models.py` → เอาชื่อโฟลเดอร์ | dirname | |

---

## 3. การจับคู่ FE ↔ BE (`pair_by`)

| ค่า | ใช้เมื่อ | ตัวอย่าง |
|---|---|---|
| `name` | ชื่อโฟลเดอร์สองฝั่งตรงกัน (หลัง normalize `-`/`_` และ strip prefix) | inventory: FE `stock-count` ↔ BE `stock-count` · ERP: FE `payment` ↔ BE `ab_payment` |
| `route` | ชื่อไม่ตรง แต่ FE เรียก API ที่ map กลับ BE ได้ — grep `fetch(`/`axios.` ใน FE module แล้วไล่ path ไป `routes/api.php` หรือ `routes.js` | wnw/wre: FE `checkout` ↔ BE `OrderController` + `InformPaymentController` |
| `manual` | จับคู่อัตโนมัติไม่ไหว → ปล่อยให้ registry มีแต่ฝั่งเดียว แล้วเติมทีหลังตอนทำ module นั้น | wre backoffice |

**FE↔BE ไม่ใช่ 1:1 เสมอ** — 1 หน้าอาจยิงหลาย controller และ 1 controller อาจรับหลายหน้า
registry รองรับ `be: [a, b]` เป็น list ได้ ห้ามบังคับให้เหลือตัวเดียว

---

## 4. สิ่งที่ "ดูเหมือน module แต่ไม่ใช่" — ต้องคัดออกหรือ mark skip

**คัดออกทันที (`exclude` ใน discovery block)** — ไม่ใช่ฟีเจอร์:
- โครงสร้าง framework: `layout.tsx`, `page.tsx`, `_app`, `_document`, `theme`, `assets`, `shared`, `common`, `utils`, `components`, `hooks`
- route พิเศษ Next: `[...slug]`, `[id]`, `(group)`, `@modal`, `opengraph-image`
- ตัวอย่าง/ตาย: `sample`, `demo`, `test`, `old`, `backup`, `_deprecated`
- ไฟล์ฐาน Laravel: `Controller.php`, `Base.php`

**เข้า registry แต่ mark `risk: skip` + เหตุผล** — เป็นฟีเจอร์จริงแต่ automate ไม่คุ้ม:
- หน้า content นิ่ง: `about-us`, `privacy-policy`, `faqs`, `how-to-order`, `articles`, `q-n-a`
- redirect/handoff ล้วน: `openline`, `openmessenger`
- dashboard/report ที่ read-only และตัวเลขเปลี่ยนตลอด (ยกเว้นทีมขอเป็นพิเศษ)

ต่างกันตรง: `exclude` = หายไปเลย · `risk: skip` = ยังอยู่ในทะเบียนให้คนเห็นว่า "รู้จักแต่ตั้งใจไม่ทำ"
**อย่าเงียบ** — ของที่ถูกตัดต้องเห็นได้เสมอ

---

## 5. เกณฑ์จัดอันดับความเสี่ยง (generic ทุก stack)

คำนวณโดย `scripts/scan_modules.py` — **ห้าม hardcode ค่าคงที่ต่อ stack** เพราะจะต้องมานั่งจูนทุกโปรเจกต์ใหม่

**สูตรที่ใช้จริง (ปรับมาจากการทดลองกับ 4 โปรเจกต์):**

1. นับ hit ของสัญญาณแต่ละกลุ่มในไฟล์ของ module แล้วหารเป็น **ความหนาแน่นต่อ 1000 บรรทัด**

| สัญญาณ | regex คร่าวๆ | น้ำหนัก |
|---|---|---|
| money | `price\|amount\|total\|qty\|stock\|balance\|discount\|refund\|cost` | ×3 |
| state | `status\|state\|approve\|reject\|cancel\|confirm\|workflow` | ×3 |
| destructive | `delete\|remove\|void\|write.?off\|adjust\|revert` | ×2 |
| permission | `guard\|permission\|role\|policy\|@Roles\|isAdmin` | ×1 |
| external | `webhook\|gateway\|line\|payment\|s3\|sheet\|smtp\|mail\|sms` | ×1 |

2. ถ่วงด้วย **พื้นที่ผิวที่เขียนข้อมูลได้**: `score × √(1 + mutation/5)`
   > ⚠️ **ทำไมต้องมีขั้นนี้** — ความหนาแน่นอย่างเดียวทำให้ module จิ๋วที่พูดถึงเงินบ่อยแซง module ใหญ่
   > ที่มี mutation เยอะจริง (เคสจริงที่เจอ: `material-unit` 825 บรรทัด แซง `purchase-order` 7205 บรรทัด)
   > ส่วนจำนวน hit ดิบอย่างเดียวก็ทำให้ module ใหญ่ชนะทุกครั้งเพราะมีบรรทัดเยอะ ไม่ใช่เพราะเสี่ยงกว่า

3. **จัดกลุ่มโดยเทียบกันเองในโปรเจกต์นั้น** (percentile) ไม่ใช่ค่าคงที่:
   บนสุด 25% = `high` · 35% ถัดมา = `medium` · ที่เหลือ = `low`
4. เพดานตามขนาด: `< 150 บรรทัด` ขึ้น high ไม่ได้ · `< 60 บรรทัด` ได้แค่ low
5. Override เป็น `skip`: **พิสูจน์ได้ว่า read-only** (เจอ GET แต่ไม่เจอ mutation เลย) หรือไม่มีไฟล์ที่ตรง `include_ext`

**`unclear_mutation` ≠ read-only** — ถ้าจับ HTTP verb **ไม่ได้เลยสักตัว** แปลว่า pattern ไม่รู้จัก stack นี้
ห้ามตัดทิ้งเงียบๆ ให้ติดธงไว้ให้คนตรวจ
> เคสจริง: ERP FE เรียก API ผ่าน `HttpServices.putData()` — pattern `\.put\(` จับไม่ได้
> ทำให้ `order_v3` (module ใหญ่สุด 38 ไฟล์) ถูกตีเป็น read-only → skip
> แก้ด้วยการจับ `\.<verb>[A-Za-z]*\(` ครอบ wrapper ที่ทีมเขียนเอง

- **ทุก module ต้องมี `why:` หนึ่งบรรทัด** แสดงตัวเลขที่ใช้คิดจริง — เพื่อให้คนเถียงกลับได้
- คะแนนเป็น **ตัวช่วยจัดลำดับ ไม่ใช่คำตัดสิน** — คนแก้ `risk`/`status` ใน `modules.yaml` ได้ตลอด สแกนรอบหน้าไม่ทับ

---

## 6. AREA code (prefix ของ BS-/TC-ID)

- 3 ตัวอักษรพิมพ์ใหญ่ · unique ทั้ง project · **ห้ามชนกับ prefix ที่มีอยู่แล้วใน `automation.areas`**
- สคริปต์ไล่ candidate ตามลำดับนี้ แล้วหยิบตัวแรกที่ยังว่าง:
  - **คำเดียว**: 3 ตัวแรก (`tag`→`TAG`, `payment`→`PAY`, `supplier`→`SUP`) → ตัวแรก + พยัญชนะ 2 ตัวถัดไป
  - **สองคำ**: ตัวแรกคำ1 + พยัญชนะถัดไปของคำ1 + ตัวแรกคำ2 (`stock-count`→`STC`, `material-receive`→`MTR`)
    → ตัวแรกคำ1 + ตัวแรกคำ2 + พยัญชนะถัดไปของคำ2 → 2 ตัวแรกคำ1 + ตัวแรกคำ2
  - **สามคำขึ้นไป**: อักษรแรกของ 3 คำแรก (`material-write-off`→`MWO`)
  - ชนหมด → 2 ตัวแรก + เลข (`order`→`OR1` เพราะ `ORD` ถูก `order_v3` จองไว้แล้ว)
- **เลขท้าย = สัญญาณว่าชนกัน** — ให้คนดูว่าควรตั้งชื่อใหม่ไหม
- **ตั้งแล้วห้ามเปลี่ยน** — TC-ID ที่ออกไปแล้วอ้างถึงมัน (merge จึงคง `area` เดิมเสมอ)

---

## 7. Pitfalls ที่เจอมาแล้วจริง

- **โฟลเดอร์ซ้อน** — `sources.code` ชี้ `frontend/frontend` (inventory) glob ต้องเริ่มจาก path ใน config เท่านั้น
- **BE monorepo หลาย app** — wre มี `backend/{web,erp,backoffice,migrate_api}` แต่ละอันมี Controllers ของตัวเอง ชื่อซ้ำข้าม app ได้ (`OrderController` มีทั้ง web และ erp) → ใส่ชื่อ app กำกับเสมอ
- **ชื่อ module โกหก** — ERP: FE app ชื่อ `supplier_contact` แต่เนื้อหาคือ "สัญญาซัพพลายเออร์" (`/supplier-contract`, BE `ab_supplier_contract`) → **ยืนยันจาก route + BE เสมอ อย่าเชื่อชื่อโฟลเดอร์**
- **1 โฟลเดอร์ = หลาย module** — ERP `order_v3` มี 38 ไฟล์ ต้องแตกเป็น batch ย่อย → ถ้า module ใหญ่เกิน ~25 ไฟล์ ให้ mark `oversized: true` แล้วเสนอ sub-module
- **module ที่ยังไม่เสร็จ** — เจอ mock data hardcode (ERP `page.delivery` ของ order_v3) → mark `wip: true` ให้คนยืนยันก่อน automate
