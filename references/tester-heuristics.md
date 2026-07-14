<!--
คลังเทคนิคออกแบบเทสเคส (universal) — อ่านโดย /gen-testcases และ /gen-behavior-spec
ไฟล์นี้ตั้งใจให้ "เป็นกลางกับทุกเว็บ/ทุก stack" — ห้ามใส่ค่า/ชื่อ/กติกาเฉพาะโปรเจกต์ใด
ถ้าต้องการ heuristic เฉพาะเว็บ ให้ทำเป็นไฟล์แยกต่อโปรเจกต์แล้วชี้ผ่าน config (ไม่บังคับ)
-->
# Tester Heuristics — คลังเทคนิคออกแบบเทสเคส (universal)

> ใช้เป็น **checklist ระหว่างคิดเทสเคส** ไม่ใช่กติกาตายตัว — เลือกเทคนิคที่เหมาะกับ "กติกาที่พบในโค้ด/สเปก" แต่ละข้อ
> ทุกเคสที่เสนอต้องผูกกับกติกาจริง (มี `file:line` หรือข้อ spec รองรับ) — heuristic ช่วย "คิดให้ครบ" ไม่ใช่ "แต่งกติกาขึ้นมา"

## วิธีใช้ไฟล์นี้

1. หยิบกติกาที่พบมาทีละข้อ (validation / business rule / สถานะ / error)
2. จับคู่กับ **เทคนิค** ที่เหมาะ (ตาราง A) แล้วดูว่ามี **มุม cross-cutting** ไหนต้องเช็กเพิ่ม (ตาราง B)
3. ให้ **ระดับความเสี่ยง** (ตาราง C) เพื่อจัด priority
4. เลี่ยง anti-pattern ท้ายไฟล์

---

## A. เทคนิคหลัก (เลือกตามชนิดกติกา)

### A1. Equivalence Partitioning (EP)
- **ใช้เมื่อ** input มีช่วง/กลุ่มที่ระบบปฏิบัติเหมือนกัน
- **ทำ** แบ่งเป็น partition แล้วเลือกตัวแทน 1 ค่า/partition — ทั้ง valid และ invalid
- **อย่าลืม** partition "ว่าง/null/ผิดชนิด" มักเป็น partition ที่ถูกลืม

### A2. Boundary Value Analysis (BVA)
- **ใช้เมื่อ** กติกามีขอบเขต (min/max/ความยาว/จำนวน/วันที่)
- **ทำ** ทดสอบ `ขอบ-1`, `ขอบพอดี`, `ขอบ+1` — บั๊กมักอยู่ที่ off-by-one และการเลือก `<` vs `<=`
- **อย่าลืม** ขอบล่างสุด (0, ค่าว่าง, ตัวแรก) และขอบบนสุด (overflow, ตัวสุดท้าย, ค่ายาวเกิน)

### A3. Decision Table
- **ใช้เมื่อ** ผลลัพธ์ขึ้นกับ **หลายเงื่อนไขพร้อมกัน** (เช่น "ถ้า A และ B แต่ไม่ C")
- **ทำ** ลิสต์เงื่อนไขเป็นคอลัมน์ → แจกแจง combination ที่ให้ผลต่างกัน → 1 เคส/combination ที่ meaningful
- **อย่าลืม** combination ที่ "ขัดกันเอง" หรือ "เป็นไปไม่ได้ตาม UI แต่ยิง API ตรงได้"

### A4. State Transition
- **ใช้เมื่อ** มีสถานะ (order: draft→paid→shipped, token: issued→used→expired, user: active→locked)
- **ทำ** ทดสอบทั้ง transition ที่ **ถูกต้อง** และ **ต้องห้าม** (ยิง event ผิดสถานะ เช่น จ่ายเงินออร์เดอร์ที่ยกเลิกแล้ว)
- **อย่าลืม** สถานะซ้ำ (จ่ายเงิน 2 ครั้ง), ย้อนสถานะ, สถานะค้าง (timeout)

### A5. Pairwise / Combinatorial
- **ใช้เมื่อ** มีพารามิเตอร์อิสระหลายตัว จน combination เยอะเกินทดสอบครบ
- **ทำ** คุมให้ทุก "คู่" ของค่าถูกทดสอบอย่างน้อยครั้ง (ลดจำนวนเคสมากโดยยัง cover คู่โต้ตอบ)

### A6. Negative & Error Paths
- **ใช้เสมอ** — ทุกฟีเจอร์มี path ที่ผิดพลาด
- **ทำ** input ผิดชนิด/ผิดรูปแบบ, ทรัพยากรไม่พบ (404), สิทธิ์ไม่พอ (403), ปลายทางล่ม/timeout, payload ใหญ่เกิน
- **ตรวจ** ระบบตอบ error ที่ **ถูกต้องและปลอดภัย** (ไม่ leak stack trace / ข้อมูลภายใน)

### A7. CRUD Completeness
- **ใช้เมื่อ** ฟีเจอร์จัดการข้อมูล (create/read/update/delete)
- **ทำ** ครบทุก verb + เคสข้าม: อ่านของที่ลบแล้ว, แก้ของคนอื่น, ลบซ้ำ, สร้างซ้ำ (unique constraint)

---

## B. มุม Cross-cutting (เช็กเพิ่มแทบทุกฟีเจอร์)

### B1. Input validation
ชนิดข้อมูล · ความยาว (สั้น/ยาวเกิน) · รูปแบบ (regex) · อักขระพิเศษ/unicode/emoji · ช่องว่างหน้า-หลัง (trim) · ค่าว่าง/null · injection (SQL, NoSQL, command, template, XSS payload)

### B2. Client ↔ Server validation parity
- กติกาฝั่ง client (FE) กับ server (BE) **ต้องสอดคล้อง** — ถ้าฝั่งหนึ่งเข้มกว่า = ช่องโหว่/ความไม่ตรงกัน
- **ต้องเทสยิง API ตรง ๆ ข้าม UI** เพื่อพิสูจน์ว่า BE บังคับเองจริง (ไม่พึ่ง FE)

### B3. Authorization matrix
- ทำตาราง **role × resource × action** — ใครทำอะไรกับของใครได้
- **IDOR** (เข้าถึงของคนอื่นด้วยการเดา id) · **vertical escalation** (user ทำงาน admin) · **horizontal** (user A แก้ข้อมูล user B)
- endpoint ที่ **ควรต้อง auth แต่เผลอเปิด public**

### B4. Concurrency & idempotency
- double-submit (กดปุ่มรัว) · race condition (2 request พร้อมกันบน resource เดียว) · การใช้ token/coupon/stock ซ้ำ
- request ซ้ำ (retry/refresh) ต้องไม่ทำงานซ้ำซ้อน (สร้างออร์เดอร์ 2 ใบ, หักเงิน 2 รอบ)

### B5. Numbers, money, dates
- ปัดเศษ/ทศนิยม/สกุลเงิน · ค่าติดลบ/ศูนย์ · overflow · เขตเวลา (timezone) & DST · วันหยุด/ขอบวัน (เที่ยงคืน) · รูปแบบวันที่ต่าง locale

### B6. Error handling & messaging
- **silent failure** — จับ error แล้วเงียบ ผู้ใช้ไม่รู้ว่าล้มเหลว
- ข้อความ error ที่ **generic เกินไป** (ผู้ใช้แก้ไม่ถูก) หรือ **เปิดเผยเกินไป** (leak ว่า record มีอยู่ / โครงสร้างภายใน)
- **information leak / enumeration** — ตอบต่างกันจนเดาได้ว่าข้อมูลมีอยู่จริงไหม (เช่น อีเมล/username)

### B7. Rate limiting & abuse
- endpoint ที่ส่งเมล/OTP/สร้าง token/login ควรมี throttle — ทดสอบว่าจำกัดจริง (กัน spam / brute-force)

### B8. Security quick-list (แนว OWASP)
Broken access control (B3) · Injection (B1) · Sensitive data exposure (B6) · Missing rate limit (B7) · CSRF/replay · Insecure token (คาดเดาได้ / ไม่หมดอายุ / ไม่ single-use) · Mass assignment (ยัด field เกินที่ตั้งใจ)

---

## C. จัดลำดับความสำคัญ (priority)

**Risk = Impact × Likelihood** — ให้เคสตาม risk ไม่ใช่ตามความง่ายที่จะเขียน

| Pri | เกณฑ์ |
|-----|-------|
| P1 | กระทบเงิน/ความปลอดภัย/ข้อมูลสูญหาย/สิทธิ์ หรือ happy path หลักของฟีเจอร์ |
| P2 | ทำให้ใช้งานผิดพลาด/สับสน แต่ไม่เสียหายถาวร · boundary/negative สำคัญ |
| P3 | ขอบเคสหายาก / คอสเมติก / เกิดยากและกระทบต่ำ |

---

## D. Anti-patterns (อย่าทำ)

- **เทสแค่ happy path** — ค่าของเทสอยู่ที่ negative/boundary/permission
- **เทส framework แทน business logic** — อย่าเทสว่า "zod ทำงานไหม"; เทสว่า "กติกาที่โค้ดตั้งไว้ถูกบังคับจริงไหม"
- **assert สิ่งที่ตรวจไม่ได้** — `expected` ต้องสังเกต/วัดได้จริง (ข้อความ, status code, สถานะ record)
- **เคสซ้ำกับเทสที่ automate แล้ว** — เป้าคือ coverage gap ไม่ใช่จำนวนเคส
- **ผูกกับข้อมูล/สภาพแวดล้อมเฉพาะจนเปราะ** — เขียนให้ deterministic ทำซ้ำได้
