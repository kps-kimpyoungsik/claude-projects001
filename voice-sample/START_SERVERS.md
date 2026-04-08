# 서버 시작 스크립트 가이드

## 개요

이 프로젝트는 2개의 서버가 필요합니다:
- **Go 웹 서버** (포트 8090): 웹 UI + WebSocket 브로드캐스트
- **Python STT 서버** (포트 9002): Whisper 모델 + STT 처리

---

## 운영체제별 실행 방법

### 🔵 **Windows (PowerShell 권장)**

#### 방법 1: PowerShell (가장 권장)
```powershell
powershell -ExecutionPolicy Bypass -File start-servers.ps1
```

**장점:**
- 두 서버를 자동으로 새 창에서 실행
- 포트 자동 정리
- 색상으로 구분된 로그
- 프로세스 ID 표시

#### 방법 2: 배치 파일 (.bat)
```cmd
start-servers.bat
```

**장점:**
- 추가 설정 없이 실행 가능
- 클래식한 Windows 배치 방식
- 두 서버를 자동으로 새 창에서 실행

#### 방법 3: 수동 실행 (터미널 2개)

**터미널 1: Python STT 서버**
```cmd
python stt_server.py 9002
```

**터미널 2: Go 웹 서버**
```cmd
set STT_HOSTS=ws://localhost:9002
go run server.go
```

---

### 🍎 **macOS/Linux (Bash)**

#### 방법 1: Shell 스크립트 (권장)
```bash
chmod +x start-servers.sh
./start-servers.sh
```

**장점:**
- 두 서버를 백그라운드에서 동시 실행
- 포트 자동 정리
- 프로세스 ID 표시

#### 방법 2: 수동 실행 (터미널 2개)

**터미널 1: Python STT 서버**
```bash
python stt_server.py 9002
```

**터미널 2: Go 웹 서버**
```bash
export STT_HOSTS="ws://localhost:9002"
go run server.go
```

---

## 실행 후 확인

### 1. 웹 접속
```
http://localhost:8090/test-viz.html
```

### 2. 포트 확인

**Windows:**
```cmd
netstat -ano | findstr :8090
netstat -ano | findstr :9002
```

**macOS/Linux:**
```bash
lsof -i :8090
lsof -i :9002
```

### 3. 프로세스 확인

**Windows (PowerShell):**
```powershell
Get-Process | Where-Object {$_.ProcessName -match "python|go"}
```

**macOS/Linux:**
```bash
ps aux | grep -E "python|go"
```

---

## 포트 정보

| 서버 | 포트 | 목적 |
|------|------|------|
| Go 웹 서버 | 8090 | HTTP + WebSocket 브로드캐스트 |
| Python STT | 9002 | Whisper STT 처리 |

---

## 서버 중지

### Windows (PowerShell)
```powershell
Stop-Process -Name "python" -Force
Stop-Process -Name "go" -Force
```

### Windows (배치)
```cmd
taskkill /F /IM python.exe
taskkill /F /IM go.exe
```

### macOS/Linux
```bash
pkill -f "python stt_server"
pkill -f "go run"
```

---

## 포트 정리 (문제 발생 시)

포트가 이미 점유 중이면:

### Windows (PowerShell)
```powershell
$port = 9002
$process = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $process.OwningProcess -Force
}
```

### macOS/Linux
```bash
lsof -ti:9002 | xargs kill -9
```

---

## 환경변수 커스터마이징

### Python STT 포트 변경
```bash
python stt_server.py 9999    # 포트 9999로 변경
```

### Go 서버의 STT 포트 지정
```bash
set STT_HOSTS=ws://localhost:9999    # Windows CMD
export STT_HOSTS="ws://localhost:9999"  # macOS/Linux
go run server.go
```

---

## 스크립트 파일 목록

| 파일 | 목적 | 운영체제 |
|------|------|---------|
| `start-servers.bat` | 배치 파일 (두 터미널 자동 실행) | Windows |
| `start-servers.ps1` | PowerShell 스크립트 (권장) | Windows |
| `start-servers.sh` | Bash 스크립트 | macOS/Linux |

---

## 문제 해결

### "포트 이미 사용 중" 오류
```
OSError: [Errno 10048] bind on address ('0.0.0.0', 9002)
```

**해결:**
1. 스크립트가 포트를 자동 정리하므로 다시 실행
2. 또는 수동으로 포트 정리 후 재시작

### "Python 모듈 없음" 오류
```
ModuleNotFoundError: No module named 'faster_whisper'
```

**해결:**
```bash
pip install faster-whisper soundfile librosa
```

### "Go 컴파일 오류"
```
command not found: go
```

**해결:**
- Go 설치 확인: `go version`
- PATH 설정 확인

---

## 참고사항

- 스크립트는 포트 9001, 9002, 8090을 자동 정리합니다
- Python STT 모델 초기 로딩에 30~60초 소요될 수 있습니다
- 웹 UI는 http://localhost:8090/test-viz.html 에서 실시간 모니터링 가능합니다
