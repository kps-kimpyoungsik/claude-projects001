"""
STT Server — faster-whisper + 화자식별 + 요약 옵션형 WebSocket 서버
포트: 9001

옵션 모드:
  stt_only   : 텍스트 변환만 (기본, 가장 빠름)
  speaker_id : STT + 화자 식별/등록
  full       : STT + 화자 식별 + 세션 요약 (추후 확장)
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import asyncio
import json
import io
import os
import wave
import logging
import numpy as np
import websockets
from faster_whisper import WhisperModel
from collections import defaultdict

# ─── 로깅 ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('stt')

# ══════════════════════════════════════════════════════════════
#  하드웨어 자동 감지 + 최적 모델 프로파일 선택
# ══════════════════════════════════════════════════════════════

def _detect_hardware() -> dict:
    """
    GPU(CUDA)/CPU 환경을 감지하여 최적 STT 프로파일을 반환한다.

    환경변수 오버라이드:
      STT_MODEL        — 모델명 직접 지정 (자동감지 무시)
      STT_DEVICE       — cpu | cuda | auto (기본: auto)
      STT_COMPUTE_TYPE — 연산 타입 직접 지정

    프로파일 표:
      GPU ≥ 10GB VRAM  → large-v3        / float16   (최고 정확도)
      GPU  6~10GB VRAM → large-v3-turbo  / float16   (균형)
      GPU  2~6GB  VRAM → medium          / float16   (경량 GPU)
      CPU  8코어+      → large-v3-turbo  / int8_float32
      CPU  4~7코어     → medium          / int8_float32
      CPU  2~3코어     → small           / int8
      CPU  1코어       → tiny            / int8
    """
    cores      = os.cpu_count() or 1
    forced_dev = os.getenv("STT_DEVICE", "auto").lower()

    # ── GPU 감지 ──────────────────────────────────────────────
    cuda_ok    = False
    vram_gb    = 0.0
    gpu_name   = "없음"

    if forced_dev != "cpu":
        # 방법 1: torch (설치된 경우)
        try:
            import torch
            if torch.cuda.is_available():
                cuda_ok  = True
                vram_gb  = torch.cuda.get_device_properties(0).total_memory / 1e9
                gpu_name = torch.cuda.get_device_name(0)
        except ImportError:
            pass

        # 방법 2: ctranslate2 직접 확인 (torch 없을 때)
        if not cuda_ok:
            try:
                import ctranslate2
                if ctranslate2.get_cuda_device_count() > 0:
                    cuda_ok  = True
                    gpu_name = "CUDA (VRAM 미측정)"
                    # nvidia-smi로 VRAM 추가 측정 시도
                    try:
                        import subprocess
                        out = subprocess.check_output(
                            ["nvidia-smi", "--query-gpu=memory.total",
                             "--format=csv,noheader,nounits"],
                            timeout=3, text=True
                        ).strip().split("\n")[0]
                        vram_gb = float(out) / 1024
                        gpu_name = "CUDA GPU"
                    except Exception:
                        pass
            except Exception:
                pass

    if forced_dev == "cuda":
        cuda_ok = True

    # ── 프로파일 결정 ─────────────────────────────────────────
    if cuda_ok:
        if vram_gb >= 10:
            profile = dict(model="large-v3",       device="cuda", compute="float16",
                           tier="GPU-HIGH",  beam=5, workers=2)
        elif vram_gb >= 6:
            profile = dict(model="large-v3-turbo", device="cuda", compute="float16",
                           tier="GPU-MID",   beam=5, workers=2)
        else:
            profile = dict(model="medium",          device="cuda", compute="float16",
                           tier="GPU-LOW",   beam=5, workers=1)
    else:
        if cores >= 8:
            profile = dict(model="large-v3-turbo", device="cpu", compute="int8_float32",
                           tier="CPU-HIGH",  beam=5, workers=1)
        elif cores >= 4:
            profile = dict(model="medium",          device="cpu", compute="int8_float32",
                           tier="CPU-MID",   beam=5, workers=1)
        elif cores >= 2:
            profile = dict(model="small",           device="cpu", compute="int8",
                           tier="CPU-LOW",   beam=3, workers=1)
        else:
            profile = dict(model="tiny",            device="cpu", compute="int8",
                           tier="CPU-TINY",  beam=1, workers=1)

    # ── 환경변수 오버라이드 ───────────────────────────────────
    if v := os.getenv("STT_MODEL"):
        profile["model"]   = v
    if v := os.getenv("STT_COMPUTE_TYPE"):
        profile["compute"] = v

    profile.update({
        "cores"    : cores,
        "cuda"     : cuda_ok,
        "vram_gb"  : round(vram_gb, 1),
        "gpu_name" : gpu_name,
    })
    return profile

HW = _detect_hardware()

# ══════════════════════════════════════════════════════════════
#  최적화 프로파일 (회의용 기본값)
# ══════════════════════════════════════════════════════════════
# STT_OPTIMIZATION_PROFILE 환경변수로 선택
#
# 사용 가능한 프로파일:
#   - baseline         : 최고 정확도 (47초)
#   - fast-int8        : 양자화 최적화 (20~25초)
#   - fast-medium      : 회의용 권장 (8~12초, 기본값) ← 현재 사용 중
#   - ultra-fast       : 속도 우선 (5~8초)
#   - gpu-optimized    : GPU 가속 (2~4초, NVIDIA 필수)

OPTIMIZATION_PROFILES = {
    "baseline": dict(
        model=None,
        compute=None,
        beam_size=5,
        best_of=5,
        desc="기본 (정확도 우선, 느림)",
        expected_time="47s",
        accuracy_loss=0,
    ),
    "fast-int8": dict(
        model="large-v3",
        compute="int8",
        beam_size=5,
        best_of=5,
        desc="int8 양자화 (47% 단축)",
        expected_time="20~25s",
        accuracy_loss="1~2%",
    ),
    "fast-medium": dict(
        model="medium",
        compute="int8",
        beam_size=5,
        best_of=5,
        desc="회의용 표준 (80% 단축, 추천)",
        expected_time="8~12s",
        accuracy_loss="5~8%",
    ),
    "ultra-fast": dict(
        model="medium",
        compute="int8",
        beam_size=3,
        best_of=3,
        desc="속도 우선 (89% 단축)",
        expected_time="5~8s",
        accuracy_loss="8~12%",
    ),
    "gpu-optimized": dict(
        model="medium",
        compute="int8_float16",
        beam_size=3,
        best_of=3,
        device="cuda",
        desc="GPU 가속 (95% 단축, NVIDIA GPU 필수)",
        expected_time="2~4s",
        accuracy_loss="5~8%",
    ),
}

# 사용자 선택 프로파일 (기본: fast-medium 회의용)
_profile_name = os.getenv("STT_OPTIMIZATION_PROFILE", "fast-medium").lower()
_profile = OPTIMIZATION_PROFILES.get(_profile_name, OPTIMIZATION_PROFILES["fast-medium"])

# 프로파일별 설정 병합
if _profile["model"]:
    HW["model"] = _profile["model"]
if _profile.get("compute"):
    HW["compute"] = _profile["compute"]
if _profile.get("device"):
    HW["device"] = _profile["device"]

# ── 환경변수 옵션 ────────────────────────────────────────────────
# STT_SCENARIO=quiet|noisy|interview|debate|phone
#   → 녹음 환경별 Whisper 파라미터 자동 설정 (기본값: quiet)
#   → VAD threshold/silence는 브라우저에서 조정, STT는 beam_size/best_of/no_speech_threshold 최적화
#
# STT_MODEL=tiny|small|medium|large-v3|large-v3-turbo
#   → 모델명 직접 지정 (기본값: 하드웨어 자동 감지 또는 프로파일)
#   → STT_OPTIMIZATION_PROFILE과 함께 사용 시 환경변수 우선
#
# STT_DEVICE=cpu|cuda|auto
#   → 연산 장치 강제 지정 (기본값: auto 또는 프로파일)
#
# STT_COMPUTE_TYPE=float32|int8|float16|int8_float32
#   → 정밀도 모드 (기본값: 하드웨어별 최적값 또는 프로파일)
#
# STT_FAST_MODE=0|1
#   → CPU 환경에서만 beam=1/best_of=1로 변경 (약 5배 빠름, 정확도 -3~5%)
#   → GPU 환경에서는 무시됨 (이미 충분히 빠름)
#   → 기본값: 0 (정확도 우선)
#
# ENABLE_SPEAKER_IDENTIFICATION=0|1
#   → 세그먼트별 화자 식별 활성화/비활성화 (기본값: 1)
#   → 0: 비활성화 → 처리 시간 20% 추가 단축, 모든 세그먼트 "화자1"로 처리
#   → 1: 활성화 → 각 세그먼트를 비동기 병렬로 화자 식별
#
# 환경변수가 명시적으로 설정되면 프로파일 설정 오버라이드
if v := os.getenv("STT_MODEL"):
    HW["model"] = v
if v := os.getenv("STT_COMPUTE_TYPE"):
    HW["compute"] = v
if v := os.getenv("STT_DEVICE"):
    if v.lower() != "auto":
        HW["device"] = v

_fast_mode = os.getenv("STT_FAST_MODE", "0") == "1" and HW["device"] == "cpu"
ENABLE_SPEAKER_IDENTIFICATION = os.getenv("ENABLE_SPEAKER_IDENTIFICATION", "1") == "1"

SCENARIOS: dict[str, dict] = {
    "quiet":     dict(
        beam_size=5,              # 빔 너비: 5 (높을수록 정확, 느림. 범위: 1~15)
        best_of=5,                # 최고 N개 후보 중 선택 (1 = 빠름, 5+ = 정확)
        no_speech_threshold=0.40, # 무음 판정 임계값 (낮을수록 무음 감지 엄격)
    ),  # 조용한 회의실 → 정확도 우선
    "noisy":     dict(
        beam_size=3,              # 3 (균형: 속도-정확도)
        best_of=3,
        no_speech_threshold=0.50, # 높음: 배경음을 음성으로 오인하는 것 방지
    ),  # 시끄러운 카페/거리 → 속도 우선
    "interview": dict(
        beam_size=5,
        best_of=5,
        no_speech_threshold=0.38, # 낮음: 1:1 대화라 정확도 중요
    ),  # 1:1 인터뷰 → 정확도 우선
    "debate":    dict(
        beam_size=3,
        best_of=3,
        no_speech_threshold=0.50, # 높음: 겹치는 발화 처리
    ),  # 다자 토론 → 속도 우선
    "phone":     dict(
        beam_size=3,
        best_of=3,
        no_speech_threshold=0.55, # 가장 높음: 전화 노이즈 심함
    ),  # 전화 녹음 → 속도+잡음 제거 우선
}

# 프로파일에서 beam_size/best_of 설정이 있으면 모든 시나리오에 적용
_scenario_name = os.getenv("STT_SCENARIO", "quiet").lower()
if _profile["beam_size"] != 5 or _profile["best_of"] != 5:
    # 프로파일이 기본값(5/5)이 아니면 모든 시나리오에 오버라이드
    SCENARIOS = {
        k: {
            **v,
            "beam_size": _profile["beam_size"],
            "best_of": _profile["best_of"]
        }
        for k, v in SCENARIOS.items()
    }

if _fast_mode:
    # CPU FAST 모드: 모든 시나리오 beam=1/best_of=1 → 약 5배 빠름, WER +3~5%
    SCENARIOS = {k: {**v, "beam_size": 1, "best_of": 1} for k, v in SCENARIOS.items()}

SCENARIO_PARAMS = SCENARIOS.get(_scenario_name, SCENARIOS["quiet"])

log.info("=" * 70)
log.info(f"  하드웨어 감지: {HW['tier']}")
log.info(f"  Device: {HW['device'].upper()}  |  GPU: {HW['gpu_name']}")
if HW['cuda']:
    log.info(f"  VRAM: {HW['vram_gb']} GB")
else:
    log.info(f"  CPU: {HW['cores']} 코어")
log.info(f"")
log.info(f"  최적화 프로파일: {_profile_name.upper()}")
log.info(f"  설명: {_profile['desc']}")
log.info(f"  예상 속도: {_profile['expected_time']} (5초 음성 기준)")
log.info(f"  정확도 손실: {_profile['accuracy_loss']}")
log.info(f"")
log.info(f"  모델: {HW['model']}  |  Compute: {HW['compute']}  |  Device: {HW['device'].upper()}")
log.info(f"  시나리오: {_scenario_name}  |  Beam: {SCENARIO_PARAMS['beam_size']}  |  Best-of: {SCENARIO_PARAMS['best_of']}")
if _fast_mode:
    log.info(f"  ⚡ STT_FAST_MODE=1 활성 — beam=1/best_of=1 (CPU 초고속 모드)")
if ENABLE_SPEAKER_IDENTIFICATION:
    log.info(f"  🎤 화자 식별 활성 (비동기 병렬 처리)")
else:
    log.info(f"  🎤 화자 식별 비활성 (모든 세그먼트 '화자1'로 처리)")
log.info("=" * 70)

# 하드웨어 프로파일을 JSON 파일로 저장 (Go 서버가 /api/hwinfo 로 노출)
_HW_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "hw_profile.json")
try:
    with open(_HW_PROFILE_PATH, "w", encoding="utf-8") as _f:
        json.dump(HW, _f, ensure_ascii=False, indent=2)
except Exception as _e:
    log.warning(f"hw_profile.json 저장 실패: {_e}")

# ─── 전역 설정값 ──────────────────────────────────────────────
TARGET_SR    = 16000    # 샘플링 레이트 (16kHz = CD급 음질, Whisper 표준)
                        # Whisper는 16kHz 고정, 다른 레이트는 자동 리샘플링

HOST         = "0.0.0.0"  # 바인드 주소 (0.0.0.0 = 모든 인터페이스)
                          # 외부 연결 허용: 변경 불필요

PORT         = int(sys.argv[1]) if len(sys.argv) > 1 else 9001
             # 바인드 포트 (기본값: 9001)
             # 명령행: python stt_server.py 9002  → 포트 9002로 시작

CPU_THREADS  = min(HW["cores"], 8) if HW["device"] == "cpu" else 1
             # CPU 스레드 수 (CPU모드: min(코어수, 8), GPU모드: 1)
             # 권장: 4~8 (과도한 스레드 → 오버헤드 증가)

MODEL_SIZE   = HW["model"]        # Whisper 모델명 (tiny/small/medium/large-v3/...)
                                  # 자동감지로 결정, STT_MODEL로 오버라이드 가능

DEVICE       = HW["device"]       # 연산 장치 (cpu / cuda)
                                  # 자동감지로 결정, STT_DEVICE로 오버라이드 가능

COMPUTE_TYPE = HW["compute"]      # 정밀도 (float32/int8/float16/int8_float32)
                                  # 자동감지로 결정, STT_COMPUTE_TYPE로 오버라이드 가능

# ─── 모델 로드 (최초 1회) ──────────────────────────────────────
log.info(f"모델 로딩: {MODEL_SIZE} (device={DEVICE}, compute={COMPUTE_TYPE}, threads={CPU_THREADS}, port={PORT})")
model = WhisperModel(
    MODEL_SIZE,
    device=DEVICE,
    compute_type=COMPUTE_TYPE,
    cpu_threads=CPU_THREADS,
    num_workers=HW["workers"],
    download_root=None,
)
log.info("모델 로드 완료")

# ─── 워밍업 (콜드스타트 제거) ──────────────────────────────────
log.info("워밍업 중...")
_warmup = np.zeros(16000, dtype=np.float32)
_segs, _ = model.transcribe(_warmup, language="ko", beam_size=1)
list(_segs)
del _warmup, _segs
log.info("워밍업 완료 — 즉시 응답 가능")


# ══════════════════════════════════════════════════════════════
#  C1: Silero-VAD 품질 게이트 (선택적)
#
#  활성화: ENABLE_SILERO_VAD=1
#  비활성(기본): RMS 체크만 사용 (기존 동작 유지)
#  torch / silero-vad 미설치 시 자동 폴백 — 서버 중단 없음
# ══════════════════════════════════════════════════════════════

_silero_model          = None
_silero_get_speech_ts  = None

def _load_silero_vad() -> None:
    """Silero-VAD 모델 선택적 로드. 실패해도 서버 동작에 영향 없음."""
    global _silero_model, _silero_get_speech_ts
    if not int(os.getenv("ENABLE_SILERO_VAD", "0")):
        log.info("Silero-VAD 비활성 (ENABLE_SILERO_VAD=0) — RMS 체크 사용")
        return
    try:
        import torch
        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        (get_speech_timestamps, *_) = utils
        _silero_model         = model
        _silero_get_speech_ts = get_speech_timestamps
        log.info("Silero-VAD 로드 완료 — 고정밀 발화 감지 활성")
    except Exception as e:
        log.warning(f"Silero-VAD 로드 실패 → RMS 폴백: {e}")


def _silero_vad_check(audio: np.ndarray, sr: int = TARGET_SR) -> bool:
    """
    오디오에 실제 발화가 있는지 Silero-VAD로 확인.

    반환:
        True  — 발화 있음 또는 Silero 비활성 (STT 진행)
        False — Silero가 무음/노이즈로 판정 → STT 스킵
    """
    if _silero_model is None:
        return True  # 비활성 → 통과 (RMS 결과 신뢰)
    try:
        import torch
        tensor = torch.FloatTensor(audio)
        ts = _silero_get_speech_ts(
            tensor, _silero_model,
            sampling_rate=sr,
            threshold=0.40,
            min_speech_duration_ms=200,
            min_silence_duration_ms=100,
        )
        return len(ts) > 0
    except Exception as e:
        log.debug(f"Silero-VAD 체크 오류 → 통과 처리: {e}")
        return True  # 오류 시 통과 (보수적 처리)


_load_silero_vad()


# ══════════════════════════════════════════════════════════════
#  C2: pyannote 화자 분리 (선택적)
#
#  활성화: ENABLE_PYANNOTE=1 + HF_TOKEN=<huggingface_token>
#  비활성(기본): MFCC 코사인 유사도 (기존 동작 유지)
#  pyannote.audio 미설치 / HF_TOKEN 미설정 시 자동 폴백
# ══════════════════════════════════════════════════════════════

_pyannote_pipeline  = None
_resemblyzer_encoder = None   # CPU-native 화자 임베딩 (resemblyzer)

# ── 화자식별 우선순위 (자동 감지) ─────────────────────────────
#
#  Level 3 pyannote   : ENABLE_PYANNOTE=1 + HF_TOKEN 설정 시 (GPU 권장, CPU도 가능)
#  Level 2 resemblyzer: ENABLE_RESEMBLYZER=1 (pip install resemblyzer, CPU 최적)
#  Level 1 MFCC       : 항상 동작 (기본, 추가 설치 불필요)
#
# 감지된 레벨은 시작 시 로그에 출력됨.
# ─────────────────────────────────────────────────────────────

def _load_pyannote() -> None:
    """
    pyannote 화자분리 파이프라인 선택적 로드.
    GPU 없어도 CPU로 동작 (속도 차이만 있음).
    """
    global _pyannote_pipeline
    if not int(os.getenv("ENABLE_PYANNOTE", "0")):
        return
    hf_token = os.getenv("HF_TOKEN", "").strip()
    if not hf_token:
        log.warning("ENABLE_PYANNOTE=1 이지만 HF_TOKEN 미설정 → 하위 레벨로 폴백")
        return
    try:
        from pyannote.audio import Pipeline
        import torch
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token,
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        pipeline.to(torch.device(device))
        _pyannote_pipeline = pipeline
        log.info(f"[화자식별 Level 3] pyannote 로드 완료 (device={device})")
    except ImportError:
        log.warning("pyannote.audio 미설치 → 하위 레벨 폴백 (pip install pyannote.audio)")
    except Exception as e:
        log.warning(f"pyannote 로드 실패 → 하위 레벨 폴백: {e}")


def _load_resemblyzer() -> None:
    """
    resemblyzer 화자 임베딩 선택적 로드.
    CPU 전용 설계, HF 토큰 불필요.
    pip install resemblyzer
    """
    global _resemblyzer_encoder
    if not int(os.getenv("ENABLE_RESEMBLYZER", "0")):
        return
    try:
        from resemblyzer import VoiceEncoder
        _resemblyzer_encoder = VoiceEncoder(device="cpu")
        log.info("[화자식별 Level 2] resemblyzer 로드 완료 (CPU)")
    except ImportError:
        log.warning("resemblyzer 미설치 → MFCC 폴백 (pip install resemblyzer)")
    except Exception as e:
        log.warning(f"resemblyzer 로드 실패 → MFCC 폴백: {e}")


_load_pyannote()
_load_resemblyzer()

# 활성 화자식별 레벨 로그
if _pyannote_pipeline:
    log.info("[화자식별] Level 3 — pyannote 활성")
elif _resemblyzer_encoder:
    log.info("[화자식별] Level 2 — resemblyzer 활성")
else:
    log.info("[화자식별] Level 1 — MFCC (기본, 추가 설치 없음)")


# ══════════════════════════════════════════════════════════════
#  오디오 유틸
# ══════════════════════════════════════════════════════════════

def wav_to_numpy(data: bytes) -> tuple[np.ndarray, int]:
    """오디오 bytes → (float32 numpy, sample_rate)
    1차: Python wave 모듈 (WAV)
    2차: PyAV 폴백 (WebM/Opus/MP4 등 브라우저가 WAV 변환 실패 시)
    """
    # 1차: WAV 시도
    if data[:4] == b'RIFF':
        return _parse_wav(data)

    # 2차: PyAV 폴백
    try:
        import av as pyav
        return _parse_av(data, pyav)
    except ImportError:
        pass

    raise ValueError(f"지원하지 않는 오디오 포맷 (시작 바이트: {data[:4]})")


def _parse_wav(data: bytes) -> tuple[np.ndarray, int]:
    with io.BytesIO(data) as f:
        with wave.open(f) as w:
            n_ch   = w.getnchannels()
            sw     = w.getsampwidth()
            sr     = w.getframerate()
            frames = w.readframes(w.getnframes())

    if sw == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"지원하지 않는 WAV 샘플 크기: {sw}")

    if n_ch > 1:
        audio = audio.reshape(-1, n_ch).mean(axis=1)

    return audio, sr


def _parse_av(data: bytes, pyav) -> tuple[np.ndarray, int]:
    """PyAV로 WebM/Opus 등 디코딩"""
    buf       = io.BytesIO(data)
    container = pyav.open(buf)
    sr        = TARGET_SR
    samples   = []

    for stream in container.streams.audio:
        sr = stream.sample_rate
        break

    for frame in container.decode(audio=0):
        arr = frame.to_ndarray()           # shape: (channels, samples) or (samples,)
        if arr.ndim > 1:
            arr = arr.mean(axis=0)
        arr = arr.flatten().astype(np.float32)
        # int16 범위이면 정규화
        if arr.max() > 1.0 or arr.min() < -1.0:
            arr = arr / 32768.0
        samples.append(arr)

    container.close()

    if not samples:
        raise ValueError("PyAV: 오디오 프레임 없음")

    return np.concatenate(samples), sr


def resample(audio: np.ndarray, orig_sr: int, target_sr: int = TARGET_SR) -> np.ndarray:
    """선형 보간 리샘플링 — 반드시 float32 반환"""
    if orig_sr == target_sr:
        return audio.astype(np.float32)
    n_out = int(len(audio) * target_sr / orig_sr)
    idx   = np.linspace(0, len(audio) - 1, n_out)
    return np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)


def normalize_audio(audio: np.ndarray, target_rms: float = 0.05) -> np.ndarray:
    """
    RMS 정규화 — 조용하거나 불분명한 발음의 음성을 목표 레벨로 증폭.

    target_rms = 0.05 ≈ -26dBFS (Whisper 권장 입력 레벨)
    최대 20dB(10배) 증폭 제한으로 클리핑 방지.
    """
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < 1e-6:
        return audio
    gain = min(target_rms / rms, 10.0)  # 최대 10배(20dB) 제한
    return np.clip(audio * gain, -1.0, 1.0).astype(np.float32)


# ══════════════════════════════════════════════════════════════
#  문맥 빌더 (STT initial_prompt 동적 생성)
# ══════════════════════════════════════════════════════════════

def _build_context(session: "Session") -> str:
    """
    최근 3발화를 initial_prompt로 사용.
    고정 안내 문구는 사용하지 않는다 — Whisper가 무음 구간에서
    프롬프트를 그대로 에코(환각)하여 transcript에 저장되는 문제 방지.
    """
    if not session.history:
        return ""
    recent = session.history[-3:]
    ctx = " ".join(h["text"] for h in recent if h.get("text"))
    return ctx


# ══════════════════════════════════════════════════════════════
#  텍스트 후처리
# ══════════════════════════════════════════════════════════════

import re

# ── 할루시네이션 패턴 자동 학습 ─────────────────────────────────
DATA_DIR = "data"              # 데이터 디렉터리 (로그/패턴 저장 위치)
os.makedirs(DATA_DIR, exist_ok=True)

PATTERNS_FILE = os.path.join(DATA_DIR, "hallucination_patterns.json")
             # 학습된 할루시네이션 패턴 저장 파일
             # 포맷: {"hardcoded": [...], "learned": {패턴: 메타데이터}}
             # 수동 편집 가능, 저장 후 자동 로드

LOG_FILE = os.path.join(DATA_DIR, "hallucination_log.jsonl")
         # 필터링된 할루시네이션 로그 (JSONL 포맷)
         # 각 줄: {"timestamp", "text", "reason", "language"}
         # 1시간마다 분석 → 패턴 자동 추출

def _load_hallucination_patterns():
    """학습된 패턴 로드 (파일 없으면 기본값 반환)"""
    default_patterns = {
        "hardcoded": [  # 고정 패턴 (항상 유지)
            r'다음은\s*한국어\s*대화(?:\s*내용)?입니다\.?',
            r'이것은\s*텍스트입니다\.?',
            r'한국어\s*대화입니다\.?',
        ],
        "learned": {}  # {패턴: {count: N, first_seen: YYYY-MM-DD, last_seen: YYYY-MM-DD}}
    }

    if not os.path.exists(PATTERNS_FILE):
        return default_patterns

    try:
        with open(PATTERNS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default_patterns

def _save_hallucination_patterns(patterns):
    """패턴을 파일에 저장"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PATTERNS_FILE, 'w', encoding='utf-8') as f:
        json.dump(patterns, f, ensure_ascii=False, indent=2)

def log_hallucination(text: str, reason: str, language: str = "ko"):
    """필터된 할루시네이션을 로그에 기록 (학습용)"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "text": text,
        "reason": reason,
        "language": language,
    }
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

def _analyze_hallucination_logs():
    """로그에서 새로운 패턴 자동 추출 (빈도 5회 이상)"""
    if not os.path.exists(LOG_FILE):
        return {}

    from collections import defaultdict
    pattern_freq = defaultdict(int)

    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    text = entry.get('text', '')
                    reason = entry.get('reason', '')

                    if not text:
                        continue

                    # 반복 문자열 패턴 추출 (자동 정규식 생성)
                    # 설정값: 3개 이상 반복 감지 (예: "안녕 안녕 안녕")
                    # → 정규식으로 변환: (안녕\s*){3,}
                    words = text.split()
                    if len(words) >= 3:      # 반복 감지 최소 개수: 3
                        if len(set(words)) == 1:  # 모두 같은 단어인지 확인
                            pattern = f'({re.escape(words[0])}\\s*){{{len(words)-1},}}'
                            pattern_freq[pattern] += 1

                    # 특수 패턴: "ㅋㅋㅋ" 반복, 웃음소리 등
                    # 설정값: 5자 이상, 2종류 이하 문자 (예: "ㅋㅋㅋㅋㅋ")
                    if len(text) >= 5 and len(set(text)) <= 2:
                        pattern = f'^[{re.escape(text[0])}]*$'
                        pattern_freq[pattern] += 1
                except:
                    pass
    except:
        pass

    # 빈도 임계값: 5회 이상만 패턴으로 등록 (오 판정 방지)
    # 설정값: 5 (낮을수록 민감, 높을수록 보수적)
    # 권장: 3~10 (5가 기본값, 조정 가능)
    MIN_PATTERN_FREQUENCY = 5
    return {p: f for p, f in pattern_freq.items() if f >= MIN_PATTERN_FREQUENCY}

def learn_from_logs():
    """로그 분석 → 새로운 패턴 자동 추가"""
    global HALLUCINATION_PATTERNS

    new_patterns = _analyze_hallucination_logs()
    if not new_patterns:
        return

    # 기존 학습된 패턴에 새로운 패턴 병합
    updated = False
    for pattern, freq in new_patterns.items():
        if pattern not in HALLUCINATION_PATTERNS["learned"]:
            HALLUCINATION_PATTERNS["learned"][pattern] = {
                "count": freq,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            }
            log.info(f"[자동 학습] 새로운 할루시네이션 패턴 발견: {pattern} (빈도: {freq})")
            updated = True
        else:
            # 기존 패턴의 빈도 업데이트
            HALLUCINATION_PATTERNS["learned"][pattern]["count"] = freq
            HALLUCINATION_PATTERNS["learned"][pattern]["last_seen"] = datetime.now().isoformat()

    if updated:
        _save_hallucination_patterns(HALLUCINATION_PATTERNS)
        log.info(f"[자동 학습] {len(new_patterns)}개의 새로운 패턴 저장됨")

# 프로그램 시작 시 패턴 로드
HALLUCINATION_PATTERNS = _load_hallucination_patterns()

def _filter_hallucination(text: str, language: str = "ko") -> str:
    """Whisper 할루시네이션 패턴 제거 (자동 학습 포함)"""
    if not text:
        return ""

    original_text = text

    # 0. 고정 안내 문구 에코 제거 (initial_prompt 유래 환각)
    for pat in HALLUCINATION_PATTERNS["hardcoded"]:
        text = re.sub(pat, '', text)

    # 0-1. 학습된 패턴 제거
    for pat in HALLUCINATION_PATTERNS["learned"].keys():
        text = re.sub(pat, '', text)

    # 1. 같은 문자 3회 이상 연속 반복 제거 (,,, / ... / ~~~ 등)
    # 설정값: {2,} = 3회 이상 연속 (2를 초과하는 부분)
    text = re.sub(r'(.)\1{2,}', r'\1', text)

    # 2. 같은 단어/구절 3회 이상 반복 제거 (예: "안녕 안녕 안녕")
    # 설정값: {2,} = 3회 이상 반복
    text = re.sub(r'(\S+)(\s+\1){2,}', r'\1', text)

    # 3. 앞뒤·중복 공백·구두점 정리
    text = re.sub(r'[,\s]+$', '', text)   # 끝 쉼표/공백 제거
    text = re.sub(r'^[,\s]+', '', text)   # 앞 쉼표/공백 제거
    text = re.sub(r'\s+', ' ', text).strip()

    # 4. 한국어 모드에서 영어 비율 과다 → 할루시네이션으로 간주
    if language == "ko":
        ko_chars = len(re.findall(r'[가-힣]', text))
        en_chars = len(re.findall(r'[a-zA-Z]', text))
        visible  = len(re.sub(r'\s', '', text))

        # 필터 조건: 영어 40% 초과 AND 한국어 3자 미만
        # 설정값:
        #   - EN_RATIO_THRESHOLD: 0.4 (40%) — 낮을수록 엄격
        #   - KO_MIN_CHARS: 3 — 낮을수록 엄격
        # 권장: EN_RATIO_THRESHOLD: 0.3~0.5 / KO_MIN_CHARS: 2~5
        EN_RATIO_THRESHOLD = 0.4
        KO_MIN_CHARS = 3

        if visible > 0 and en_chars / visible > EN_RATIO_THRESHOLD and ko_chars < KO_MIN_CHARS:
            log_hallucination(original_text, "high_english_ratio", language)
            return ""

    # 5. 너무 짧거나 의미 없는 결과 무시
    # 설정값:
    #   - MIN_TEXT_LEN: 2 — 최소 텍스트 길이
    #   - MIN_LEN_NO_KO: 5 — 한국어 없을 때의 최소 길이
    # 권장: MIN_TEXT_LEN: 1~3 / MIN_LEN_NO_KO: 3~7
    MIN_TEXT_LEN = 2
    MIN_LEN_NO_KO = 5

    korean_chars = len(re.findall(r'[가-힣]', text))
    if len(text) < MIN_TEXT_LEN or (len(text) < MIN_LEN_NO_KO and korean_chars == 0):
        log_hallucination(original_text, "too_short_or_no_korean", language)
        return ""

    # 텍스트가 변경되었으면 로그에 기록 (학습용)
    if text != original_text:
        log_hallucination(original_text, "pattern_filtered", language)

    return text


# ══════════════════════════════════════════════════════════════
#  화자 식별 (MFCC 코사인 유사도, numpy 전용)
# ══════════════════════════════════════════════════════════════

def extract_mfcc_mean(audio: np.ndarray, sr: int = TARGET_SR,
                       n_mfcc: int = 13, n_fft: int = 512) -> np.ndarray:
    """단순 MFCC 평균 벡터 추출 (외부 라이브러리 불필요)

    파라미터:
      sr         : 샘플링 레이트 (기본값: 16000 Hz)
      n_mfcc     : MFCC 계수 개수 (기본값: 13)
                   설정: 낮을수록 빠름, 높을수록 정확 (권장: 12~40)
      n_fft      : FFT 윈도우 크기 (기본값: 512)
                   설정: 낮을수록 시간분해능 높음, 높을수록 주파수분해능 높음
                   권장: 256~2048 (512가 균형)

    반환값: (n_mfcc,) 형태의 1D 배열 — 평균 MFCC 특성
    """
    hop  = n_fft // 2              # 홉 크기 = FFT 크기의 50% (50% 겹침)
    n_fr = max(1, (len(audio) - n_fft) // hop + 1)  # 프레임 개수
    frames = np.array([
        audio[i*hop : i*hop + n_fft] * np.hanning(n_fft)
        for i in range(n_fr)
        if i*hop + n_fft <= len(audio)
    ])
    if len(frames) == 0:
        return np.zeros(n_mfcc)

    # 멜 필터뱅크 (음성 주파수 영역을 인간 청각에 맞춰 변환)
    spec    = np.abs(np.fft.rfft(frames, axis=1)) ** 2
    n_mel   = 40  # 멜 필터 개수 (설정: 낮을수록 빠름/낮은 해상도, 높을수록 정확)
                  # 권장: 20~128 (40이 표준)
    mel_fb  = _mel_filterbank(n_fft, sr, n_mel)
    mel_e   = np.dot(spec, mel_fb.T)
    log_mel = np.log(mel_e + 1e-8)

    # DCT → MFCC
    mfcc = _dct(log_mel)[:, :n_mfcc]
    return mfcc.mean(axis=0)


def _mel_filterbank(n_fft, sr, n_mel):
    """음성의 멜 필터뱅크 생성 (인간 청각 주파수 스케일)

    파라미터:
      n_fft  : FFT 크기
      sr     : 샘플링 레이트
      n_mel  : 멜 필터 개수
    """
    # 주파수 범위 설정 (설정값)
    low_hz  = 80.0       # 최저 주파수 (설정: 낮을수록 저음 강조, 권장: 50~200)
    high_hz = sr / 2.0   # 최고 주파수 = Nyquist 주파수 (고정값)

    def hz2mel(h): return 2595 * np.log10(1 + h / 700)
    def mel2hz(m): return 700 * (10 ** (m / 2595) - 1)

    mel_pts = np.linspace(hz2mel(low_hz), hz2mel(high_hz), n_mel + 2)
    hz_pts  = mel2hz(mel_pts)
    bins    = np.floor((n_fft + 1) * hz_pts / sr).astype(int)

    fbank = np.zeros((n_mel, n_fft // 2 + 1))
    for m in range(1, n_mel + 1):
        lo, c, hi = bins[m-1], bins[m], bins[m+1]
        for k in range(lo, c):
            fbank[m-1, k] = (k - lo) / max(c - lo, 1)
        for k in range(c, hi):
            fbank[m-1, k] = (hi - k) / max(hi - c, 1)
    return fbank


def _dct(x):
    N = x.shape[1]
    n = np.arange(N)
    k = n[:, None]
    dct_m = np.cos(np.pi * k * (2 * n + 1) / (2 * N))
    return x @ dct_m.T


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ══════════════════════════════════════════════════════════════
#  세션 상태
# ══════════════════════════════════════════════════════════════

class Session:
    # 화자 식별 임계값 (코사인 유사도: 0~1)
    ENROLL_THRESH  = 0.82  # 화자 등록 시 유사도 임계값 (설정: 높을수록 엄격)
                           # 권장: 0.75~0.90 (0.82가 표준, 다인데 조정 필요 시 0.75)
                           # 낮음(0.7): 많이 등록되지만 오인식 증가
                           # 높음(0.9): 정확하지만 같은 화자도 분리될 수 있음

    CLUSTER_THRESH = 0.75  # 화자 클러스터링 임계값 (설정: 높을수록 엄격)
                           # 권장: 0.65~0.85 (0.75가 표준)
                           # 낮음(0.65): 더 공격적으로 클러스터 병합 (속도 향상)
                           # 높음(0.85): 보수적으로 분리 유지 (정확도 향상)

    def __init__(self, mode: str = "stt_only", language: str = "ko"):
        self.mode            = mode
        self.language        = language
        self.scenario_params = dict(SCENARIO_PARAMS)  # 연결별 시나리오 (config로 재지정 가능)
        self.profiles  : dict[str, np.ndarray] = {}   # name → mfcc_mean (MFCC)
        self.clusters  : list[dict]            = []   # {label, center, count} (MFCC/resemblyzer 클러스터)
        self.history   : list[dict]            = []   # {speaker, text}
        self.seg_id    : int = 0
        self._enrolling: str | None = None
        self._enroll_vecs: list[np.ndarray] = []
        # Level 3 pyannote: 세션 내 원시 레이블 → 일관 레이블 매핑
        self._pyannote_label_map: dict[str, str] = {}
        # Level 2 resemblyzer: 화자별 임베딩 평균 저장
        self._resemblyzer_clusters: list[dict] = []  # {label, center, count}

    # ── 화자 등록 ──────────────────────────────────────────────

    def start_enroll(self, name: str):
        self._enrolling   = name
        self._enroll_vecs = []

    def add_enroll_audio(self, audio: np.ndarray):
        vec = extract_mfcc_mean(audio)
        self._enroll_vecs.append(vec)

    def finish_enroll(self) -> dict:
        if not self._enrolling or not self._enroll_vecs:
            return {"ok": False, "msg": "등록 데이터 없음"}
        center = np.mean(self._enroll_vecs, axis=0)
        self.profiles[self._enrolling] = center
        name = self._enrolling
        self._enrolling   = None
        self._enroll_vecs = []
        return {"ok": True, "msg": f"{name} 등록 완료 ({len(self._enroll_vecs)} 세그먼트)"}

    # ── 화자 식별 ──────────────────────────────────────────────

    def identify(self, audio: np.ndarray) -> dict:
        vec = extract_mfcc_mean(audio)

        # 1. 등록 화자 비교
        best_name, best_sim = None, 0.0
        for name, center in self.profiles.items():
            sim = cosine_similarity(vec, center)
            if sim > best_sim:
                best_sim, best_name = sim, name

        if best_sim >= self.ENROLL_THRESH:
            return {"speaker": best_name, "similarity": round(best_sim, 3), "is_known": True}

        # 2. 클러스터 재사용
        for c in self.clusters:
            sim = cosine_similarity(vec, c["center"])
            if sim >= self.CLUSTER_THRESH:
                c["center"] = (c["center"] * c["count"] + vec) / (c["count"] + 1)
                c["count"] += 1
                return {"speaker": c["label"], "similarity": round(sim, 3), "is_known": False}

        # 3. 새 화자
        label = f"화자{len(self.clusters)+1}"
        self.clusters.append({"label": label, "center": vec, "count": 1})
        return {"speaker": label, "similarity": 0.0, "is_known": False}

    # ── 화자 식별 (통합 라우터: Level 3→2→1 자동 선택) ───────────

    def identify_smart(self, audio: np.ndarray) -> dict:
        """
        활성화된 가장 높은 레벨의 화자식별 방법 사용.
        실패 시 하위 레벨로 자동 폴백.

        Level 3: pyannote  (ENABLE_PYANNOTE=1 + HF_TOKEN)
        Level 2: resemblyzer (ENABLE_RESEMBLYZER=1, CPU-native)
        Level 1: MFCC       (기본, 항상 동작)
        """
        # Level 3 — pyannote
        if _pyannote_pipeline is not None:
            result = self._identify_pyannote(audio)
            if result:
                return result

        # Level 2 — resemblyzer (CPU-native)
        if _resemblyzer_encoder is not None:
            result = self._identify_resemblyzer(audio)
            if result:
                return result

        # Level 1 — MFCC (폴백)
        return self.identify(audio)

    def _identify_pyannote(self, audio: np.ndarray) -> dict | None:
        """pyannote 화자분리 — 실패 시 None 반환 (상위 코드에서 폴백)."""
        try:
            import torch, io, soundfile as sf
            buf = io.BytesIO()
            sf.write(buf, audio, TARGET_SR, format="WAV")
            buf.seek(0)
            waveform = torch.FloatTensor(audio).unsqueeze(0)
            diarization = _pyannote_pipeline({
                "waveform": waveform,
                "sample_rate": TARGET_SR,
            })
            durations: dict[str, float] = {}
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                durations[speaker] = durations.get(speaker, 0) + (turn.end - turn.start)
            if not durations:
                return None
            raw_spk = max(durations, key=durations.get)
            # 세션 내 일관 레이블 변환
            if raw_spk not in self._pyannote_label_map:
                idx = len(self._pyannote_label_map) + 1
                self._pyannote_label_map[raw_spk] = f"화자{idx}"
            return {"speaker": self._pyannote_label_map[raw_spk],
                    "similarity": 1.0, "is_known": False}
        except Exception as e:
            log.debug(f"pyannote 식별 오류 → 하위 레벨 폴백: {e}")
            return None

    def _identify_resemblyzer(self, audio: np.ndarray) -> dict | None:
        """
        resemblyzer GE2E 임베딩 기반 화자 클러스터링 (CPU-native).
        MFCC보다 정확한 화자 구분, HF 토큰 불필요.
        """
        RESEM_THRESH = 0.75
        try:
            from resemblyzer import preprocess_wav
            wav = preprocess_wav(audio, source_sr=TARGET_SR)
            embed = _resemblyzer_encoder.embed_utterance(wav)

            # 등록 화자 비교
            best_name, best_sim = None, 0.0
            for name, center in self.profiles.items():
                sim = cosine_similarity(embed, center)
                if sim > best_sim:
                    best_sim, best_name = sim, name
            if best_sim >= self.ENROLL_THRESH:
                return {"speaker": best_name, "similarity": round(best_sim, 3), "is_known": True}

            # 클러스터 비교
            for c in self._resemblyzer_clusters:
                sim = cosine_similarity(embed, c["center"])
                if sim >= RESEM_THRESH:
                    c["center"] = (c["center"] * c["count"] + embed) / (c["count"] + 1)
                    c["count"]  += 1
                    return {"speaker": c["label"], "similarity": round(sim, 3), "is_known": False}

            # 새 화자
            label = f"화자{len(self._resemblyzer_clusters)+1}"
            self._resemblyzer_clusters.append({"label": label, "center": embed, "count": 1})
            return {"speaker": label, "similarity": 0.0, "is_known": False}
        except Exception as e:
            log.debug(f"resemblyzer 식별 오류 → MFCC 폴백: {e}")
            return None

    # ── 기록 추가 ──────────────────────────────────────────────

    def add_history(self, speaker: str, text: str):
        self.history.append({"speaker": speaker, "text": text})

    # ── 세션 요약 ──────────────────────────────────────────────

    def get_summary(self) -> dict:
        by_speaker: dict[str, list[str]] = defaultdict(list)
        for h in self.history:
            by_speaker[h["speaker"]].append(h["text"])

        summary = {}
        for spk, texts in by_speaker.items():
            joined = " ".join(texts)
            # 간단 요약: 첫 문장 + 총 발화 수
            first = texts[0] if texts else ""
            summary[spk] = {
                "utterances"  : len(texts),
                "first"       : first,
                "full_text"   : joined,
                "char_count"  : len(joined),
            }
        return {"speakers": summary, "total_segments": self.seg_id}


# ══════════════════════════════════════════════════════════════
#  WebSocket 핸들러
# ══════════════════════════════════════════════════════════════

async def handle(ws):
    remote = ws.remote_address
    log.info(f"[연결] {remote}")
    session = Session()

    try:
        async for msg in ws:
            # ── 텍스트 메시지 (JSON 제어) ──────────────────────
            if isinstance(msg, str):
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    await ws.send(json.dumps({"type": "error", "message": "JSON 파싱 오류"}))
                    continue

                t = data.get("type", "")

                if t == "config":
                    session.mode     = data.get("mode", "stt_only")
                    session.language = data.get("language", "ko")
                    # 시나리오 동적 적용 (없으면 서버 시작 시 환경변수 기준)
                    if sc := data.get("scenario"):
                        session.scenario_params = SCENARIOS.get(sc, SCENARIO_PARAMS)
                    log.info(f"[config] mode={session.mode} lang={session.language} scenario={data.get('scenario', _scenario_name)}")
                    await ws.send(json.dumps({"type": "ready", "mode": session.mode}))

                elif t == "enroll_start":
                    name = data.get("name", "화자?")
                    session.start_enroll(name)
                    await ws.send(json.dumps({"type": "enroll_started", "name": name}))

                elif t == "enroll_finish":
                    result = session.finish_enroll()
                    await ws.send(json.dumps({"type": "enroll_result", **result}))

                elif t == "get_summary":
                    await ws.send(json.dumps({"type": "summary", **session.get_summary()}))

                elif t == "reset":
                    session = Session(session.mode, session.language)
                    await ws.send(json.dumps({"type": "reset_ok"}))

                elif t == "ping":
                    await ws.send(json.dumps({"type": "pong"}))

                continue

            # ── 바이너리 메시지 (WAV 오디오) ──────────────────
            if not isinstance(msg, bytes) or len(msg) < 44:
                continue

            try:
                audio, sr = wav_to_numpy(msg)
            except Exception as e:
                log.warning(f"WAV 디코딩 실패: {e}")
                await ws.send(json.dumps({"type": "error", "message": f"오디오 디코딩 실패: {e}"}))
                continue

            # 최소 오디오 길이 필터 (설정값)
            MIN_AUDIO_LEN_SEC = 0.3   # 최소 오디오 길이 (초)
                                      # 설정: 낮을수록 짧은 음성도 처리, 권장: 0.2~0.5
                                      # 낮음(0.2): 짧은 발화도 처리, 노이즈 증가
                                      # 높음(0.5): 명확한 발화만, 짧은 단어 제외
            if len(audio) < TARGET_SR * MIN_AUDIO_LEN_SEC:  # 설정 미만은 스킵
                continue

            # 리샘플링 + float32 보장 (faster-whisper 필수 조건)
            # ⚠️ 병목 지점 1: 리샘플링이 오래 걸릴 수 있음 (8kHz → 16kHz는 특히 느림)
            t_resample = time.time()
            if sr != TARGET_SR:
                audio = resample(audio, sr)  # 설정값 없음, librosa 기본값 사용
                                              # 최적화: sr이 16kHz가 아니면 이 단계에서 시간 소비
            audio = audio.astype(np.float32)
            resample_elapsed = time.time() - t_resample

            # ── Gate 1: RMS 에너지 체크 ───────────────────────────
            rms = float(np.sqrt(np.mean(audio ** 2)))
            if rms < 0.004:  # 약 -48dBFS 이하 = 무음 판정
                log.debug(f"[skip/RMS] 에너지 너무 낮음 RMS={rms:.4f}")
                continue

            # ── Gate 2: Silero-VAD 품질 게이트 (활성 시) ─────────
            # ENABLE_SILERO_VAD=1 일 때만 동작. 미활성 시 통과.
            if not _silero_vad_check(audio, TARGET_SR):
                log.debug(f"[skip/Silero-VAD] 발화 없음으로 판정 — STT 스킵")
                continue

            # 음량 정규화 — 조용하거나 발음이 불분명한 화자 보정
            audio = normalize_audio(audio)

            # ── 화자 등록 모드 ─────────────────────────────────
            if session._enrolling:
                session.add_enroll_audio(audio)
                await ws.send(json.dumps({
                    "type"   : "enroll_progress",
                    "count"  : len(session._enroll_vecs),
                    "name"   : session._enrolling,
                }))
                continue

            # ── STT ───────────────────────────────────────────
            try:
                import time
                t_start = time.time()

                # ═══ 단계별 시간 로깅 (병목 분석용) ═══
                timing_log = {
                    "audio_duration_sec": len(audio) / TARGET_SR,
                    "stages": {}
                }

                # 📥 상태: 오디오 수신 완료
                t_stage = time.time()
                duration = len(audio) / TARGET_SR
                await ws.send(json.dumps({
                    "type": "stt_status",
                    "status": "receiving",
                    "step": f"📥 오디오 수신 완료 ({duration:.2f}s)",
                    "progress": 20,
                }, ensure_ascii=False))

                # go-whisper fullparams 분석 반영:
                #   beam_size=5, no_speech_thold=0.6, word_timestamps=True
                lang = session.language if session.language != "auto" else None

                # ── 발음 보정 최적화 파라미터 ──────────────────────────────
                # temperature: 0.0 실패 시 0.2→0.4→0.6 순으로 폴백
                #   → 불분명한 발음/노이즈 환경에서 인식률 향상
                # condition_on_previous_text: 이전 문맥 참조로 자연스러운 연속 인식
                # initial_prompt: 한국어 힌트 → 영어 할루시네이션 억제
                # 최근 3발화를 문맥으로 주입 → 연속 대화 인식 정확도 향상
                initial_prompt = _build_context(session)

                sp = session.scenario_params

                # 🎤 상태: 음성 인식 중
                # ⚠️ 병목 지점 2: Whisper 인식이 가장 오래 걸림 (음성 길이 × beam_size에 비례)
                t_stt_start = time.time()
                await ws.send(json.dumps({
                    "type": "stt_status",
                    "status": "processing",
                    "step": f"🎤 음성 인식 중 (Whisper {sp['beam_size']}-beam)...",
                    "progress": 40,
                }, ensure_ascii=False))

                # asyncio.to_thread: CPU 블로킹 transcribe를 스레드풀에서 실행
                # → 이벤트 루프 비블록 → 동시 연결(다중 Go 워커) 정상 처리
                def _run_transcribe():
                    kwargs = dict(
                        language                    = lang,
                        initial_prompt              = initial_prompt,
                        beam_size                   = sp["beam_size"],  # ⚠️ 병목: 높을수록 느림
                                                                         #   1: 초고속, 정확도↓
                                                                         #   5: 균형 (기본)
                                                                         #   10+: 초정확, 초저속
                        best_of                     = sp["best_of"],    # ⚠️ 병목: 높을수록 느림
                                                                         #   1: 빠름, 1회만 추론
                                                                         #   5+: N회 추론 후 최선택 (정확도↑)
                        temperature                 = [0.0, 0.2, 0.4, 0.6],  # temperature 폴백 시퀀스
                                                                               # 0.0: 결정적 (항상 같은 결과)
                                                                               # 0.2~0.6: 다양성 증가 (노이즈 환경에서 시도)
                                                                               # 권장: 낮은 값부터 폴백
                        condition_on_previous_text  = True,  # 이전 문맥 참조 (연속 대화 인식 정확도 향상)
                                                             # False로 하면 약간 빨라지지만 정확도↓
                        no_speech_threshold         = sp["no_speech_threshold"],  # 무음 판정 임계값 (시나리오별 설정)
                        compression_ratio_threshold = 2.6,   # 압축 비율 임계값 (설정: 높을수록 엄격)
                                                               # 낮음(2.0): 낮은 압축 콘텐츠 감지 (신뢰도 낮음)
                                                               # 높음(3.0): 매우 엄격한 필터 (일부 언어 제외 가능)
                                                               # 권장: 2.4~2.8
                        suppress_blank              = True,  # 빈 세그먼트 제거 (속도 미미)
                        word_timestamps             = True,  # 단어 타임스탐프 생성 (속도 미미, 정확도↑)
                        # ⚠️ 병목: VAD 필터 활성화 시 음성/침묵 구분으로 속도↑ (실음성에서 특히 효과)
                        vad_filter = os.getenv("STT_VAD_FILTER", "0") == "1",
                    )
                    if kwargs["vad_filter"]:
                        kwargs["vad_parameters"] = dict(
                            min_silence_duration_ms=300, speech_pad_ms=200)
                    seg_list, info = model.transcribe(audio, **kwargs)
                    return list(seg_list)

                segs_collected = await asyncio.to_thread(_run_transcribe)
                t_stt_end = time.time()
                stt_elapsed = t_stt_end - t_stt_start
                timing_log["stages"]["whisper_recognition"] = round(stt_elapsed, 2)

                # 📝 상태: 텍스트 변환 중
                t_convert_start = time.time()
                await ws.send(json.dumps({
                    "type": "stt_status",
                    "status": "converting",
                    "step": f"📝 텍스트 변환 중... ({stt_elapsed:.1f}초 인식 완료)",
                    "progress": 70,
                }, ensure_ascii=False))

                # ── 세그먼트별 텍스트 필터링 ────────────────────────────────────
                speaker_segments = []
                t_identify_total = 0

                # 단계1: 텍스트 필터링 (화자 식별 전)
                # 설명: Whisper의 할루시네이션 제거 (정규식 기반, 매우 빠름)
                t_filter_start = time.time()
                filtered_segs = []
                for s in segs_collected:
                    seg_text = s.text.strip()
                    seg_text = _filter_hallucination(seg_text, lang or "ko")
                    if seg_text:
                        filtered_segs.append((s, seg_text))
                t_filter_end = time.time()
                timing_log["stages"]["text_filtering"] = round(t_filter_end - t_filter_start, 3)

                # 단계2: 화자 식별 (옵션에 따라)
                if ENABLE_SPEAKER_IDENTIFICATION and filtered_segs:
                    # 세그먼트별 화자 식별 최소 길이 (설정값)
                    MIN_SEG_AUDIO_LEN_SEC = 0.3   # 세그먼트 최소 길이 (초)
                                                   # 설정: 낮을수록 짧은 세그먼트도 식별, 권장: 0.2~0.5
                                                   # 낮음(0.2): 짧은 발화도 인식, 부정확 위험
                                                   # 높음(0.5): 명확한 발화만, 짧은 단어 제외

                    # 비동기 병렬 화자 식별
                    async def _identify_speaker(s, seg_text):
                        start_sample = int(s.start * TARGET_SR)
                        end_sample   = int(s.end   * TARGET_SR)
                        seg_audio    = audio[start_sample:end_sample]

                        if len(seg_audio) < TARGET_SR * MIN_SEG_AUDIO_LEN_SEC:
                            return None  # 설정 미만 길이 → 나중에 이전 화자로 채움

                        # CPU 블로킹 작업을 스레드풀에서 실행
                        if session.mode in ("speaker_id", "full"):
                            spk = await asyncio.to_thread(session.identify_smart, seg_audio)
                        else:
                            spk = await asyncio.to_thread(session.identify, seg_audio)
                        return spk["speaker"]

                    # ⚠️ 병목 지점 3: 화자 식별 (비동기 병렬 처리로 개선, 하지만 여전히 느릴 수 있음)
                    t_id_start = time.time()
                    # 모든 세그먼트의 화자 식별을 동시에 실행 (asyncio.gather = 병렬 처리)
                    speaker_labels = await asyncio.gather(
                        *[_identify_speaker(s, seg_text) for s, seg_text in filtered_segs]
                    )
                    t_id_end = time.time()
                    t_identify_total = t_id_end - t_id_start
                    timing_log["stages"]["speaker_identification"] = round(t_identify_total, 2)
                    timing_log["segments_count"] = len(filtered_segs)

                    # 결과 조합 (None인 경우 이전 화자 유지)
                    prev_speaker = None
                    for (s, seg_text), spk in zip(filtered_segs, speaker_labels):
                        speaker_label = spk if spk else (prev_speaker or "화자1")
                        prev_speaker = speaker_label
                        speaker_segments.append({
                            "start"  : round(s.start, 3),
                            "end"    : round(s.end,   3),
                            "text"   : seg_text,
                            "speaker": speaker_label,
                        })
                else:
                    # 화자 식별 비활성화 → 모두 "화자1"로 처리
                    for s, seg_text in filtered_segs:
                        speaker_segments.append({
                            "start"  : round(s.start, 3),
                            "end"    : round(s.end,   3),
                            "text"   : seg_text,
                            "speaker": "화자1",
                        })

                t_convert_end = time.time()
                convert_elapsed = t_convert_end - t_convert_start

                # 전체 텍스트: 세그먼트 합치기
                text = " ".join(seg["text"] for seg in speaker_segments).strip()
                if not text:
                    text = ""

                # ═══ 완료 상태 메시지 (상세 타이밍 포함) ═══
                t_total = time.time() - t_start
                timing_log["total_elapsed"] = round(t_total, 2)

                # 타이밍 로그에 프로파일 정보 추가
                timing_log["profile"] = _profile_name
                timing_log["model"] = HW["model"]
                timing_log["compute"] = HW["compute"]
                timing_log["device"] = HW["device"]
                timing_log["beam_size"] = SCENARIO_PARAMS['beam_size']
                timing_log["scenario"] = _scenario_name

                # 콘솔 로그 (병목 분석용)
                log.info(f"[STT 완료] Profile:{_profile_name.upper()} | Model:{HW['model']} | Compute:{HW['compute']}")
                log.info(f"           음성:{timing_log['audio_duration_sec']:.1f}s | "
                        f"리샘플링:{resample_elapsed:.3f}s | "
                        f"Whisper:{timing_log['stages'].get('whisper_recognition', 0):.1f}s | "
                        f"필터링:{timing_log['stages'].get('text_filtering', 0):.3f}s | "
                        f"화자식별:{timing_log['stages'].get('speaker_identification', 0):.2f}s ({timing_log.get('segments_count', 0)}세그먼트) | "
                        f"합계:{t_total:.2f}s")

                speaker_msg = f"화자:{t_identify_total:.1f}s" if ENABLE_SPEAKER_IDENTIFICATION else "화자:비활성화"

                # 타이밍 변수 기본값 설정 (정의되지 않은 경우)
                resample_elapsed = resample_elapsed if 'resample_elapsed' in locals() else 0.0
                stt_elapsed = stt_elapsed if 'stt_elapsed' in locals() else 0.0
                convert_elapsed = convert_elapsed if 'convert_elapsed' in locals() else 0.0

                await ws.send(json.dumps({
                    "type": "stt_status",
                    "status": "completed",
                    "step": f"✅ STT 완료 (리샘플링:{resample_elapsed:.3f}s + 인식:{stt_elapsed:.1f}s + 변환:{convert_elapsed:.1f}s + {speaker_msg} = 합계:{t_total:.1f}s)",
                    "progress": 100,
                    "timing": timing_log,  # 상세 타이밍 포함
                }, ensure_ascii=False))

                # SRT용 세그먼트 데이터 (타임스탬프 포함)
                segments_json = [
                    {"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()}
                    for s in segs_collected
                    if s.text.strip()
                ]
            except Exception as e:
                log.error(f"STT 오류: {e}")
                await ws.send(json.dumps({"type": "error", "message": str(e)}))
                continue

            session.seg_id += 1

            # 빈 텍스트(무음/VAD 제거)도 result 전송 — Go 서버 timeout 방지
            if not text:
                await ws.send(json.dumps({
                    "type": "result", "text": "", "segments": [],
                    "seg_id": session.seg_id, "speaker": "화자1",
                    "similarity": 0.0, "is_known": False,
                }, ensure_ascii=False))
                continue

            result = {
                "type"              : "result",
                "text"              : text,
                "segments"          : segments_json,
                "speaker_segments"  : speaker_segments,  # ← 세그먼트별 화자 정보
                "seg_id"            : session.seg_id,
                "speaker"           : "화자?",
                "similarity"        : 0.0,
                "is_known"          : False,
            }

            # ── 전체 대표 화자 결정 (가장 많이 등장한 화자) ────────────────
            if speaker_segments:
                speaker_counts = defaultdict(int)
                for seg in speaker_segments:
                    speaker_counts[seg["speaker"]] += 1
                most_common = max(speaker_counts.items(), key=lambda x: x[1])[0]
                result["speaker"] = most_common
                result["similarity"] = 1.0
                result["is_known"] = False

            # speaker_id/full 모드: 추가 정보 (이미 세그먼트별 식별 완료)
            # 추가 화자 식별은 스킵 (성능 최적화)

            # ✅ 상태: 완료
            await ws.send(json.dumps({
                "type": "stt_status",
                "status": "completed",
                "step": "✅ 완료",
                "progress": 100,
            }, ensure_ascii=False))

            session.add_history(result["speaker"], text)
            preview = text[:50] + ("..." if len(text) > 50 else "")
            log.info(f"[STT:{PORT}] {result['speaker']}: {preview}")
            await ws.send(json.dumps(result, ensure_ascii=False))

    except websockets.exceptions.ConnectionClosedOK:
        pass
    except Exception as e:
        log.error(f"[오류] {remote}: {e}")
    finally:
        log.info(f"[종료] {remote}")


# ══════════════════════════════════════════════════════════════
#  진입점
# ══════════════════════════════════════════════════════════════

async def _periodic_log_analyzer():
    """주기적으로 로그 분석 (설정: 1시간마다)

    설정값:
      - 분석 주기: 3600초 = 1시간 (설정: 낮을수록 자주 학습, 권장: 300~3600초)
      - 낮음(300초): 실시간 패턴 학습, CPU 부하 증가
      - 높음(3600초): 낮은 CPU 부하, 학습 지연
    """
    LOG_ANALYSIS_INTERVAL = 3600  # 로그 분석 주기 (초)
    while True:
        try:
            await asyncio.sleep(LOG_ANALYSIS_INTERVAL)
            learn_from_logs()
        except Exception as e:
            log.error(f"로그 분석 오류: {e}")

async def main():
    log.info(f"STT 서버 시작 → ws://{HOST}:{PORT}")
    log.info(f"모드: stt_only | speaker_id | full")
    log.info(f"화자 식별: {'활성화' if ENABLE_SPEAKER_IDENTIFICATION else '비활성화'}")

    # 시작 시 한 번 로그 분석 (이전 로그에서 패턴 학습)
    learn_from_logs()

    # 백그라운드에서 주기적으로 로그 분석
    analyzer_task = asyncio.create_task(_periodic_log_analyzer())

    async with websockets.serve(handle, HOST, PORT, max_size=10 * 1024 * 1024):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
