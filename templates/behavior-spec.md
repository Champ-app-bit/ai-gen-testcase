<!--
เทมเพลต Draft Behavior Spec — ใช้โดย /gen-behavior-spec
กติกาสำคัญ (ห้ามละเมิด):
- นี่คือ "draft behavior spec" (descriptive) ไม่ใช่ requirement doc (prescriptive)
- ทุกข้อต้องมี tag ✅/❓/🚩 + Evidence เป็น file:line เสมอ
- 🚩 ต้องเขียนเป็น "คำถาม" พร้อมชี้ evidence ที่ขัดกัน ห้ามเขียนเป็นประโยค requirement
- ไฟล์นี้อยู่ใน draft_dir เท่านั้น — /gen-testcases ห้ามอ่านเป็น spec จนกว่าจะ promote ไป confirmed_dir
-->
---
module: <ชื่อ module เช่น reset-password>
project: <ชื่อ project config>
status: draft            # draft → confirmed (เปลี่ยนตอน promote เท่านั้น)
generated: <YYYY-MM-DD>
confirmed_by: null       # ชื่อคนยืนยัน + วันที่ ตอน promote
sources:                 # ไฟล์หลักที่ใช้ reverse-engineer
  - <path:line-range>
---

# Draft Behavior Spec — <module>

> ⚠️ **ร่างจาก AI (reverse-engineered จากโค้ด)** — ข้อ ❓/🚩 ยังไม่ใช่ requirement
> ต้องตอบ "คำถามถึง user" ด้านล่างแล้ว promote ก่อน จึงจะใช้ ground เทสเคสได้

## ❓🚩 คำถามถึง user (ตอบก่อน promote)

<!-- รวบทุกข้อ ❓/🚩 ขึ้นมาเป็นแบบฟอร์ม ให้ user ตอบง่ายๆ -->
| # | จากข้อ | คำถาม | ตัวเลือก | คำตอบ |
|---|--------|-------|----------|-------|
| Q1 | BS-XXX-NN | <คำถาม> | (a) ... (b) ... | |

## ขอบเขต module

<1–3 ประโยค: module นี้ครอบคลุม flow อะไร หน้าไหน endpoint ไหน — อ้างจากกราฟ/โค้ด>

## พฤติกรรมที่พบ

<!-- BS-<AREA>-<NN> รันเลขต่อเนื่องต่อ module · จัดกลุ่มตาม sub-flow ได้ -->

### BS-XXX-01 ✅ <พฤติกรรมที่ชัด ไม่กำกวม — เขียนเป็นประโยค spec ได้เลย>
- Evidence: `path/to/file:line` — `<โค้ดบรรทัดที่เป็นหลักฐาน>`
- Test coverage: <TC-ID ถ้ามีเทส automate ยืนยันอยู่แล้ว / "—">

### BS-XXX-02 ❓ <ข้อสันนิษฐาน — พฤติกรรมจริงชัด แต่ "เจตนา" ต้องให้ user ยืนยัน> → ดู Q<n>
- Evidence: `path/to/file:line` — `<โค้ด>`
- สันนิษฐาน: <ตีความว่าอะไร เพราะอะไร>

### BS-XXX-03 🚩 <สิ่งที่โค้ดทำ + ทำไมน่าสงสัย — เขียนเป็นข้อสังเกต ไม่ใช่ requirement> → ดู Q<n>
- Evidence (ฝั่งนี้): `path/to/file:line` — `<โค้ด>`
- Evidence (ที่ขัดกัน): `path/to/other:line` — `<โค้ด flow พี่น้อง / อีกชั้นที่ทำต่างกัน>`

## หลัง promote

- คำตอบที่ยืนยันพฤติกรรมเดิม → แก้ tag เป็น ✅ และเขียน body ใหม่เป็นประโยค spec
- คำตอบที่บอกว่า "เป็นบั๊ก/ต้องแก้" → **ห้ามเขียนเป็น spec** — ย้ายไปไฟล์ `findings-<module>.md`
  (spec เขียนตามพฤติกรรมที่ *ควรเป็น* ตามคำตอบ user และ mark ว่าโค้ดปัจจุบันยังไม่ตรง)
- เปลี่ยน `status: confirmed` + ใส่ `confirmed_by` แล้วย้ายไฟล์ไป `confirmed_dir`
