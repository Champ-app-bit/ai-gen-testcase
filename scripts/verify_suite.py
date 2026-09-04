#!/usr/bin/env python3
"""verify_suite.py — ตรวจ Robot suite แบบ mechanical (ส่วนที่ตัดสินได้โดยไม่ต้องใช้ AI)

ใช้: python3 scripts/verify_suite.py <project> <module> [--testcases <ไฟล์ .md>] [--json]

ตรวจตาม references/robot-conventions.md — ทุกข้อ "พิสูจน์ได้/ผิดได้" ไม่ใช่ความเห็น:
  placeholder ค้าง · Documentation+Evidence · Evidence ชี้ไฟล์:บรรทัดที่มีจริง · TC-ID ตรงชื่อไฟล์
  · TC-ID ซ้ำ · 1 เคส/ไฟล์ · Force Tags ครบ taxonomy · locator มี # source: ที่ชี้ของจริง
  · เทสหลอก (stub ที่ dry-run เขียวแต่ไม่ได้ assert อะไร) · creds หลุด · เคสหายไปจากไฟล์เทสเคสต้นทาง

exit 1 = มีข้อ blocking ตก · exit 0 = ผ่าน (อาจมี warning)
สิ่งที่สคริปต์นี้ตรวจ *ไม่ได้* และต้องให้ agent ทำต่อ: locator ชี้ element ที่ถูกตัวจริงไหม,
endpoint ตรง route จริงไหม, expected ของเคสสมเหตุสมผลไหม
"""
import json, re, sys, subprocess
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("ต้องมี pyyaml ก่อน: pip install pyyaml")

TOOL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL_DIR / "scripts"))
from scan_modules import load_cfg, automation_root, norm      # noqa: E402

REQUIRED_TAGS = ("feature:", "group:", "level:")
# locator ที่มากับ template (widget กลาง/หน้า login) ไม่ได้ ground จากโค้ด product → ไม่บังคับ # source:
TEMPLATE_LOCATORS = {p.name for p in (TOOL_DIR / "templates" / "robot-pom" / "resources"
                                      / "locators").glob("*.resource")} \
    if (TOOL_DIR / "templates" / "robot-pom" / "resources" / "locators").is_dir() else set()
STUB_PAT = re.compile(r"^\s*(Fail|Log)\s+.*(not yet implemented|TODO|placeholder|ยังไม่ได้)",
                      re.I | re.M)
CRED_PAT = re.compile(r"(password|passwd|secret|token)\s*[=:]\s*[\"']?(?!\$\{|%\{|<)"
                      r"[A-Za-z0-9!@#$%^&*_-]{6,}", re.I)


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, check, msg, where=None):
        self.items.append({"level": level, "check": check, "msg": msg, "where": where})

    fail = lambda self, *a: self.add("FAIL", *a)      # blocking
    warn = lambda self, *a: self.add("WARN", *a)      # ต้องอ่าน แต่ไม่บล็อก
    info = lambda self, *a: self.add("INFO", *a)


def resolve_suite(cfg, module, root):
    areas = cfg.get("automation", {}).get("areas", {}) or {}
    key = norm(module, {})
    for name, a in areas.items():
        if norm(name, {}) == key:
            d = a["dir"] if isinstance(a, dict) else a
            prefix = (a.get("prefix") if isinstance(a, dict) else None) or ""
            sub = root / (d.split("/")[0] if cfg["automation"].get("layout") == "multi-suite" else d)
            return sub, prefix.replace("TC-", "")
    hits = [p for p in root.glob(f"*{key.replace('-', '_')}*robot*") if p.is_dir()]
    return (hits[0] if hits else None), ""


def code_roots(cfg):
    return [Path(p) for p in cfg.get("sources", {}).get("code", [])] + \
           [Path(p) for p in (cfg.get("sources", {}).get("specs") or [])]


def evidence_exists(ref, roots, suite, hint=""):
    """ref เช่น 'model.js:12' — หาไฟล์จาก roots แล้วเช็กว่ามีบรรทัดนั้นจริง

    ⚠️ basename ซ้ำได้เยอะ (ERP มี model.js ทุก module) — ถ้าเจอหลายตัวต้องดู *ทุกตัว*
    ก่อนสรุปว่าไม่มี ไม่งั้นจะฟ้องผิด (บั๊กเดิม: ดูแค่ 3 ตัวแรกแล้วสรุปว่าไม่มีบรรทัด 721
    ทั้งที่ ab_payment/model.js มี 1204 บรรทัด)
    """
    m = re.match(r"([\w./\\-]+\.\w+):(\d+)", ref)
    if not m:
        return None, "รูปแบบไม่ใช่ file:line"
    fname, line = m.group(1), int(m.group(2))
    cands = []
    for r in roots + [suite]:
        p = r / fname
        if p.is_file():
            cands.append(p)
        cands += list(r.rglob(Path(fname).name))
    cands = list(dict.fromkeys(cands))
    if not cands:
        return False, f"ไม่พบไฟล์ {fname}"
    # ถ้ามีคำใบ้ (ชื่อ module) ให้ไฟล์ที่ path ตรงคำใบ้มาก่อน
    if hint:
        cands.sort(key=lambda p: hint.replace("-", "_") not in str(p))
    ok = []
    for p in cands:
        try:
            if len(p.read_text(encoding="utf-8", errors="ignore").splitlines()) >= line:
                ok.append(p)
        except OSError:
            continue
    if ok:
        return True, str(ok[0])
    return False, (f"{fname} มี {len(cands)} ไฟล์ในโปรเจกต์ แต่ไม่มีตัวไหนยาวถึงบรรทัด {line}")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    project, module = sys.argv[1], sys.argv[2]
    as_json = "--json" in sys.argv
    tc_file = None
    if "--testcases" in sys.argv:
        tc_file = Path(sys.argv[sys.argv.index("--testcases") + 1])

    cfg = load_cfg(project)
    root = automation_root(cfg)
    suite, prefix = resolve_suite(cfg, module, root)
    rep = Report()
    if not suite or not suite.is_dir():
        rep.fail("suite", f"หา suite ของ module '{module}' ไม่เจอใต้ {root}")
        return emit(rep, as_json, None)

    tests = sorted(suite.rglob("*.robot"))
    tests = [t for t in tests if "resources" not in t.parts]
    if not tests:
        rep.fail("suite", f"ไม่มีไฟล์ .robot ใน {suite}")
        return emit(rep, as_json, suite)
    rep.info("suite", f"{suite.name} · {len(tests)} ไฟล์เทส")

    # 1) placeholder ค้างจาก template
    for f in suite.rglob("*"):
        if f.is_file() and f.suffix in (".robot", ".resource", ".yaml", ".py", ".md"):
            txt = f.read_text(encoding="utf-8", errors="ignore")
            for ph in set(re.findall(r"\{\{[A-Z_]+\}\}", txt)):
                rep.fail("placeholder", f"ยังมี {ph} ค้างอยู่", str(f.relative_to(root)))

    roots = code_roots(cfg)
    seen_ids, ev_checked = {}, 0

    for f in tests:
        rel = str(f.relative_to(root))
        txt = f.read_text(encoding="utf-8", errors="ignore")

        # 2) ชื่อไฟล์ตาม convention + TC-ID
        # ยอมรับ sub-area ด้วย (TC-OV3-ISS-01) — บาง suite ใหญ่แตกกลุ่มย่อย
        m = re.match(r"(TC-[A-Z0-9]+(?:-[A-Z]+)*(?:-\d+[a-z]?)?)_.+\.robot$", f.name)
        if not m:
            rep.fail("naming", "ชื่อไฟล์ไม่ตรง TC-<PREFIX>[-SUB]-NN_slug.robot", rel)
            tc_id = None
        else:
            tc_id = m.group(1)
            if not re.search(r"-\d+[a-z]?$", tc_id):
                rep.warn("naming", f"{tc_id} ไม่มีเลขลำดับท้าย — ไล่เลขเคสต่อไม่ได้", rel)
            if prefix and not tc_id.startswith(f"TC-{prefix}-"):
                rep.fail("naming", f"{tc_id} ใช้ prefix ไม่ตรง config (ต้องเป็น TC-{prefix}-) "
                                   f"— prefix ปนกันใน suite เดียวทำให้ไล่เลขต่อพลาด", rel)
            if tc_id in seen_ids:
                rep.fail("duplicate", f"{tc_id} ซ้ำกับ {seen_ids[tc_id]}", rel)
            seen_ids[tc_id] = rel

        # 3) Documentation + Evidence
        # Robot ต่อบรรทัดด้วย "..." ซึ่งขึ้นต้นบรรทัดเหมือนกัน — ต้องรวมเข้ามาด้วย
        # (บั๊กเดิม: ตัดที่บรรทัด ... ทำให้ Evidence ที่อยู่บรรทัดสองหายไปทั้งหมด)
        doc = re.search(r"^Documentation[ \t]+(.*(?:\n\.\.\..*)*)", txt, re.M)
        if not doc:
            rep.fail("doc", "ไม่มี [Documentation] ระดับ suite", rel)
        else:
            body = doc.group(1)
            if tc_id and tc_id not in body:
                rep.fail("doc", f"Documentation ไม่ได้อ้าง {tc_id}", rel)
            evs = re.findall(r"Evidence:\s*([^\n]+)", body)   # ห้ามตัดที่ "." — ชื่อไฟล์มีจุด
            if not evs:
                has_ref = re.search(r"[\w./\\-]+\.\w+:\d+", body)
                rep.fail("evidence",
                         "อ้าง file:line อยู่แต่ไม่ได้ขึ้นต้นด้วย 'Evidence:' ตาม convention"
                         if has_ref else "Documentation ไม่มี 'Evidence: <file:line>'", rel)
            for ev in evs:
                for ref in re.findall(r"[\w./\\-]+\.\w+:\d+", ev):
                    ok, detail = evidence_exists(ref, roots, suite, module)
                    ev_checked += 1
                    if ok is False:
                        rep.fail("evidence", f"Evidence ชี้ของที่ไม่มีจริง: {ref} — {detail}", rel)

        # 4) Force Tags ครบ taxonomy
        ft = re.search(r"^Force Tags\s+(.+)$", txt, re.M)
        if not ft:
            rep.fail("tags", "ไม่มี Force Tags", rel)
        else:
            for t in REQUIRED_TAGS:
                if t not in ft.group(1):
                    rep.fail("tags", f"Force Tags ขาด {t}*", rel)

        # 5) 1 TC-ID/ไฟล์ (ไม่ใช่ 1 เคส/ไฟล์) + ห้าม [Template]
        # กฎเดิมเขียนว่า "1 เคส/ไฟล์" ซึ่งตีกลับงานที่ทีมยอมรับไปแล้วเอง
        # สำรวจ repo จริง 2026-09-01: ไฟล์ที่มีหลายเคส 46 ไฟล์ เป็นเคส A/B/C ของ
        # TC-ID เดียวกัน 100% · ไม่มีไฟล์ไหนปน TC-ID ต่างกันเลย
        # (erp_store_robot 10 ไฟล์ · supplier/payment/delivery/contract 1 ไฟล์ — ทั้งหมด status done)
        # สิ่งที่ต้องกันจริงคือการปน TC-ID เพราะทำให้ TC-ID ↔ ชื่อไฟล์ไม่ 1:1 ตามข้อ 4
        cases = re.findall(r"^([A-Za-z0-9].+)$", txt.split("*** Test Cases ***")[-1], re.M) \
            if "*** Test Cases ***" in txt else []
        ids = {m.group(0) for c in cases
               if (m := re.match(r"TC-[A-Z0-9]+-\d+", c.strip()))}
        if len(ids) > 1:
            rep.fail("layout", f"ปน TC-ID ต่างกัน {len(ids)} ตัวในไฟล์เดียว "
                               f"({', '.join(sorted(ids))}) — TC-ID ต้องตรงชื่อไฟล์ 1:1", rel)
        elif len(cases) > 1:
            rep.warn("layout", f"มี {len(cases)} เคสย่อยของ {next(iter(ids), '?')} ในไฟล์เดียว "
                               f"(รูปแบบที่ใช้จริงทั้ง repo — ยอมรับได้)", rel)
        if "[Template]" in txt:
            rep.fail("layout", "ใช้ [Template] (กติกาห้าม)", rel)

        # 6) เทสหลอก — dry-run เขียวแต่ไม่ได้พิสูจน์อะไร
        if STUB_PAT.search(txt):
            rep.warn("stub", "เป็น stub (Fail/Log ว่ายังไม่ implement) — dry-run เขียวแต่ไม่ได้ assert", rel)

        # 7) creds หลุด
        for hit in CRED_PAT.findall(txt):
            # heuristic ล้วน — เทส negative มัก "ตั้งใจ" ใส่ token ปลอม (TC-SUP-35 bad-static-token)
            # ฟันธงไม่ได้ ให้คนดู · ของที่ฟันธงได้คือ users.json ที่ถูก git track (ด้านล่าง)
            rep.warn("secret", f"อาจมี credential ฝังในไฟล์ ({hit[0]}…) — ตรวจด้วยตา", rel)

    # 8) locator ต้องมี # source: ที่ชี้ของจริง
    for lf in (suite / "resources" / "locators").glob("*.resource") \
            if (suite / "resources" / "locators").is_dir() else []:
        rel = str(lf.relative_to(root))
        from_template = lf.name in TEMPLATE_LOCATORS
        head = lf.read_text(encoding="utf-8", errors="ignore")
        # ของจริงส่วนใหญ่ประกาศที่มาไว้ใน Documentation ระดับไฟล์ ("Locators for … (form.supplier.vue)")
        # ถือว่า ground แล้ว → ขาด # source: รายบรรทัดเป็น WARN ไม่ใช่ FAIL
        # แต่ถ้าทั้งไฟล์ไม่มีที่มาเลย = เดา DOM → FAIL
        file_sourced = bool(re.search(r"\*\*\* Settings \*\*\*[\s\S]{0,600}?"
                                      r"[\w-]+\.(vue|tsx?|jsx?|php|html)", head))
        for i, line in enumerate(lf.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if re.match(r"^\$\{[A-Z0-9_]+\}", line):
                if "# source:" not in line:
                    (rep.warn if (from_template or file_sourced) else rep.fail)(
                        "locator",
                        f"locator ไม่มี '# source: <file:line>' (บรรทัด {i})"
                        + (" — มาจาก template ไม่บังคับ" if from_template
                           else " — ไฟล์ประกาศที่มาไว้ที่ Documentation แล้ว" if file_sourced else ""),
                        rel)
                else:
                    for ref in re.findall(r"[\w./\\-]+\.\w+:\d+", line.split("# source:")[1]):
                        ok, detail = evidence_exists(ref, roots, suite, module)
                        if ok is False:
                            rep.fail("locator", f"source ชี้ของที่ไม่มีจริง: {ref} — {detail}", rel)

    # 9) users.json ต้องไม่ถูก track + ต้องมี .example
    if (suite / "resources" / "variables" / "test_data" / "users.json").exists():
        ignored = any("users.json" in g.read_text(encoding="utf-8", errors="ignore")
                      for g in (root / ".gitignore", suite / ".gitignore") if g.exists())
        if not ignored:
            rep.fail("secret", "มี users.json จริงแต่ไม่เจอใน .gitignore (ทั้งของราก repo และของ suite)")
    tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--", "*users.json"],
                             capture_output=True, text=True).stdout.strip()
    if tracked:
        rep.fail("secret", f"users.json ถูก git track อยู่: {tracked}")

    # 10) เทียบกับไฟล์เทสเคสต้นทาง — เคสหายไปกี่เคส
    if tc_file and tc_file.is_file():
        want = set(re.findall(r"TC-[A-Z0-9]+-\d+[a-z]?", tc_file.read_text(encoding="utf-8")))
        missing = sorted(want - set(seen_ids))
        extra = sorted(set(seen_ids) - want)
        if missing:
            rep.warn("coverage", f"ยังไม่ได้เขียน {len(missing)} เคสจากไฟล์เทสเคส: "
                                 + ", ".join(missing[:12]) + ("…" if len(missing) > 12 else ""))
        if extra:
            rep.warn("coverage", f"มีเทสที่ไม่อยู่ในไฟล์เทสเคสต้นทาง: {', '.join(extra[:12])}")
        rep.info("coverage", f"เขียนแล้ว {len(seen_ids)}/{len(want)} เคส")
    elif tc_file:
        rep.warn("coverage", f"เปิดไฟล์เทสเคสไม่ได้: {tc_file}")

    rep.info("evidence", f"ตรวจ Evidence/source ที่ชี้ file:line แล้ว {ev_checked} จุด")
    return emit(rep, as_json, suite)


def emit(rep, as_json, suite):
    fails = [i for i in rep.items if i["level"] == "FAIL"]
    warns = [i for i in rep.items if i["level"] == "WARN"]
    if as_json:
        print(json.dumps({"suite": str(suite) if suite else None,
                          "passed": not fails, "items": rep.items},
                         ensure_ascii=False, indent=2))
    else:
        for i in rep.items:
            icon = {"FAIL": "❌", "WARN": "⚠️ ", "INFO": "ℹ️ "}[i["level"]]
            print(f"{icon} [{i['check']}] {i['msg']}" + (f"\n      → {i['where']}" if i["where"] else ""))
        print(f"\n{'❌ ไม่ผ่าน' if fails else '✅ ผ่าน (static)'} — "
              f"blocking {len(fails)} · warning {len(warns)}")
        print("หมายเหตุ: นี่คือขั้นที่ 0 ของบันไดความเชื่อมั่น — ยังไม่ได้พิสูจน์กับระบบจริง "
              "(ดู references/robot-conventions.md §7)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
