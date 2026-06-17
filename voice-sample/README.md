# Voice Sample — STT 최적화 파이프라인

> 회의 녹음 → Whisper STT → 화자 식별 → 자동 요약 시스템
> 
> **핵심:** 5가지 최적화 프로파일로 정확도 vs 속도를 자유롭게 선택

## 🚀 특징

### 1. 5가지 STT 프로파일
- **정확도우선(47초)** — 학술/법정 기록용, 최고 정확도
- **int8양자화(20~25초)** — 회의 정확도 중요할 때
- **회의용표준(8~12초)** ⭐ — **권장 (기본값)**
- **속도우선(5~8초)** — 빠른 메모용
- **GPU가속(2~4초)** — NVIDIA GPU 필수

### 2. 멀티 채널 화자 식별
- VAD(Voice Activity Detection)로 발화 자동 감지
- MFCC 기반 화자 음성 특성 분석
- 선택: resemblyzer 또는 pyannote 고도화 가능

### 3. 웹 기반 UI
- 실시간 파형/VAD 시각화
- STT 진행 상태 모니터링
- 프로파일 실시간 전환 (재시작 불필요)

---

## 📋 필수 요구사항

```
Python 3.8+
Go 1.18+
Node.js 16+ (선택)
```

### Python 패키지
```bash
pip install faster-whisper soundfile librosa pydub silero-vad
```

### Go 모듈
```bash
go get github.com/gorilla/websocket
go get github.com/gorilla/mux
```

---

## 🎯 빠른 시작

### 1단계: 서버 시작

```bash
# 터미널 1: Python STT 서버
python stt_server.py

# 터미널 2: Go 웹 서버
go run server.go

# 브라우저 열기
http://localhost:8090/test-viz.html
```

### 2단계: 프로파일 선택
드롭다운에서 "회의용표준(8~12초)" 선택

### 3단계: 녹음 시작
[▶ 시작] 클릭 → 두 명이 번갈아 말하기 → [⏹ 중지] 클릭

### 4단계: 결과 확인
```
recordings/{주제}/transcript.txt
```

---

## 📖 상세 가이드

| 가이드 | 용도 |
|--------|------|
| **RUN_GUIDE.md** | 전체 실행 절차 + 웹 UI 사용법 |
| **STT_PROFILE_SETTINGS.md** | 5가지 프로파일 상세 설명 |
| **STT_OPTIMIZATION_GUIDE.md** | 성능 최적화 기술 심층 분석 |
| **SETUP.md** | 설치 및 환경 설정 |
| **TROUBLESHOOTING.md** | 문제 해결 가이드 |

---

## 🔧 환경변수 설정

### 기본 사용
```bash
python stt_server.py
# 기본값: fast-medium (회의용 표준)
```

### 프로파일 변경
```bash
# 정확도 우선
STT_OPTIMIZATION_PROFILE=baseline python stt_server.py

# 속도 우선
STT_OPTIMIZATION_PROFILE=ultra-fast python stt_server.py

# GPU 가속
STT_OPTIMIZATION_PROFILE=gpu-optimized python stt_server.py
```

### 고급 옵션
```bash
# 시나리오 선택 (배경음 최적화)
STT_SCENARIO=noisy python stt_server.py

# 화자 식별 비활성 (속도 +20%)
ENABLE_SPEAKER_IDENTIFICATION=0 python stt_server.py

# 저장 모드 선택
SAVE_MODE=text python stt_server.py  # txt만 저장
SAVE_MODE=full python stt_server.py  # wav + txt + srt 모두 저장
```

---

## 📁 프로젝트 구조

```
voice-sample/
├── server.go                    ← Go HTTP/WebSocket 서버
├── stt_server.py               ← Python Whisper STT 서버
├── index.html                  ← 메인 녹음 UI
├── test-viz.html               ← 파이프라인 시각화
├── src/
│   ├── voice-stt.js            ← VAD + 음성 캡처
│   └── app.js                  ← UI 로직
├── pipeline/
│   └── batch_stt.py            ← 배치 처리
├── tests/                       ← E2E 테스트
├── recordings/                  ← 결과 저장
├── RUN_GUIDE.md                ← 실행 가이드
├── STT_PROFILE_SETTINGS.md     ← 프로파일 설명
└── STT_OPTIMIZATION_GUIDE.md   ← 성능 분석
```

---

## 🎤 작업흐름

```
[브라우저]
마이크 → VAD(음성감지) → WAV 인코딩
    ↓
POST /api/recordings?topic=회의명
    ↓
[Go 서버]
WAV 저장 → STT 큐 추가 → WebSocket 브로드캐스트
    ↓
[Python 서버]
Whisper 음성→텍스트 → 화자식별 → 필터링
    ↓
[Go 서버]
transcript.txt 업데이트 → 최종 상태 반환
```

---

## ✅ 성능 비교

| 프로파일 | 시간 | 정확도 | 메모리 | 손실 |
|---------|------|--------|--------|------|
| baseline | 47s | ✓✓✓✓✓ | 1.5GB | 0% |
| fast-int8 | 20~25s | ✓✓✓✓ | 1.5GB | 1~2% |
| **fast-medium** | **8~12s** | **✓✓✓** | **400MB** | **5~8%** |
| ultra-fast | 5~8s | ✓✓ | 400MB | 8~12% |
| gpu-optimized | 2~4s | ✓✓✓ | 400MB+VRAM | 5~8% |

> 기준: 5초 음성 파일 (1초 음성 = 1/5 처리시간)

---

## 🐛 문제 해결

### "처리 중이라고만 나오고 진행이 안 됨"
1. Python 콘솔에서 `[STT 완료]` 메시지 확인
2. 음성이 0.3초 이상 있는지 확인
3. 마이크 권한 확인

### "정확도가 떨어짐"
1. 프로파일을 int8양자화 또는 baseline으로 변경
2. 환경변수: `STT_SCENARIO=noisy python stt_server.py`
3. 마이크를 배경음에서 멀리 배치

### "GPU가 없는데 gpu-optimized 선택함"
→ CPU 프로파일 선택: fast-medium 또는 baseline

상세 답변: **TROUBLESHOOTING.md** 참고

---

## 🚀 다음 단계

1. **배치 처리:** `pipeline/batch_stt.py`로 대량 파일 처리
2. **고도화:** resemblyzer/pyannote 활성화로 화자 분류 정확도 90%+ 달성
3. **요약:** LLM 통합으로 자동 회의 요약 생성

---

## 📝 라이선스

MIT
