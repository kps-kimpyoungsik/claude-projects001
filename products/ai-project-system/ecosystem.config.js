// [WORK-B 2026-07-25, 재시작폭주 실측 후 수정] 최초 버전은 uvicorn을 pm2가 직접 기동했으나,
// 기동 실패(예: server.py 부재/ImportError)를 강제 재현한 결과 pm2 7.0.1에서 max_restarts=10을
// 넘겨서도(restarts:11) 계속 재시도하고 unstable_restarts가 0에서 멈추는 현상을 실측 확인함
// (§W-5 물증 — pm2 describe 원문). AEGIS SYS-009(graphify-hub boot_preflight.py) 패턴을
// 재사용(CRZ)하되, pm2 카운터를 신뢰하지 않는 자체 회로차단기(boot_preflight.py 내부, 파일
// 기반 실패이력)를 추가 — pm2 설정과 무관하게 폭주를 억제한다. --workers는 절대 지정하지
// 않는다(§DRL-1 — requirements_api._write_lock이 단일 프로세스 안에서만 쓰기 경합을 막음).
module.exports = {
  apps: [{
    name: "ai-project-system",
    script: "python",
    args: ["boot_preflight.py"],
    interpreter: "none",
    windowsHide: true,
    cwd: __dirname,
    env: { PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" },
    autorestart: true,
    max_restarts: 10,
    min_uptime: 30000,
    restart_delay: 3000,
    exp_backoff_restart_delay: 100,
    kill_timeout: 10000,
    out_file: "server.log",
    error_file: "server.error.log"
  }]
}
