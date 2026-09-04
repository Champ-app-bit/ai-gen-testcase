#!/usr/bin/env python3
"""bootstrap_project.py — สร้าง config ของ project ใหม่จาก "path repo" อย่างเดียว

ใช้: python3 scripts/bootstrap_project.py <ชื่อ project> --code <path> [--code <path>...]
                                          [--automation <path>] [--specs <path>...]
                                          [--out-dir <path>] [--dry-run]

ตรวจ stack ของแต่ละ repo เอง แล้วเขียน:
  projects/<name>.yaml        portable — include_ext / ignore_dirs / signal_dirs / discovery
  projects/<name>.local.yaml  path จริงบนเครื่องนี้

เป้าหมาย: **project ใหม่ต้องไม่มีใครนั่งเขียน YAML เอง** — คนแค่ชี้ว่า repo อยู่ไหน
glob ทุกอันที่เขียนลง discovery ถูกทดสอบกับดิสก์จริงแล้วว่า match กี่ตัว (ไม่เดา)
"""
import argparse, json, re, sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent.parent

BASE_IGNORE = ["node_modules", ".git", "dist", "build", "out", "coverage", "vendor",
               "__pycache__", ".cache", "public", "assets", "uploads", "storage",
               "migrations", ".turbo", ".vercel"]
BASE_IGNORE_GLOBS = ['"*.env*"', '"*.lock"', '"*.min.*"', '"*.map"', '"*.log"',
                     '"*.d.ts"', '"*.spec.*"', '"*.test.*"']

# stack → (ext, signal_dirs, ตัวเลือก glob ของ module, ignore เพิ่ม)
STACKS = {
    "nestjs":    ([".ts"], ["modules", "controllers", "services", "dto", "entities",
                            "guards", "decorator", "prisma", "schema"],
                  ["src/modules/*", "src/*/"], []),
    "strapi":    ([".ts", ".js", ".json"],
                  ["api", "controllers", "routes", "services", "content-types",
                   "middlewares", "policies", "components"],
                  ["src/api/*"], ["dist", ".strapi", "types", ".tmp"]),
    "next-app":  ([".ts", ".tsx", ".js", ".jsx"],
                  ["app", "components", "lib", "store", "hooks", "utils", "validation", "middleware"],
                  ["src/app/modules/*", "src/app/*", "app/*"], [".next"]),
    "next-pages":([".ts", ".tsx", ".js", ".jsx"],
                  ["pages", "components", "lib", "store", "hooks", "utils", "validation"],
                  ["src/pages/*", "pages/*"], [".next"]),
    "vue2":      ([".vue", ".js", ".ts"], ["apps", "views", "components", "store", "services", "router"],
                  ["src/apps/*", "src/views/*", "src/modules/*"], []),
    "vue3":      ([".vue", ".ts", ".js"], ["views", "modules", "components", "stores", "composables", "router"],
                  ["src/modules/*", "src/views/*"], []),
    "express":   ([".js", ".ts"], ["app", "modules", "routes", "controllers", "models", "middleware", "services"],
                  ["app/*", "src/modules/*", "routes/*"], []),
    "laravel":   ([".php"], ["Controllers", "Requests", "Models", "Services", "Rules",
                             "Policies", "Middleware", "routes"],
                  ["app/Http/Controllers/*Controller.php",
                   "*/app/Http/Controllers/*Controller.php", "Modules/*"], ["bootstrap"]),
    "django":    ([".py"], ["views", "models", "serializers", "forms", "urls"],
                  ["*/models.py"], []),
    "spring":    ([".java", ".kt"], ["controller", "service", "repository", "dto", "entity"],
                  ["src/main/java/**/controller/*.java"], []),
}
SIDE_HINT = {"nestjs": "be", "strapi": "be", "express": "be", "laravel": "be", "django": "be", "spring": "be",
             "next-app": "fe", "next-pages": "fe", "vue2": "fe", "vue3": "fe"}


def detect_stack(root: Path, _depth=0):
    """คืน (ชื่อ stack, หลักฐาน, เป็น monorepo ไหม) — ดูจาก marker file เท่านั้น ไม่เดาจากชื่อโฟลเดอร์

    ถ้าไม่เจอ marker ที่ราก ให้มองลูกชั้นเดียว — repo แบบ monorepo วาง marker ไว้ในแต่ละ app
    (เคสจริง: wre/backend มี web/ erp/ backoffice/ migrate_api/ แต่ละตัวเป็น Laravel แยก)
    """
    pkg = {}
    pj = root / "package.json"
    if pj.is_file():
        try:
            pkg = json.loads(pj.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            pkg = {}
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

    if (root / "nest-cli.json").is_file() or "@nestjs/core" in deps:
        return "nestjs", "nest-cli.json / @nestjs/core", False
    if "@strapi/strapi" in deps or (root / "config" / "admin.ts").is_file():
        return "strapi", "@strapi/strapi", False
    if (root / "artisan").is_file() or (root / "composer.json").is_file():
        return "laravel", "artisan / composer.json", False
    if (root / "manage.py").is_file():
        return "django", "manage.py", False
    if (root / "pom.xml").is_file() or (root / "build.gradle").is_file():
        return "spring", "pom.xml / build.gradle", False
    if any((root / f"next.config{e}").is_file() for e in (".js", ".ts", ".mjs")) or "next" in deps:
        has_app = (root / "src" / "app").is_dir() or (root / "app").is_dir()
        return ("next-app" if has_app else "next-pages"), "next.config / next", False
    if "vue" in deps:
        v = str(deps.get("vue", ""))
        return ("vue2" if re.search(r"[\^~]?2\.", v) else "vue3"), f"vue {v}", False
    if "express" in deps:
        return "express", "express", False
    if _depth == 0:
        kids = {}
        for c in sorted(root.iterdir()):
            if c.is_dir() and not c.name.startswith("."):
                st, _w, _m = detect_stack(c, _depth=1)
                if st != "unknown":
                    kids.setdefault(st, []).append(c.name)
        if kids:
            st, names = max(kids.items(), key=lambda kv: len(kv[1]))
            return st, f"monorepo — {len(names)} app: {', '.join(names[:4])}", True
    return "unknown", "ไม่พบ marker ที่รู้จัก", False


def common_prefix(names):
    """หา prefix ที่ "ส่วนใหญ่" ใช้ร่วมกัน — ไม่ใช่ที่ทุกตัวใช้ร่วมกัน

    เคสจริง (ERP): `app/` มี ab_customer, ab_order … 41 ตัว ปนกับ auth, core, master, resources
    ที่เป็นโฟลเดอร์โครงสร้าง — ถ้าบังคับว่าต้องตรงทุกตัวจะได้ prefix ว่าง แล้ว:
      · ชื่อ module ฝั่ง BE เป็น ab-customer ส่วน FE เป็น customer → pair_by: name จับคู่ไม่ติดสักตัว
      · โฟลเดอร์โครงสร้าง 4 ตัวหลุดเข้ามาเป็น "module"
    เกณฑ์: prefix ที่พบบ่อยสุดต้องครอบ >= 60% ของชื่อทั้งหมด และมีอย่างน้อย 3 ตัว
    """
    if len(names) < 5:
        return ""
    from collections import Counter
    c = Counter()
    for n in names:
        m = re.match(r"^([A-Za-z]{1,6}[_-])", n)
        if m:
            c[m.group(1)] += 1
    if not c:
        return ""
    pre, hits = c.most_common(1)[0]
    return pre if hits >= 3 and hits / len(names) >= 0.6 else ""


def try_globs(root: Path, cands, exclude_names):
    """ทดสอบ glob จริงกับดิสก์ แล้วให้คะแนน — ไม่เสนอ glob ที่ไม่เคยรัน"""
    out = []
    for g in cands:
        hits = [p for p in root.glob(g)
                if p.name not in exclude_names and not p.name.startswith((".", "_"))]
        if g.endswith("/*") or g.endswith("/*/"):
            hits = [h for h in hits if h.is_dir()]
        n = len(hits)
        if n == 0:
            continue
        score = 0
        if 5 <= n <= 80:
            score += 10
        elif n < 5:
            score += 2
        else:
            score -= 4                       # กว้างไป มักจับไฟล์โครงสร้างปนมา
        # ชื่อที่ได้ควรดูเป็น "โดเมนธุรกิจ" ไม่ใช่ชื่อโครงสร้าง framework
        generic = {"components", "utils", "lib", "shared", "common", "hooks", "types", "styles"}
        score -= sum(2 for h in hits if h.name in generic)
        names = sorted(h.name for h in hits)
        out.append({"glob": g, "count": n, "names": names,
                    "sample": names[:6], "score": score})
    out.sort(key=lambda d: -d["score"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name")
    ap.add_argument("--code", action="append", required=True, help="path repo โค้ด product (ระบุซ้ำได้)")
    ap.add_argument("--specs", action="append", default=[])
    ap.add_argument("--automation")
    ap.add_argument("--out-dir", help="ที่เก็บไฟล์ที่ generate (ดีฟอลต์ = <automation>/docs/generated)")
    ap.add_argument("--domain", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    name = a.name.lower()
    roots = [Path(p).expanduser().resolve() for p in a.code]
    missing = [str(r) for r in roots if not r.is_dir()]
    if missing:
        sys.exit("path โค้ดไม่มีอยู่จริง: " + ", ".join(missing))

    exclude = {"components", "utils", "lib", "shared", "common", "hooks", "types", "styles",
               "layout.tsx", "page.tsx", "theme", "sample", "Controller.php", "Base.php",
               "loading.tsx", "error.tsx", "not-found.tsx", "template.tsx", "middleware.ts",
               "config", "constants", "helpers", "interfaces", "models", "assets"}
    ext, signal, ignore, disc, report = set(), set(), set(BASE_IGNORE), [], []

    for r in roots:
        stack, why, mono = detect_stack(r)
        report.append((r, stack, why))
        if stack == "unknown":
            continue
        e, s, globs, ig = STACKS[stack]
        if mono:                       # marker อยู่ในลูก → glob ต้องข้ามชั้น app ไปหนึ่งชั้น
            globs = [f"*/{g}" for g in globs]
        ext.update(e); signal.update(s); ignore.update(ig)
        if (r / "prisma" / "schema.prisma").is_file() or list(r.glob("**/schema.prisma"))[:1]:
            ext.add(".prisma")
        ranked = try_globs(r, globs, exclude)
        if ranked:
            best = ranked[0]
            pre = common_prefix(best["names"])
            entry = {"side": SIDE_HINT.get(stack, "be"), "root_match": r.name,
                     "glob": best["glob"].rstrip("/"), "stack": stack,
                     "count": best["count"], "sample": best["sample"],
                     "alts": [x["glob"] for x in ranked[1:3]]}
            if stack == "laravel" and "Controller.php" in best["glob"]:
                entry["name_from"] = "basename"; entry["strip_suffix"] = "Controller.php"
                entry["label_with_parent"] = True
            else:
                entry["name_from"] = "dirname"
                if pre:
                    entry["strip_prefix"] = pre
                    entry["glob"] = entry["glob"][:-1] + pre + "*"
                    # นับใหม่หลังบีบ glob — comment ในไฟล์ต้องบอกจำนวนที่ทดสอบได้จริง ไม่ใช่ของ glob เดิม
                    entry["count"] = len([x for x in r.glob(entry["glob"]) if x.is_dir()])
            disc.append(entry)

    sides = {d["side"] for d in disc}
    pair_by = "name" if len(sides) > 1 and not any(d.get("label_with_parent") for d in disc) else \
              ("route" if len(sides) > 1 else "manual")

    print(f"── ตรวจ stack ({len(roots)} repo) ──")
    for r, stack, why in report:
        print(f"  {r.name:<28} {stack:<11} ({why})")
    print(f"\n── discovery ที่ทดสอบกับดิสก์แล้ว ──")
    for d in disc:
        print(f"  [{d['side']}] {d['root_match']}/{d['glob']} → {d['count']} รายการ")
        print(f"       ตัวอย่าง: {', '.join(d['sample'])}")
        if d["alts"]:
            print(f"       ตัวเลือกรอง: {', '.join(d['alts'])}")
    print(f"  pair_by: {pair_by}")
    if not disc:
        print("  ⚠️  หา glob ที่ใช้ได้ไม่เจอเลย — ต้องให้คนระบุเอง")

    auto = Path(a.automation).expanduser().resolve() if a.automation else None
    outdir = Path(a.out_dir).expanduser().resolve() if a.out_dir else (
        auto / "docs" / "generated" if auto else None)

    def q(items):
        return "[" + ", ".join(items) + "]"

    portable = f"""# โปรเจกต์ {name.upper()} — สร้างโดย /setup (bootstrap อัตโนมัติ) · ตรวจแล้วแก้ได้ตามจริง
name: {name.upper()}
domain: "{a.domain or 'ยังไม่ระบุ — เติมคำอธิบายระบบสั้นๆ ตรงนี้ ช่วยให้ AI เดาโดเมนถูกขึ้น'}"
lang: th
tc_prefix: TC

# git remote (URL สะอาด ห้ามฝัง PAT) — เติมเองถ้าต้องการให้ /setup เสนอ clone บนเครื่องอื่น
remotes:
  code: []

automation:
  framework: robot
  layout: multi-suite            # ราก repo มีหลาย <module>_robot อยู่ข้างกัน
  conventions: docs/CONVENTIONS.md
  # schema: <module>: {{ dir: <path relative จาก automation.path>, prefix: TC-<AREA> }}
  # /gen-batch เติม entry ตรงนี้เองทุกครั้งที่ scaffold suite ใหม่ — ไม่ต้องเขียนมือ
  areas: {{}}

# ─────────────────────────────────────────────────────────────────────
# discovery — บอก /module-scout ว่า "module ของ stack นี้อยู่ตรงไหน"
# ทุก glob ด้านล่างถูกทดสอบกับดิสก์จริงแล้ว (จำนวนที่ match อยู่ใน comment)
# ─────────────────────────────────────────────────────────────────────
discovery:
  modules:
"""
    for d in disc:
        extra = ""
        if d.get("strip_suffix"):
            extra = f', strip_suffix: "{d["strip_suffix"]}", label_with_parent: true'
        if d.get("strip_prefix"):
            extra = f', strip_prefix: "{d["strip_prefix"]}"'
        portable += (f'    - {{ side: {d["side"]}, root_match: {d["root_match"]}, '
                     f'glob: "{d["glob"]}", name_from: {d["name_from"]}{extra} }}'
                     f'   # {d["stack"]} · {d["count"]} รายการ\n')
    portable += f"""  pair_by: {pair_by}
  # exclude = "ไม่ใช่ฟีเจอร์" เท่านั้น (โครงสร้าง framework/ไฟล์ฐาน)
  # ฟีเจอร์จริงที่ไม่คุ้ม automate ให้ mark risk: skip ในทะเบียนแทน จะได้เห็นว่ารู้จักแต่ตั้งใจไม่ทำ
  exclude: [shared, common, components, utils, lib, hooks, types, styles, assets, config, constants]

include_ext: {q(sorted(ext) or ['.ts', '.js'])}
ignore_dirs: {q(sorted(ignore))}
ignore_globs: {q(BASE_IGNORE_GLOBS)}
signal_dirs: {q(sorted(signal))}

max_files: 25
max_total_chars: 120000
"""

    local = f"""# path จริงบน "เครื่องนี้" — สร้างโดย /setup (ไม่ commit; ดู .gitignore)
sources:
  code:
"""
    for r in roots:
        local += f"    - {r}\n"
    if a.specs:
        local += "  specs:\n" + "".join(f"    - {Path(p).expanduser().resolve()}\n" for p in a.specs)
    if auto:
        local += f"automation:\n  path: {auto}\n"
    if outdir:
        local += f"output:\n  dir: {outdir}\n"
        base = outdir.parent if outdir.name == "generated" else outdir
        local += f"""behavior_spec:
  draft_dir: {base}/behavior-spec/draft
  confirmed_dir: {base}/behavior-spec/confirmed
batch:
  dir: {base}/batch
"""

    pf = TOOL_DIR / "projects" / f"{name}.yaml"
    lf = TOOL_DIR / "projects" / f"{name}.local.yaml"
    if a.dry_run:
        print("\n────────── projects/%s.yaml ──────────\n%s" % (name, portable))
        print("────────── projects/%s.local.yaml ──────────\n%s" % (name, local))
        print("(--dry-run: ไม่เขียนไฟล์)")
        return
    for p, body in ((pf, portable), (lf, local)):
        if p.exists():
            bak = p.with_suffix(p.suffix + ".bak")
            bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  สำรองของเดิมไว้ที่ {bak.name}")
        p.write_text(body, encoding="utf-8")
    print(f"\n→ {pf}\n→ {lf}")
    print(f"\nขั้นถัดไป: /module-scout {name}")


if __name__ == "__main__":
    main()
