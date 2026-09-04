#!/usr/bin/env python3
"""mark_inchat.py — เขียน logs/<project>.state ให้ dashboard เห็นรอบที่ "เดินสายพานในแชท"

ใช้:  python3 scripts/mark_inchat.py <project> <phase> [detail]
      python3 scripts/mark_inchat.py <project> --clear

ทำไมต้องมี: `./testgen` (daemon) เขียน .state เองผ่าน mark() แต่โหมด PILOT เดินใน
Claude Code ซึ่งไม่มี daemon → dashboard เลยขึ้น "ไม่ได้รัน" ทั้งที่งานเดินอยู่

pid ที่เขียนลงไปคือ **process ของ claude session ที่เป็น orchestrator จริง** (ไล่ขึ้นจาก
parent chain ของตัวเอง) ไม่ใช่ pid ปลอม → ป้าย "ทำงานอยู่" ของ dashboard จะพลิกเป็น
"ไม่ได้รัน" เองทันทีที่ปิด session ซึ่งตรงความจริง
"""
import os, sys
from datetime import datetime
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = TOOL_DIR / "logs"


def orchestrator_pid():
    """ไล่ parent ขึ้นไปหา process ชื่อ claude — คือ session ที่กำลังสั่งงาน"""
    pid = os.getpid()
    for _ in range(12):
        try:
            st = (Path(f"/proc/{pid}/stat").read_text()).rsplit(")", 1)
            comm = st[0].split("(", 1)[1]
            ppid = int(st[1].split()[1])
        except Exception:
            return None
        if comm == "claude":
            return pid
        if ppid <= 1:
            return None
        pid = ppid
    return None


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    project, phase = sys.argv[1], sys.argv[2]
    detail = sys.argv[3] if len(sys.argv) > 3 else ""
    LOG_DIR.mkdir(exist_ok=True)
    state = LOG_DIR / f"{project}.state"

    if phase == "--clear":
        state.unlink(missing_ok=True)
        print(f"ลบ {state} แล้ว — dashboard จะกลับไปขึ้น 'ไม่ได้รัน'")
        return

    log = LOG_DIR / f"{project}-inchat.log"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pid = orchestrator_pid()

    # started: คงค่าเดิมไว้ถ้ามี .state อยู่แล้ว (เริ่มรอบนี้ตอนไหนต้องไม่ถูกรีเซ็ตทุก stage)
    started = now
    if state.exists():
        for line in state.read_text(encoding="utf-8").splitlines():
            if line.startswith("started=") and line[8:].strip():
                started = line[8:].strip()

    state.write_text(
        f"project={project}\nphase={phase}\ndetail={detail}\nheartbeat={now}\n"
        f"started={started}\npid={pid or ''}\nlog={log}\n", encoding="utf-8")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"{now}  {phase}  {detail}\n")
    print(f"✓ {state.name}: phase={phase} pid={pid} · log={log.name}")


if __name__ == "__main__":
    main()
