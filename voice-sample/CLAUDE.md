# voice-sample 프로젝트 지침

## 테스트 정책 (MANDATORY — 예외 없음)

> **이 정책은 모든 기능 개발·수정·버그 수정 후 반드시 적용된다.**

### E2E 워크플로우 테스트 원칙

**"테스트란 시작부터 끝까지다."**

멀티 스텝 기능은 단일 API 호출이나 첫 단계만 테스트하는 것은 **테스트가 아니다.**
반드시 전체 워크플로우를 처음부터 끝까지 검증해야 한다.

```
[금지]
  ❌ 첫 단계만 테스트 (예: POST /api/recordings 성공 확인만)
  ❌ 개별 함수 단독 테스트로 통합 테스트 대체
  ❌ "첫 번째 세그먼트는 되니까 OK" 판단

[필수]
  ✅ 입력(마이크/WAV) → 처리 → 최종 출력(transcript.txt) 전 구간 검증
  ✅ 단계 전환 검증: queued → processing → done 상태 변화 확인
  ✅ N회 반복 검증: 1회가 아닌 최소 3개 세그먼트로 파이프라인 지속성 확인
  ✅ 세션 생명주기 검증: start → 녹음 → stop → 최종 상태
```

### Voice Pipeline 전체 워크플로우

```
[Browser]
  ① Mic → ScriptProcessorNode → Raw PCM
  ② VAD → Pre-buffer 롤링
  ③ 발화 감지 → Active buffer 누적
  ④ 침묵 확정 → WAV 인코딩 (PCM → ArrayBuffer)
  ⑤ POST /api/recordings?topic=xxx

[Go Server]
  ⑥ WAV 수신 → filename 생성 → sttQueue push
  ⑦ sttWorker → WebSocket → Python STT 서버 전송

[Python STT Server]
  ⑧ config → ready → WAV → 화자식별 → 텍스트 추출
  ⑨ result 반환 {text, speaker, segments}

[Go Server — 후처리]
  ⑩ applyChunkBoundary → 완결 문장 판별
  ⑪ appendAndRewrite → transcript.txt (시간순 정렬 + 화자 병합)
  ⑫ /ws/live 브로드캐스트
  ⑬ status → "done"

[종료]
  ⑭ POST /api/recordings/stop → flushPending → 미완성 문장 기록
  ⑮ 최종 transcript.txt 완결성 확인
```

### E2E 테스트 실행 의무

| 변경 종류 | 실행 필수 테스트 |
|---------|--------------|
| voice-stt.js 수정 | `test_e2e_wav_chain.py` + `test_e2e_pipeline.py` |
| stt_server.py 수정 | `test_e2e_stt_protocol.py` + `test_e2e_pipeline.py` |
| server.go 수정 | `test_e2e_pipeline.py` (전체) |
| test-viz.html 수정 | 브라우저 E2E 수동 확인 (전체 워크플로우) |
| 버그 수정 | 해당 단계를 포함한 E2E 테스트 전체 |

### 테스트 파일 목록

```
tests/
  test_c1_c2.py              ← C1(Silero-VAD) + C2(화자식별) 단위 테스트
  test_e2e_pipeline.py       ← Go 서버 + Python STT 전체 파이프라인 E2E
  test_e2e_stt_protocol.py   ← STT WebSocket 프로토콜 E2E (다중 세그먼트)
```

## 프로젝트 구조

```
voice-sample/
  server.go          ← Go HTTP + WebSocket 서버 (포트 8090)
  stt_server.py      ← Python Whisper STT 서버 (포트 9001/9002)
  src/
    voice-stt.js     ← 브라우저 VAD + PCM 캡처 (ScriptProcessorNode)
    app.js           ← 메인 앱 로직
  index.html         ← 메인 UI
  test-viz.html      ← 파이프라인 시각화 페이지
  pipeline/
    batch_stt.py     ← 배치 STT 처리
  tests/             ← 테스트 파일
```

## 서버 실행

```bash
# Python STT 서버 (터미널 1)
python stt_server.py

# Go 서버 (터미널 2)
go run server.go

# 테스트 실행
python tests/test_e2e_pipeline.py
python tests/test_e2e_stt_protocol.py
```

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SAVE_MODE` | `memory` | `memory`/`text`/`full` |
| `STT_SCENARIO` | `quiet` | `quiet`/`noisy`/`interview`/`debate`/`phone` |
| `ENABLE_SILERO_VAD` | `0` | Silero-VAD 활성화 |
| `ENABLE_RESEMBLYZER` | `0` | resemblyzer 화자식별 활성화 |
| `ENABLE_PYANNOTE` | `0` | pyannote 화자분리 활성화 |
| `STT_HOSTS` | `ws://localhost:9001,ws://localhost:9002` | STT 서버 목록 |
