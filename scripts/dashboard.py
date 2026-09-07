#!/usr/bin/env python3
"""dashboard.py — หน้าจอดูสถานะ autopilot แบบ realtime (อ่านอย่างเดียว)

ใช้:  python3 scripts/dashboard.py <project> [--port 8787] [--all]

ทำไมต้องเป็น server ในเครื่อง ไม่ใช่ Artifact: ข้อมูลทั้งหมด (modules.yaml, *.state,
log, results/*/output.xml) อยู่ในดิสก์ local — หน้าเว็บที่ host ที่อื่นอ่านไม่ได้

ความปลอดภัย: bind 127.0.0.1 เท่านั้น · ไม่มี endpoint ที่เขียนอะไร · ไม่ส่งค่า env
หรือเนื้อไฟล์ config ออกไป (เฉพาะ path กับตัวเลขสถานะ)
"""
import argparse, json, os, re, sys, threading, time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

try:
    import yaml
except ImportError:
    sys.exit("ต้องมี pyyaml ก่อน: pip install pyyaml")

TOOL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL_DIR / "scripts"))
from scan_modules import load_cfg, automation_root          # noqa: E402
import make_report                                           # noqa: E402
import token_usage                                           # noqa: E402

_cache, _lock = {}, threading.Lock()
CACHE_TTL = 25          # วิเคราะห์ output.xml ใหม่ทุกกี่วินาที (แพงกว่าส่วนอื่นมาก)


def projects():
    out = []
    for f in sorted((TOOL_DIR / "projects").glob("*.yaml")):
        n = f.stem
        if n.endswith(".local") or n.startswith("_"):
            continue
        out.append({"name": n, "setup": (TOOL_DIR / "projects" / f"{n}.local.yaml").exists()})
    return out


def read_state(project):
    f = TOOL_DIR / "logs" / f"{project}.state"
    if not f.exists():
        return {}
    d = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def alive(pid):
    try:
        Path(f"/proc/{int(pid)}").exists()
        return Path(f"/proc/{int(pid)}").is_dir()
    except Exception:
        return False


def mins_since(path):
    try:
        return int((time.time() - Path(path).stat().st_mtime) // 60)
    except Exception:
        return None


def log_tail(path, n=60):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:]
    except Exception:
        return []


# โฟลเดอร์ที่ห้ามเดินลงไปเด็ดขาด — ใช้เมื่อ config ไม่ได้ตั้ง ignore_dirs
# (ก่อนหน้านี้โค้ดกรองด้วยชื่อ repo ของ project erp แบบ hardcode จึงใช้กับ project อื่นไม่ได้
#  ผลคือ /api/state เดิน node_modules ~160k ไฟล์ต่อคำขอ แล้วไม่ตอบเลย — dashboard ค้าง)
_SKIP_DIRS_FALLBACK = {
    ".git", ".hg", ".svn", ".cache", ".next", ".nuxt", ".strapi", ".tmp", ".turbo",
    ".vercel", ".venv", "__pycache__", "build", "coverage", "dist", "node_modules",
    "out", "storage", "target", "vendor", "venv",
}

# เพดานกันแขวน: ต่อให้ config เพี้ยน คำขอเดียวต้องไม่เดินเกินนี้
_WALK_FILE_BUDGET = 40000
_WALK_TIME_BUDGET = 3.0  # วินาที


def _skip_dirs(cfg):
    d = set(_SKIP_DIRS_FALLBACK)
    for name in (cfg.get("ignore_dirs") or []):
        n = str(name).strip()
        if n:
            d.add(n)
    d.discard(".git")      # เติมกลับด้านล่างเสมอ ไม่ให้ config ถอดออกได้
    d.add(".git")
    return d


def recent_writes(cfg, minutes=15, limit=14):
    roots = [Path(p) for p in cfg.get("sources", {}).get("code", [])]
    roots.append(automation_root(cfg))
    for k in ("output", "behavior_spec", "batch"):
        b = cfg.get(k) or {}
        for kk in ("dir", "draft_dir", "confirmed_dir"):
            if b.get(kk):
                roots.append(Path(b[kk]))

    skip = _skip_dirs(cfg)
    cut, out = time.time() - minutes * 60, []
    seen = set()
    scanned = 0
    deadline = time.monotonic() + _WALK_TIME_BUDGET
    truncated = False

    for r in sorted(roots, key=lambda x: len(str(x))):
        if not r.is_dir():
            continue
        rr = str(r.resolve())
        # ข้าม root ที่ซ้ำ และ root ที่ซ้อนอยู่ใต้ root ที่เดินไปแล้ว
        # (batch.dir / behavior_spec อยู่ใต้ automation_root → เดินซ้ำ = รายการซ้ำ)
        if any(rr == s0 or rr.startswith(s0 + os.sep) for s0 in seen):
            continue
        seen.add(rr)

        # os.walk + ตัด dirnames ทิ้ง = ไม่เดินลง node_modules เลย (rglob ตัดไม่ได้)
        for dirpath, dirnames, filenames in os.walk(rr, followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
            if scanned >= _WALK_FILE_BUDGET or time.monotonic() > deadline:
                truncated = True
                dirnames[:] = []
                break
            for fn in filenames:
                scanned += 1
                fp = os.path.join(dirpath, fn)
                try:
                    m = os.stat(fp).st_mtime
                except OSError:
                    continue
                if m >= cut:
                    out.append({"t": datetime.fromtimestamp(m).strftime("%H:%M:%S"),
                                "p": fp, "mt": m})
        if truncated:
            break

    out.sort(key=lambda x: -x["mt"])
    res = out[:limit]
    if truncated and res:
        res[-1] = dict(res[-1], truncated=True)
    return res


def registry(cfg):
    bdir = Path(cfg.get("batch", {}).get("dir") or (automation_root(cfg) / "docs" / "batch"))
    f = bdir / "modules.yaml"
    if not f.exists():
        return bdir, None
    return bdir, (yaml.safe_load(f.read_text(encoding="utf-8")) or {})


def results_block(project):
    with _lock:
        c = _cache.get(project)
        if c and time.time() - c["at"] < CACHE_TTL:
            return c["v"]
    try:
        d = make_report.analyse(project, 0)
        suites = [s for s in d["suites"] if s["state"] == "รันจริงแล้ว"]
        never = [s for s in d["suites"] if s["state"].startswith("ยังไม่เคยรัน")]
        by = {}
        for x in d["causes"]:
            by[x["bucket"]] = by.get(x["bucket"], 0) + 1
        v = {
            "ok": True,
            "pass": sum(s["PASS"] for s in suites), "fail": sum(s["FAIL"] for s in suites),
            "skip": sum(s["SKIP"] for s in suites),
            "suites": [{"m": s["module"], "s": s["suite"], "run": s["run"], "when": s["when"],
                        "p": s["PASS"], "f": s["FAIL"], "k": s["SKIP"],
                        "age": s.get("age_days"), "df": s.get("delta_fail")} for s in suites],
            "never": [{"m": s["module"], "s": s["suite"]} for s in never],
            "causes_total": d["cause_total"], "by_bucket": by,
            "top": [{"b": x["bucket"], "n": len(x["tests"]), "msg": x["msg"][:150]}
                    for x in d["causes"][:8]],
        }
    except SystemExit as e:
        v = {"ok": False, "why": str(e)}
    except Exception as e:
        v = {"ok": False, "why": f"{type(e).__name__}: {e}"}
    with _lock:
        _cache[project] = {"at": time.time(), "v": v}
    return v


def tokens_block(started):
    """token ของรอบนี้ (นับจากเวลาที่ autopilot เริ่ม) + ของทั้งวันนี้"""
    since = None
    if started:
        try:
            since = datetime.strptime(started, "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            pass
    idx = token_usage.index()
    run = idx.summary(since)
    day = idx.summary(datetime.now().replace(hour=0, minute=0, second=0,
                                             microsecond=0).timestamp())
    for d in (run, day):
        d["by_agent"] = d.get("by_agent", [])[:8]
        d.pop("by_hour", None)
    return {"run": run, "day": day}


def payload(project):
    cfg = load_cfg(project)
    st = read_state(project)
    bdir, reg = registry(cfg)
    mods = (reg or {}).get("modules", [])
    planned = [m for m in mods if m.get("risk") != "skip"]
    counts = {}
    for m in planned:
        counts[m.get("status") or "pending"] = counts.get(m.get("status") or "pending", 0) + 1

    inprog = [{"name": m["name"], "stage": m.get("stage"), "attempt": m.get("attempt"),
               "note": m.get("note"), "risk": m.get("risk")}
              for m in planned if m.get("status") == "in_progress"]
    blocked = [{"name": m["name"], "why": m.get("blocked_reason") or m.get("note")}
               for m in planned if m.get("status") == "blocked"]
    nxt = [{"name": m["name"], "risk": m.get("risk"), "score": m.get("score"),
            "files": m.get("files")}
           for m in sorted([m for m in planned if m.get("status") == "pending"],
                           key=lambda m: (make_report.__dict__.get("_x", 0),
                                          {"high": 0, "medium": 1, "low": 2}.get(m.get("risk"), 5),
                                          -(m.get("score") or 0)))[:6]]

    qdir = bdir / "questions"
    questions = sorted(str(p.name) for p in qdir.glob("*.md")) if qdir.is_dir() else []
    findings = bdir / "findings.md"
    lg = st.get("log", "")
    return {
        "now": datetime.now().strftime("%H:%M:%S"),
        "project": project,
        "runner": {
            "phase": st.get("phase"), "detail": st.get("detail"),
            "heartbeat": st.get("heartbeat"), "started": st.get("started"),
            "pid": st.get("pid"), "alive": alive(st.get("pid", "")) if st.get("pid") else False,
            "log": lg, "log_quiet_min": mins_since(lg) if lg else None,
            "stopping": (TOOL_DIR / "logs" / f"{project}.stop").exists(),
        },
        "modules": {"planned": len(planned), "skip": len(mods) - len(planned), "counts": counts,
                    "in_progress": inprog, "blocked": blocked, "next": nxt},
        "questions": questions,
        "findings": str(findings) if findings.exists() else None,
        "report": str(bdir / "report.md") if (bdir / "report.md").exists() else None,
        "activity": recent_writes(cfg),
        "log_tail": log_tail(lg) if lg else [],
        "results": results_block(project),
        "tokens": tokens_block(st.get("started")),
        "run_configured": bool((cfg.get("run") or {}).get("cmd")),
    }


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html")
        if u.path == "/api/projects":
            return self._send(200, json.dumps(projects(), ensure_ascii=False), "application/json")
        if u.path == "/api/state":
            q = parse_qs(u.query)
            p = (q.get("project") or [DEFAULT_PROJECT])[0]
            try:
                return self._send(200, json.dumps(payload(p), ensure_ascii=False),
                                  "application/json")
            except SystemExit as e:
                return self._send(200, json.dumps({"error": str(e)}, ensure_ascii=False),
                                  "application/json")
            except Exception as e:
                return self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"},
                                                  ensure_ascii=False), "application/json")
        self._send(404, "not found", "text/plain")


PAGE = r"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>autopilot · dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sarabun:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap">
<style>
:root{
  --bg:#0F1319; --panel:#161B23; --panel2:#1C222C; --line:#252C38; --line2:#333C4B;
  --ink:#E3E8F0; --mut:#93A0B5; --faint:#68748B;
  --ac:#6FA8E8; --ok:#5FBF95; --warn:#D9A55E; --bad:#E08770; --loc:#A995D8; --tst:#8FA6BC;
}
@media (prefers-color-scheme:light){
  :root{--bg:#EEF1F5; --panel:#FFFFFF; --panel2:#F3F5F9; --line:#DCE1EA; --line2:#C3CBD8;
        --ink:#171A21; --mut:#54607A; --faint:#7C889E;
        --ac:#2C4A7E; --ok:#1F6B4D; --warn:#8A5910; --bad:#A03F28; --loc:#5B4382; --tst:#3F5265;}
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Sarabun","Noto Sans Thai",system-ui,sans-serif;font-size:14.5px;line-height:1.6}
.wrap{max-width:1500px;margin:0 auto;padding:16px 18px 60px}
header{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;padding:8px 0 14px;
  border-bottom:1px solid var(--line2);margin-bottom:16px}
h1{font-size:19px;margin:0;font-weight:600;letter-spacing:-.01em}
.mono{font-family:"JetBrains Mono",ui-monospace,monospace}
.pill{font-family:"JetBrains Mono",monospace;font-size:11px;letter-spacing:.05em;padding:3px 9px;
  border-radius:99px;border:1px solid var(--line2);color:var(--mut);white-space:nowrap}
.pill.on{color:var(--ok);border-color:var(--ok)}
.pill.off{color:var(--bad);border-color:var(--bad)}
.pill.wait{color:var(--warn);border-color:var(--warn)}
#tick{margin-left:auto;font-family:"JetBrains Mono",monospace;font-size:11.5px;color:var(--faint)}
select{background:var(--panel);color:var(--ink);border:1px solid var(--line2);border-radius:4px;
  padding:4px 8px;font-family:"JetBrains Mono",monospace;font-size:12px}

.grid{display:grid;grid-template-columns:1fr;gap:14px}
@media(min-width:980px){.grid{grid-template-columns:minmax(0,1.15fr) minmax(0,1fr)}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:14px 16px}
.card h2{font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:var(--faint);
  margin:0 0 12px;font-family:"JetBrains Mono",monospace;font-weight:500}
.kv{display:grid;grid-template-columns:112px minmax(0,1fr);gap:4px 12px;font-size:13.5px}
.kv dt{color:var(--faint);font-family:"JetBrains Mono",monospace;font-size:11.5px;padding-top:2px}
.kv dd{margin:0;word-break:break-word}

.bar{display:flex;height:9px;border-radius:99px;overflow:hidden;background:var(--panel2);
  border:1px solid var(--line);margin:4px 0 9px}
.bar i{display:block;height:100%}
.bar .d{background:var(--ok)} .bar .p{background:var(--ac)}
.bar .b{background:var(--bad)} .bar .w{background:var(--line2)}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12px;color:var(--mut)}
.legend b{font-variant-numeric:tabular-nums;color:var(--ink)}
.dot{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:5px;vertical-align:1px}

.stat{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);border-radius:5px;overflow:hidden;margin-bottom:12px}
.stat div{background:var(--panel2);padding:10px 12px}
.stat .n{font-family:"JetBrains Mono",monospace;font-size:22px;font-weight:700;
  font-variant-numeric:tabular-nums;line-height:1.1}
.stat .l{font-size:11.5px;color:var(--faint);margin-top:3px}
.stat .n.ok{color:var(--ok)} .stat .n.bad{color:var(--bad)} .stat .n.ac{color:var(--ac)}

table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:6px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-family:"JetBrains Mono",monospace;font-size:10.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--faint);font-weight:500}
tr:last-child td{border-bottom:none}
td.n{text-align:right;font-variant-numeric:tabular-nums;font-family:"JetBrains Mono",monospace}
.tw{overflow-x:auto}
.tag{font-family:"JetBrains Mono",monospace;font-size:10.5px;padding:1px 7px;border-radius:3px;
  border:1px solid;white-space:nowrap}
.t-bug{color:var(--bad);border-color:var(--bad)} .t-env{color:var(--warn);border-color:var(--warn)}
.t-loc{color:var(--loc);border-color:var(--loc)} .t-tst{color:var(--tst);border-color:var(--tst)}
.t-hi{color:var(--bad);border-color:var(--bad)} .t-me{color:var(--warn);border-color:var(--warn)}
.t-lo{color:var(--mut);border-color:var(--line2)}

pre.log{margin:0;background:var(--bg);border:1px solid var(--line);border-radius:5px;
  padding:10px 12px;max-height:300px;overflow:auto;font-family:"JetBrains Mono",monospace;
  font-size:11.5px;line-height:1.65;color:var(--mut);white-space:pre-wrap;word-break:break-word}
pre.log b{color:var(--ink);font-weight:500}
ul.act{list-style:none;margin:0;padding:0;font-family:"JetBrains Mono",monospace;font-size:11.5px;
  max-height:220px;overflow:auto}
ul.act li{padding:3px 0;border-bottom:1px solid var(--line);color:var(--mut);
  display:grid;grid-template-columns:62px minmax(0,1fr);gap:8px}
ul.act li span{color:var(--faint)}
ul.act li b{color:var(--ink);font-weight:400;word-break:break-all}
.empty{color:var(--faint);font-size:13px;padding:6px 0}
.err{color:var(--bad);font-size:13px}
.full{grid-column:1/-1}
</style></head><body>
<div class="wrap">
<header>
  <h1>autopilot</h1>
  <select id="proj"></select>
  <span class="pill" id="p-phase">—</span>
  <span class="pill" id="p-alive">—</span>
  <span class="pill" id="p-quiet">—</span>
  <span id="tick">กำลังต่อ…</span>
</header>

<div class="grid">
  <div class="card">
    <h2>ความคืบหน้า</h2>
    <div class="bar" id="bar"></div>
    <div class="legend" id="legend"></div>
    <div style="margin-top:14px" id="inprog"></div>
  </div>

  <div class="card">
    <h2>ตัวรัน</h2>
    <dl class="kv" id="runner"></dl>
  </div>

  <div class="card full">
    <h2>ผลรันเทสจริง</h2>
    <div id="results"></div>
  </div>

  <div class="card">
    <h2>คิวงานถัดไป</h2>
    <div class="tw" id="next"></div>
  </div>

  <div class="card">
    <h2>ไฟล์ที่เพิ่งถูกเขียน (15 นาที)</h2>
    <ul class="act" id="act"></ul>
  </div>

  <div class="card full">
    <h2>token ที่ใช้</h2>
    <div id="tok"></div>
  </div>

  <div class="card full">
    <h2>log</h2>
    <pre class="log" id="log"></pre>
  </div>
</div>
</div>
<script>
var PROJ = new URLSearchParams(location.search).get('project') || null;
var TAGB = {product:['t-bug','ต้องสงสัยเป็นบั๊ก'],env:['t-env','ENV/SESSION'],
            locator:['t-loc','LOCATOR เก่า'],testbug:['t-tst','สคริปต์เทสผิด']};
var RISK = {high:['t-hi','high'],medium:['t-me','medium'],low:['t-lo','low']};
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function el(id){return document.getElementById(id);}

fetch('/api/projects').then(function(r){return r.json();}).then(function(ps){
  var s = el('proj');
  ps.forEach(function(p){
    var o = document.createElement('option');
    o.value = p.name; o.textContent = p.name + (p.setup ? '' : ' (ยังไม่ setup)');
    s.appendChild(o);
  });
  if(!PROJ && ps.length) PROJ = ps[0].name;
  s.value = PROJ;
  s.addEventListener('change', function(){ PROJ = s.value; load(); });
  load();
}).catch(function(){ el('tick').textContent = 'ต่อ /api/projects ไม่ได้'; });

function load(){
  fetch('/api/state?project=' + encodeURIComponent(PROJ)).then(function(r){return r.json();})
  .then(render).catch(function(e){ el('tick').textContent = 'ดึงข้อมูลไม่ได้: ' + e; });
}

function render(d){
  if(d.error){ el('tick').textContent = d.error; return; }
  el('tick').textContent = 'อัปเดต ' + d.now + ' · รีเฟรชทุก 5 วิ';

  var r = d.runner, m = d.modules;
  el('p-phase').textContent = 'phase: ' + (r.phase || '—');
  var a = el('p-alive');
  a.textContent = r.alive ? 'ทำงานอยู่' : 'ไม่ได้รัน';
  a.className = 'pill ' + (r.alive ? 'on' : 'off');
  var q = el('p-quiet');
  if(r.phase === 'waiting-quota'){ q.textContent = 'รอโควตา'; q.className = 'pill wait'; }
  else if(r.log_quiet_min == null){ q.textContent = 'ไม่มี log'; q.className = 'pill'; }
  else { q.textContent = 'log เงียบ ' + r.log_quiet_min + ' นาที';
         q.className = 'pill ' + (r.log_quiet_min > 45 ? 'wait' : ''); }

  var c = m.counts, tot = m.planned || 1;
  var seg = [['d','done'],['p','in_progress'],['b','blocked'],['w','pending']];
  el('bar').innerHTML = seg.map(function(s){
    var v = c[s[1]] || 0;
    return v ? '<i class="' + s[0] + '" style="width:' + (v*100/tot) + '%"></i>' : '';
  }).join('');
  var names = {done:['var(--ok)','เสร็จ'],in_progress:['var(--ac)','กำลังทำ'],
               blocked:['var(--bad)','ติดปัญหา'],pending:['var(--line2)','ยังไม่เริ่ม']};
  el('legend').innerHTML = Object.keys(names).map(function(k){
    return '<span><i class="dot" style="background:' + names[k][0] + '"></i>' +
           names[k][1] + ' <b>' + (c[k] || 0) + '</b></span>';
  }).join('') + '<span style="color:var(--faint)">จากทั้งหมด <b>' + m.planned +
    '</b> module · ตัดออก ' + m.skip + '</span>';

  el('inprog').innerHTML = m.in_progress.length ? m.in_progress.map(function(x){
    var rk = RISK[x.risk] || RISK.low;
    return '<div style="background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:10px 12px">' +
      '<div style="display:flex;gap:9px;align-items:baseline;flex-wrap:wrap">' +
      '<b class="mono">' + esc(x.name) + '</b>' +
      '<span class="tag ' + rk[0] + '">' + rk[1] + '</span>' +
      '<span class="mono" style="font-size:11.5px;color:var(--ac)">stage: ' + esc(x.stage || 'pending') + '</span>' +
      (x.attempt ? '<span class="mono" style="font-size:11.5px;color:var(--warn)">รอบที่ ' + esc(x.attempt) + '</span>' : '') +
      '</div>' + (x.note ? '<div style="font-size:12.5px;color:var(--mut);margin-top:4px">' + esc(x.note) + '</div>' : '') +
      '</div>';
  }).join('') : '<div class="empty">ไม่มี module ที่กำลังทำอยู่</div>';

  el('runner').innerHTML = [
    ['detail', esc(r.detail || '—')],
    ['heartbeat', esc(r.heartbeat || '—')],
    ['started', esc(r.started || '—')],
    ['pid', esc(r.pid || '—') + (r.stopping ? ' <span class="tag t-me">มีคำสั่งหยุด</span>' : '')],
    ['เฟส 5', d.run_configured ? '<span style="color:var(--ok)">ตั้ง run: แล้ว</span>'
                               : '<span style="color:var(--warn)">ยังไม่ตั้ง run: (จะข้าม)</span>'],
    ['คำถามค้าง', d.questions.length ? '<b>' + d.questions.length + '</b> ไฟล์: ' +
        d.questions.map(esc).join(', ') : '0'],
    ['findings', d.findings ? '<span class="mono" style="font-size:11.5px">' + esc(d.findings) + '</span>' : '—'],
    ['รายงาน', d.report ? '<span class="mono" style="font-size:11.5px">' + esc(d.report) + '</span>' : 'ยังไม่มี'],
    ['log', '<span class="mono" style="font-size:11px">' + esc(r.log || '—') + '</span>']
  ].map(function(x){ return '<dt>' + x[0] + '</dt><dd>' + x[1] + '</dd>'; }).join('');

  var R = d.results;
  if(!R.ok){ el('results').innerHTML = '<div class="err">' + esc(R.why) + '</div>'; }
  else {
    var bk = Object.keys(R.by_bucket || {}).map(function(k){
      var t = TAGB[k] || ['t-tst', k];
      return '<span class="tag ' + t[0] + '">' + t[1] + ' ' + R.by_bucket[k] + '</span>';
    }).join(' ');
    var h = '<div class="stat">' +
      '<div><div class="n ok">' + R.pass + '</div><div class="l">ผ่าน</div></div>' +
      '<div><div class="n bad">' + R.fail + '</div><div class="l">แดง</div></div>' +
      '<div><div class="n">' + R.skip + '</div><div class="l">ข้าม</div></div>' +
      '<div><div class="n ac">' + R.causes_total + '</div><div class="l">สาเหตุราก</div></div>' +
      '<div><div class="n">' + R.suites.length + '</div><div class="l">suite ที่รันแล้ว</div></div>' +
      '<div><div class="n">' + R.never.length + '</div><div class="l">ยังไม่เคยรัน</div></div>' +
      '</div>';
    if(bk) h += '<div style="margin-bottom:10px;display:flex;gap:6px;flex-wrap:wrap">' + bk + '</div>';
    h += '<div class="tw"><table><thead><tr><th>module</th><th>รอบล่าสุด</th>' +
      '<th class="n">ผ่าน</th><th class="n">แดง</th><th class="n">ข้าม</th><th>อายุ</th><th>เทียบรอบก่อน</th></tr></thead><tbody>' +
      R.suites.map(function(s){
        var age = s.age == null ? '—' : (s.age + ' วัน');
        return '<tr><td class="mono">' + esc(s.m) + '</td><td class="mono" style="font-size:11.5px">' +
          esc(s.run) + '<br><span style="color:var(--faint)">' + esc(s.when) + '</span></td>' +
          '<td class="n" style="color:var(--ok)">' + s.p + '</td>' +
          '<td class="n" style="color:' + (s.f ? 'var(--bad)' : 'var(--faint)') + '">' + s.f + '</td>' +
          '<td class="n">' + s.k + '</td>' +
          '<td style="color:' + (s.age > 7 ? 'var(--warn)' : 'var(--mut)') + '">' + age + '</td>' +
          '<td style="color:var(--mut)">' + (s.df == null ? 'ไม่มีรอบก่อน' :
             (s.df === 0 ? 'เท่าเดิม' : 'แดง ' + (s.df > 0 ? '+' : '') + s.df)) + '</td></tr>';
      }).join('') +
      R.never.map(function(s){
        return '<tr><td class="mono">' + esc(s.m) + '</td><td colspan="6" style="color:var(--warn)">ยังไม่เคยรันจริง</td></tr>';
      }).join('') + '</tbody></table></div>';
    if(R.top && R.top.length){
      h += '<div style="margin-top:12px"><table><thead><tr><th>สาเหตุที่กระทบมากสุด</th>' +
        '<th class="n">เคส</th><th>กลุ่ม</th></tr></thead><tbody>' +
        R.top.map(function(x){
          var t = TAGB[x.b] || ['t-tst', x.b];
          return '<tr><td class="mono" style="font-size:11.5px;color:var(--mut)">' + esc(x.msg) + '</td>' +
            '<td class="n">' + x.n + '</td><td><span class="tag ' + t[0] + '">' + t[1] + '</span></td></tr>';
        }).join('') + '</tbody></table></div>';
    }
    el('results').innerHTML = h;
  }

  var T = d.tokens;
  if(T){
    var R2 = T.run, D2 = T.day;
    function f(n){ return n >= 1e6 ? (n/1e6).toFixed(2) + 'M'
                 : n >= 1e3 ? (n/1e3).toFixed(1) + 'k' : String(n); }
    var h2 = '<div class="stat">' +
      '<div><div class="n ac">' + f(R2.output) + '</div><div class="l">output (รอบนี้)</div></div>' +
      '<div><div class="n">' + f(R2.billable_in) + '</div><div class="l">input ที่จ่ายจริง</div></div>' +
      '<div><div class="n">' + f(R2.cache_read) + '</div><div class="l">cache อ่านซ้ำ</div></div>' +
      '<div><div class="n">' + f(R2.total) + '</div><div class="l">รวมทุกชนิด</div></div>' +
      '<div><div class="n">' + f(R2.out_per_hour) + '</div><div class="l">output/ชม.</div></div>' +
      '<div><div class="n">' + R2.calls + '</div><div class="l">ครั้งที่เรียกโมเดล</div></div>' +
      '<div><div class="n bad">$' + (R2.cost_usd || 0).toFixed(2) + '</div><div class="l">มูลค่า (ราคา API เต็ม)</div></div>' +
      '</div>' +
      '<div style="font-size:12.5px;color:var(--mut);margin-bottom:10px">' +
      'รอบนี้ ' + (R2.first || '—') + '–' + (R2.last || '—') + ' (' + (R2.span_hours || 0) + ' ชม.) · ' +
      'ทั้งวันนี้: output <b style="color:var(--ink)">' + f(D2.output) + '</b> · รวม <b style="color:var(--ink)">' +
      f(D2.total) + '</b> · มูลค่า <b style="color:var(--ink)">$' + (D2.cost_usd || 0).toFixed(2) + '</b>' +
      (D2.by_model && D2.by_model.length ? ' · ' + esc(D2.by_model[0].model) : '') +
      '<br>บัญชี Pro/Max คิดเป็นโควตา ไม่ใช่ต่อ token — ตัวเลข $ คือ<b>มูลค่าที่ใช้ไป</b> ' +
      'ถ้าจ่ายราคา API เต็ม ไม่ใช่ยอดที่ถูกเรียกเก็บ · ' +
      '<b>โควตาที่เหลือ</b> อ่านจากเครื่องไม่ได้ — พิมพ์ <span class="mono">/usage</span> ในหน้าต่าง claude</div>';
    if(R2.by_agent && R2.by_agent.length){
      h2 += '<div class="tw"><table><thead><tr><th>subagent (1 ตัว = 1 stage)</th><th>ช่วงเวลา</th>' +
        '<th class="n">นาที</th><th class="n">ครั้ง</th><th class="n">output</th><th class="n">รวม</th></tr></thead><tbody>' +
        R2.by_agent.map(function(g){
          var isOrch = g.src === 'orchestrator';
          return '<tr><td class="mono" style="font-size:11.5px;color:' +
            (isOrch ? 'var(--ac)' : 'var(--mut)') + '">' + esc(g.src) + '</td>' +
            '<td class="mono" style="font-size:11.5px">' + esc(g.from) + '–' + esc(g.to) + '</td>' +
            '<td class="n">' + g.mins + '</td><td class="n">' + g.calls + '</td>' +
            '<td class="n" style="color:var(--ac)">' + f(g.out) + '</td>' +
            '<td class="n">' + f(g.total) + '</td></tr>';
        }).join('') + '</tbody></table></div>';
    }
    el('tok').innerHTML = h2;
  }

  el('next').innerHTML = m.next.length ? '<table><thead><tr><th>module</th><th>risk</th>' +
    '<th class="n">score</th><th class="n">ไฟล์</th></tr></thead><tbody>' +
    m.next.map(function(x){
      var rk = RISK[x.risk] || RISK.low;
      return '<tr><td class="mono">' + esc(x.name) + '</td><td><span class="tag ' + rk[0] + '">' +
        rk[1] + '</span></td><td class="n">' + (x.score == null ? '—' : x.score) +
        '</td><td class="n">' + (x.files == null ? '—' : x.files) + '</td></tr>';
    }).join('') + '</tbody></table>' +
    (m.blocked.length ? '<div style="margin-top:10px;font-size:12.5px;color:var(--bad)">ติดปัญหา ' +
      m.blocked.length + ': ' + m.blocked.map(function(b){return esc(b.name);}).join(', ') + '</div>' : '')
    : '<div class="empty">ไม่มี module ที่ทำต่อได้</div>';

  el('act').innerHTML = d.activity.length ? d.activity.map(function(x){
    return '<li><span>' + esc(x.t) + '</span><b>' + esc(x.p.replace(/^.*?\/(erp_|docs\/|behavior)/, '$1')) + '</b></li>';
  }).join('') : '<li class="empty">ไม่มีไฟล์ถูกเขียนใน 15 นาที</li>';

  var lt = d.log_tail.map(function(l){
    return /^\d{2}-\d{2} [\d:]+\s+(▶|✓|⚠|═══|โควตา|เฟส)/.test(l) ? '<b>' + esc(l) + '</b>' : esc(l);
  }).join('\n');
  var pre = el('log');
  var atBottom = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
  pre.innerHTML = lt || '(ยังไม่มี log)';
  if(atBottom) pre.scrollTop = pre.scrollHeight;
}

setInterval(function(){ if(PROJ) load(); }, 5000);
</script></body></html>"""

DEFAULT_PROJECT = "erp"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default="erp")
    ap.add_argument("--port", type=int, default=8787)
    a = ap.parse_args()
    DEFAULT_PROJECT = a.project
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    print(f"dashboard: http://127.0.0.1:{a.port}/?project={a.project}")
    print("bind 127.0.0.1 เท่านั้น · อ่านอย่างเดียว · Ctrl-C เพื่อปิด")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nปิดแล้ว")
