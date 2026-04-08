# voice-sample — 작업 로그

> 마지막 작업: 2026-04-08 | 상태: **진행중**

## 최근 작업 (최신순)

### 2026-04-08 (3차)
- **STT 성능 향상 전략 구현 (3단계)**
  - `stt_server.py`: `vad_filter=True` (음성 구간만 추론, 무음 클립 속도↑)
  - `stt_server.py`: `STT_FAST_MODE=1` 환경변수 — CPU beam=1/best_of=1 (약 5배 빠름, WER +3~5%)
  - `start_stt_workers.sh` / `.bat` 신규: 병렬 워커 N개 기동 스크립트 (9001~900N)
  - `index.html`: ⚡ 하이브리드 모드 라디오 버튼 추가
  - `src/app.js`: `engine='hybrid'` — Web Speech API(즉시) + Whisper(교정) 동시 실행
  - E2E: `test_e2e_pipeline.py` **38/38 PASS** ✅ (회귀 없음)

### 2026-04-08 (2차)
- **Phase 1 Headless API 구현 완료 + E2E 회귀 검증**
  - `server.go`: MonitorConfig 구조체 + loadMonitorConfig() (HEADLESS/API_KEY/WS_BROADCAST)
  - `server.go`: authMiddleware, handleDirectSTT (POST /api/stt), handleMonitorConfig (GET/POST /api/monitor/config)
  - `server.go`: broadcastJSON() — WsBroadcast 플래그 조건부 브로드캐스트
  - `server.go`: HEADLESS=1 시 Static 파일 서빙 OFF, "/" → JSON 응답, 기타 404
  - `tests/test_e2e_stt_protocol.py`: 동적 timeout (Go 서버 방식: estSec×60+120), FAST_STT=1 지원
  - E2E 결과: `test_e2e_pipeline.py` **38/38 PASS** ✅ | `test_e2e_stt_protocol.py` **18/18 PASS** (FAST_STT=1)
  - `API_HEADLESS_DESIGN.md` 설계 계획서 신규 생성 (Phase 1~3 설계 포함)

### 2026-04-08
- **보고서 파이프라인 구현** (transcript → LLM → doc → UI)
  - `pipeline/post_pipeline.py` 신규: JSON 이벤트 스트림으로 Go 서버와 통신
  - `server.go`: `POST /api/summary`, `GET /api/summary/status`, `GET /api/docs/download`, `GET /api/docs/view` 추가
  - `server.go`: `runPostPipeline()` 고루틴 — Python subprocess + WS 브로드캐스트
  - `test-viz.html`: 보고서 패널, 파이프라인 진행 단계, 보고서 뷰어 모달 추가
  - E2E 검증: 49초 내 transcript → summary.md + .docx 생성 확인
- **STT 파이프라인 버그 수정**
  - `server.go`: 기본 STT_HOSTS를 9001만으로 변경 (Worker-0의 9002 실패 문제 해결)
  - `server.go`: `hostForAttempt` + `transcribeBytesOnHost` — 재시도 시 호스트 순환
  - `stt_server.py`: `asyncio.to_thread()` — 이벤트 루프 블로킹 해결
  - E2E: `test_e2e_pipeline.py` 38/38 PASS, `test_e2e_stt_protocol.py` 23/23 PASS

### 2026-04-07
- `src/voice-stt.js` ScriptProcessorNode 방식으로 전면 재작성 (MediaRecorder 제거)
- `test-viz.html` VAD 카운팅·Pre-Buffer 표시 수정
- `tests/test_e2e_pipeline.py` 신규 (T01~T11, 38개 검증 항목)
- `tests/test_e2e_stt_protocol.py` 신규 (T01~T09, 23개 검증 항목)
- `CLAUDE.md` E2E 테스트 정책 추가

## 다음 TODO
- [ ] Phase 2: /api/v1/ 버전닝된 엔드포인트 구현 (sessions CRUD, WAV upload, SSE)
- [ ] 실제 브라우저에서 보고서 패널 UI 동작 확인
- [ ] 실제 회의 녹음으로 전체 파이프라인 검증 (긴 텍스트 map-reduce 요약)
- [ ] summary.md 뷰어에서 Markdown 렌더링 추가 (현재 plain text)
- [ ] /simplify 실행하여 코드 정리

## 주의사항
- 서버 시작 시 환경변수 주의: HEADLESS=1, WS_BROADCAST=0으로 시작하면 E2E 테스트가 실패함
  → 테스트 전 `curl -X POST /api/monitor/config -d '{"headless":false,"ws_broadcast":true}'`로 리셋
- CPU-only 환경 (large-v3-turbo): STT 추론당 ~135s 소요
  → E2E pipeline: POLL_TIMEOUT=300 필수 | STT protocol: FAST_STT=1 권장

## 참조
→ 서버: `./voice-server.exe` (포트 8090) + `python stt_server.py` (포트 9001)
→ 테스트: `POLL_TIMEOUT=300 python tests/test_e2e_pipeline.py`
→ 파이프라인: `pipeline/post_pipeline.py --transcript ... --topic ... --doctype docx --outdir ...`
→ API: `POST /api/summary?topic=xxx&doctype=docx`
