#!/usr/bin/env python3
"""scan_modules.py — ส่วน "นับ" ของ /module-scout (deterministic, ไม่ใช้ LLM)

อ่าน projects/<project>.yaml + .local.yaml → enumerate module ตาม discovery block
→ นับไฟล์/บรรทัด/endpoint/สัญญาณความเสี่ยง → ให้คะแนน + ตั้ง AREA code
→ merge เข้า <batch.dir>/modules.yaml (ไม่ทับ status/area/suite/note ที่มีอยู่) + เขียน modules.md

ใช้: python3 scripts/scan_modules.py <project> [--dry-run]

agent (/module-scout) รันไฟล์นี้ก่อน แล้วค่อยเติม "วิจารณญาณ" ทับ:
ชื่อ module ที่โกหก, wip/mock, การแตก sub-module, เหตุผล skip ที่ลึกกว่าคะแนน
"""
import math, os, re, sys, glob as globlib, subprocess
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("ต้องมี pyyaml ก่อน: pip install pyyaml")

TOOL_DIR = Path(__file__).resolve().parent.parent

# ── สัญญาณความเสี่ยง (ตรงกับ references/module-discovery.md §5) ──────────────
# น้ำหนักคูณกับ "ความหนาแน่น" (hit ต่อ 1000 บรรทัด) ไม่ใช่จำนวนดิบ —
# ไม่งั้น module ใหญ่ชนะทุกครั้งเพราะมีบรรทัดเยอะ ไม่ใช่เพราะเสี่ยงกว่า
SIGNALS = {
    "money":       (r"price|amount|total|qty|quantity|stock|balance|discount|refund|cost", 3),
    "state":       (r"\bstatus\b|\bstate\b|approve|reject|cancel|confirm|workflow", 3),
    "destructive": (r"delete|remove|void|write.?off|adjust|revert", 2),
    "permission":  (r"guard|permission|\brole\b|policy|@Roles|isAdmin|can\(", 1),
    "external":    (r"webhook|gateway|\bline\b|payment|s3|sheet|smtp|mail|sms", 1),
}
# จับ HTTP verb ให้ครอบคลุมหลาย stack — รวม wrapper ที่ทีมเขียนเอง
# (เคสจริง: ERP FE เรียกผ่าน HttpServices.putData() → pattern `\.put\(` เดิมจับไม่ได้
#  ทำให้ order_v3 module ใหญ่สุดถูกตี read-only) → ใช้ `\.<verb>[A-Za-z]*\(` ครอบไว้
VERB_PAT = {
    # `(?:<[^>()]*>)?` = เผื่อ TypeScript generic คั่น เช่น api.post<SignInResponse>(...)
    v: (rf"@{v.capitalize()}\(|\.{v}[A-Za-z]*(?:<[^>()]*>)?\s*\(|Route::{v}\(|router\.{v}\b"
        rf"|['\"]{v.upper()}['\"]|method\s*:\s*['\"]{v}")
    for v in ("get", "post", "put", "patch", "delete")
}
WIP_PAT = r"\bTODO\b|\bFIXME\b|mock(Data|_data)?\s*=|hardcode|ยังไม่|dummy"


def load_cfg(project):
    base = TOOL_DIR / "projects" / f"{project}.yaml"
    loc  = TOOL_DIR / "projects" / f"{project}.local.yaml"
    if not base.exists():
        sys.exit(f"ไม่พบ {base}")
    if not loc.exists():
        sys.exit(f"ไม่พบ {loc} — ยังไม่ได้ setup เครื่องนี้ ให้รัน /setup {project} ก่อน")
    cfg = yaml.safe_load(base.read_text(encoding="utf-8")) or {}
    lcl = yaml.safe_load(loc.read_text(encoding="utf-8")) or {}

    def merge(a, b):
        for k, v in b.items():
            a[k] = merge(a.get(k, {}), v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
        return a
    return merge(cfg, lcl)


def automation_root(cfg):
    p = Path(cfg.get("automation", {}).get("path", "."))
    if cfg.get("automation", {}).get("layout") == "multi-suite":
        return p
    return p.parent if p.name == "tests" else p


def norm(name, entry):
    n = name
    for k, f in (("strip_prefix", str.startswith), ("strip_suffix", str.endswith)):
        v = entry.get(k)
        if v and f(n, v):
            n = n[len(v):] if k == "strip_prefix" else n[: -len(v)]
    n = re.sub(r"(?<!^)(?=[A-Z])", "-", n)            # CamelCase → kebab
    return re.sub(r"[_\s]+", "-", n).strip("-").lower()


def enumerate_modules(cfg, project="<project>"):
    disc = cfg.get("discovery")
    if not disc:
        sys.exit("config ยังไม่มี discovery block — ให้ /module-scout เดา+ยืนยันกับผู้ใช้ก่อน")
    roots = [Path(p) for p in cfg.get("sources", {}).get("code", [])]
    missing = [str(r) for r in roots if not r.is_dir()]
    if missing:
        sys.exit("sources.code ชี้ path ที่ไม่มีจริง: " + ", ".join(missing))
    exclude = {str(x).lower() for x in disc.get("exclude", [])}
    # discovery.modules ว่าง = bootstrap เดา layout ของ repo นี้ไม่ออก (เจอบ่อยกับ repo ใหม่)
    # ต้องบอกให้ชัดว่าต้องเติมอะไร ไม่ใช่ traceback — autopilot อ่านข้อความนี้ไปโชว์ผู้ใช้ต่อ
    found = {}
    entries = disc.get("modules") or []
    if not entries:
        hint = ""
        for r in roots:
            for cand in ("src/apps/*", "src/modules/*", "src/pages/*", "src/views/*",
                         "app/*", "apps/*", "modules/*", "src/app/*"):
                n = len([x for x in globlib.glob(str(r / cand)) if Path(x).is_dir()])
                if n:
                    hint += f"\n      - root_match: {r.name}\n        glob: {cand}   # เจอ {n} โฟลเดอร์"
        sys.exit("discovery.modules ยังว่าง — bootstrap เดา layout ของ repo นี้ไม่ออก\n"
                 f"เติมใน projects/{project}.yaml ใต้ discovery: แล้วสั่งใหม่\n"
                 "    modules:" + (hint or "\n      - root_match: <ชื่อ repo>\n        glob: <path/ที่มีโฟลเดอร์ละ 1 ฟีเจอร์>/*"))
    for entry in entries:
        rm = entry.get("root_match", "")
        for root in [r for r in roots if rm.lower() in str(r).lower()]:
            for hit in sorted(globlib.glob(str(root / entry["glob"]))):
                h = Path(hit)
                # name_from: dirname = "1 module คือ 1 โฟลเดอร์" → ไฟล์ที่ glob จับติดมาไม่ใช่ module
                # (เคสจริง Next App Router: layout.tsx / page.tsx นอนอยู่ใน src/app/modules/ ด้วย)
                if entry.get("name_from", "dirname") == "dirname" and not h.is_dir():
                    continue
                raw = h.name
                if raw.lower() in exclude or raw.startswith((".", "_")):
                    continue
                key = norm(raw, entry)
                if not key or key in exclude:
                    continue
                rec = found.setdefault(key, {"name": key, "paths": []})
                item = {"side": entry["side"], "path": str(h), "root": str(root), "raw": raw}
                if entry.get("label_with_parent"):
                    m = re.search(r"([^/]+)/app/Http", str(h))
                    item["app"] = m.group(1) if m else None
                rec["paths"].append(item)
    return found


def scan_paths(items, cfg):
    """นับไฟล์/บรรทัด/verb/สัญญาณ จากไฟล์จริง (ข้าม ignore_dirs)"""
    ign = set(cfg.get("ignore_dirs", []))
    exts = set(cfg.get("include_ext", [])) or None
    files, lines, blob = 0, 0, []
    for it in items:
        p = Path(it["path"])
        cand = [p] if p.is_file() else [
            f for f in p.rglob("*")
            if f.is_file() and not (set(f.parts) & ign)
        ]
        for f in cand:
            if exts and f.suffix not in exts:
                continue
            files += 1
            try:
                t = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            lines += t.count("\n")
            blob.append(t)
    text = "\n".join(blob)
    verbs = {v: len(re.findall(pat, text, re.I)) for v, pat in VERB_PAT.items()}
    sigs  = {k: len(re.findall(pat, text, re.I)) for k, (pat, _) in SIGNALS.items()}
    wip   = len(re.findall(WIP_PAT, text, re.I))
    return files, lines, verbs, sigs, wip


def raw_score(verbs, sigs, lines):
    """คะแนนดิบ = ผลรวมความหนาแน่นถ่วงน้ำหนัก + โบนัส mutation · ยังไม่ตัดสินว่า high/low"""
    kloc = max(lines, 200) / 1000.0          # กันหารด้วยศูนย์ + กัน module จิ๋วคะแนนพุ่ง
    s, why = 0.0, []
    for k, (_, w) in SIGNALS.items():
        d = sigs[k] / kloc
        if d >= 1:
            s += w * min(d / 20.0, 1.5)      # เพดาน 1.5× กันตัวที่ท่วมจอกินรวบ
            why.append(f"{k} {sigs[k]}ครั้ง ({d:.0f}/kloc)")
    mut = verbs["post"] + verbs["put"] + verbs["patch"] + verbs["delete"]
    if mut:
        # ถ่วงด้วย "พื้นที่ผิวที่เขียนข้อมูลได้" — ความหนาแน่นอย่างเดียวทำให้ module จิ๋วที่พูดถึงเงินบ่อย
        # แซง module ใหญ่ที่ mutation เยอะจริง (เคสจริง: material-unit แซง purchase-order)
        s *= math.sqrt(1 + mut / 5)
        why.append(f"mutation {mut} จุด")
    elif verbs["get"]:
        s -= 3
        why.append("read-only (ไม่พบ mutation)")
    return round(s, 2), mut, why


def bucket(mods):
    """จัดอันดับ *เทียบกันเองในโปรเจกต์นี้* — ไม่ต้อง calibrate ค่าคงที่ต่อ stack

    บนสุด 25% = high, 35% ถัดมา = medium, ที่เหลือ = low
    override เด็ดขาด: ไม่มี mutation เลย (read-only) หรือไม่มีไฟล์ → skip
    """
    live = [m for m in mods if m["files"] > 0 and not m.get("proven_readonly")]
    live.sort(key=lambda m: -m["score"])
    n = len(live)
    for i, m in enumerate(live):
        r = "high" if i < n * 0.25 else "medium" if i < n * 0.60 else "low"
        # เพดานตามขนาด: ของชิ้นเล็กมีความหนาแน่นสูงง่าย (controller ไฟล์เดียว 80 บรรทัด
        # ที่พูดถึง price 10 ครั้ง) — ไม่พอจะเป็นงานลำดับแรกของโปรเจกต์
        if m["lines"] < 60:
            r = "low"
        elif m["lines"] < 150 and r == "high":
            r = "medium"
        m["risk"] = m["risk_auto"] = r
    for m in mods:
        if m["files"] == 0:
            m["risk"] = m["risk_auto"] = "skip"
            m["skip_reason"] = "ไม่พบไฟล์ที่ตรง include_ext"
        elif m.get("proven_readonly"):
            m["risk"] = m["risk_auto"] = "skip"
            m["skip_reason"] = "อ่านอย่างเดียว — เจอ GET แต่ไม่เจอ mutation เลย"
def area_candidates(name):
    w = [x for x in re.split(r"[-_\s]+", name) if x]
    cons = lambda s: [c for c in s if c not in "aeiou"]
    out = []
    if len(w) == 1:
        out += [w[0][:3], (w[0][0] + "".join(cons(w[0][1:]))[:2])]
    elif len(w) == 2:
        c0, c1 = cons(w[0][1:]), cons(w[1][1:])
        out += [w[0][0] + (c0[0] if c0 else w[0][1:2]) + w[1][0],
                w[0][0] + w[1][0] + (c1[0] if c1 else w[1][1:2]),
                w[0][:2] + w[1][0]]
    else:
        out += ["".join(x[0] for x in w[:3]), w[0][0] + w[1][0] + w[-1][0]]
    out += [name[:3], name.replace("-", "")[:3]]
    return [x.upper() for x in out if len(x) == 3]


def assign_area(name, taken):
    for c in area_candidates(name):
        if c not in taken:
            taken.add(c)
            return c
    for i in range(1, 100):                      # ทางหนีสุดท้าย
        c = (area_candidates(name)[0][:2] + str(i)).upper()
        if c not in taken:
            taken.add(c)
            return c
    raise RuntimeError("ตั้ง AREA ไม่ได้: " + name)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    project, dry = sys.argv[1], "--dry-run" in sys.argv
    cfg = load_cfg(project)
    root = automation_root(cfg)
    bdir = Path(cfg.get("batch", {}).get("dir") or (root / "docs" / "batch"))
    out = bdir / "modules.yaml"

    prev = {}
    if out.exists():
        old = yaml.safe_load(out.read_text(encoding="utf-8")) or {}
        prev = {m["name"]: m for m in old.get("modules", [])}

    areas = cfg.get("automation", {}).get("areas", {}) or {}
    known_area, known_suite = {}, {}
    taken = set()
    for mod, a in areas.items():
        if isinstance(a, dict):
            pref = str(a.get("prefix", "")).replace("TC-", "")
            d = a.get("dir", "")
        else:                                    # schema เก่า (string) — ยังอ่านได้
            pref, d = "", str(a)
        k = norm(mod, {})
        if pref:
            known_area[k] = pref
            taken.add(pref)
        if d:
            known_suite[k] = d.split("/")[0] if cfg.get("automation", {}).get("layout") == "multi-suite" else d
    for m in prev.values():
        if m.get("area"):
            taken.add(m["area"])
            known_area.setdefault(m["name"], m["area"])

    found = enumerate_modules(cfg, project)
    want_sides = {e["side"] for e in cfg["discovery"]["modules"]}
    pair_by = cfg["discovery"].get("pair_by", "name")
    specs = [Path(p) for p in (cfg.get("sources", {}).get("specs") or [])]
    cdir = cfg.get("behavior_spec", {}).get("confirmed_dir")
    if cdir:
        specs.append(Path(cdir))

    mods = []
    for name in sorted(found):
        items = found[name]["paths"]
        files, lines, verbs, sigs, wip = scan_paths(items, cfg)
        s, mut, why = raw_score(verbs, sigs, lines)
        # แยก "พิสูจน์ได้ว่า read-only" ออกจาก "จับ verb ไม่ได้เลย" — อย่างหลังคือ pattern ไม่รู้จัก
        # stack นี้ ห้ามตัดทิ้งเงียบๆ ต้องชูธงให้คนตรวจ
        proven_ro = mut == 0 and verbs["get"] > 0
        unclear = mut == 0 and verbs["get"] == 0
        rec = {
            "name": name,
            "area": known_area.get(name) or assign_area(name, taken),
            "risk": None, "score": s, "mut": mut, "proven_readonly": proven_ro,
            "why": ", ".join(why) or "ไม่พบสัญญาณความเสี่ยง",
            "files": files, "lines": lines,
            "endpoints": {k: v for k, v in verbs.items() if v},
            "suite": known_suite.get(name),
            "status": "pending",
        }
        # suite ที่ scaffold แล้วจริงบนดิสก์ → ถือว่า done เพื่อไม่ให้ /gen-batch ทำซ้ำ
        # (config อาจลิสต์ suite ที่ "วางแผนไว้" แต่ยังไม่มีโฟลเดอร์ — ต้องดูของจริง)
        if rec["suite"]:
            sdir = root / rec["suite"]
            n_robot = len(list(sdir.rglob("*.robot"))) if sdir.is_dir() else 0
            rec["tests"] = n_robot
            if n_robot:
                rec["status"] = "done"
        for it in items:
            side = it["side"] + (f":{it['app']}" if it.get("app") else "")
            rec.setdefault(side, []).append(os.path.relpath(it["path"], it["root"]))
        sides = {it["side"] for it in items}
        if len(want_sides) > 1 and len(sides) == 1:
            # เจอฝั่งเดียว — ถ้า pair_by: route แปลว่ายังไม่ได้เชื่อม FE↔BE (ต้องใช้วิจารณญาณ
            # ไล่ fetch()/axios → routes/api.php) ปล่อยให้ agent ทำต่อ ห้ามเดาจับคู่เอง
            rec["unpaired"] = list(sides)[0]
        hits = 0
        for sp in specs:
            if sp.is_dir():
                try:
                    hits += int(subprocess.run(
                        ["grep", "-ril", "--include=*.md", name, str(sp)],
                        capture_output=True, text=True).stdout.count("\n"))
                except OSError:
                    pass
        rec["spec_hits"] = hits
        if files > 25 or lines > 4000:
            rec["oversized"] = True
        # ใช้ความหนาแน่น ไม่ใช่จำนวนดิบ — เกณฑ์ 5 ครั้งทำให้เกือบทุก module ติดธง (ธงที่ติดทุกตัว = ไม่มีข้อมูล)
        if wip / max(lines, 200) * 1000 >= 5:
            rec["wip_signals"] = wip
        if unclear:
            rec["unclear_mutation"] = True      # จับ HTTP verb ไม่ได้เลย → คนต้องดูเอง
        if name in prev:                          # ── merge: ของเดิมชนะ ──
            for k in ("status", "area", "suite", "note", "owner", "sub_modules",
                      "depends_on", "title", "wip", "stage", "artifacts", "attempts",
                      "blocked_reason", "questions"):
                if prev[name].get(k) not in (None, "", "pending"):
                    rec[k] = prev[name][k]
            rec["_prev"] = prev[name]
        mods.append(rec)

    bucket(mods)                                  # จัดอันดับหลังสแกนครบทุกตัว
    for m in mods:
        # ── เคารพ risk ที่ "คนแก้เอง" ──
        # รู้ได้จากรอบก่อน: ถ้า risk != risk_auto แปลว่ามีคนเปลี่ยนด้วยมือ → ห้ามทับ
        pv = m.pop("_prev", None)
        if pv and pv.get("risk_auto") and pv.get("risk") != pv["risk_auto"]:
            m["risk"], m["risk_override"] = pv["risk"], True
            m["skip_reason"] = pv.get("skip_reason") if m["risk"] == "skip" else None
        if m["risk"] != "skip":
            m.pop("skip_reason", None)
        m.pop("mut", None); m.pop("proven_readonly", None)
        m.pop("_prev", None)
        if m.get("status") == "pending" and m["risk"] == "skip" and not m.get("skip_reason"):
            m["skip_reason"] = "คะแนนความเสี่ยงต่ำสุดของโปรเจกต์"

    gone = [m for n, m in prev.items() if n not in found]
    for g in gone:
        g["status"] = "gone"
        mods.append(g)

    today = subprocess.run(["date", "-I"], capture_output=True, text=True).stdout.strip()
    doc = {"project": project, "scanned_at": today,
           "discovery_from": f"projects/{project}.yaml#discovery", "modules": mods}

    counts = {r: sum(1 for m in mods if m.get("risk") == r) for r in ("high", "medium", "low", "skip")}
    unpaired = sum(1 for m in mods if m.get("unpaired"))
    if unpaired and pair_by != "name":
        print(f"   ⚠ {unpaired} รายการยังจับคู่ FE↔BE ไม่ได้ (pair_by: {pair_by}) — "
              f"agent ต้องไล่ route เชื่อมเอง ห้ามเดา")
    print(f"[{project}] เจอ {len(found)} module · "
          + " · ".join(f"{k} {v}" for k, v in counts.items())
          + (f" · gone {len(gone)}" if gone else ""))
    for m in sorted(mods, key=lambda x: -x.get("score", -99))[:12]:
        print(f"   {m.get('risk','?'):<6} {m['area']:<4} {m['name']:<28} "
              f"files={m['files']:<4} {m['why'][:60]}")
    if dry:
        print("(--dry-run: ไม่เขียนไฟล์)")
        return

    bdir.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120),
                   encoding="utf-8")

    md = [f"# ทะเบียน module — {project}", "",
          f"สแกน {today} · ทั้งหมด {len(found)} module · "
          + " · ".join(f"**{k}** {v}" for k, v in counts.items()), "",
          "| risk | AREA | module | ไฟล์ | endpoints | suite | status | เหตุผลของคะแนน |",
          "|---|---|---|---|---|---|---|---|"]
    order = {"high": 0, "medium": 1, "low": 2, "skip": 3}
    for m in sorted(mods, key=lambda x: (order.get(x.get("risk"), 9), -x.get("score", 0), x["name"])):
        ep = " ".join(f"{k}:{v}" for k, v in (m.get("endpoints") or {}).items())
        flags = " ".join(f"`{f}`" for f in ("oversized", "wip_signals", "unclear_mutation") if m.get(f))
        if m.get("unpaired"):
            flags += f" `{m['unpaired']}-only`"
        md.append(f"| {m.get('risk','?')} | {m['area']} | {m['name']} {flags} | {m['files']} | {ep} "
                  f"| {m.get('suite') or '—'} | {m.get('status')} | {m['why']} |")
    over = [m["name"] for m in mods if m.get("risk_override")]
    md += ["", "> คะแนนมาจาก `references/module-discovery.md` §5 — เป็นตัวช่วยจัดลำดับ ไม่ใช่คำตัดสิน",
           "> แก้ `risk`/`status`/`skip_reason` ใน `modules.yaml` ได้ตลอด สแกนรอบหน้าจะไม่ทับของที่แก้ไว้",
           ("> คนแก้ risk เองแล้ว (สคริปต์ไม่แตะ): " + ", ".join(over)) if over else ""]
    (bdir / "modules.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"→ {out}\n→ {bdir/'modules.md'}")


if __name__ == "__main__":
    main()
