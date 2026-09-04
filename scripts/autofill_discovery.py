#!/usr/bin/env python3
"""autofill_discovery.py — เติม discovery.modules ให้ project ที่ bootstrap เดา layout ไม่ออก

ใช้: python3 scripts/autofill_discovery.py <project> [--force]

exit 0 = เติมให้แล้ว (มี candidate ที่ชนะชัดเจนตัวเดียว) · exit 1 = ต้องให้คนตัดสิน
เหตุผลที่ต้องมี: autopilot ที่ปล่อยทิ้งไว้ข้ามวัน ไม่ควรตายเพราะ config ขาดบรรทัดเดียว
แต่ถ้ามีหลาย layout ที่เข้าเค้าเท่ากัน การเดาผิดจะถูก clone ไปทุก module → ต้องหยุดถามคน
"""
import argparse, glob as globlib, sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("ต้องมี pyyaml ก่อน: pip install pyyaml")

TOOL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL_DIR / "scripts"))
from scan_modules import load_cfg                                  # noqa: E402

# glob → ฝั่งไหน (fe/be) · ใช้ schema เดียวกับที่ bootstrap_project.py เขียน
CANDIDATES = [("src/apps/*", "fe"), ("src/modules/*", "fe"), ("src/features/*", "fe"),
              ("src/pages/*", "fe"), ("src/views/*", "fe"), ("src/app/*", "fe"),
              ("app/*", "be"), ("apps/*", "be"), ("modules/*", "be"), ("packages/*", "be")]
# โฟลเดอร์ที่เจอทุก repo แต่ไม่ใช่ฟีเจอร์ — ไม่นับเป็นหลักฐานว่า glob นี้ถูก
NOISE = {"shared", "common", "components", "utils", "lib", "hooks", "types",
         "styles", "assets", "config", "constants", "helpers", "core", "public"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--force", action="store_true", help="เขียนทับ discovery.modules ที่มีอยู่")
    a = ap.parse_args()

    base = TOOL_DIR / "projects" / f"{a.project}.yaml"
    cfg = load_cfg(a.project)
    disc = cfg.get("discovery") or {}
    if disc.get("modules") and not a.force:
        print("discovery.modules มีอยู่แล้ว — ไม่แตะ")
        return 0

    roots = [Path(p) for p in cfg.get("sources", {}).get("code", [])]
    hits = []
    for r in roots:
        if not r.is_dir():
            continue
        for cand, side in CANDIDATES:
            dirs = [Path(x).name for x in globlib.glob(str(r / cand)) if Path(x).is_dir()]
            real = [d for d in dirs if d.lower() not in NOISE and not d.startswith((".", "_"))]
            if real:
                hits.append({"root_match": r.name, "glob": cand, "side": side,
                             "n": len(real), "sample": sorted(real)[:4]})

    if not hits:
        print(f"หา layout ไม่เจอเลยใน {', '.join(str(r) for r in roots)}", file=sys.stderr)
        print("ต้องเติม discovery.modules เองใน " + str(base), file=sys.stderr)
        return 1

    hits.sort(key=lambda h: -h["n"])
    top = [h for h in hits if h["n"] == hits[0]["n"]]
    if len(top) > 1:
        print("มีหลาย layout ที่เข้าเค้าเท่ากัน — ต้องให้คนเลือก:", file=sys.stderr)
        for h in top:
            print(f"  - root_match: {h['root_match']} · glob: {h['glob']} "
                  f"({h['n']} โฟลเดอร์: {', '.join(h['sample'])})", file=sys.stderr)
        return 1

    win = hits[0]
    doc = yaml.safe_load(base.read_text(encoding="utf-8")) or {}
    doc.setdefault("discovery", {})["modules"] = [
        {"side": win["side"], "root_match": win["root_match"], "glob": win["glob"],
         "name_from": "dirname"}]
    # 1 ฝั่ง = จับคู่ fe/be ไม่ได้ → pair_by ต้องเป็น manual ไม่งั้น scan จะหาคู่ที่ไม่มีอยู่
    doc["discovery"]["pair_by"] = "manual"
    base.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120),
                    encoding="utf-8")
    print(f"เติมให้แล้ว: [{win['side']}] root_match={win['root_match']} glob={win['glob']} "
          f"({win['n']} โฟลเดอร์ เช่น {', '.join(win['sample'])})")
    print(f"→ {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
