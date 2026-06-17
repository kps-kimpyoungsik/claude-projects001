# 문제 해결 가이드

이 문서는 voice-sample 시스템에서 발생할 수 있는 모든 문제의 해결 방법을 다룹니다.

---

## 🔍 빠른 진단

먼저 아래 체크리스트를 확인하세요:

- [ ] Python 서버 실행 중인가? (`Ctrl+C`로 중지하면 안 됨)
- [ ] Go 서버 실행 중인가?
- [ ] 브라우저 마이크 권한 허용되었는가?
- [ ] 포트 8090, 9001 사용 가능한가?
- [ ] 마이크가 정상 작동하는가?

---

## 문제별 해결 방법

### 1️⃣ "처리 중이라고만 나오고 진행이 안 됨"

**증상:**
```
[처리중] 상태가 계속 유지
텍스트 출력 패널에 결과가 안 보임
```

**원인:**
1. Python STT 서버가 응답하지 않음
2. 음성이 너무 짧음 (< 0.3초)
3. 마이크가 인식되지 않음
4. 네트워크 연결 문제

**해결:**

```bash
# Step 1: Python 서버 상태 확인
# 터미널에서 아래 메시지 있는지 확인:
# "======================================================================
#   최적화 프로파일: FAST-MEDIUM
#   모델: medium  |  Compute: int8  |  Device: cpu
# ======================================================================"

# 메시지 없으면 Python 서버 재시작
python stt_server.py
```

**추가 확인:**

```bash
# Step 2: WebSocket 연결 테스트
# 브라우저 개발자 도구 (F12) → Console
# 아래 명령 실행:
const ws = new WebSocket('ws://localhost:9001/stt');
ws.onopen = () => console.log('연결됨');
ws.onerror = (e) => console.error('오류:', e);

# "연결됨" 표시되면 정상
```

**Step 3: 음성 길이 확인**

마이크에 대고 **3초 이상** 말하세요.
너무 짧으면 처리되지 않을 수 있습니다.

**Step 4: 마이크 권한 확인**

```bash
# Windows: 설정 → 개인 정보 보호 → 마이크
# Chrome도 권한 확인: 주소창 마이크 아이콘

# 권한 초기화 (Chrome)
# 1. 주소창: chrome://settings/content/microphone
# 2. localhost:8090 제거
# 3. 페이지 새로고침 (F5)
# 4. 마이크 "허용" 클릭
```

---

### 2️⃣ "파형이 안 보임 / 마이크 인식 안 됨"

**증상:**
```
[실시간 입력] 패널의 파형이 비어있음
VAD 인디케이터 반응 없음
```

**원인:**
1. 브라우저 마이크 권한 없음
2. 마이크가 다른 앱에 점유됨
3. 마이크 하드웨어 문제
4. JavaScript 오류

**해결:**

```bash
# Step 1: 브라우저 권한 확인 및 초기화 (Chrome)
# 주소창 왼쪽 마이크 아이콘 클릭
# → "허용" 선택

# Step 2: 페이지 새로고침
# F5 또는 Ctrl+R

# Step 3: 다른 앱이 마이크를 사용 중인지 확인
# Windows: 설정 → 개인 정보 보호 → 마이크 → 사용 중인 앱 확인
# macOS: 시스템 정보 → 디바이스 → 오디오
```

**개발자 도구에서 확인:**

```javascript
// F12 → Console에서 실행
navigator.mediaDevices.enumerateDevices()
  .then(devices => {
    const audioDevices = devices.filter(d => d.kind === 'audioinput');
    console.log('사용 가능한 마이크:', audioDevices);
  });
```

"사용 가능한 마이크: []" 나오면 마이크 하드웨어 문제

**Step 4: 다른 브라우저 시도**

- Chrome (권장)
- Firefox
- Edge

하나라도 작동하면 브라우저 설정 문제

---

### 3️⃣ "정확도가 떨어짐"

**증상:**
```
"클라우드" → "클라우웃"
"프로젝트" → "프로제트"
전문 용어 오인식
```

**원인:**
1. 프로파일이 속도 최적화로 설정됨
2. 배경음이 많은 환경
3. 마이크 품질 저하

**해결:**

**Option 1: 프로파일 변경** (권장)

```bash
# 현재 설정 확인
python stt_server.py
# 콘솔에서 프로파일 확인

# Step 1: Python 서버 중지
# Ctrl+C

# Step 2: 고정확도 프로파일로 재시작
STT_OPTIMIZATION_PROFILE=fast-int8 python stt_server.py
# 또는
STT_OPTIMIZATION_PROFILE=baseline python stt_server.py
```

**Step 3: 브라우저에서 프로파일 변경**
- test-viz.html 드롭다운
- "int8양자화(20~25초)" 또는 "정확도우선(47초)" 선택
- **다음 녹음부터 적용** (재시작 불필요)

**Option 2: 시나리오 설정**

배경음이 많으면:
```bash
STT_SCENARIO=noisy python stt_server.py
```

| 시나리오 | 용도 | 명령어 |
|---------|------|--------|
| quiet | 조용한 회의실 (기본) | `STT_SCENARIO=quiet` |
| noisy | 시끄러운 카페 | `STT_SCENARIO=noisy` |
| interview | 인터뷰 | `STT_SCENARIO=interview` |
| debate | 토론/회의 | `STT_SCENARIO=debate` |
| phone | 전화/저음질 | `STT_SCENARIO=phone` |

**Option 3: 하드웨어 개선**

- 마이크를 입에 더 가깝게 (10cm)
- 배경음을 줄일 수 있는 환경 선택
- 더 좋은 마이크 사용 고려

---

### 4️⃣ "GPU 프로파일 선택했는데 오류"

**증상:**
```
"CUDA device not found"
"GPU not available"
처리 시간이 여전히 느림
```

**원인:**
1. NVIDIA GPU가 없음
2. CUDA 드라이버 미설치
3. PyTorch GPU 버전 미설치

**해결:**

**Step 1: NVIDIA GPU 확인**

```bash
# Windows
nvidia-smi

# GPU 없으면 아래 오류 나옴:
# "nvidia-smi : 용어 '...'을(를) cmdlet ... 명령으로 인식하지 못합니다"
```

**GPU 없으면:**
```bash
# CPU 프로파일로 변경
STT_OPTIMIZATION_PROFILE=fast-medium python stt_server.py

# 브라우저: "회의용표준(8~12초)" 선택
```

**GPU 있으면:**

```bash
# Step 1: CUDA 드라이버 확인
nvidia-smi

# Step 2: PyTorch GPU 버전 설치
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Step 3: GPU 프로파일 실행
STT_OPTIMIZATION_PROFILE=gpu-optimized python stt_server.py
```

**Step 4: CUDA 버전 확인**

```bash
nvidia-smi | grep "CUDA Version"

# 결과: CUDA Version: 12.1 또는 11.8
# 위의 pip 명령에서 cu118 또는 cu121로 변경
```

---

### 5️⃣ "포트가 이미 사용 중입니다"

**증상:**
```
"Address already in use: port 8090"
"Connection refused: port 9001"
```

**원인:**
1. 이전 프로세스가 여전히 실행 중
2. 다른 애플리케이션이 포트 사용 중

**해결:**

**Windows:**

```powershell
# Step 1: 포트 사용 프로세스 확인
netstat -ano | findstr :8090
netstat -ano | findstr :9001

# 출력 예:
# TCP    127.0.0.1:8090    0.0.0.0:0    LISTENING    12345

# Step 2: 프로세스 종료
taskkill /F /PID 12345

# Step 3: 포트 다시 확인
netstat -ano | findstr :8090  # 결과 없어야 함

# Step 4: 서버 재시작
go run server.go
python stt_server.py
```

**macOS/Linux:**

```bash
# Step 1: 포트 사용 프로세스 확인
lsof -i :8090
lsof -i :9001

# Step 2: 프로세스 강제 종료
lsof -ti :8090 | xargs kill -9
lsof -ti :9001 | xargs kill -9

# Step 3: 서버 재시작
go run server.go
python stt_server.py
```

**포트 변경하기 (대체 방안):**

```bash
# Go 서버 포트 변경 (server.go 라인 25)
# const PORT = "8091"  // 8090 → 8091

# 브라우저: http://localhost:8091/test-viz.html

# Python 포트 변경
STT_PORT=9003 python stt_server.py
```

---

### 6️⃣ "결과가 저장되지 않음"

**증상:**
```
recordings/ 폴더가 비어있음
transcript.txt 파일이 없음
```

**원인:**
1. 저장 모드가 "memory"로 설정됨
2. 권한 문제로 파일 쓰기 실패
3. 디스크 공간 부족

**해결:**

**Step 1: 저장 모드 확인**

```bash
# 현재 모드 확인: stt_server.py 콘솔 로그
# "저장 모드: memory" 나오면 변경 필요

# 텍스트 저장 모드로 변경
SAVE_MODE=text python stt_server.py

# 또는 전체 저장
SAVE_MODE=full python stt_server.py
```

**Step 2: 폴더 권한 확인**

```bash
# recordings/ 폴더 생성
mkdir recordings

# Windows: 오른쪽 클릭 → 속성 → 보안 → 수정 권한 확인
# macOS/Linux: chmod 755 recordings
```

**Step 3: 디스크 공간 확인**

```bash
# Windows PowerShell
Get-PSDrive C | Select-Object Used, Free

# macOS/Linux
df -h .
```

공간 부족 시 다른 드라이브 또는 외부 저장소 사용

---

### 7️⃣ "Python 패키지 설치 실패"

**증상:**
```
"Failed building wheel for faster-whisper"
"No module named 'torch'"
```

**원인:**
1. C++ 컴파일러 없음
2. Python 버전 호환성 문제
3. pip 버전 오래됨

**해결:**

**faster-whisper 설치 실패:**

```bash
# Step 1: pip 업그레이드
python -m pip install --upgrade pip

# Step 2: C++ 빌드 도구 설치

# Windows:
# - Visual Studio Build Tools 다운로드
# - "C++ 빌드 도구" 설치
# - 재부팅

# macOS:
xcode-select --install

# Linux (Ubuntu):
sudo apt install build-essential python3-dev
```

**torch 설치 실패:**

```bash
# Step 1: 정확한 버전 설치
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Step 2: GPU 버전 필요 시 cu118 추가
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**librosa/soundfile 설치 실패:**

```bash
# Windows: Visual Studio Build Tools 필요 (위 참고)

# macOS: 추가 라이브러리 설치
brew install libsndfile

# Linux:
sudo apt install libsndfile1-dev
```

---

### 8️⃣ "WebSocket 연결 실패"

**증상:**
```
WebSocket is closed
"Failed to connect to STT server"
```

**원인:**
1. Python STT 서버 미실행
2. 방화벽 차단
3. 포트 미스매치

**해결:**

```bash
# Step 1: Python 서버 상태 확인
# 콘솔에서 아래 메시지 보이는지 확인:
# "Listening on ws://0.0.0.0:9001"

# 없으면 재시작:
python stt_server.py

# Step 2: 포트 응답 확인 (개발자 도구)
# F12 → Console에서:
const ws = new WebSocket('ws://localhost:9001/stt');
ws.onopen = () => console.log('✓ 연결됨');
ws.onerror = (e) => console.log('✗ 오류:', e.message);

# Step 3: 방화벽 확인
# Windows Defender 방화벽 → 앱 허용
# "Node.js" 또는 "go" 앱이 개인/공개 모두 체크되었는지 확인
```

---

### 9️⃣ "화자 식별이 안 됨"

**증상:**
```
모든 텍스트가 "화자1"로 분류됨
다른 사람이 말해도 화자 변경 안 됨
```

**원인:**
1. 음성이 너무 짧음 (< 0.5초 세그먼트)
2. 화자 식별 모드 비활성화됨
3. 음성 특성이 너무 비슷함 (쌍둥이, 유사 음성)

**해결:**

**Step 1: 화자 식별 활성화 확인**

```bash
# Python 콘솔에서 아래 메시지 확인:
# "🎤 화자 식별 활성 (비동기 병렬 처리)"

# 없으면 활성화:
python stt_server.py
# (기본값으로 활성화됨)

# 또는 명시적 활성화:
ENABLE_SPEAKER_IDENTIFICATION=1 python stt_server.py
```

**Step 2: 발화 길이 확인**

세그먼트당 **최소 0.5초 이상** 말하세요.
너무 짧으면 화자 분류 어려움

```bash
# 화자 식별을 위해
# 각 발화: "네 알겠습니다" (최소 1~2초)
# 매우 짧은 발화: "응" (< 0.3초) — 화자 식별 불가
```

**Step 3: 고급 화자 식별 활성화**

resemblyzer 활성화 (90%+ 정확도):
```bash
pip install resemblyzer
ENABLE_RESEMBLYZER=1 python stt_server.py
```

**Step 4: 음성 특성이 매우 비슷한 경우**

현재 MFCC 기반 식별은 음성이 비슷하면 어려움.
→ pyannote.audio 사용 고려 (신경망 기반):
```bash
pip install pyannote.audio
ENABLE_PYANNOTE=1 python stt_server.py
```

---

### 🔟 "프로파일 선택이 반영되지 않음"

**증상:**
```
브라우저에서 프로파일 선택했는데
여전히 이전 프로파일로 처리됨
```

**원인:**
1. 환경변수로 고정된 프로파일이 있음
2. 브라우저 캐시 문제
3. 선택이 저장되지 않음

**해결:**

```bash
# Step 1: 환경변수 프로파일 없는지 확인
# 현재 Python 콘솔에서:
# "프로파일: FAST-MEDIUM"으로 나오는가?

# 다른 프로파일이면 환경변수 확인:
# Windows: set | findstr STT_OPTIMIZATION_PROFILE
# macOS/Linux: env | grep STT_OPTIMIZATION_PROFILE

# 있으면 Python 서버 중지 후 환경변수 제거:
# Windows PowerShell: Remove-Item env:STT_OPTIMIZATION_PROFILE
# macOS/Linux: unset STT_OPTIMIZATION_PROFILE

# Step 2: 브라우저 캐시 삭제
# F12 → Application → Local Storage → localhost:8090 → 삭제

# Step 3: 페이지 새로고침
# Ctrl+Shift+R (강력 새로고침)
```

---

## 📞 추가 지원

### 콘솔 로그 확인

```bash
# Python 서버 로그 파일 저장
python stt_server.py > stt_server.log 2>&1

# 로그 레벨 상향
LOGLEVEL=DEBUG python stt_server.py

# 특정 오류 메시지 검색
cat stt_server.log | grep -i "error"
```

### 개발자 도구 확인

```javascript
// F12 → Console에서 아래 정보 수집

// 1. 서버 연결 상태
console.log(navigator.onLine);  // true면 인터넷 연결됨

// 2. localStorage 확인
console.log(localStorage.getItem('stt-profile'));  // 저장된 프로파일

// 3. WebSocket 상태
// Network 탭에서 ws://localhost:9001/stt 검색
```

### 시스템 정보 수집 (버그 리포트용)

```bash
# Windows PowerShell
$info = @{
  Python = (python --version)
  Go = (go version)
  OS = [System.Environment]::OSVersion
  RAM = (Get-ComputerInfo | Select-Object OsHardwareAbstractionLayerVersion)
}
$info | ConvertTo-Json | Out-File system_info.json

# macOS/Linux
python --version > system_info.txt
go version >> system_info.txt
uname -a >> system_info.txt
```

---

**이 문서에서 해결되지 않은 문제?**
→ GitHub Issues에 system_info.txt와 함께 보고해주세요.
