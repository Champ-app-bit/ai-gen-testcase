#!/usr/bin/env python3
"""batch_state.py — สมุดคุมงานของ /gen-batch (แหล่งความจริงเดียว = modules.yaml)

ใช้:
  python3 scripts/batch_state.py next   <project> [--limit N] [--json]
  python3 scripts/batch_state.py set    <project> <module> [--status S] [--stage T]
                                        [--note "..."] [--artifact key=path] [--blocked "เหตุผล"]
  python3 scripts/batch_state.py report <project>

ทำไมต้องมีสคริปต์นี้: ให้ orchestrator อัปเดตสถานะแบบ atomic ไม่ต้องแก้ YAML ด้วยมือ
(แก้มือทีละรอบ = พัง/เปลืองโทเคน) และเพื่อให้ "ทำถึงไหนแล้ว" อยู่ในไฟล์ ไม่ใช่ในบทสนทนา
→ โดน quota ตัดกลางทางแล้วสั่งใหม่ ก็ไปต่อจากเดิมได้

stage: pending → spec → testcases → automation → verify → done
status: pending | in_progress | done | blocked | skipped | gone
"""
import argparse, json, sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("ต้องมี pyyaml ก่อน: pip install pyyaml")

TOOL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL_DIR / "scripts"))
from scan_modules import load_cfg, automation_root      # noqa: E402

RISK_ORDER = {"high": 0, "medium": 1, "low": 2, "skip": 9}
STAGES = ["pending", "spec", "testcases", "automation", "verify", "done"]


def registry_path(project):
    cfg = load_cfg(project)
    bdir = Path(cfg.get("batch", {}).get("dir") or (automation_root(cfg) / "docs" / "batch"))
    p = bdir / "modules.yaml"
    if not p.exists():
        sys.exit(f"ยังไม่มีทะเบียน module ที่ {p} — รัน /module-scout {project} ก่อน")
    return p


def load(project):
    p = registry_path(project)
    return p, yaml.safe_load(p.read_text(encoding="utf-8"))


def save(p, doc):
    p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120),
                 encoding="utf-8")


def cmd_next(args):
    _, doc = load(args.project)
    mods = doc["modules"]
    done = {m["name"] for m in mods if m.get("status") == "done"}
    ready, waiting = [], []
    for m in mods:
        if m.get("status") in ("done", "skipped", "gone", "blocked") or m.get("risk") == "skip":
            continue
        dep = [d for d in (m.get("depends_on") or []) if d not in done]
        (waiting if dep else ready).append((m, dep))
    # งานที่ค้างกลางคัน (in_progress) ต้องมาก่อนงานใหม่เสมอ — ไม่งั้น batch จะทิ้งของครึ่งๆ ไว้เต็มไปหมด
    ready.sort(key=lambda t: (t[0].get("status") != "in_progress",
                              RISK_ORDER.get(t[0].get("risk"), 5), -t[0].get("score", 0)))
    picked = [m for m, _ in ready[: args.limit]]
    if args.json:
        print(json.dumps(picked, ensure_ascii=False, indent=2))
        return
    if not picked:
        print("ไม่มี module ที่ทำต่อได้ — ดู `report` ว่าติดอะไรอยู่")
    for m in picked:
        print(f"{m['risk']:<6} {m['area']:<4} {m['name']:<26} stage={m.get('stage','pending'):<11} "
              f"files={m['files']:<3} {m.get('title') or m['why'][:50]}")
    if waiting:
        print(f"\nรออยู่ {len(waiting)} ตัว (ติด depends_on): "
              + ", ".join(f"{m['name']}←{'+'.join(d)}" for m, d in waiting[:5]))


def cmd_set(args):
    p, doc = load(args.project)
    hit = [m for m in doc["modules"] if m["name"] == args.module]
    if not hit:
        sys.exit(f"ไม่มี module '{args.module}' ในทะเบียน (ชื่อต้องตรงกับ modules.yaml)")
    m = hit[0]
    if args.stage:
        if args.stage not in STAGES:
            sys.exit(f"stage ต้องเป็นหนึ่งใน {STAGES}")
        m["stage"] = args.stage
        if args.stage == "done" and not args.status:
            m["status"] = "done"
    if args.status:
        m["status"] = args.status
    if args.blocked:
        m["status"], m["blocked_reason"] = "blocked", args.blocked
    if args.note:
        m["note"] = args.note
    for a in args.artifact or []:
        k, _, v = a.partition("=")
        m.setdefault("artifacts", {})[k] = v
        # suite ต้องขึ้นไปอยู่ field ระดับบนด้วย เพราะ scan_modules/make_report อ่านจาก m["suite"]
        # ไม่ใช่จาก artifacts — ถ้าไม่ทำ suite ที่ generate ใหม่จะหายจากรายงานทั้งหมด
        # (เจอจริง: order เสร็จแล้วแต่รายงานมองไม่เห็น 2026-09-01)
        if k == "suite" and v:
            m["suite"] = v.split(",")[0].strip()
    if args.attempt:
        m["attempts"] = m.get("attempts", 0) + 1
    save(p, doc)
    print(f"✓ {m['name']}: status={m.get('status')} stage={m.get('stage','pending')}"
          + (f" blocked={m['blocked_reason']}" if m.get("blocked_reason") else ""))


def cmd_report(args):
    _, doc = load(args.project)
    mods = [m for m in doc["modules"] if m.get("risk") != "skip"]
    by = {}
    for m in mods:
        by.setdefault(m.get("status", "pending"), []).append(m)
    print(f"[{doc['project']}] สแกนล่าสุด {doc.get('scanned_at')} · "
          f"{len(mods)} module ที่อยู่ในแผน (ไม่นับ skip)")
    for st in ("done", "in_progress", "blocked", "pending"):
        if st in by:
            print(f"  {st:<12} {len(by[st]):>3}")
    for m in by.get("blocked", []):
        print(f"    ⛔ {m['name']}: {m.get('blocked_reason', '(ไม่ระบุเหตุผล)')}")
    tests = sum(m.get("tests") or 0 for m in mods)
    if tests:
        print(f"  เทสที่มีอยู่รวม {tests} ไฟล์")
    qs = [m["name"] for m in mods if m.get("questions")]
    if qs:
        print(f"  ❓ รอคนตอบคำถาม: {', '.join(qs)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next"); n.add_argument("project"); n.add_argument("--limit", type=int, default=1)
    n.add_argument("--json", action="store_true"); n.set_defaults(func=cmd_next)
    s = sub.add_parser("set"); s.add_argument("project"); s.add_argument("module")
    s.add_argument("--status"); s.add_argument("--stage"); s.add_argument("--note")
    s.add_argument("--blocked"); s.add_argument("--artifact", action="append")
    s.add_argument("--attempt", action="store_true"); s.set_defaults(func=cmd_set)
    r = sub.add_parser("report"); r.add_argument("project"); r.set_defaults(func=cmd_report)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
