#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""boot_preflight.py — ai-project-system 기동 전 syntax/import 프리플라이트 + 재시작 폭주 회로차단기.

배경(2026-07-25 실측, 이 저장소 세션): pm2 ecosystem.config.js에 `python -m uvicorn ...`을
직접 지정하고 backend/server.py가 없는 상태(import 즉시 실패)로 강제 재현한 결과, pm2가
`max_restarts=10`을 넘겨서도(`restarts: 11`) 계속 재시작을 시도했고 `unstable restarts`
카운터는 0에서 멈춰 있었다(pm2 7.0.1 실측 — min_uptime 기반 unstable 판정이 초고속
연속실패에서는 증가하지 않는 것으로 관측됨). 즉 **pm2 설정값(max_restarts/min_uptime)
단독으로는 이 환경에서 재시작 폭주를 막지 못함**이 실측으로 확인됐다 — 이 사실을 문서화한다.

이 문제에 대해 AEGIS는 이미 동일 계열 문제(SYS-009, graphify-hub)를 겪었고
`boot_preflight.py`(py_compile+import 프리플라이트) 패턴으로 재발을 막았다 — 그 패턴을
그대로 재사용(CRZ)하되, pm2 카운터에만 의존하지 않도록 **자체 회로차단기**(파일 기반 실패
이력)를 추가한다. pm2가 몇 번을 재시도하든, 짧은 시간 창 안에 실패가 누적되면 이 스크립트가
스스로 긴 지연을 걸어 CPU/로그 폭주를 막는다(pm2 설정과 무관하게 동작 — 이중 안전망).

CLI:
  (인자 없음)   기동 — preflight 통과 시 uvicorn.run() (같은 프로세스, execv 아님 — PID 유지)
  --check       preflight 검사만(exec 안 함). exit 0=OK / 1=FAIL — 테스트·CI용
"""
from __future__ import annotations

import json
import os
import py_compile
import subprocess
import sys
import time
from pathlib import Path

APP = "backend.server:app"
HOST = os.environ.get("AIPS_HOST", "127.0.0.1")
PORT = os.environ.get("AIPS_PORT", "8899")
HERE = Path(__file__).resolve().parent

# 회로차단기 설정 — WINDOW초 안에 FAIL_THRESHOLD회 이상 실패하면 COOLDOWN초 대기 후 재시도.
CIRCUIT_FILE = HERE / ".boot_preflight_failures.json"
WINDOW_SECONDS = 60
FAIL_THRESHOLD = 5
COOLDOWN_SECONDS = 120


def preflight() -> tuple[bool, str]:
    target = HERE / "backend" / "server.py"
    if not target.exists():
        return False, f"{target} 없음"
    try:
        py_compile.compile(str(target), doraise=True)
    except py_compile.PyCompileError as e:
        return False, f"SyntaxError: {e}"
    r = subprocess.run(
        [sys.executable, "-c", "import backend.server"],
        cwd=str(HERE), capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if r.returncode != 0:
        tail = (r.stderr or "").strip().splitlines()[-3:]
        return False, "ImportError: " + " | ".join(tail)
    return True, "OK"


def _read_failures() -> list[float]:
    if not CIRCUIT_FILE.exists():
        return []
    try:
        return json.loads(CIRCUIT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_failures(ts_list: list[float]) -> None:
    CIRCUIT_FILE.write_text(json.dumps(ts_list), encoding="utf-8")


def record_failure() -> None:
    """실패 기록 후, 최근 WINDOW_SECONDS 안 누적 실패가 FAIL_THRESHOLD 이상이면 그 자리에서
    COOLDOWN_SECONDS만큼 대기한다(exit 전에 sleep — pm2가 다음 재시작을 시도하기까지의 실질
    간격을 강제로 늘려 폭주를 억제). **preflight 재시도보다 먼저 대기하지 않는다** — 문제가
    이미 고쳐졌으면 다음 호출의 preflight()가 즉시 통과해 불필요한 지연이 없어야 하므로,
    이 함수는 "이번 실패가 확정된 뒤"에만 호출된다(순서: preflight 시도 → 실패 시에만 기록+대기)."""
    now = time.time()
    failures = _read_failures()
    failures.append(now)
    failures = [t for t in failures if now - t < WINDOW_SECONDS]
    _write_failures(failures[-50:])  # 무한 증가 방지
    if len(failures) >= FAIL_THRESHOLD:
        print(
            f"[BOOT-PREFLIGHT] 회로차단기 트립 — 최근 {WINDOW_SECONDS}s 안 실패 {len(failures)}회 "
            f"(임계 {FAIL_THRESHOLD}) → {COOLDOWN_SECONDS}s 대기 후 exit(pm2 재시작 폭주 자체 억제)",
            flush=True,
        )
        time.sleep(COOLDOWN_SECONDS)
        _write_failures([])  # 쿨다운 후 이력 초기화 — 다음 호출은 즉시 재시도


def record_success() -> None:
    if CIRCUIT_FILE.exists():
        CIRCUIT_FILE.unlink()


def main() -> int:
    check_only = "--check" in sys.argv

    ok, reason = preflight()
    if not ok:
        print(f"[BOOT-PREFLIGHT] FAILED — {reason}", file=sys.stderr, flush=True)
        print("[BOOT-PREFLIGHT] uvicorn 기동 중단 (재시작 폭주 방지)", file=sys.stderr, flush=True)
        record_failure()  # 임계 초과 시 이 안에서 COOLDOWN만큼 대기 후 반환
        return 1

    record_success()
    print(f"[BOOT-PREFLIGHT] OK ({APP}) — uvicorn 기동", flush=True)
    if check_only:
        return 0

    os.chdir(str(HERE))
    import uvicorn
    uvicorn.run(APP, host=HOST, port=int(PORT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
