"""
recorder.py — 마이크 녹음 + WAV 저장 모듈

사용법:
    python recorder.py --topic 회의
    python recorder.py --topic 인터뷰 --threshold 0.005

의존성:
    pip install sounddevice soundfile numpy
"""

import sys
# P02: UTF8-FORCE — Windows cp949 인코딩 오류 방지
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import argparse
import json
import os
import queue
import threading
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

# ── 기본 설정 ──────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
BLOCK_SIZE = 1024  # 프레임당 샘플 수 (~64ms @ 16kHz)

SILENCE_THRESHOLD = 0.004   # RMS 에너지 기준 무음 임계값
SILENCE_DURATION = 1.5      # 연속 무음 시간(초) 초과 시 자동 저장
MIN_DURATION = 0.5          # 최소 발화 길이(초) 미만이면 버림

# 저장 경로 (pipeline 기준 ../data/recordings/)
_THIS_DIR = Path(__file__).parent
RECORDINGS_DIR = _THIS_DIR.parent / "data" / "recordings"


def _rms(block: np.ndarray) -> float:
    """int16 블록의 RMS 에너지를 0~1 범위로 반환."""
    float_block = block.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(float_block ** 2)))


class RecordingSession:
    """
    단일 녹음 세션을 관리한다.

    사용 예:
        session = RecordingSession()
        session.start("회의")
        input("Enter를 누르면 종료...")
        path = session.stop()
        print(f"저장됨: {path}")
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        silence_threshold: float = SILENCE_THRESHOLD,
        silence_duration: float = SILENCE_DURATION,
        min_duration: float = MIN_DURATION,
        recordings_dir: Path = RECORDINGS_DIR,
    ):
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.min_duration = min_duration
        self.recordings_dir = Path(recordings_dir)

        self._topic: str = ""
        self._frames: list[np.ndarray] = []
        self._audio_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._vad_thread: threading.Thread | None = None
        self._stream: sd.InputStream | None = None
        self._saved_path: str = ""

    # ── 공개 API ───────────────────────────────────────────────────────────

    def start(self, topic: str) -> None:
        """녹음을 시작한다. topic은 파일명에 포함된다."""
        self._topic = topic.strip().replace(" ", "_") or "unknown"
        self._frames = []
        self._stop_event.clear()
        self._saved_path = ""

        self.recordings_dir.mkdir(parents=True, exist_ok=True)

        # VAD 처리 스레드 시작
        self._vad_thread = threading.Thread(target=self._vad_loop, daemon=True)
        self._vad_thread.start()

        # 오디오 스트림 열기
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCK_SIZE,
            callback=self._stream_callback,
        )
        self._stream.start()
        print(f"[recorder] 녹음 시작 (topic={self._topic}) — Enter 또는 stop()으로 종료")

    def stop(self) -> str:
        """녹음을 중단하고 WAV 파일 경로를 반환한다."""
        self._stop_event.set()

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # VAD 스레드 종료 대기
        if self._vad_thread is not None and self._vad_thread.is_alive():
            self._vad_thread.join(timeout=3.0)

        # 아직 저장되지 않은 경우 수동 저장
        if not self._saved_path and self._frames:
            self._saved_path = self._save(self._frames)

        return self._saved_path

    # ── 내부 메서드 ────────────────────────────────────────────────────────

    def _stream_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status,
    ) -> None:
        """sounddevice 콜백 — 블록 단위로 큐에 넣는다."""
        if status:
            print(f"[recorder] stream status: {status}")
        self._audio_queue.put(indata.copy())

    def _vad_loop(self) -> None:
        """
        백그라운드 스레드: 큐에서 블록을 꺼내 RMS 기반 VAD를 수행한다.
        - SILENCE_DURATION 연속 무음 → 자동 저장 후 종료
        - stop_event 세트 → 즉시 종료
        """
        silent_samples = 0
        silence_limit = int(self.silence_duration * self.sample_rate)

        while not self._stop_event.is_set():
            try:
                block = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            self._frames.append(block)
            energy = _rms(block)

            if energy < self.silence_threshold:
                silent_samples += len(block)
                if silent_samples >= silence_limit:
                    # 무음 임계 초과 → 자동 저장
                    print(f"\n[recorder] 무음 {self.silence_duration}초 감지 → 자동 저장")
                    self._saved_path = self._save(self._frames)
                    self._stop_event.set()
                    break
            else:
                silent_samples = 0  # 발화 감지 시 무음 카운터 초기화

    def _save(self, frames: list[np.ndarray]) -> str:
        """
        누적 프레임을 WAV + JSON 메타데이터로 저장한다.
        최소 발화 길이 미만이면 저장하지 않고 빈 문자열을 반환한다.
        """
        if not frames:
            print("[recorder] 저장할 오디오 데이터 없음")
            return ""

        audio = np.concatenate(frames, axis=0).flatten()
        duration = len(audio) / self.sample_rate

        if duration < self.min_duration:
            print(f"[recorder] 발화 {duration:.2f}초 — 최소 길이({self.min_duration}초) 미만, 버림")
            return ""

        timestamp = datetime.now()
        stem = timestamp.strftime("%Y%m%d_%H%M%S") + f"_{self._topic}"
        wav_path = self.recordings_dir / f"{stem}.wav"
        json_path = self.recordings_dir / f"{stem}.json"

        # WAV 저장 (16bit PCM mono)
        sf.write(str(wav_path), audio, self.sample_rate, subtype="PCM_16")

        # 메타데이터 JSON 저장
        metadata = {
            "filename": wav_path.name,
            "topic": self._topic,
            "duration": round(duration, 3),
            "recorded_at": timestamp.isoformat(),
        }
        json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"[recorder] 저장 완료: {wav_path} ({duration:.1f}초)")
        return str(wav_path)


# ── CLI 진입점 ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="마이크 녹음 → WAV 저장")
    parser.add_argument("--topic", type=str, default="recording", help="녹음 주제 (파일명에 포함)")
    parser.add_argument(
        "--threshold",
        type=float,
        default=SILENCE_THRESHOLD,
        help=f"무음 RMS 임계값 (기본: {SILENCE_THRESHOLD})",
    )
    parser.add_argument(
        "--silence",
        type=float,
        default=SILENCE_DURATION,
        help=f"자동 저장 무음 지속 시간(초) (기본: {SILENCE_DURATION})",
    )
    args = parser.parse_args()

    session = RecordingSession(
        silence_threshold=args.threshold,
        silence_duration=args.silence,
    )
    session.start(args.topic)

    try:
        input("  → Enter를 누르면 즉시 저장/종료합니다...\n")
    except KeyboardInterrupt:
        print("\n[recorder] Ctrl+C 감지")

    saved = session.stop()
    if saved:
        print(f"[recorder] 최종 경로: {saved}")
    else:
        print("[recorder] 저장된 파일 없음 (발화 없음 또는 너무 짧음)")


if __name__ == "__main__":
    main()
