"""
batch_stt.py — data/recordings/ 감시 → 미처리 WAV 배치 STT 변환

사용법:
    python batch_stt.py --watch          # 폴더 감시 모드 (Ctrl+C로 종료)
    python batch_stt.py --file audio.wav # 단일 파일 처리
    python batch_stt.py                  # pending 파일만 일괄 처리 후 종료

의존성:
    pip install faster-whisper watchdog numpy
"""

import sys
# P02: UTF8-FORCE — Windows cp949 인코딩 오류 방지
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel
from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

# ── 경로 설정 ──────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).parent
_PROJECT_DIR = _THIS_DIR.parent
DATA_DIR = _PROJECT_DIR / "data"

# 기존 녹음 폴더(recordings/)와 신규 data/recordings/ 모두 감시
RECORDINGS_DIRS = [
    _PROJECT_DIR / "recordings",   # 기존: recordings/시스템회의/, recordings/화자인식테스트/
    DATA_DIR / "recordings",       # 신규: data/recordings/
]
RECORDINGS_DIR = DATA_DIR / "recordings"  # 기본 저장 경로 (신규 파일용)
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
STATUS_FILE = TRANSCRIPTS_DIR / "status.json"

# ── 모델 설정 ──────────────────────────────────────────────────────────────
MODEL_SIZE = "large-v3-turbo"
COMPUTE_TYPE = "int8_float32"
DEVICE = "cpu"           # GPU 사용 시 "cuda"로 변경

TRANSCRIBE_PARAMS = {
    "language": "ko",
    "beam_size": 5,              # 배치: 정확도 우선 beam=5 유지
    "best_of": 5,
    "temperature": 0.0,
    "condition_on_previous_text": True,
    "no_speech_threshold": 0.5,
    "word_timestamps": True,
    "vad_filter": False,         # VAD는 녹음 시 브라우저에서 이미 처리됨
}

MAX_WORKERS = 2  # 병렬 변환 스레드 수

_status_lock = threading.Lock()  # status.json 동시 접근 방지


# ── 상태 관리 헬퍼 ─────────────────────────────────────────────────────────

def _load_status() -> dict:
    """status.json을 읽어 반환한다. 없으면 빈 dict."""
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_status(status: dict) -> None:
    """status.json을 저장한다. (Lock 내부에서 호출해야 함)"""
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _set_file_status(wav_path: Path, state: str, error: str = "") -> None:
    """단일 파일의 처리 상태를 갱신한다. (Lock으로 동시 쓰기 방지)"""
    with _status_lock:
        status = _load_status()
        entry: dict = status.get(wav_path.name, {})
        entry["state"] = state
        entry["updated_at"] = datetime.now().isoformat()
        if error:
            entry["error"] = error
        elif "error" in entry:
            del entry["error"]
        status[wav_path.name] = entry
        _save_status(status)


def _get_file_status(wav_path: Path) -> str:
    """파일의 현재 처리 상태를 반환한다. 없으면 'pending'."""
    with _status_lock:
        status = _load_status()
        return status.get(wav_path.name, {}).get("state", "pending")


# ── SRT 포맷 헬퍼 ──────────────────────────────────────────────────────────

def _seconds_to_srt_time(seconds: float) -> str:
    """초(float)를 SRT 타임스탬프 형식(HH:MM:SS,mmm)으로 변환한다."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# ── STT 처리 클래스 ────────────────────────────────────────────────────────

class STTProcessor:
    """faster-whisper 기반 STT 처리기."""

    def __init__(self) -> None:
        print(f"[stt] 모델 로드 중: {MODEL_SIZE} / {COMPUTE_TYPE} / {DEVICE}")
        self.model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        self.warmup()

    def warmup(self) -> None:
        """
        모델 워밍업: 1초짜리 무음 numpy 배열로 첫 추론 지연을 해소한다.
        """
        print("[stt] 워밍업 중...")
        dummy = np.zeros(16000, dtype=np.float32)  # 1초 무음 (16kHz mono)
        try:
            segments, _ = self.model.transcribe(dummy, language="ko", beam_size=1)
            list(segments)  # generator 소비
        except Exception as e:
            print(f"[stt] 워밍업 경고 (무시): {e}")
        print("[stt] 워밍업 완료")

    def transcribe_file(self, wav_path: Path) -> dict:
        """
        WAV 파일을 변환한다.

        반환:
            {
                "text": "전체 텍스트",
                "segments": [{"start": 0.0, "end": 1.5, "text": "..."}, ...],
                "language": "ko",
                "duration": 5.3,
            }
        """
        wav_path = Path(wav_path)
        print(f"[stt] 변환 시작: {wav_path.name}")

        segments_gen, info = self.model.transcribe(str(wav_path), **TRANSCRIBE_PARAMS)

        segments = []
        full_text_parts = []

        for seg in segments_gen:
            segments.append(
                {
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": seg.text.strip(),
                }
            )
            full_text_parts.append(seg.text.strip())

        return {
            "text": " ".join(full_text_parts),
            "segments": segments,
            "language": info.language,
            "duration": round(info.duration, 3) if info.duration else 0.0,
        }

    def save_txt(self, result: dict, path: Path) -> None:
        """전체 텍스트를 .txt 파일로 저장한다."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result["text"], encoding="utf-8")
        print(f"[stt] TXT 저장: {path.name}")

    def save_srt(self, result: dict, path: Path) -> None:
        """세그먼트를 SRT 자막 파일로 저장한다."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        for idx, seg in enumerate(result["segments"], start=1):
            start_ts = _seconds_to_srt_time(seg["start"])
            end_ts = _seconds_to_srt_time(seg["end"])
            lines.append(str(idx))
            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(seg["text"])
            lines.append("")  # 빈 줄 구분

        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"[stt] SRT 저장: {path.name}")


# ── 단일 파일 처리 함수 ────────────────────────────────────────────────────

def process_single(processor: STTProcessor, wav_path: Path) -> bool:
    """
    단일 WAV 파일을 변환하고 결과를 저장한다.

    반환:
        True  — 성공
        False — 실패 또는 스킵
    """
    wav_path = Path(wav_path)

    if not wav_path.exists():
        print(f"[stt] 파일 없음: {wav_path}")
        return False

    if not wav_path.suffix.lower() == ".wav":
        return False  # WAV 파일만 처리

    current_state = _get_file_status(wav_path)
    if current_state in ("processing", "done"):
        print(f"[stt] 스킵 ({current_state}): {wav_path.name}")
        return False

    _set_file_status(wav_path, "processing")

    try:
        result = processor.transcribe_file(wav_path)

        stem = wav_path.stem
        txt_path = TRANSCRIPTS_DIR / f"{stem}.txt"
        srt_path = TRANSCRIPTS_DIR / f"{stem}.srt"

        processor.save_txt(result, txt_path)
        processor.save_srt(result, srt_path)

        # 결과 JSON 저장
        result_json_path = TRANSCRIPTS_DIR / f"{stem}.json"
        result_json_path.write_text(
            json.dumps(
                {
                    "source": wav_path.name,
                    "language": result["language"],
                    "duration": result["duration"],
                    "text": result["text"],
                    "segments": result["segments"],
                    "transcribed_at": datetime.now().isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        _set_file_status(wav_path, "done")
        print(f"[stt] 완료: {wav_path.name} ({result['duration']}초, {len(result['segments'])}개 세그먼트)")
        return True

    except Exception as e:
        error_msg = str(e)
        print(f"[stt] 오류: {wav_path.name} — {error_msg}")
        _set_file_status(wav_path, "error", error=error_msg)
        return False


# ── 배치 처리 함수 ─────────────────────────────────────────────────────────

def process_pending(processor: STTProcessor) -> int:
    """
    recordings/ 폴더의 pending 상태 WAV 파일을 병렬로 변환한다.

    반환:
        처리 성공 파일 수
    """
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    # 기존 recordings/ 폴더(하위 폴더 포함) + data/recordings/ 모두 스캔
    wav_files = []
    for rec_dir in RECORDINGS_DIRS:
        if rec_dir.exists():
            for p in rec_dir.rglob("*.wav"):
                if _get_file_status(p) == "pending":
                    wav_files.append(p)
    wav_files = list({p.resolve(): p for p in wav_files}.values())  # 중복 제거

    if not wav_files:
        print("[stt] 처리할 pending 파일 없음")
        return 0

    print(f"[stt] pending 파일 {len(wav_files)}개 처리 시작 (workers={MAX_WORKERS})")
    success_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single, processor, p): p for p in wav_files}
        for future in as_completed(futures):
            if future.result():
                success_count += 1

    print(f"[stt] 배치 완료: {success_count}/{len(wav_files)}개 성공")
    return success_count


# ── watchdog 핸들러 ────────────────────────────────────────────────────────

class BatchWatcher(FileSystemEventHandler):
    """
    recordings/ 폴더를 감시하고 신규 WAV 파일을 스레드 풀에 제출한다.
    """

    def __init__(self, processor: STTProcessor, executor: ThreadPoolExecutor) -> None:
        super().__init__()
        self.processor = processor
        self.executor = executor

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() != ".wav":
            return

        print(f"[watcher] 신규 파일 감지: {path.name}")

        # WAV 파일이 완전히 쓰여질 때까지 잠시 대기
        for _ in range(10):
            try:
                size_before = path.stat().st_size
                time.sleep(0.3)
                size_after = path.stat().st_size
                if size_before == size_after and size_after > 0:
                    break
            except FileNotFoundError:
                time.sleep(0.3)

        self.executor.submit(process_single, self.processor, path)


# ── CLI 진입점 ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="WAV → STT 배치 변환기")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--watch",
        action="store_true",
        help="recordings/ 폴더 감시 모드 (Ctrl+C로 종료)",
    )
    group.add_argument(
        "--file",
        type=str,
        metavar="WAV",
        help="단일 WAV 파일 변환",
    )
    args = parser.parse_args()

    # 필요한 디렉토리 사전 생성
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # 모델 초기화 (워밍업 포함)
    processor = STTProcessor()

    if args.file:
        # ── 단일 파일 모드 ──
        wav_path = Path(args.file)
        if not wav_path.is_absolute():
            wav_path = Path.cwd() / wav_path
        ok = process_single(processor, wav_path)
        if not ok:
            print("[stt] 변환 실패 또는 스킵")

    elif args.watch:
        # ── 감시 모드 ──
        # 시작 시 pending 파일 먼저 처리
        process_pending(processor)

        # 기존 recordings/ + data/recordings/ 모두 감시
        watch_dirs = [d for d in RECORDINGS_DIRS if d.exists()]
        print(f"[watcher] 감시 시작: {[str(d) for d in watch_dirs]}")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            handler = BatchWatcher(processor, executor)
            observer = Observer()
            for watch_dir in watch_dirs:
                observer.schedule(handler, str(watch_dir), recursive=True)
            observer.start()
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[watcher] 종료 중...")
                observer.stop()
            observer.join()

    else:
        # ── 기본 모드: pending 파일 일괄 처리 후 종료 ──
        process_pending(processor)


if __name__ == "__main__":
    main()
