# 설치 및 환경 설정 가이드

## 사전 요구사항

### 시스템 사양
- **OS:** Windows 10+ / macOS / Linux
- **Python:** 3.8 이상
- **Go:** 1.18 이상
- **RAM:** 최소 4GB (권장 8GB)
- **디스크:** 최소 2GB (모델 다운로드 포함)

### 마이크 권한
- **Windows 10/11:** 설정 → 개인 정보 보호 → 마이크 → Claude Code 앱 허용
- **macOS:** 시스템 환경설정 → 보안 및 개인정보 보호 → 마이크 → 추가
- **Linux:** PulseAudio/ALSA 사용자 그룹 추가

---

## Step 1: Python 환경 설정

### 1-1. Python 설치 확인
```bash
python --version
# Python 3.8.0 이상인지 확인
```

### 1-2. 가상환경 생성 (권장)
```bash
cd voice-sample
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 1-3. 필수 패키지 설치
```bash
pip install --upgrade pip
pip install faster-whisper soundfile librosa pydub numpy scipy scikit-learn
```

### 1-4. 선택 패키지 설치 (화자 식별 고도화)

**resemblyzer 설치** (음성 특성 분석)
```bash
pip install resemblyzer PyDrive google-auth-oauthlib google-auth-httplib2
```

**pyannote.audio 설치** (신경망 기반 화자분리 — 복잡)
```bash
pip install pyannote.audio
# Hugging Face 토큰 등록 필요
huggingface-cli login
```

**Silero-VAD 설치** (음성 활동 감지 고도화)
```bash
pip install silero-vad torchaudio
```

### 1-5. 모델 다운로드

첫 실행 시 Whisper 모델이 자동 다운로드됩니다.
```bash
# 사전 다운로드 (선택)
python -c "from faster_whisper import WhisperModel; WhisperModel('medium')"
```

**모델 크기 참고:**
- tiny: 39MB (가장 빠름, 정확도 낮음)
- base: 140MB
- small: 466MB
- medium: 1.5GB ⭐
- large-v3: 3.1GB (정확도 최고, 느림)

---

## Step 2: Go 환경 설정

### 2-1. Go 설치 확인
```bash
go version
# go version go1.18 이상인지 확인
```

### 2-2. 필수 Go 모듈 설치
```bash
cd voice-sample
go mod download

# 또는 처음부터
go mod init voice-sample
go get github.com/gorilla/websocket
go get github.com/gorilla/mux
go get github.com/google/uuid
```

### 2-3. Go 빌드 (선택)
```bash
# 개발 중: go run server.go
# 배포용: go build -o server server.go
```

---

## Step 3: 브라우저 설정

### 3-1. 지원 브라우저
- Chrome 50+ (권장)
- Firefox 40+
- Safari 11+
- Edge 79+

### 3-2. 마이크 권한 활성화
1. http://localhost:8090 방문
2. 브라우저 주소창에 마이크 아이콘 클릭
3. "허용" 선택

---

## Step 4: 환경변수 설정

### 4-1. STT 프로파일 선택
```bash
# Windows PowerShell
$env:STT_OPTIMIZATION_PROFILE="fast-medium"
python stt_server.py

# Windows CMD
set STT_OPTIMIZATION_PROFILE=fast-medium
python stt_server.py

# macOS/Linux
export STT_OPTIMIZATION_PROFILE=fast-medium
python stt_server.py
```

### 4-2. 시나리오 설정 (음성 특성에 맞게)
```bash
# 조용한 회의실
STT_SCENARIO=quiet python stt_server.py

# 시끄러운 카페
STT_SCENARIO=noisy python stt_server.py

# 인터뷰 (정확도 중요)
STT_SCENARIO=interview python stt_server.py

# 토론/회의 (다중 화자)
STT_SCENARIO=debate python stt_server.py
```

### 4-3. 저장 모드 선택
```bash
# 텍스트만 저장 (권장, 자동 요약 가능)
SAVE_MODE=text python stt_server.py
SAVE_MODE=text go run server.go

# 메모리에만 저장 (임시, 자동 요약 불가)
SAVE_MODE=memory python stt_server.py
SAVE_MODE=memory go run server.go

# WAV + TXT + SRT 모두 저장 (용량 많음, 자동 요약 가능)
SAVE_MODE=full python stt_server.py
SAVE_MODE=full go run server.go
```

> **주의:** 자동 요약을 사용하려면 **SAVE_MODE=text 또는 SAVE_MODE=full** 필수

### 4-4. 자동 요약 설정

**자동 요약 활성화** (기본):
```bash
# AUTO_SUMMARY=1 (기본값) — 녹음 종료 시 자동으로 요약 생성
python stt_server.py
go run server.go
```

**자동 요약 비활성화**:
```bash
AUTO_SUMMARY=0 go run server.go
# 수동으로 "🚀 요약 생성" 버튼 클릭해야 함
```

**요약 문서 형식 선택**:
```bash
# 마크다운 (기본, 빠름)
SUMMARY_DOCTYPE=md python stt_server.py

# Word 문서 (권장)
SUMMARY_DOCTYPE=docx python stt_server.py

# PDF
SUMMARY_DOCTYPE=pdf python stt_server.py

# Excel
SUMMARY_DOCTYPE=xlsx python stt_server.py

# PowerPoint
SUMMARY_DOCTYPE=pptx python stt_server.py
```

### 4-4. GPU 활성화 (NVIDIA만)
```bash
# NVIDIA GPU 확인
nvidia-smi

# GPU 프로파일 선택
STT_OPTIMIZATION_PROFILE=gpu-optimized python stt_server.py
```

---

## Step 5: 포트 설정

### 포트 목록
| 포트 | 서비스 | 설명 |
|------|--------|------|
| 8090 | Go 웹 서버 | HTTP + WebSocket |
| 9001 | Python STT 서버 | WebSocket (기본) |
| 9002 | Python STT 서버 | WebSocket (백업) |

### 포트 변경
**Go 서버 (server.go)**
```go
const PORT = "8090"  // 라인 25 수정
```

**Python 서버 (stt_server.py)**
```python
port = int(os.getenv("STT_PORT", "9001"))  # 라인 243 수정
```

---

## Step 6: 데이터 저장 위치

### 기본 경로
```
voice-sample/
└── recordings/
    └── {주제}/
        ├── 녹음_20240115_150405.wav
        ├── 녹음_20240115_150410.wav
        ├── transcript.txt
        └── summary.md
```

### 경로 변경
**server.go (라인 45)**
```go
const recordingsDir = "./recordings"  // 변경 가능
```

---

## Step 7: 로그 설정

### 콘솔 로그 레벨 (Python)
```bash
# INFO (기본)
python stt_server.py

# DEBUG (상세 로그)
LOGLEVEL=DEBUG python stt_server.py

# 파일로 저장
python stt_server.py > stt_server.log 2>&1
```

---

## 🔍 설치 검증

모든 설정이 완료되었는지 확인:

```bash
# Python 패키지 확인
python -c "import faster_whisper; print('✓ faster_whisper')"
python -c "import librosa; print('✓ librosa')"
python -c "import soundfile; print('✓ soundfile')"

# Go 버전 확인
go version

# 포트 확인 (사용 가능한지)
# Windows
netstat -ano | findstr :8090
netstat -ano | findstr :9001

# macOS/Linux
lsof -i :8090
lsof -i :9001
```

모두 성공하면 **준비 완료!**

---

## 📋 체크리스트

- [ ] Python 3.8+ 설치 및 PATH 등록
- [ ] 가상환경 생성 및 활성화
- [ ] faster-whisper, librosa, soundfile 설치
- [ ] Go 1.18+ 설치 및 PATH 등록
- [ ] Go 모듈 설치 (websocket, mux)
- [ ] 마이크 권한 활성화 (OS 수준)
- [ ] 브라우저 마이크 권한 허용
- [ ] 포트 8090, 9001 사용 가능 확인
- [ ] Whisper 모델 다운로드 완료
- [ ] 첫 테스트 성공

---

## 🆘 설치 문제 해결

### "faster-whisper 설치 실패"
```bash
# C++ 빌드 도구 필요
# Windows: Visual Studio Build Tools 설치
# macOS: xcode-select --install
# Linux: sudo apt install build-essential
```

### "CUDA 오류"
```bash
# GPU가 없으면 CPU 프로파일 사용
STT_OPTIMIZATION_PROFILE=fast-medium python stt_server.py

# CUDA가 있지만 오류나면
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### "포트 8090/9001 이미 사용 중"
```bash
# Windows: 프로세스 종료
netstat -ano | findstr :8090
taskkill /F /PID <PID>

# macOS/Linux
lsof -ti :8090 | xargs kill -9
```

---

다음: **RUN_GUIDE.md**로 실행 방법 확인
