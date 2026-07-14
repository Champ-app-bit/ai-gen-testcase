<!--
แพทเทิร์นตามชนิดฟีเจอร์ (general web archetypes) — อ่านโดย /gen-testcases และ /gen-behavior-spec
ไฟล์นี้เป็นกลางกับทุกเว็บ — เป็น "ชนิดฟีเจอร์ที่พบได้ทั่วไป" ไม่ใช่กติกาของเว็บใดเว็บหนึ่ง
วิธีใช้: จับฟีเจอร์ที่กำลังทำเข้ากับ archetype ที่ตรง (ได้หลายอัน) แล้วเดินตาม checklist ของมัน
ค่าจริง (min เท่าไร, สถานะชื่ออะไร) ต้องดึงจากโค้ด/สเปกเสมอ — ไฟล์นี้บอกแค่ "ต้องเช็กมุมไหน"
-->
# Domain Patterns — แพทเทิร์นตามชนิดฟีเจอร์ (general)

> จับฟีเจอร์เข้ากับ archetype ที่ตรง (ได้มากกว่า 1) แล้วใช้ checklist เป็นตัวกันตกหล่น
> checklist บอก "มุมที่ต้องคิดถึง" — **ค่าจริงต้องยืนยันจากโค้ด/สเปก** (อ้าง `file:line`)

## Authentication (login / register / logout)
- credential ผิด/ถูก · บัญชีไม่มี · รหัสผ่านผิดนับครั้ง → ล็อก/throttle (ดู B7)
- นโยบายรหัสผ่าน (ความยาว/ความซับซ้อน) บังคับ **ทั้ง FE และ BE** และ **สอดคล้องกันทุกจุดที่ตั้งรหัส** (register/reset/change ต้องเท่ากัน)
- session/cookie: หมดอายุ, logout ล้าง session จริง, ใช้ session เดิมหลัง logout ไม่ได้
- account enumeration: ข้อความ/เวลาตอบต้องไม่บอกว่าบัญชีมีอยู่จริง (ดู B6)

## Token / link flows (verify email · reset password · magic link · invite)
- **หมดอายุ** — ใช้หลังหมดเวลาต้องไม่ผ่าน (ทดสอบขอบเวลา)
- **single-use** — ใช้แล้วต้องใช้ซ้ำไม่ได้
- **คาดเดาไม่ได้** — token สุ่มแข็งแรงพอ ไม่อิง timestamp/ค่าที่เดาได้ ไม่มี secret hardcoded
- **ผูกกับเจ้าของ** — token ของ A ใช้กับบัญชี B ไม่ได้ · token ปลอม/ตัดต่อ → ปฏิเสธ
- พฤติกรรมเมื่อ token หาย/ผิดรูปแบบ ต้องชัดและปลอดภัย

## Authorization / roles
- ตาราง role × resource × action (ดู B3) · guest vs user vs admin
- endpoint ที่เปลี่ยน/อ่านข้อมูลคนอื่นด้วย id → ต้องเช็คเจ้าของ (กัน IDOR)

## Forms & multi-step / wizard
- required/optional ทุก field · ค่าคงอยู่เมื่อย้อน step · ออกกลางคันแล้วกลับมา
- validation cross-field (เช่น 2 ค่าต้องตรงกัน/สัมพันธ์กัน) · submit ซ้ำ (ดู B4)

## Cart / pricing / coupon / discount
- ยอดขั้นต่ำ-สูงสุด (BVA ที่ค่าจริง) · ส่วนลดทำให้ยอดติดลบ/เป็นศูนย์ได้ไหม
- coupon: หมดอายุ, ใช้เกินโควตา, ใช้ซ้ำ/ต่อคน, ซ้อนหลายใบ, ใช้กับสินค้าที่ไม่เข้าเงื่อนไข
- ปัดเศษ/สกุลเงิน · คำนวณใหม่เมื่อแก้ตะกร้า · ราคาที่ client ส่งมาต้องไม่เชื่อ (คิดใหม่ที่ server)

## Payment / checkout / transaction
- state machine ของออร์เดอร์ (ดู A4) · จ่ายซ้ำ/กดซ้ำ → idempotency (ดู B4)
- webhook ผลชำระเงิน: มาช้า/มาซ้ำ/มาผิดลำดับ/ปลอม (ตรวจ signature)
- ยกเลิก/คืนเงินบางส่วน-เต็ม · จ่ายสำเร็จแต่ระบบล่มกลางทาง (reconcile)
- validation ฝั่ง client มี/ไม่มี — ยิงตรงข้าม UI ได้ไหม (ดู B2)

## File upload
- ชนิดไฟล์ (allow-list ไม่ใช่ block-list) · ขนาด (ขอบบน) · ไฟล์ว่าง/เสีย
- ชื่อไฟล์ชนกัน/อักขระพิเศษ/path traversal · ไฟล์อันตราย (สคริปต์ปลอมเป็นรูป)
- โควตา/จำนวนไฟล์ · เข้าถึงไฟล์ที่อัปโหลดของคนอื่นได้ไหม

## Search / list / filter / sort / pagination
- ไม่พบผลลัพธ์ · query ว่าง/ยาวมาก/อักขระพิเศษ · injection ผ่านช่องค้นหา
- pagination ขอบ (หน้าแรก/หน้าสุดท้าย/เกินหน้า) · sort ทุกคอลัมน์ทั้ง asc/desc · filter หลายตัวพร้อมกัน (A3)

## CRUD resources
- ครบ create/read/update/delete (ดู A7) · unique/ซ้ำ · แก้/ลบของที่ไม่มีหรือของคนอื่น · soft vs hard delete

## Notifications / email / async jobs / queue
- งาน async สำเร็จ/ล้มเหลว/retry · ลำดับ/ซ้ำ · idempotency ของ consumer
- เนื้อหา/ปลายทางถูกต้อง · จัดคิวจำนวนมาก · dead-letter เมื่อ fail ตลอด

## Third-party integration / webhook
- ปลายทาง timeout/ล่ม/ตอบ error → ระบบ degrade อย่างไร (ไม่ค้าง/ไม่พัง)
- retry & backoff · ตรวจ signature ของ webhook ขาเข้า · ข้อมูล mock/hardcoded หลงเหลือใน production path

## i18n / locale / timezone
- ข้อความครบทุกภาษา (ไม่มี key หลุด) · รูปแบบวันที่/ตัวเลข/สกุลเงินตาม locale · เขตเวลา (ดู B5) · ทิศทางข้อความ (ถ้ารองรับ RTL)

## Consent / legal / privacy gating
- FE บังคับติ๊กยอมรับ **และ BE ต้อง block ด้วย** (อย่าเชื่อ FE อย่างเดียว, ดู B2)
- บันทึกการยินยอม (เวลา/เวอร์ชันเอกสาร) · ถอนความยินยอม
