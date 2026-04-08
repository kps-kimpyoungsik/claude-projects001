# STT 성능 최적화 가이드

## 🚀 빠른 시작 — 회의용 기본 설정

**현재 기본값: `fast-medium` (회의용 표준)**

```bash
# 기본 실행 (회의 녹음용 추천 설정)
python stt_server.py
# → 8~12초, 정확도 ✓✓✓ (충분함)

# 정확도 우선 (회의 기록 중요한 경우)
STT_OPTIMIZATION_PROFILE=fast-int8 python stt_server.py
# → 20~25초, 정확도 ✓✓✓✓ (거의 손실 없음)

# 기본값 명시 (fast-medium = 위와 동일)
STT_OPTIMIZATION_PROFILE=fast-medium python stt_server.py
# → 8~12초

# 속도 우선 (개인 메모용)
STT_OPTIMIZATION_PROFILE=ultra-fast python stt_server.py
# → 5~8초, 정확도 ✓✓

# GPU 가속 (NVIDIA GPU 있는 경우)
STT_OPTIMIZATION_PROFILE=gpu-optimized python stt_server.py
# → 2~4초, NVIDIA GPU 필수

# 원본 설정 (최고 정확도, 느림)
STT_OPTIMIZATION_PROFILE=baseline python stt_server.py
# → 47초, 정확도 ✓✓✓✓✓
```

---

## 프로파일 상세 설명

### baseline (기본값)
```
설정: large-v3 | float32 | beam=5
시간: 47초 (5초 음성)
정확도: 매우 높음 ✓✓✓✓✓
특징: 현재 기본 설정, 정확도 우선
용도: 학술발표, 정부 회의, 법정 기록
```

### fast-int8 (Layer 2-1: 양자화)
```
설정: large-v3 | int8 | beam=5
시간: 20~25초
정확도: -1~2% 손실 ✓✓✓✓
개선: 47% 단축
특징: large-v3 정확도 + 빠른 속도
용도: 회의 녹음 (정확도 중요)
```

### fast-medium (Layer 2-2: 모델 축소)
```
설정: medium | int8 | beam=5
시간: 8~12초
정확도: -5~8% 손실 ✓✓✓
개선: 80% 단축
특징: 일반인용 최고 추천, 속도+정확도 균형
용도: 회의 녹음, 강연 녹음, 뉴스 기사 작성
```

### ultra-fast (Layer 2-1+2: 양자화+축소+빠른 파라미터)
```
설정: medium | int8 | beam=3
시간: 5~8초
정확도: -8~12% 손실 ✓✓
개선: 89% 단축
특징: 극도로 빠른 처리
용도: 실시간 자막, 빠른 피드백 필요, 개인 메모
```

### gpu-optimized (Layer 3: GPU 가속화)
```
설정: medium | int8_float16 | beam=3 | device=cuda
시간: 2~4초
정확도: -5~8% 손실 ✓✓✓
개선: 95% 단축
특징: NVIDIA GPU 필수, 극도로 빠름
요구사항: NVIDIA GPU (RTX 3060 이상 권장)
VRAM: 2GB+
용도: 대량 음성 파일 배치 처리, 실시간 시스템
```

---

## 프로파일 선택 가이드

| 상황 | 추천 프로파일 | 이유 |
|------|------------|------|
| 정확도 최우선 | `baseline` | 원본 설정, 가장 높은 정확도 |
| 회의 기록 | `fast-medium` | 정확도-속도 최고 균형 |
| 강연/강의 | `fast-medium` | 전문 용어 처리 충분함 |
| 개인 메모 | `ultra-fast` | 속도 우선, 정확도 허용 |
| 실시간 자막 | `ultra-fast` | 저지연 처리 필요 |
| 대량 배치 처리 | `gpu-optimized` | GPU 있으면 최고의 선택 |
| 성능 테스트 | 모두 시도 | 환경별 최적값 찾기 |

---

## 환경변수 조합 옵션

프로파일 외에 **추가 세밀한 조정**도 가능합니다:

```bash
# 프로파일 + 시나리오 조합
STT_OPTIMIZATION_PROFILE=fast-medium STT_SCENARIO=noisy python stt_server.py
# → fast-medium 속도 + noisy 환경 최적화

# 프로파일 + 화자 식별 비활성화 (추가 20% 단축)
STT_OPTIMIZATION_PROFILE=ultra-fast ENABLE_SPEAKER_IDENTIFICATION=0 python stt_server.py
# → 5~8s → 4~6s

# 프로파일 + 환경변수 오버라이드
STT_OPTIMIZATION_PROFILE=fast-medium STT_COMPUTE_TYPE=float16 python stt_server.py
# → fast-medium 모델 + 사용자 지정 정밀도

# CPU FAST 모드 (beam=1/best_of=1)
STT_OPTIMIZATION_PROFILE=fast-medium STT_FAST_MODE=1 python stt_server.py
# → 추가 5배 빠름 (정확도 -3~5% 추가 손실)
```

---

## 2분 병목 분석

### 병목 지점별 소요 시간

**현재 기본 설정 (quiet 시나리오, large-v3 모델):**

```
리샘플링      : ~0.1초  (8kHz→16kHz 변환)
Whisper 인식  : ~90초  ← 🔴 가장 오래 걸림 (beam=5, best_of=5)
필터링        : ~0.05초 (정규식 기반, 무시할 수준)
화자 식별     : ~20초  (비동기 병렬, 세그먼트 5개 기준)
─────────────────────
합계          : ~120초 (2분)
```

---

## 최적화 전략 (가장 효과 높은 순서)

### 1️⃣ **Whisper beam_size/best_of 줄이기** (가장 중요)

| 설정 | beam_size | best_of | 속도 | 정확도 | 소요시간 |
|------|-----------|---------|------|--------|---------|
| 초고속 | 1 | 1 | ⚡⚡⚡ | 낮음(WER+5~7%) | ~15초 |
| 빠름 | 3 | 3 | ⚡⚡ | 중간(WER+2~3%) | ~45초 |
| **기본(quiet)** | **5** | **5** | ⚡ | **높음(기준)** | **~90초** |
| 정확 | 10 | 10 | 🐢 | 높음(WER-1~2%) | ~180초 |

**권장:**
```bash
# 빠른 처리 (정확도 약간 하락)
STT_SCENARIO=noisy python stt_server.py
# → beam=3, best_of=3 → ~45초

# 최고속 (회의록 용도, 빠른 피드백 필요)
STT_SCENARIO=phone python stt_server.py
# → beam=3, best_of=3 → ~45초
```

**효과:** 90초 → 45초 (50% 단축) ✅

---

### 2️⃣ **화자 식별 비활성화** (두 번째)

| 옵션 | 화자식별 | 소요시간 | 용도 |
|------|--------|---------|------|
| **활성화** | ✅ 각 세그먼트 식별 | ~90초+20초 = **110초** | 1:1 인터뷰, 토론 |
| **비활성화** | ❌ 모두 "화자1" | ~90초 | 개인 메모, 빠른 처리 |

**권장:**
```bash
# 화자 식별 끄고 속도 우선
ENABLE_SPEAKER_IDENTIFICATION=0 python stt_server.py
```

**효과:** 110초 → 90초 (18% 단축)

**결합 효과 (1 + 2):** 120초 → 45초 (62% 단축) ✅✅

---

### 3️⃣ **VAD 필터 활성화** (추가)

음성/침묵을 미리 구분하여 추론 속도 향상.
**실제 음성 녹음에서만 효과** (합성음/배경음은 오류 가능)

```bash
STT_SCENARIO=phone STT_VAD_FILTER=1 python stt_server.py
```

**효과:** 추가 10~15% 단축 (실음성 기준)

---

### 4️⃣ **모델 크기 줄이기** (마지막)

| 모델 | 정확도 | 속도 | 메모리 | VRAM |
|------|--------|------|--------|------|
| tiny | 낮음 | 초고속 | 39M | 1GB |
| small | 중간 | 빠름 | 141M | 2GB |
| medium | 높음 | 보통 | 405M | 5GB |
| **large-v3** | **매우높음** | **느림** | **1.5GB** | **10GB** |

**권장:**
```bash
# CPU 환경 + 속도 우선
STT_MODEL=small python stt_server.py
# → 정확도 약간 하락, 속도 2배 향상

# GPU 환경 + 균형
STT_MODEL=medium python stt_server.py
# → 정확도 중간, 속도 1.5배 향상
```

---

## 프로파일별 성능 비교표

| 프로파일 | 모델 | 정밀도 | Beam | 시간 | 정확도 | 개선율 | 용도 |
|---------|------|--------|------|------|--------|--------|------|
| **baseline** | large-v3 | float32 | 5 | 47s | 매우높음 | — | 정확도 우선 |
| **fast-int8** | large-v3 | int8 | 5 | 20~25s | -1~2% | 47% ↓ | 회의+정확도 |
| **fast-medium** | medium | int8 | 5 | 8~12s | -5~8% | 80% ↓ | 일반용 최고 |
| **ultra-fast** | medium | int8 | 3 | 5~8s | -8~12% | 89% ↓ | 속도 우선 |
| **gpu-optimized** | medium | int8_float16 | 3 | 2~4s | -5~8% | 95% ↓ | GPU 가속 |

> 시간: 5초 음성 기준 (CPU의 경우, GPU는 0.5~1초 추가 로딩)

---

## 최적화 시나리오별 구성

### 🚀 **시나리오 A: 최고 속도** (초고속 피드백)
```bash
STT_OPTIMIZATION_PROFILE=ultra-fast \
ENABLE_SPEAKER_IDENTIFICATION=0 \
STT_SCENARIO=phone \
python stt_server.py
```
**예상 시간:** ~5초 | **정확도:** 중간 | **용도:** 실시간 자막, 빠른 피드백, 개인 메모

---

### ⚖️ **시나리오 B: 균형** (속도 + 정확도, 권장)
```bash
STT_OPTIMIZATION_PROFILE=fast-medium \
ENABLE_SPEAKER_IDENTIFICATION=1 \
STT_SCENARIO=quiet \
python stt_server.py
```
**예상 시간:** ~10초 | **정확도:** 높음 | **용도:** 회의 녹음, 강연 기록, 일반 용도 (🏆 최고 추천)

---

### 🎯 **시나리오 C: 높은 정확도** (토론/학술)
```bash
STT_OPTIMIZATION_PROFILE=fast-int8 \
ENABLE_SPEAKER_IDENTIFICATION=1 \
STT_SCENARIO=quiet \
python stt_server.py
```
**예상 시간:** ~22초 | **정확도:** 매우높음 | **용도:** 학술발표, 정부 회의, 법정 기록

---

### ⚡ **시나리오 D: GPU 극고속** (대량 배치 처리)
```bash
STT_OPTIMIZATION_PROFILE=gpu-optimized \
ENABLE_SPEAKER_IDENTIFICATION=1 \
STT_SCENARIO=quiet \
python stt_server.py
```
**예상 시간:** ~3초 | **정확도:** 높음 | **용도:** 대량 파일 처리, 실시간 시스템
**조건:** NVIDIA GPU 필수 (RTX 3060 이상 권장)

---

## 설정값 상세 설명

### Whisper 파라미터

#### `beam_size` (빔 너비)
- **역할:** Whisper 추론 시 동시에 탐색하는 후보 개수
- **범위:** 1~15
- **효과:**
  - 낮음(1): 초고속, 정확도 낮음
  - 높음(10): 초저속, 정확도 높음
- **공식:** 소요시간 ≈ 음성길이 × beam_size

#### `best_of` (최고 N개 중 선택)
- **역할:** 추론을 N번 수행 후 가장 좋은 결과 선택
- **범위:** 1~10
- **효과:**
  - 1: 1회만 추론, 초고속
  - 5+: 정확도 증가, 속도 ↓
- **공식:** 소요시간 × best_of

#### `no_speech_threshold` (무음 판정)
- **역할:** 얼마나 침묵으로 판단할지의 기준
- **범위:** 0.0~1.0
- **효과:**
  - 낮음(0.3): 엄격, 짧은 발화도 감지, 오인식 가능
  - 높음(0.5+): 관대, 배경음 무시, 짧은 단어 제외
- **시나리오별:**
  - quiet(회의): 0.40 (정확도 우선)
  - noisy(카페): 0.50 (잡음 제거 우선)
  - phone(전화): 0.55 (노이즈 심함)

---

### 화자 식별 파라미터

#### `ENABLE_SPEAKER_IDENTIFICATION` (활성화/비활성화)
- **활성화(1):** 비동기 병렬로 세그먼트별 화자 식별
  - 장점: 화자별 구분 가능
  - 단점: ~20초 추가 소요
- **비활성화(0):** 모든 세그먼트를 "화자1"로 처리
  - 장점: 20초 단축
  - 단점: 화자 구분 불가

#### `ENROLL_THRESH` (화자 등록 임계값)
- **범위:** 0.70~0.95
- **효과:**
  - 낮음(0.70): 관대, 많이 등록, 오인식 증가
  - 높음(0.90): 엄격, 적게 등록, 정확성 높음
- **권장:** 0.82 (기본, 다인데 0.75로 조정)

#### `CLUSTER_THRESH` (화자 클러스터링 임계값)
- **범위:** 0.65~0.85
- **효과:**
  - 낮음(0.65): 공격적으로 병합, 속도 ↑
  - 높음(0.85): 보수적으로 분리, 정확도 ↑
- **권장:** 0.75 (기본)

---

### 오디오 전처리

#### `MIN_AUDIO_LEN_SEC` (최소 오디오 길이)
- **기본:** 0.3초
- **효과:**
  - 낮음(0.2): 짧은 발화도 처리
  - 높음(0.5): 명확한 발화만
- **권장:** 회의(0.3), 메모(0.2)

#### 리샘플링
- **병목 위치:** 입력이 16kHz가 아닐 때
  - 8kHz → 16kHz: ~0.1초
  - 44.1kHz → 16kHz: ~0.3초
- **최적화:** 브라우저에서 16kHz로 캡처하여 리샘플링 회피

---

## 병목 분석 방법

### 콘솔 로그 읽기
```
[STT 완료] 음성:5.0s | 리샘플링:0.100s | Whisper:95.2s | 필터링:0.001s | 화자식별:18.5s (5세그먼트) | 합계:118.8s
```

**해석:**
1. **리샘플링 > 0.1초?** → 입력 샘플링 레이트 확인
2. **Whisper > 100초?** → beam_size/best_of 줄이기
3. **화자식별 > 30초?** → 비활성화 고려

---

## 빠른 최적화 체크리스트

- [ ] `beam_size=3, best_of=3` (또는 phone 시나리오) 시도 → **50% 단축**
- [ ] `ENABLE_SPEAKER_IDENTIFICATION=0` 시도 → **추가 18% 단축**
- [ ] `STT_VAD_FILTER=1` 시도 (실음성만) → **추가 10% 단축**
- [ ] 리샘플링 시간 확인 (0.1초 이상이면 입력 SR 확인)
- [ ] 테스트: 콘솔 로그에서 단계별 시간 확인

---

## 예상 효과

```
기본 설정 (quiet)
└─ Whisper: 90s, 화자식별: 20s
   합계: 120s (2분)

최적화 1: phone 시나리오 (beam=3, best_of=3)
└─ Whisper: 45s, 화자식별: 20s
   합계: 65s (1분 5초) ← 45% 단축

최적화 2: 화자식별 OFF
└─ Whisper: 45s
   합계: 45s (45초) ← 62% 단축

최적화 3: VAD 필터 ON (실음성 기준)
└─ Whisper: 35s
   합계: 35s (35초) ← 70% 단축
```

---

## 권장 시작점

### 1단계: 현재 구성 측정
```bash
python stt_server.py
```
콘솔에 타이밍 로그가 출력됩니다:
```
[STT 완료] Profile:BASELINE | Model:large-v3 | Compute:float32
           음성:5.0s | 리샘플링:0.100s | Whisper:47.2s | 필터링:0.001s | 화자식별:18.5s (5세그) | 합계:65.8s
```

### 2단계: 프로파일 시도 (추천: fast-medium)
```bash
STT_OPTIMIZATION_PROFILE=fast-medium python stt_server.py
```
- 47s → 10s 단축
- 정확도 -5~8% (대부분의 경우 무시할 수준)

### 3단계: 미세 조정
```bash
# 속도가 더 필요하면
STT_OPTIMIZATION_PROFILE=ultra-fast python stt_server.py

# 정확도가 더 필요하면
STT_OPTIMIZATION_PROFILE=fast-int8 python stt_server.py

# GPU가 있으면
STT_OPTIMIZATION_PROFILE=gpu-optimized python stt_server.py
```

### 결과 비교
| 설정 | 시간 | 정확도 | 추천도 |
|------|------|--------|--------|
| baseline | 65s | ✓✓✓✓✓ | 학술용 |
| fast-int8 | 22s | ✓✓✓✓ | 회의용 |
| **fast-medium** | **10s** | **✓✓✓** | **🏆 최고** |
| ultra-fast | 5s | ✓✓ | 메모용 |
| gpu-optimized | 3s | ✓✓✓ | 배치용 |
