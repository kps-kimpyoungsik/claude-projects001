# Voice Pipeline — Headless API 분기 설계 계획서

> 작성일: 2026-04-08 | 대상 브랜치: main | 우선순위: 기능 보존 + API 독립

---

## 1. 현황 분석

### 1.1 현재 아키텍처 (문제)

```
[외부 요청]        [브라우저 UI]
     │                  │
     └──────┬───────────┘
            ▼
     Go Server :8090
     ├─ /api/* (REST)         ← UI/API 혼재, 분리 기준 없음
     ├─ /ws/live              ← UI 전용 브로드캐스트
     ├─ /ws/stt               ← WebAudio 전용
     └─ / (정적 파일 서빙)    ← HTML 항상 노출
            │
            ▼
     Python STT Server :9001  ← WebSocket만, HTTP 없음
     
     FastAPI :8000            ← 구현됨, 현재 미기동 (미통합)
```

### 1.2 핵심 문제

| # | 문제 | 영향 |
|---|------|------|
| P1 | UI/API 분리 기준 없음 | 외부 API 호출 시 HTML 노출 |
| P2 | SAVE_MODE 기본값 = memory | API 호출 시 파일이 남지 않음 |
| P3 | /ws/live 항상 브로드캐스트 | API 구독자 없을 때도 오버헤드 |
| P4 | post_pipeline.py subprocess 방식 | API 응답 지연, 에러 핸들링 취약 |
| P5 | FastAPI(api/) 미통합 | 풍부한 기능 사장 |
| P6 | WAV 업로드 방식 미지원 | 브라우저 WebAudio 전용 구조 |

---

## 2. 목표 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│  외부 API 클라이언트 (앱/서비스)   브라우저 UI (모니터링)       │
│         │                                    │                   │
│    REST + WebSocket                    REST + WebSocket          │
│         │                                    │                   │
│         └──────────────┬────────────────────┘                   │
│                        ▼                                         │
│             Go Server :8090                                      │
│             ├─ HEADLESS=1 모드  ───→ UI 서빙 OFF                │
│             │   ├─ /api/v1/*    ← 버전닝된 REST API              │
│             │   ├─ /ws/events   ← 이벤트 스트림 (SSE or WS)     │
│             │   └─ /ws/stt      ← WAV 업로드 STT                │
│             │                                                     │
│             └─ HEADLESS=0 (기본) ───→ UI 서빙 ON                │
│                 ├─ /api/v1/* (동일)                              │
│                 ├─ /ws/live     ← 실시간 패널                    │
│                 └─ / → index.html, test-viz.html                │
│                        │                                         │
│                        ▼                                         │
│             Python STT Server :9001                              │
│             (변경 없음 — 이미 독립적)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 구현 계획 (단계별)

### Phase 1 — 즉시 적용 가능 (충돌 없는 분기, 1~2시간)

**목표:** 환경변수 하나로 UI ON/OFF 분기. 기존 동작 100% 유지.

#### 3.1.1 환경변수 추가

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `HEADLESS` | `0` | `1` = UI 서빙 OFF, API 전용 모드 |
| `API_KEY` | `` | API 인증 키 (비어있으면 인증 없음) |
| `SAVE_MODE` | `memory` | headless 기본값은 `text` 권장 |

#### 3.1.2 server.go 분기 (Static 파일 서빙 조건부)

```go
// 현재:
mux.Handle("/", http.FileServer(http.Dir(".")))

// 변경 후:
headless := os.Getenv("HEADLESS") == "1"
if !headless {
    mux.Handle("/", http.FileServer(http.Dir(".")))
} else {
    mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path == "/" {
            w.Header().Set("Content-Type", "application/json")
            json.NewEncoder(w).Encode(map[string]string{
                "mode": "headless",
                "docs": "http://localhost:8090/api/docs",
            })
        } else {
            http.NotFound(w, r)
        }
    })
}
```

#### 3.1.3 /ws/live 조건부 브로드캐스트

```go
// 현재: 항상 브로드캐스트
hub.broadcast(payload)

// 변경 후: 구독자 있을 때만
if hub.HasClients() || !headless {
    hub.broadcast(payload)
}
```

#### 3.1.4 API Key 인증 미들웨어 (선택적)

```go
func authMiddleware(next http.HandlerFunc) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        apiKey := os.Getenv("API_KEY")
        if apiKey == "" { next(w, r); return } // 인증 없음 모드
        
        key := r.Header.Get("X-API-Key")
        if key == "" { key = r.URL.Query().Get("api_key") }
        if key != apiKey {
            http.Error(w, `{"error":"unauthorized"}`, 401)
            return
        }
        next(w, r)
    }
}

// 적용:
mux.HandleFunc("/api/recordings", authMiddleware(handleRecordings))
```

#### 3.1.5 WAV 파일 업로드 직접 STT 엔드포인트 추가

```
POST /api/stt
Content-Type: multipart/form-data
  file: <WAV 바이너리>
  topic: "회의"
  scenario: "quiet"

→ 즉시 STT 처리 → JSON 반환
  {"text": "...", "speaker": "화자1", "segments": [...]}
```

**현재 코드 재활용:** `transcribeBytesOnHost()` 직접 호출

---

### Phase 2 — API 구조화 (v1 네임스페이스, 3~4시간)

**목표:** 외부 공개 API를 `/api/v1/` 하위로 정리. 기존 `/api/` 유지(deprecated).

#### 3.2.1 엔드포인트 v1 매핑

| 기존 | v1 신규 | 변경점 |
|------|---------|--------|
| `POST /api/recordings/start` | `POST /api/v1/sessions` | topic 자동생성 옵션 추가 |
| `POST /api/recordings` | `POST /api/v1/sessions/{id}/audio` | multipart WAV 업로드 |
| `GET /api/recordings` | `GET /api/v1/sessions/{id}/files` | 페이징 추가 |
| `POST /api/recordings/stop` | `POST /api/v1/sessions/{id}/stop` | |
| `POST /api/summary` | `POST /api/v1/sessions/{id}/report` | doctype 파라미터 |
| `GET /api/summary/status` | `GET /api/v1/sessions/{id}/report/status` | |
| `GET /api/docs/download` | `GET /api/v1/sessions/{id}/report/download` | |
| `GET /api/storage/stats` | `GET /api/v1/stats` | |

#### 3.2.2 세션 ID 중심 설계

```
1. POST /api/v1/sessions
   → {"session_id": "sess_20260408_abc123", "topic": "회의"}

2. POST /api/v1/sessions/{session_id}/audio
   Body: WAV binary (Content-Type: audio/wav)
   → {"file": "rec_120000_000.wav", "status": "queued"}

3. GET  /api/v1/sessions/{session_id}/status
   → {"files": [{...}], "transcript": "...", "done_count": 3}

4. POST /api/v1/sessions/{session_id}/stop
   → {"status": "stopped"}

5. POST /api/v1/sessions/{session_id}/report?doctype=docx
   → {"status": "started"}

6. GET  /api/v1/sessions/{session_id}/report/status
   → {"status": "done", "doc_file": "20260408_회의.docx"}

7. GET  /api/v1/sessions/{session_id}/report/download
   → <파일 바이너리>
```

#### 3.2.3 Server-Sent Events (SSE) 추가

WebSocket 대신 HTTP SSE로 이벤트 수신 (방화벽 친화적):

```
GET /api/v1/sessions/{session_id}/events
Accept: text/event-stream

data: {"type":"stt_result","text":"...","speaker":"화자1"}
data: {"type":"pipeline_progress","step":"summarizing"}
data: {"type":"pipeline_done","doc_file":"20260408_회의.docx"}
```

---

### Phase 3 — FastAPI 통합 (선택, 장기)

**목표:** Go 서버의 API 역할을 FastAPI로 이관. Go는 STT 워커 역할만 유지.

```
FastAPI :8000
├─ /api/v1/* (현재 Go에서 담당)
├─ /ws/events (SSE 또는 WS)
└─ /docs (Swagger UI 자동 생성)

Go Server :8090 (역할 축소)
├─ sttWorker (goroutine)
├─ /ws/stt (WebSocket STT 프록시)
└─ /ws/live (브라우저 실시간 패널 전용)
```

---

## 4. UI/UX 모니터링 옵션 관리

### 4.1 런타임 제어

`/api/mode` 엔드포인트를 확장하여 모니터링 옵션 관리:

```
GET  /api/monitor/config
POST /api/monitor/config
  Body: {
    "ui_enabled":       true,   // UI 서빙 ON/OFF
    "ws_live_enabled":  true,   // /ws/live 브로드캐스트 ON/OFF
    "auth_required":    false,  // API 키 인증 ON/OFF
    "save_mode":        "text", // memory / text / full
    "headless":         false   // headless 모드 전체 토글
  }
```

### 4.2 환경변수 → 런타임 오버라이드 흐름

```
환경변수 (서버 시작 시 기본값 결정)
        │
        ▼
monitorConfig (전역 struct, sync.Mutex 보호)
        │
        ├─ API 요청 처리 시 참조
        ├─ /api/monitor/config POST로 런타임 변경
        └─ /ws/live 브로드캐스트 여부 결정
```

### 4.3 모니터링 모드 프리셋

```bash
# 기본 (UI + API 함께)
HEADLESS=0 ./voice-server.exe

# Headless API 전용
HEADLESS=1 SAVE_MODE=text API_KEY=my-secret ./voice-server.exe

# API + 경량 모니터링 (WS 브로드캐스트만 OFF)
HEADLESS=0 WS_BROADCAST=0 ./voice-server.exe
```

---

## 5. 외부 API 연계 예시 (완성 후)

### 5.1 Python 클라이언트

```python
import requests

BASE = "http://voice-server:8090"
HEADERS = {"X-API-Key": "my-secret"}

# 1. 세션 생성
r = requests.post(f"{BASE}/api/v1/sessions",
    json={"topic": "고객상담"}, headers=HEADERS)
session_id = r.json()["session_id"]

# 2. WAV 업로드
with open("recording.wav", "rb") as f:
    requests.post(f"{BASE}/api/v1/sessions/{session_id}/audio",
        data=f, headers={**HEADERS, "Content-Type": "audio/wav"})

# 3. 종료
requests.post(f"{BASE}/api/v1/sessions/{session_id}/stop", headers=HEADERS)

# 4. 보고서 생성
requests.post(f"{BASE}/api/v1/sessions/{session_id}/report",
    params={"doctype": "docx"}, headers=HEADERS)

# 5. 상태 폴링
import time
while True:
    st = requests.get(f"{BASE}/api/v1/sessions/{session_id}/report/status",
        headers=HEADERS).json()
    if st["status"] == "done": break
    time.sleep(3)

# 6. 다운로드
doc = requests.get(f"{BASE}/api/v1/sessions/{session_id}/report/download",
    headers=HEADERS)
open("output.docx", "wb").write(doc.content)
```

### 5.2 curl 예시

```bash
# 세션 생성
SESSION=$(curl -s -X POST http://localhost:8090/api/v1/sessions \
  -H "X-API-Key: my-secret" \
  -H "Content-Type: application/json" \
  -d '{"topic":"회의"}' | jq -r .session_id)

# WAV 업로드
curl -X POST http://localhost:8090/api/v1/sessions/$SESSION/audio \
  -H "X-API-Key: my-secret" \
  -H "Content-Type: audio/wav" \
  --data-binary @recording.wav

# 보고서 생성 및 다운로드
curl -X POST "http://localhost:8090/api/v1/sessions/$SESSION/report?doctype=pdf" \
  -H "X-API-Key: my-secret"

curl "http://localhost:8090/api/v1/sessions/$SESSION/report/download" \
  -H "X-API-Key: my-secret" -o report.pdf
```

---

## 6. 구현 우선순위 (충돌 없는 순서)

```
Phase 1 (오늘, 충돌 없음)
├─ [P1-A] HEADLESS 환경변수 + Static 분기 → server.go 10줄
├─ [P1-B] /ws/live HasClients() 조건부 → server.go 5줄
├─ [P1-C] POST /api/stt 직접 업로드 엔드포인트 → server.go 40줄
├─ [P1-D] API_KEY 미들웨어 (선택) → server.go 20줄
└─ [P1-E] /api/monitor/config 엔드포인트 → server.go 30줄

Phase 2 (다음 세션, 기존 /api/* 유지하며 추가)
├─ [P2-A] /api/v1/sessions CRUD → server.go 신규 핸들러
├─ [P2-B] /api/v1/sessions/{id}/audio WAV 업로드 → transcribeBytesOnHost 재활용
├─ [P2-C] GET /api/v1/sessions/{id}/events SSE → server.go
└─ [P2-D] /api/v1/* 전체 v1 래핑 완료

Phase 3 (장기, 선택)
├─ FastAPI 통합 (/api/v1/ 이관)
├─ Go 서버 STT 워커 전용화
└─ Swagger UI 자동 생성
```

---

## 7. Phase 1 체크리스트 (즉시 실행 가능)

- [ ] `HEADLESS=1` 환경변수 → Static 파일 서빙 OFF
- [ ] `API_KEY` 환경변수 → X-API-Key 헤더 인증
- [ ] `WS_BROADCAST=0` → /ws/live 브로드캐스트 OFF
- [ ] `POST /api/stt` → WAV 바이너리 직접 업로드 → STT 결과 반환
- [ ] `GET/POST /api/monitor/config` → 런타임 모드 조회/변경
- [ ] `go build` + `test_e2e_pipeline.py` 38/38 통과 확인

---

> **핵심 원칙:** UI는 API 위에 얹혀 있는 선택적 레이어.  
> 모든 기능은 REST API로 접근 가능해야 하고, UI는 그 API를 시각화한다.
