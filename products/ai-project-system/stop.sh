#!/usr/bin/env bash
# ai-project-system 종료 전용 스크립트 (restart.sh에서 분리 — 재기동 없이 순수 종료만 필요할 때)
set -euo pipefail

PORT="${PORT:-8899}"
PID_FILE=".server.pid"

cd "$(dirname "$0")"

# 1) 이전 실행에서 남긴 PID 파일 우선 정리
if [ -f "$PID_FILE" ]; then
  old_pid=$(cat "$PID_FILE" 2>/dev/null || true)
  if [ -n "${old_pid:-}" ]; then
    taskkill //F //PID "$old_pid" >/dev/null 2>&1 || true
  fi
  rm -f "$PID_FILE"
fi

# 2) 그래도 포트를 점유 중인 프로세스가 있으면(예: 터미널 직접 실행분) 실측으로 찾아 종료
listen_pid=$(netstat -ano 2>/dev/null | grep "LISTENING" | grep ":$PORT " | awk '{print $NF}' | sort -u | head -1 || true)
if [ -n "${listen_pid:-}" ]; then
  echo "[stop] 포트 $PORT 점유 중인 PID $listen_pid 종료"
  taskkill //F //PID "$listen_pid" >/dev/null 2>&1 || true
  sleep 1
  echo "[stop] 종료 완료"
else
  echo "[stop] 포트 $PORT 이미 비어있음 (실행 중인 서버 없음)"
fi
