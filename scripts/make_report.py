#!/usr/bin/env python3
"""make_report.py — รายงานผลเทสที่ "วิเคราะห์แล้ว" ของทั้ง project

ใช้:
  python3 scripts/make_report.py <project> [--out PATH] [--json PATH] [--top N]

ทำอะไร: รวบผลรันจริงล่าสุดของทุก suite (results/*/output.xml) + ทะเบียน module +
findings + คำถามค้าง แล้ว **จัดกลุ่มความล้มเหลวตามสาเหตุราก** ไม่ใช่รายงานเป็นจำนวนเทสแดง

ทำไมต้องจัดกลุ่ม: เทสแดง 21 เคสมักมาจากสาเหตุเดียว (session หลุด / locator เก่า)
รายงานที่นับหัวเทสทำให้ dev เห็นภูเขา แล้วเลิกอ่าน — รายงานที่นับสาเหตุทำให้เห็นว่ามีงาน 4 ชิ้น

การจัดประเภท (bucket) ตัดสินจากข้อความ error → ใครต้องรับไปทำต่อ:
  env      — environment/session/login พัง  → เจ้าของ env
  locator  — หน้าจอเปลี่ยน ตัวชี้ element เก่า → คนดูแลเทส
  testbug  — สคริปต์เทสเขียนผิดเอง           → คนดูแลเทส (ของเราผิด ไม่ใช่ product)
  product  — assertion ไม่ตรงคาด             → dev (ผู้ต้องสงสัยว่าเป็นบั๊กจริง)
"""
import argparse, json, re, sys
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

try:
    import yaml
except ImportError:
    sys.exit("ต้องมี pyyaml ก่อน: pip install pyyaml")

TOOL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL_DIR / "scripts"))
from scan_modules import load_cfg, automation_root          # noqa: E402

# ── การจัดประเภท: เรียงตามลำดับ ตัวแรกที่ match ชนะ ────────────────────────
BUCKETS = [
    # เทสเขียนผิดเอง — ต้องเช็กก่อน env เพราะ error พวกนี้พ่วง "(Session info: ...)" มาด้วยทุกครั้ง
    ("testbug", re.compile(
        r"invalid index|used with invalid|invalid selector|No keyword with name|"
        r"Non-existing setting|Invalid syntax|Resolving variable|Variable .* not found|"
        r"jQuery not on the page|JavascriptException|Setting variable .* failed|"
        r"Keyword name cannot be empty", re.I)),
    ("env", re.compile(
        r"session id|sessionStorage|login|dashboard|empty form|connection refused|net::ERR|"
        r"WebDriverException|SessionNotCreated|no such window|browser.*not.*(start|open)|"
        r"suite setup failed|Timeout.*(connect|url)|ไม่โหลดข้อมูล|ฟอร์มว่าง", re.I)),
    ("locator", re.compile(
        r"locator .* not found|Element .* not (found|visible|enabled)|"
        r"ElementNotInteractable|StaleElementReference|Page should have contained|"
        r"did not appear|element click intercepted", re.I)),
]
STALE_DAYS = 7          # ผลรันเก่ากว่านี้ ห้ามอ่านเป็นสถานะวันนี้
BUCKET_TH = {
    "env":     ("ENV/SESSION", "เจ้าของ environment", "ระบบทดสอบหรือ session หลุด — เทสยังไม่ได้พิสูจน์อะไรเลย"),
    "locator": ("LOCATOR เก่า", "คนดูแลเทส",          "หน้าจอเปลี่ยน ตัวชี้ element ไม่ตรงของจริงแล้ว"),
    "testbug": ("สคริปต์เทสผิด", "คนดูแลเทส",          "เทสเขียนผิดเอง ไม่เกี่ยวกับ product"),
    "product": ("ต้องสงสัยเป็นบั๊ก", "dev",             "assert ไม่ตรงคาด — ของที่ dev ต้องดูก่อนใคร"),
}


NOISE = re.compile(r"\s*\(Session info:.*?\)|\s*Stacktrace:[\s\S]*$|\s*#\d+ 0x[0-9a-f]+.*$",
                   re.I | re.M)


def clean(msg: str) -> str:
    """ตัดส่วนที่ selenium ต่อท้ายทุก error ออก — ไม่ตัด จะจัดประเภทผิดและอ่านไม่รู้เรื่อง"""
    s = NOISE.sub("", msg or "").strip()
    return re.sub(r"\s*\n\s*", " | ", s).strip(" |")


def bucket_of(msg: str) -> str:
    for name, rx in BUCKETS:
        if rx.search(msg or ""):
            return name
    return "product"


def fingerprint(msg: str) -> str:
    """ยุบข้อความให้เหลือแกน เพื่อจับว่าเทสหลายตัวพังด้วยสาเหตุเดียวกัน"""
    s = (msg or "").strip().split("\n")[0]
    s = re.sub(r"QA-AUTO-[A-Z0-9\-]+", "<ID>", s)
    s = re.sub(r"\b\d{4,}\b", "<N>", s)
    s = re.sub(r"\b\d+\b", "<n>", s)
    s = re.sub(r"'[^']{0,120}'", "'<X>'", s)
    s = re.sub(r"chrome=[\d.]+", "chrome=<v>", s)
    s = re.sub(r"\s+", " ", s)
    return s[:180]


def parse_run(path: Path):
    """อ่าน output.xml → (generated, [test dict]) · คืน None ถ้าอ่านไม่ได้"""
    try:
        root = ET.parse(path).getroot()
    except Exception as e:
        return None, f"อ่านไม่ได้: {e}"
    gen = root.get("generated") or ""
    tests, elapsed = [], 0.0
    for t in root.iter("test"):
        st = t.find("status")
        if st is None:
            continue
        try:
            elapsed += float(st.get("elapsed") or 0)
        except (TypeError, ValueError):
            pass
        tests.append({
            "name": t.get("name") or "",
            "status": st.get("status") or "",
            "msg": (st.text or "").strip(),
        })
    return {"generated": gen, "tests": tests, "path": path, "elapsed": elapsed}, None


# dry-run ตัวจริงใช้เวลาหลักมิลลิวินาทีต่อเคส เพราะไม่เปิด browser ไม่ยิง HTTP
# รันจริงระดับ UI ~4-13 วิ/เคส · ระดับ API ยังต้อง >0.05 วิ เพราะมี network
# ต้องดูจากเนื้อหา ไม่ใช่ชื่อโฟลเดอร์ — เจอจริง: erp_order_robot/results/output.xml
# เป็น dry-run 88 เคส/2.45 วิ แต่ path ไม่มีคำว่า dryrun ตัวกรองเดิมจึงนับเป็นรันจริง
DRYRUN_SEC_PER_TEST = 0.05


def is_aborted(run):
    """รอบที่ล้มก่อนเริ่มทดสอบจริง — ไม่ผ่านเลยแม้แต่เคสเดียว และเร็วผิดปกติ
    (เช่น credential ผิด → ตายที่ Suite Setup ทุกเคส) รอบแบบนี้ไม่ได้พิสูจน์อะไร
    จึงห้ามใช้เป็นรอบก่อนสำหรับเทียบ ไม่งั้นจะได้ตัวเลข 'ดีขึ้น -36' ที่หลอกตัวเอง
    (เจอจริง: auto-20260901-1934 ของ delivery — 0 pass / 41 fail / 0.01 วิ/เคส)"""
    n = len(run.get("tests") or [])
    if not n:
        return True
    t = tally(run["tests"])
    return t["PASS"] == 0 and (run.get("elapsed", 0.0) / n) < 0.5


def is_dryrun(run):
    n = len(run.get("tests") or [])
    if not n:
        return False
    t = tally(run["tests"])
    if t["FAIL"] or t["SKIP"]:
        return False
    return (run.get("elapsed", 0.0) / n) < DRYRUN_SEC_PER_TEST


def run_dirs(suite_dir: Path):
    """ทุกโฟลเดอร์ผลรันของ suite นี้ เรียงใหม่→เก่า · แยก dry-run ออกด้วยเนื้อหา"""
    real, dry, aborted = [], [], []
    for x in sorted(suite_dir.glob("results/**/output.xml")):
        r, err = parse_run(x)
        if err or r is None:
            continue
        if "dryrun" in str(x).lower() or is_dryrun(r):
            dry.append((r.get("generated") or "", x))
        elif is_aborted(r):
            aborted.append((r.get("generated") or "", x))
        else:
            real.append((r.get("generated") or "", x))
    real.sort(reverse=True); dry.sort(reverse=True)
    return [x for _, x in real], [x for _, x in dry]


def tally(tests):
    c = {"PASS": 0, "FAIL": 0, "SKIP": 0, "NOT RUN": 0}
    for t in tests:
        c[t["status"]] = c.get(t["status"], 0) + 1
    return c


def analyse(project, top):
    cfg = load_cfg(project)
    aroot = automation_root(cfg)
    bdir = Path(cfg.get("batch", {}).get("dir") or (aroot / "docs" / "batch"))
    reg_path = bdir / "modules.yaml"
    if not reg_path.exists():
        sys.exit(f"ยังไม่มีทะเบียน module ที่ {reg_path} — รัน /module-scout {project} ก่อน")
    reg = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {}
    modules = reg.get("modules", [])

    suites, causes = [], {}
    for m in modules:
        suite = m.get("suite")
        if not suite:
            continue
        sdir = aroot / suite
        if not sdir.is_dir():
            suites.append({"module": m["name"], "suite": suite, "state": "ไม่พบโฟลเดอร์ suite"})
            continue
        real, dry = run_dirs(sdir)
        if not real:
            dn = 0
            if dry:
                dr, _e = parse_run(dry[0])
                dn = len((dr or {}).get("tests") or [])
            suites.append({"module": m["name"], "suite": suite,
                           "state": "ยังไม่เคยรันจริง" + (f" (dry-run ผ่าน {dn} เคส — ยังไม่พิสูจน์อะไร)" if dry else ""),
                           "robot_files": len(list(sdir.glob("**/*.robot")))})
            continue
        cur, err = parse_run(real[0])
        if err:
            suites.append({"module": m["name"], "suite": suite, "state": err})
            continue
        prev, _ = parse_run(real[1]) if len(real) > 1 else (None, None)
        t = tally(cur["tests"])
        age = None
        try:
            age = (datetime.now() - datetime.strptime(cur["generated"][:10], "%Y-%m-%d")).days
        except Exception:
            pass
        row = {
            "module": m["name"], "suite": suite, "state": "รันจริงแล้ว",
            "run": real[0].parent.name, "when": cur["generated"][:16].replace("T", " "),
            "runs_kept": len(real), "age_days": age, **t,
        }
        if prev:
            pt = tally(prev["tests"])
            row["prev"] = {"when": prev["generated"][:10], "run": real[1].parent.name, **pt}
            row["delta_fail"] = t["FAIL"] - pt["FAIL"]
        suites.append(row)

        for tc in cur["tests"]:
            if tc["status"] != "FAIL":
                continue
            cmsg = clean(tc["msg"])
            key = (bucket_of(cmsg), fingerprint(cmsg))
            c = causes.setdefault(key, {"bucket": key[0], "msg": cmsg[:220],
                                        "tests": [], "suites": set()})
            c["tests"].append(f"{m['name']} · {tc['name']}")
            c["suites"].add(suite)

    ranked = sorted(causes.values(), key=lambda c: (-len(c["tests"]), c["bucket"]))
    order = {"product": 0, "env": 1, "locator": 2, "testbug": 3}
    ranked.sort(key=lambda c: (order[c["bucket"]], -len(c["tests"])))

    findings = (bdir / "findings.md")
    qdir = bdir / "questions"
    questions = sorted(qdir.glob("*.md")) if qdir.is_dir() else []

    planned = [m for m in modules if m.get("risk") != "skip"]
    return {
        "project": project, "scanned_at": reg.get("scanned_at"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "batch_dir": str(bdir), "automation_root": str(aroot),
        "modules": {"planned": len(planned), "skip": len(modules) - len(planned),
                    "done": sum(1 for m in planned if m.get("status") == "done"),
                    "in_progress": sum(1 for m in planned if m.get("status") == "in_progress"),
                    "blocked": sum(1 for m in planned if m.get("status") == "blocked"),
                    "pending": sum(1 for m in planned if m.get("status") == "pending")},
        "suites": suites, "causes": (ranked[:top] if top else ranked), "cause_total": len(ranked),
        "findings": str(findings) if findings.exists() else None,
        "questions": [str(q) for q in questions],
    }


def md(d, top):
    S = [s for s in d["suites"] if s["state"] == "รันจริงแล้ว"]
    never = [s for s in d["suites"] if s["state"].startswith("ยังไม่เคยรัน")]
    P = sum(s["PASS"] for s in S); F = sum(s["FAIL"] for s in S); K = sum(s["SKIP"] for s in S)
    m = d["modules"]
    by = {}
    for c in d["causes"]:
        by[c["bucket"]] = by.get(c["bucket"], 0) + 1
    L = []
    A = L.append
    A(f"# รายงานผลเทส — {d['project']}\n")
    A(f"> สร้าง {d['generated_at']} · ทะเบียน module สแกน {d['scanned_at']} · "
      f"วิเคราะห์จากผลรันจริงล่าสุดของแต่ละ suite\n")

    A("## บรรทัดเดียว\n")
    if S:
        A(f"เทสรันจริง **{P+F+K} เคส** ใน {len(S)} suite → ผ่าน **{P}** · แดง **{F}** · ข้าม {K}  ")
        A(f"เทสแดง {F} เคสยุบเหลือ **{d['cause_total']} สาเหตุราก** "
          f"({', '.join(f'{BUCKET_TH[b][0]} {n}' for b, n in by.items())})  ")
        A(f"งานที่ต้องมีคนทำจริงคือ {d['cause_total']} ชิ้น ไม่ใช่ {F} ชิ้น\n")
        big = max(d["causes"], key=lambda c: len(c["tests"])) if d["causes"] else None
        if big and len(big["tests"]) > 1:
            A(f"สาเหตุเดียวที่กระทบมากสุด — **{len(big['tests'])} เคส** จาก "
              f"{BUCKET_TH[big['bucket']][0]}: `{big['msg'][:110]}`  ")
            A(f"→ เจ้าภาพ: {BUCKET_TH[big['bucket']][1]} · แก้จุดนี้จุดเดียว "
              f"เทสแดงหายไป {len(big['tests'])*100//max(F,1)}%\n")
        stale = [s for s in S if (s.get("age_days") or 0) > STALE_DAYS]
        if stale:
            A(f"⚠ {len(stale)} จาก {len(S)} suite มีผลรันเก่ากว่า {STALE_DAYS} วัน "
              f"({', '.join(s['module'] for s in stale)}) — ตัวเลขของ suite เหล่านี้ "
              f"บอกสถานะของวันที่รัน ไม่ใช่วันนี้\n")
    else:
        A("ยังไม่มี suite ไหนถูกรันจริง — ตัวเลขทั้งหมดในรายงานนี้จะว่าง จนกว่าจะรันกับ env จริง\n")

    A("## ความคืบหน้าทั้ง project\n")
    A(f"| module ในแผน | ทำเสร็จ | กำลังทำ | ติดปัญหา | ยังไม่เริ่ม | ถูกตัดออก (read-only) |")
    A("|---|---|---|---|---|---|")
    A(f"| {m['planned']} | {m['done']} | {m['in_progress']} | {m['blocked']} | {m['pending']} | {m['skip']} |\n")

    A("## ผลรันต่อ suite\n")
    A("| module | suite | รอบล่าสุด | ผ่าน | แดง | ข้าม | เทียบรอบก่อน |")
    A("|---|---|---|---:|---:|---:|---|")
    for s in S:
        if "prev" in s:
            dl = s["delta_fail"]
            trend = ("แดงเท่าเดิม" if dl == 0 else f"แดง {'+' if dl>0 else ''}{dl} จาก {s['prev']['when']}")
        else:
            trend = "ไม่มีรอบก่อนให้เทียบ"
        age = s.get("age_days")
        if age is not None and age > STALE_DAYS:
            trend += f" · ⚠ ผลเก่า {age} วัน"
        A(f"| {s['module']} | `{s['suite']}` | {s['run']} ({s['when']}) | {s['PASS']} | "
          f"**{s['FAIL']}** | {s['SKIP']} | {trend} |")
    for s in never:
        A(f"| {s['module']} | `{s['suite']}` | — | — | — | — | **{s['state']}** "
          f"({s.get('robot_files','?')} ไฟล์ .robot รอ env) |")
    A("")

    A(f"## สาเหตุราก เรียงตามคนที่ต้องรับไปทำ (แสดง {len(d['causes'])} จาก {d['cause_total']})\n")
    A("เรียง dev ขึ้นก่อน เพราะเป็นของเดียวในรายงานนี้ที่อาจเป็นบั๊กของ product จริง\n")
    cur_b = None
    for c in d["causes"]:
        if c["bucket"] != cur_b:
            cur_b = c["bucket"]
            lab, owner, why = BUCKET_TH[cur_b]
            A(f"\n### {lab} → {owner}\n")
            A(f"*{why}*\n")
        n = len(c["tests"])
        A(f"- **กระทบ {n} เคส** · {', '.join(sorted(c['suites']))}  ")
        A(f"  `{c['msg']}`  ")
        A(f"  ตัวอย่าง: {c['tests'][0]}" + (f" (+{n-1} เคส)" if n > 1 else ""))
    A("")

    A("## ของที่ต้องตัดสินใจ\n")
    A(f"- บั๊กที่ระบบเจอระหว่างอ่านโค้ด: {d['findings'] or '— ยังไม่มีไฟล์ findings (ยังไม่เคยรัน batch โหมดไม่มีคนเฝ้า)'}")
    A(f"- คำถามค้างรอคนตอบ: {len(d['questions'])} ไฟล์"
      + (f" — {', '.join(Path(q).stem for q in d['questions'])}" if d["questions"] else " (ไม่มี)"))
    A(f"- module ที่ยังไม่เริ่ม: {m['pending']} ตัว — สั่งต่อด้วย `/testgen {d['project']}`\n")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--out", help="ไฟล์ .md ที่จะเขียน (ดีฟอลต์: <batch.dir>/report.md)")
    ap.add_argument("--json", dest="js", help="เขียนข้อมูลดิบเป็น JSON ด้วย")
    ap.add_argument("--top", type=int, default=0, help="แสดงสาเหตุรากกี่ข้อ (0 = ทั้งหมด)")
    ap.add_argument("--stdout", action="store_true", help="พิมพ์ออกจอ ไม่เขียนไฟล์")
    a = ap.parse_args()

    d = analyse(a.project, a.top)
    text = md(d, a.top)
    if a.stdout:
        print(text)
    else:
        out = Path(a.out) if a.out else Path(d["batch_dir"]) / "report.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"เขียนรายงานแล้ว: {out}")
    if a.js:
        raw = json.loads(json.dumps(d, default=lambda o: sorted(o) if isinstance(o, set) else str(o)))
        Path(a.js).write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"เขียน JSON แล้ว: {a.js}")


if __name__ == "__main__":
    main()
