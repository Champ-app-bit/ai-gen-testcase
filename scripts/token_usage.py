#!/usr/bin/env python3
"""token_usage.py — รวบยอด token ที่สายพานใช้ จาก transcript ของ Claude Code

ใช้:  python3 scripts/token_usage.py [--since "2026-09-01 15:46:25"] [--json]

อ่านจาก ~/.claude/projects/<slug ของ repo เครื่องมือ>/**/*.jsonl ซึ่งมี usage ต่อข้อความจริง
→ ย้อนหลังได้ ไม่ต้องเริ่มนับใหม่ และแยกได้ว่า token หมดไปกับ stage ไหน (attributionSkill)

อ่านแบบ incremental (จำ byte offset ต่อไฟล์) เพราะ dashboard เรียกทุก 5 วินาที
และ transcript ไฟล์ละหลาย MB — อ่านทั้งไฟล์ทุกครั้งจะกินซีพียูทั้งคืนเปล่า ๆ

หมายเหตุ: บัญชี Pro/Max คิดเป็นโควตา ไม่ใช่ต่อ token — ตัวเลขนี้ใช้ดู "หมดไปกับอะไร"
และประมาณว่าโควตาที่เหลือพอทำอีกกี่ module ไม่ใช่ค่าเงิน
"""
import argparse, json, os, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent.parent

# ราคา API first-party ต่อ 1M token (อ้างอิงตาราง Claude API cached 2026-06-24)
# cache write = 1.25x ของ input (TTL 5 นาที) / 2x (TTL 1 ชม.) · cache read = 0.1x ของ input
PRICES = {
    "claude-opus-5":   {"in": 5.00, "out": 25.00},
    "claude-opus-4-8": {"in": 5.00, "out": 25.00},
    "claude-sonnet-5": {"in": 2.00, "out": 10.00},
    "claude-haiku-4-5": {"in": 1.00, "out": 5.00},
    "claude-fable-5":  {"in": 10.00, "out": 50.00},
}
DEFAULT_PRICE = PRICES["claude-opus-5"]


def price_of(model):
    for k, v in PRICES.items():
        if model and model.startswith(k):
            return v
    return DEFAULT_PRICE


def cost_usd(model, inp, out, cw5, cw1h, cr):
    """ค่าเงินถ้าจ่ายราคา API เต็ม — บัญชี Pro/Max คิดเป็นโควตา ตัวเลขนี้คือ 'มูลค่าที่ใช้ไป'"""
    pr = price_of(model)
    return (inp * pr["in"] + out * pr["out"]
            + cw5 * pr["in"] * 1.25 + cw1h * pr["in"] * 2.0
            + cr * pr["in"] * 0.10) / 1_000_000


def transcript_dir(work_dir: Path = TOOL_DIR) -> Path:
    """Claude Code เก็บ transcript ใน ~/.claude/projects/<path ที่แทน / ด้วย ->"""
    slug = str(work_dir.resolve()).replace("/", "-").replace("_", "-")
    return Path.home() / ".claude" / "projects" / slug


class UsageIndex:
    """อ่าน transcript แบบต่อเนื่อง เก็บเฉพาะตัวเลขที่ต้องใช้"""

    def __init__(self, root: Path):
        self.root = root
        self.pos = {}          # path -> byte offset ที่อ่านไปแล้ว
        self.recs = []         # (epoch, skill, sidechain, model, in, out, cache_create, cache_read)
        self.lock = threading.Lock()

    def refresh(self):
        if not self.root.is_dir():
            return
        with self.lock:
            for f in sorted(self.root.rglob("*.jsonl")):
                try:
                    size = f.stat().st_size
                except OSError:
                    continue
                start = self.pos.get(str(f), 0)
                if size < start:            # ไฟล์ถูกเขียนทับ/หมุน — อ่านใหม่ทั้งไฟล์
                    start = 0
                if size == start:
                    continue
                try:
                    with f.open("r", encoding="utf-8", errors="replace") as fh:
                        fh.seek(start)
                        data = fh.read()
                        # บรรทัดสุดท้ายอาจถูกเขียนค้างอยู่ — กันไว้ อ่านรอบหน้า
                        cut = data.rfind("\n")
                        if cut < 0:
                            continue
                        consumed = cut + 1
                        src = f.stem if f.stem.startswith("agent-") else "orchestrator"
                        for line in data[:cut].splitlines():
                            self._add(line, src)
                        self.pos[str(f)] = start + len(data[:consumed].encode("utf-8"))
                except OSError:
                    continue

    def _add(self, line: str, src: str = "?"):
        line = line.strip()
        if not line or '"usage"' not in line:
            return
        try:
            d = json.loads(line)
        except ValueError:
            return
        if d.get("type") != "assistant":
            return
        m = d.get("message") or {}
        u = m.get("usage") or {}
        if not u:
            return
        ts = d.get("timestamp") or ""
        try:
            ep = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            ep = 0.0
        self.recs.append((
            ep,
            d.get("attributionSkill") or ("subagent" if d.get("isSidechain") else "main"),
            bool(d.get("isSidechain")),
            m.get("model") or "?",
            int(u.get("input_tokens") or 0),
            int(u.get("output_tokens") or 0),
            int(u.get("cache_creation_input_tokens") or 0),
            int(u.get("cache_read_input_tokens") or 0),
            src,
            int((u.get("cache_creation") or {}).get("ephemeral_5m_input_tokens") or 0),
            int((u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0),
        ))

    def summary(self, since_epoch=None):
        self.refresh()
        with self.lock:
            recs = [r for r in self.recs if since_epoch is None or r[0] >= since_epoch]
        if not recs:
            return {"calls": 0, "input": 0, "output": 0, "cache_create": 0, "cache_read": 0,
                    "billable_in": 0, "total": 0, "by_skill": [], "by_model": [],
                    "by_agent": [], "by_hour": [], "first": None, "last": None,
                    "span_hours": 0, "out_per_hour": 0, "cost_usd": 0.0,
                    "cache_write_5m": 0, "cache_write_1h": 0}
        tot = {"calls": len(recs), "input": 0, "output": 0, "cache_create": 0, "cache_read": 0}
        skill, model, hour, agent = {}, {}, {}, {}
        cw5 = cw1h = 0.0; cost = 0.0
        for ep, sk, side, md, i, o, cc, cr, src, c5, c1 in recs:
            cw5 += c5; cw1h += c1
            # ถ้า cache_creation ไม่แยก TTL มา ให้ถือเป็น 5 นาที (ค่าเริ่มต้นของ API)
            cost += cost_usd(md, i, o, c5 or (cc if not c1 else 0), c1, cr)
            tot["input"] += i; tot["output"] += o
            tot["cache_create"] += cc; tot["cache_read"] += cr
            s = skill.setdefault(sk, {"skill": sk, "calls": 0, "input": 0, "output": 0,
                                      "cache_create": 0, "cache_read": 0})
            s["calls"] += 1; s["input"] += i; s["output"] += o
            s["cache_create"] += cc; s["cache_read"] += cr
            model[md] = model.get(md, 0) + i + o + cc + cr
            hk = datetime.fromtimestamp(ep).strftime("%H:00") if ep else "?"
            h = hour.setdefault(hk, {"h": hk, "out": 0, "total": 0})
            h["out"] += o; h["total"] += i + o + cc + cr
            g = agent.setdefault(src, {"src": src, "calls": 0, "out": 0, "total": 0,
                                       "first": ep, "last": ep})
            g["calls"] += 1; g["out"] += o; g["total"] += i + o + cc + cr
            if ep:
                g["first"] = min(g["first"] or ep, ep); g["last"] = max(g["last"] or ep, ep)
        # cache_create คิดเป็น input ที่จ่ายจริง · cache_read ถูกกว่ามาก แต่ยังนับรวมใน total
        tot["cache_write_5m"] = int(cw5); tot["cache_write_1h"] = int(cw1h)
        tot["cost_usd"] = round(cost, 2)
        tot["billable_in"] = tot["input"] + tot["cache_create"]
        tot["total"] = tot["input"] + tot["output"] + tot["cache_create"] + tot["cache_read"]
        eps = [r[0] for r in recs if r[0]]
        first, last = (min(eps), max(eps)) if eps else (None, None)
        span_h = ((last - first) / 3600) if (first and last and last > first) else 0
        return {
            **tot,
            "by_skill": sorted(skill.values(), key=lambda x: -(x["output"] + x["cache_create"])),
            "by_model": [{"model": k, "total": v} for k, v in sorted(model.items(), key=lambda x: -x[1])],
            "by_agent": [{**g,
                          "from": datetime.fromtimestamp(g["first"]).strftime("%H:%M") if g["first"] else "?",
                          "to": datetime.fromtimestamp(g["last"]).strftime("%H:%M") if g["last"] else "?",
                          "mins": int(((g["last"] or 0) - (g["first"] or 0)) / 60)}
                         for g in sorted(agent.values(), key=lambda x: -x["out"])],
            "by_hour": [hour[k] for k in sorted(hour)],
            "first": datetime.fromtimestamp(first).strftime("%H:%M:%S") if first else None,
            "last": datetime.fromtimestamp(last).strftime("%H:%M:%S") if last else None,
            "span_hours": round(span_h, 2),
            "out_per_hour": int(tot["output"] / span_h) if span_h > 0.05 else 0,
        }


_IDX = None


def index():
    global _IDX
    if _IDX is None:
        _IDX = UsageIndex(transcript_dir())
    return _IDX


def fmt(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help='เช่น "2026-09-01 15:46:25" (เวลาเครื่อง)')
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    since = None
    if a.since:
        try:
            since = datetime.strptime(a.since, "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            sys.exit('รูปแบบ --since ต้องเป็น "YYYY-MM-DD HH:MM:SS"')
    d = index().summary(since)
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=2)); return
    if not d["calls"]:
        print(f"ไม่พบ transcript ใน {transcript_dir()}"); return
    print(f"transcript: {transcript_dir()}")
    print(f"ช่วงเวลา  : {d['first']} → {d['last']} ({d['span_hours']} ชม.) · {d['calls']} ครั้งที่เรียกโมเดล")
    print(f"input     : {fmt(d['input'])}  (จ่ายจริงรวม cache_create = {fmt(d['billable_in'])})")
    print(f"output    : {fmt(d['output'])}  ({fmt(d['out_per_hour'])}/ชม.)")
    print(f"cache     : สร้าง {fmt(d['cache_create'])} · อ่านซ้ำ {fmt(d['cache_read'])}")
    print(f"รวมทุกชนิด: {fmt(d['total'])}")
    print(f"cache write: 5 นาที {fmt(d['cache_write_5m'])} · 1 ชม. {fmt(d['cache_write_1h'])}")
    print(f"\nมูลค่าที่ใช้ไป (ถ้าจ่ายราคา API เต็ม): ${d['cost_usd']:,.2f}")
    print("  บัญชี Pro/Max คิดเป็นโควตา ไม่ใช่ต่อ token — ตัวเลขนี้คือมูลค่า ไม่ใช่ยอดที่ถูกเรียกเก็บ")
    print("\nแยกตาม stage (เรียงตาม output+cache_create ซึ่งคือส่วนที่กินโควตาจริง):")
    for s in d["by_skill"]:
        print(f"  {s['skill']:<22} {s['calls']:>4} ครั้ง · out {fmt(s['output']):>7} · "
              f"cache_create {fmt(s['cache_create']):>7} · cache_read {fmt(s['cache_read']):>7}")
    print("\nแยกตาม subagent (1 ตัว = 1 stage ของสายพาน):")
    for g in d["by_agent"]:
        print(f"  {g['src']:<26} {g['from']}–{g['to']} ({g['mins']:>3} นาที) · "
              f"{g['calls']:>4} ครั้ง · out {fmt(g['out']):>7} · รวม {fmt(g['total']):>7}")
    print("\nแยกตามโมเดล:")
    for m in d["by_model"]:
        print(f"  {m['model']:<24} {fmt(m['total'])}")


if __name__ == "__main__":
    main()
