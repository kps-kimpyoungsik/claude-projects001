"""
spell_checker.py
STT 결과 텍스트 한국어 오타 검증 + 교정

사용법:
    python spell_checker.py --file ../data/transcripts/파일.txt
"""

import sys
# P02: UTF8-FORCE — Windows cp949 인코딩 오류 방지
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# .env 로드 (pipeline 디렉터리 기준)
load_dotenv(Path(__file__).parent.parent / ".env")

# ---------------------------------------------------------------------------
# Whisper 오인식 패턴 + 추가 교정 딕셔너리
# ---------------------------------------------------------------------------
WHISPER_CORRECTIONS: dict[str, str] = {
    "않은데요": "않는데요",
    "됬": "됐",
    "돼요": "돼요",          # 형태는 같지만 혼용 패턴 정규화용
    "에요": "예요",
    "할께요": "할게요",
    "할껄": "할걸",
    "어떻게요": "어떻게요",  # 보존
    "맞춤법": "맞춤법",      # 보존
    "몇일": "며칠",
    "왠만하면": "웬만하면",
    "왠지": "왠지",          # 보존 (원래 맞음)
    "어의없다": "어이없다",
    "어이없다": "어이없다",   # 보존
    "설레임": "설렘",
    "희안하다": "희한하다",
    "홀홀이": "홀로이",
    "넘어": "너무",          # 구어체 → 표준어 (문맥 의존 주의)
}


# ---------------------------------------------------------------------------
# SpellChecker 클래스
# ---------------------------------------------------------------------------
class SpellChecker:
    """
    STT 텍스트 한국어 맞춤법 검사기.

    1. py-hanspell API로 500자 단위 청크 교정
    2. hanspell 실패 시 WHISPER_CORRECTIONS 패턴만 적용 (graceful fallback)
    3. 결과 JSON + 교정본 txt 저장
    """

    CHUNK_SIZE = 500
    CHUNK_DELAY = 0.5  # 청크 간 딜레이 (초)

    def __init__(self) -> None:
        self._hanspell_available = self._check_hanspell()

    # ------------------------------------------------------------------
    # 공개 메서드
    # ------------------------------------------------------------------

    def check(self, text: str) -> dict:
        """
        전체 파이프라인 실행.

        Returns:
            {
                "original": str,
                "corrected": str,
                "corrections": [{"original": str, "corrected": str, "pos": int}],
                "error_count": int,
                "error_rate": float,
                "checked_at": str  (ISO8601)
            }
        """
        if not text or not text.strip():
            return self._empty_result(text or "")

        # 1단계: hanspell API 교정
        if self._hanspell_available:
            corrected_text, corrections = self._full_check(text)
        else:
            corrected_text = text
            corrections = []

        # 2단계: 패턴 딕셔너리 교정 (API 결과 위에 추가 적용)
        pattern_corrected, pattern_corrections = self._apply_patterns_with_diff(
            corrected_text, base_offset=0
        )

        all_corrections = corrections + pattern_corrections
        error_count = len(all_corrections)
        error_rate = round(error_count / max(len(text), 1), 6)

        return {
            "original": text,
            "corrected": pattern_corrected,
            "corrections": all_corrections,
            "error_count": error_count,
            "error_rate": error_rate,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def check_file(self, txt_path: str) -> str:
        """
        텍스트 파일 → 교정 → 결과 저장.

        Returns:
            저장된 교정본 파일 경로 (str)
        """
        src = Path(txt_path)
        if not src.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {txt_path}")

        text = src.read_text(encoding="utf-8")
        result = self.check(text)

        # 저장 디렉터리
        out_dir = src.parent.parent / "data" / "corrected"
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = src.stem
        corrected_path = out_dir / f"{stem}_corrected.txt"
        report_path = out_dir / f"{stem}_report.json"

        corrected_path.write_text(result["corrected"], encoding="utf-8")
        report_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"[spell_checker] 교정 완료")
        print(f"  교정본 : {corrected_path}")
        print(f"  리포트 : {report_path}")
        print(f"  오류 수: {result['error_count']}건 / 오류율: {result['error_rate']:.2%}")

        return str(corrected_path)

    # ------------------------------------------------------------------
    # 내부 메서드
    # ------------------------------------------------------------------

    def _chunk_check(self, chunk: str) -> str:
        """
        단일 청크에 hanspell API 적용.
        실패 시 원본 청크 반환 (graceful fallback).
        """
        try:
            from hanspell import spell_checker as hs

            result = hs.check(chunk)
            return result.checked
        except Exception as exc:  # noqa: BLE001
            print(f"[spell_checker] hanspell 오류 (패턴 교정만 적용): {exc}")
            return chunk

    def _apply_patterns(self, text: str) -> str:
        """WHISPER_CORRECTIONS 패턴 적용 (위치 정보 없이)."""
        corrected = text
        for wrong, right in WHISPER_CORRECTIONS.items():
            if wrong == right:
                continue
            corrected = corrected.replace(wrong, right)
        return corrected

    def _apply_patterns_with_diff(
        self, text: str, base_offset: int = 0
    ) -> tuple[str, list[dict]]:
        """
        WHISPER_CORRECTIONS 적용 + 변경 위치 추적.

        Returns:
            (교정된 텍스트, corrections 리스트)
        """
        corrections: list[dict] = []
        corrected = text
        offset_delta = 0  # 교정으로 인한 길이 변화 누적

        for wrong, right in WHISPER_CORRECTIONS.items():
            if wrong == right:
                continue
            start = 0
            while True:
                pos = corrected.find(wrong, start)
                if pos == -1:
                    break
                corrections.append(
                    {
                        "original": wrong,
                        "corrected": right,
                        "pos": base_offset + pos + offset_delta,
                    }
                )
                corrected = corrected[:pos] + right + corrected[pos + len(wrong):]
                offset_delta += len(right) - len(wrong)
                start = pos + len(right)

        return corrected, corrections

    def _full_check(self, text: str) -> tuple[str, list[dict]]:
        """
        전체 텍스트를 CHUNK_SIZE 단위로 분할하여 hanspell 적용.

        Returns:
            (교정된 전체 텍스트, corrections 리스트)
        """
        chunks = self._split_chunks(text)
        corrected_parts: list[str] = []
        corrections: list[dict] = []
        offset = 0

        for i, chunk in enumerate(chunks):
            corrected_chunk = self._chunk_check(chunk)

            # 청크 내 교정 위치 추적 (단어 단위 diff)
            chunk_corrections = self._diff_corrections(chunk, corrected_chunk, offset)
            corrections.extend(chunk_corrections)
            corrected_parts.append(corrected_chunk)
            offset += len(chunk)

            if i < len(chunks) - 1:
                time.sleep(self.CHUNK_DELAY)

        return "".join(corrected_parts), corrections

    def _split_chunks(self, text: str) -> list[str]:
        """문장 경계를 최대한 유지하면서 CHUNK_SIZE 단위로 분할."""
        chunks: list[str] = []
        pos = 0
        length = len(text)

        while pos < length:
            end = pos + self.CHUNK_SIZE
            if end >= length:
                chunks.append(text[pos:])
                break

            # 청크 끝에서 가장 가까운 문장 부호 위치 탐색 (역방향)
            split_pos = end
            for i in range(end, max(pos + self.CHUNK_SIZE // 2, pos), -1):
                if text[i - 1] in (".", "!", "?", "\n"):
                    split_pos = i
                    break

            chunks.append(text[pos:split_pos])
            pos = split_pos

        return chunks

    def _diff_corrections(
        self, original: str, corrected: str, base_offset: int
    ) -> list[dict]:
        """
        원본·교정 청크를 단어 단위로 비교하여 corrections 리스트 생성.
        간단한 토큰 비교 방식 (difflib 미사용으로 의존성 최소화).
        """
        corrections: list[dict] = []
        orig_words = re.split(r"(\s+)", original)
        corr_words = re.split(r"(\s+)", corrected)

        pos = base_offset
        min_len = min(len(orig_words), len(corr_words))
        for i in range(min_len):
            o_word = orig_words[i]
            c_word = corr_words[i]
            if o_word != c_word and not re.fullmatch(r"\s*", o_word):
                corrections.append(
                    {"original": o_word, "corrected": c_word, "pos": pos}
                )
            pos += len(o_word)

        return corrections

    @staticmethod
    def _check_hanspell() -> bool:
        """py-hanspell 가용 여부 확인."""
        try:
            from hanspell import spell_checker  # noqa: F401

            return True
        except ImportError:
            print(
                "[spell_checker] py-hanspell 미설치 — 패턴 교정만 사용합니다.\n"
                "  설치: pip install py-hanspell"
            )
            return False

    @staticmethod
    def _empty_result(text: str) -> dict:
        return {
            "original": text,
            "corrected": text,
            "corrections": [],
            "error_count": 0,
            "error_rate": 0.0,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="STT 텍스트 한국어 맞춤법 교정기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="예시:\n  python spell_checker.py --file ../data/transcripts/sample.txt",
    )
    parser.add_argument(
        "--file",
        required=True,
        metavar="PATH",
        help="교정할 텍스트 파일 경로",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    checker = SpellChecker()
    checker.check_file(args.file)


if __name__ == "__main__":
    main()
