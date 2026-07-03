#!/usr/bin/env python3
"""AI Test-Case Generator — เครื่องมือกลางคิดเทสเคสด้วย AI จาก codebase จริง

ไหล: อ่าน config โปรเจกต์ -> clone repo จาก git remote (Azure DevOps/GitHub) สด
     -> คัดไฟล์โค้ดที่เกี่ยวกับฟีเจอร์ -> ให้ Gemini ออกแบบเทสเคสตามเทคนิค QA
     พร้อมอ้างอิง source -> เขียน md/csv (เป็นร่างให้คนรีวิว)

ใช้กับเว็บไหนก็ได้ แค่เพิ่มไฟล์ projects/<name>.yaml
ดู README.md สำหรับรายละเอียด

env: GEMINI_API_KEY (จำเป็นตอน generate), AZURE_DEVOPS_PAT (จำเป็นถ้า repo เป็น private Azure)
"""

import argparse
import base64
import fnmatch
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(HERE, "projects")
CACHE_DIR = os.environ.get("TESTGEN_CACHE", os.path.expanduser("~/.cache/ai-gen-testcase"))
GEN_MODEL = os.environ.get("AI_MODEL", "gemini-2.5-pro")        # โหมดอ่านโค้ด: ใช้รุ่นฉลาด
TERMS_MODEL = os.environ.get("AI_TERMS_MODEL", "gemini-2.5-flash")
PER_FILE_CHARS = 8000          # ตัดเนื้อไฟล์ต่อไฟล์ กันยาวเกิน
MAX_FILE_BYTES = 200_000       # ข้ามไฟล์ใหญ่ผิดปกติ (มัก generated/minified)


# ---------------------------------------------------------------- config
def load_project(name):
    import yaml
    path = os.path.join(PROJECTS_DIR, f"{name}.yaml")
    if not os.path.exists(path):
        sys.exit(f"ERROR: ไม่พบ config โปรเจกต์: {path}")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("include_ext", [".ts", ".tsx", ".js", ".jsx", ".py", ".php", ".go", ".java", ".vue"])
    cfg.setdefault("ignore_dirs", ["node_modules", ".git", ".next", "dist", "build", "out",
                                    "coverage", "vendor", "__pycache__", ".turbo", ".cache"])
    cfg.setdefault("ignore_globs", ["*.env*", "*.lock", "*.min.*", "*.map", "*.snap",
                                    "*.test.*", "*.spec.*", "*.d.ts"])
    cfg.setdefault("signal_dirs", [])
    cfg.setdefault("max_files", 25)
    cfg.setdefault("max_total_chars", 120_000)
    cfg.setdefault("tc_prefix", "TC")
    cfg.setdefault("lang", "th")
    cfg.setdefault("domain", "")
    return cfg


# ---------------------------------------------------------------- git
def git_auth_args():
    """auth Azure DevOps / GitHub ผ่าน HTTP header (ไม่ฝัง PAT ใน URL)"""
    pat = os.environ.get("AZURE_DEVOPS_PAT") or os.environ.get("GIT_PAT")
    if not pat:
        return []
    token = base64.b64encode(f":{pat}".encode()).decode()
    return ["-c", f"http.extraHeader=Authorization: Basic {token}"]


def _run(args, **kw):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kw)


def ensure_repo(url, dest, branch, refresh):
    """clone แบบ shallow ลง cache; ถ้ามีแล้วและ --refresh ค่อย fetch ใหม่"""
    auth = git_auth_args()
    if os.path.isdir(os.path.join(dest, ".git")):
        if refresh:
            fetch = ["git", *auth, "-C", dest, "fetch", "--depth", "1", "origin"]
            if branch:
                fetch.append(branch)
            _run(fetch)
            _run(["git", "-C", dest, "reset", "--hard", "FETCH_HEAD"])
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    clone = ["git", *auth, "clone", "--depth", "1", "--single-branch"]
    if branch:
        clone += ["--branch", branch]
    clone += [url, dest]
    _run(clone)
    return dest


# ---------------------------------------------------------------- file selection
def collect_files(root, cfg, scope=None):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in cfg["ignore_dirs"]]
        for fn in filenames:
            if os.path.splitext(fn)[1] not in cfg["include_ext"]:
                continue
            if any(fnmatch.fnmatch(fn, g) for g in cfg["ignore_globs"]):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            if scope and not rel.replace("\\", "/").startswith(scope.strip("/")):
                continue
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            out.append((full, rel))
    return out


def score_file(rel, content, terms, signal_dirs):
    p = rel.lower().replace("\\", "/")
    c = content.lower()
    score = 0
    for t in terms:
        tl = t.lower().strip()
        if not tl:
            continue
        score += p.count(tl) * 5
        score += min(c.count(tl), 20)
    for d in signal_dirs:
        if f"/{d}/" in "/" + p:
            score += 2
    return score


def select_files(repo_roots, terms, cfg, scope=None):
    """คัดไฟล์ที่เกี่ยวสุด ข้ามทุก repo -> [(label, content)] ภายในงบ"""
    scored = []
    for repo_name, root in repo_roots:
        for full, rel in collect_files(root, cfg, scope):
            try:
                with open(full, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except OSError:
                continue
            s = score_file(rel, content, terms, cfg["signal_dirs"])
            if s > 0:
                scored.append((s, f"{repo_name}/{rel}", content))
    scored.sort(key=lambda x: -x[0])

    picked, total = [], 0
    for s, label, content in scored:
        snippet = content[:PER_FILE_CHARS]
        if total + len(snippet) > cfg["max_total_chars"]:
            continue
        picked.append((label, snippet))
        total += len(snippet)
        if len(picked) >= cfg["max_files"]:
            break
    return picked


# ---------------------------------------------------------------- AI
def _client():
    from google import genai
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def extract_terms(feature, cfg, extra):
    """แปลงฟีเจอร์ (ไทย) เป็นคำค้นภาษาอังกฤษที่น่าจะอยู่ใน codebase"""
    terms = [t.strip() for t in (extra or "").split(",") if t.strip()]
    try:
        from google.genai import types
        fw = ", ".join(r.get("framework") or "" for r in cfg.get("repos", []))
        resp = _client().models.generate_content(
            model=TERMS_MODEL,
            contents=(f"ฟีเจอร์: {feature}\nโค้ดเบสเป็น: {fw}\n"
                      "ให้คำค้น (identifier/ชื่อไฟล์/route/ตัวแปร/business term) ภาษาอังกฤษ "
                      "ที่น่าจะปรากฏใน codebase นี้ 8-15 คำ สำหรับใช้ grep หาโค้ดที่เกี่ยว"),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction='ตอบเป็น JSON: {"terms":["...","..."]} เท่านั้น',
                temperature=0.2, max_output_tokens=1024),
        )
        data = json.loads(resp.text or "{}")
        terms += [t for t in data.get("terms", []) if isinstance(t, str)]
    except Exception as e:  # noqa: BLE001
        print(f"หมายเหตุ: ดึงคำค้นด้วย AI ไม่สำเร็จ ({type(e).__name__}) — ใช้เฉพาะ --keywords", file=sys.stderr)
    # unique
    seen, out = set(), []
    for t in terms:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


SYS_GEN = (
    "คุณเป็น Senior QA Engineer ออกแบบเทสเคสจาก 'โค้ดจริง' ของระบบ. "
    "ขั้นแรกอ่านโค้ดที่ให้มาเพื่อหา 'กติกาที่ทดสอบได้' — validation (min/max/required/regex), "
    "business rule, สถานะ, enum/constant, ข้อความ error. "
    "จากนั้นออกแบบเทสเคสให้ครอบคลุมด้วยเทคนิค: EP, BVA (ค่าขอบจากค่าจริงในโค้ด), "
    "Decision Table, State Transition, Pairwise. ต้องมีทั้ง positive/negative/boundary. "
    "ยึดค่าจริงจากโค้ด (เช่นเจอ min=500 ให้ทดสอบ 499/500/501). ห้ามแต่งกติกาที่โค้ดไม่มี. "
    "expected result ต้องตรวจสอบได้. ระบุ source (ไฟล์:บรรทัด ถ้าทำได้) ที่กติกามาจาก. "
    "ตอบเป็น JSON เท่านั้น:\n"
    '{"rules":["สรุปกติกาที่เจอในโค้ด ..."],'
    '"cases":[{"id":"<PREFIX-01>","title":"...","technique":"EP|BVA|DT|ST|PW",'
    '"category":"positive|negative|boundary|edge","precondition":"...",'
    '"steps":["..."],"expected":"...","priority":"สูง|กลาง|ต่ำ","source":"path:line"}]}'
)


def generate_cases(feature, files, cfg, prefix, count):
    from google.genai import types
    code_ctx = "\n\n".join(f"// ===== FILE: {label} =====\n{content}" for label, content in files)
    prompt = (
        f"โดเมนระบบ: {cfg.get('domain','')}\n\n"
        f"ฟีเจอร์ที่ต้องออกแบบเทสเคส:\n{feature}\n\n"
        f"ใช้ prefix TC-ID: {prefix} · ออกแบบอย่างน้อย {count} เคส\n\n"
        f"=== โค้ดจริงที่เกี่ยวข้อง ({len(files)} ไฟล์) ===\n{code_ctx or '(ไม่พบโค้ดที่เกี่ยว — ออกแบบจากคำอธิบายเท่าที่ทำได้)'}"
    )
    resp = _client().models.generate_content(
        model=GEN_MODEL, contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYS_GEN, response_mime_type="application/json",
            temperature=0.3, max_output_tokens=16384),
    )
    return json.loads(resp.text or "{}")


# ---------------------------------------------------------------- render
def render_markdown(feature, data, model):
    cases = data.get("cases", [])
    md = [f"# เทสเคส (ร่างจาก AI) — {feature}", "",
          f"> สร้างโดย testgen ({model}) จากโค้ดจริง — **เป็นร่าง ต้องรีวิวก่อนใช้**",
          f"> {len(cases)} เคส", ""]
    rules = data.get("rules", [])
    if rules:
        md.append("## กติกาที่พบในโค้ด")
        md += [f"- {r}" for r in rules]
        md.append("")
    md.append("| TC-ID | เคส | เทคนิค | ประเภท | Precondition | ขั้นตอน | ผลที่คาดหวัง | Pri | Source |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for c in cases:
        steps = "<br>".join(f"{i+1}. {s}" for i, s in enumerate(c.get("steps", [])))
        md.append("| " + " | ".join([
            c.get("id", ""), c.get("title", ""), c.get("technique", ""), c.get("category", ""),
            c.get("precondition", ""), steps, c.get("expected", ""), c.get("priority", ""),
            f"`{c.get('source','')}`" if c.get("source") else "",
        ]) + " |")
    return "\n".join(md) + "\n"


def render_csv(data, path):
    import csv
    cases = data.get("cases", [])
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["TC-ID", "เคส", "เทคนิค", "ประเภท", "Precondition", "ขั้นตอน", "ผลที่คาดหวัง", "Priority", "Source"])
        for c in cases:
            w.writerow([c.get("id", ""), c.get("title", ""), c.get("technique", ""), c.get("category", ""),
                        c.get("precondition", ""), " / ".join(c.get("steps", [])),
                        c.get("expected", ""), c.get("priority", ""), c.get("source", "")])


def slugify(text):
    import re
    s = re.sub(r"\s+", "-", text.strip())
    s = re.sub(r"[^0-9A-Za-z฀-๿\-]", "", s)
    return (s[:40] or "feature").strip("-")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="AI Test-Case Generator (codebase-grounded)")
    ap.add_argument("feature", help="คำอธิบายฟีเจอร์ (ภาษาไทย)")
    ap.add_argument("--project", default="wnw", help="ชื่อ config ใน projects/ (ดีฟอลต์ wnw)")
    ap.add_argument("--repos", help="เลือก repo เฉพาะบางตัว คั่นด้วย , (ดีฟอลต์ทั้งหมดใน config)")
    ap.add_argument("--path", help="จำกัดขอบเขตไฟล์ใต้ subpath (เช่น src/checkout)")
    ap.add_argument("--keywords", help="คำค้นเพิ่ม (อังกฤษ) คั่นด้วย ,")
    ap.add_argument("--prefix", help="prefix ของ TC-ID (ดีฟอลต์อิง config/feature)")
    ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--format", choices=["md", "csv", "both"], default="md")
    ap.add_argument("--refresh", action="store_true", help="re-fetch repo ล่าสุด")
    ap.add_argument("--dry-run", action="store_true", help="แค่ clone + โชว์ไฟล์ที่คัดได้ ไม่เรียก AI generate")
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()

    cfg = load_project(args.project)
    repos = cfg.get("repos", [])
    if args.repos:
        want = {r.strip() for r in args.repos.split(",")}
        repos = [r for r in repos if r.get("name") in want]
    if not repos:
        sys.exit("ERROR: ไม่มี repo ให้ประมวลผล (เช็ค config / --repos)")

    # 1) clone/refresh
    roots = []
    for r in repos:
        dest = os.path.join(CACHE_DIR, args.project, r["name"])
        print(f"• เตรียม repo {r['name']} …", file=sys.stderr)
        try:
            ensure_repo(r["url"], dest, r.get("branch"), args.refresh)
        except subprocess.CalledProcessError as e:
            hint = " (ตรวจ AZURE_DEVOPS_PAT / สิทธิ์ Code Read)" if "Authentication" in (e.stderr or "") or "403" in (e.stderr or "") else ""
            sys.exit(f"ERROR: clone {r['name']} ไม่สำเร็จ{hint}\n{(e.stderr or '')[:500]}")
        roots.append((r["name"], dest))

    # 2) หาคำค้น (ต้องมี key ถ้าอยากให้ AI ช่วย) + คัดไฟล์
    if args.dry_run and not os.environ.get("GEMINI_API_KEY"):
        terms = [t.strip() for t in (args.keywords or "").split(",") if t.strip()]
        if not terms:
            print("dry-run ไม่มี key/keywords — ใส่ --keywords เพื่อทดสอบการคัดไฟล์", file=sys.stderr)
    else:
        terms = extract_terms(args.feature, cfg, args.keywords)
    print(f"• คำค้น: {', '.join(terms) or '(ไม่มี)'}", file=sys.stderr)
    files = select_files(roots, terms, cfg, args.path)
    print(f"• คัดโค้ดที่เกี่ยว {len(files)} ไฟล์:", file=sys.stderr)
    for label, _ in files:
        print(f"    - {label}", file=sys.stderr)

    if args.dry_run:
        print("\n(dry-run — ไม่เรียก AI generate)")
        return 0
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("ERROR: ต้องตั้ง GEMINI_API_KEY เพื่อ generate")

    # 3) generate
    prefix = args.prefix or (f"{cfg['tc_prefix']}-" + slugify(args.feature)[:6].upper())
    try:
        data = generate_cases(args.feature, files, cfg, prefix, args.count)
    except Exception as e:  # noqa: BLE001
        low = f"{getattr(e,'status','')} {e}".lower()
        if getattr(e, "code", None) == 429 or any(k in low for k in ("resource_exhausted", "429", "quota", "rate limit")):
            sys.exit("ERROR: Gemini ติดโควตา/เรตลิมิต — ลองใหม่ หรือเปลี่ยน AI_MODEL")
        sys.exit(f"ERROR: generate ไม่สำเร็จ ({type(e).__name__}: {e})")

    cases = data.get("cases", [])
    if not cases:
        sys.exit("ERROR: AI ไม่ได้ส่งเทสเคสกลับ (ลองระบุฟีเจอร์ชัดขึ้น หรือ --path เจาะจง)")

    os.makedirs(args.out, exist_ok=True)
    slug = f"{args.project}-{slugify(args.path or args.feature)}"
    written = []
    if args.format in ("md", "both"):
        p = os.path.join(args.out, f"{slug}-testcases.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(render_markdown(args.feature, data, GEN_MODEL))
        written.append(p)
    if args.format in ("csv", "both"):
        p = os.path.join(args.out, f"{slug}-testcases.csv")
        render_csv(data, p)
        written.append(p)

    print(f"\n✅ สร้าง {len(cases)} เทสเคส (prefix {prefix})")
    for p in written:
        print(f"   → {p}")
    print("   ⚠️  ร่างจาก AI — รีวิวก่อนนำไปเขียนเป็นเทสจริง")
    return 0


if __name__ == "__main__":
    sys.exit(main())
