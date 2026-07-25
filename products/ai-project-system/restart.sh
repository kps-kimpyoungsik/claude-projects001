#!/usr/bin/env bash
# ai-project-system 재기동 스크립트 (POC 단계 — 수동 기동, pm2/systemd 등 상시 서비스화는 미적용)
#
# backend/server.py(FastAPI)가 API + frontend/ 정적 서빙(StaticFiles, html=True)을
# 한 프로세스로 함께 처리하므로, 이 스크립트 하나로 프론트+백엔드가 같이 뜬다.
# 참고: --workers를 늘리지 말 것(§DRL-1) — requirements_api._write_lock이 단일
# 프로세스 안에서만 쓰기 경합을 막는다.
set -euo pipefail

PORT="${PORT:-8899}"
LOG_FILE="server.log"
PID_FILE=".server.pid"

cd "$(dirname "$0")"

start_server() {
  echo "[restart] uvicorn backend.server:app --port $PORT 기동 (frontend/ 동시 서빙)"
  nohup python -m uvicorn backend.server:app --host 127.0.0.1 --port "$PORT" \
    > "$LOG_FILE" 2>&1 &
}

wait_healthy() {
  local tries=0
  local max_tries=15
  while [ "$tries" -lt "$max_tries" ]; do
    if curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '^200$'; then
      echo "[restart] 기동 확인: http://127.0.0.1:$PORT/health -> 200"
      echo "[restart] 화면: http://127.0.0.1:$PORT/ (root -> /views/index.html)"
      # git-bash의 `&` job PID는 실제 리스닝 프로세스와 다를 수 있어(MSYS 래핑),
      # netstat으로 실제 포트 점유 PID를 다시 조회해 기록한다(다음 재기동의 fallback용).
      local real_pid
      real_pid=$(netstat -ano 2>/dev/null | grep "LISTENING" | grep ":$PORT " | awk '{print $NF}' | sort -u | head -1 || true)
      [ -n "${real_pid:-}" ] && echo "$real_pid" > "$PID_FILE"
      return 0
    fi
    tries=$((tries + 1))
    sleep 1
  done
  echo "[restart] 실패 — $LOG_FILE 확인 필요" >&2
  return 1
}

"$(dirname "$0")/stop.sh"
start_server
wait_healthy
