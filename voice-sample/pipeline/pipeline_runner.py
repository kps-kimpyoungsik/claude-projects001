"""
pipeline_runner.py
전체 파이프라인: WAV 파일 → 최종 문서

사용법:
    python pipeline_runner.py --file audio.wav --topic 회의 --doctype docx
    python pipeline_runner.py --file audio.wav --topic 회의 --doctype pdf --template tmpl.docx
"""

from __future__ import annotations

import sys
# P02: UTF8-FORCE — Windows cp949 인코딩 오류 방지
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 로거 설정 (공통)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Stage 래퍼 — 시작/완료 로그 + elapsed 측정
# ---------------------------------------------------------------------------

def _run_stage(name: str, fn, *args, **kwargs):
    """
    단계 실행 래퍼.

    Parameters
    ----------
    name   : 단계 이름 (로그 출력용)
    fn     : 실행할 callable
    *args  : fn 에 전달할 위치 인자
    **kwargs : fn 에 전달할 키워드 인자

    Returns
    -------
    (result, elapsed_seconds)
    """
    logger.info("▶ [%s] 시작", name)
    t0 = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - t0
        logger.info("✔ [%s] 완료 (%.1fs)", name, elapsed)
        return result, elapsed
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        logger.error("✖ [%s] 실패 (%.1fs): %s", name, elapsed, exc)
        raise


# ---------------------------------------------------------------------------
# 각 모듈 동적 임포트 헬퍼
# (파이프라인 폴더가 sys.path 에 없을 수 있으므로 안전하게 처리)
# ---------------------------------------------------------------------------

def _import_pipeline_modules():
    """pipeline/ 폴더를 sys.path 에 추가하고 모듈을 임포트합니다."""
    pipeline_dir = Path(__file__).resolve().parent
    if str(pipeline_dir) not in sys.path:
        sys.path.insert(0, str(pipeline_dir))

    modules = {}

    # STTProcessor
    try:
        from batch_stt import STTProcessor  # type: ignore
        modules["STTProcessor"] = STTProcessor
    except ImportError as e:
        logger.warning("batch_stt 임포트 실패: %s", e)
        modules["STTProcessor"] = None

    # SpellChecker
    try:
        from spell_checker import SpellChecker  # type: ignore
        modules["SpellChecker"] = SpellChecker
    except ImportError as e:
        logger.warning("spell_checker 임포트 실패: %s", e)
        modules["SpellChecker"] = None

    # LLMSummarizer
    try:
        from llm_summarizer import LLMSummarizer  # type: ignore
        modules["LLMSummarizer"] = LLMSummarizer
    except ImportError as e:
        logger.warning("llm_summarizer 임포트 실패: %s", e)
        modules["LLMSummarizer"] = None

    # DocumentGenerator (항상 존재해야 함)
    from doc_generator import DocumentGenerator  # type: ignore
    modules["DocumentGenerator"] = DocumentGenerator

    return modules


# ---------------------------------------------------------------------------
# 폴백 구현체 (모듈 없을 때 사용)
# ---------------------------------------------------------------------------

class _FallbackSTT:
    """batch_stt 없을 때 파일 경로를 그대로 반환하는 더미."""

    def transcribe(self, wav_path: str) -> str:
        logger.warning(
            "[STT 폴백] batch_stt 모듈 없음 — WAV 경로를 텍스트로 사용: %s", wav_path
        )
        return f"(STT 미처리) {wav_path}"


class _FallbackSpell:
    """spell_checker 없을 때 입력을 그대로 반환하는 더미."""

    def check(self, text: str) -> str:
        logger.warning("[맞춤법 폴백] spell_checker 모듈 없음 — 원문 그대로 사용")
        return text


class _FallbackLLM:
    """llm_summarizer 없을 때 텍스트를 Markdown 형태로 감싸는 더미."""

    def summarize(self, text: str, topic: str) -> str:
        logger.warning("[LLM 폴백] llm_summarizer 모듈 없음 — 원문을 요약으로 사용")
        return f"# {topic}\n\n## 원문\n\n{text}"


# ---------------------------------------------------------------------------
# 메인 파이프라인 클래스
# ---------------------------------------------------------------------------

class PipelineRunner:
    """WAV → STT → 맞춤법 교정 → LLM 요약 → 문서 생성 전체 파이프라인."""

    def __init__(self):
        mods = _import_pipeline_modules()

        STTCls = mods.get("STTProcessor")
        SpellCls = mods.get("SpellChecker")
        LLMCls = mods.get("LLMSummarizer")
        DocCls = mods["DocumentGenerator"]

        self.stt: object = STTCls() if STTCls else _FallbackSTT()
        self.spell: object = SpellCls() if SpellCls else _FallbackSpell()
        self.llm: object = LLMCls() if LLMCls else _FallbackLLM()
        self.doc: object = DocCls()

    def run(
        self,
        wav_path: str,
        topic: str,
        doc_type: str = "docx",
        template_path: str | None = None,
    ) -> dict:
        """
        전체 파이프라인을 순서대로 실행합니다.

        Parameters
        ----------
        wav_path      : 입력 WAV 파일 경로
        topic         : 문서 주제
        doc_type      : 출력 문서 형식 ("docx"|"pdf"|"xlsx"|"pptx"|"hwpx")
        template_path : 문서 템플릿 파일 경로 (선택)

        Returns
        -------
        {
          "wav": str,
          "transcript": str,
          "corrected": str,
          "summary": str,
          "document": str,
          "stages": {"stt": "done"|"error", ...},
          "elapsed": {"stt": float, ...},
          "started_at": str,
          "finished_at": str,
          "total_elapsed": float,
        }
        """
        pipeline_start = time.perf_counter()
        started_at = datetime.now().isoformat(timespec="seconds")

        wav_path = str(Path(wav_path).resolve())
        results: dict = {
            "wav": wav_path,
            "transcript": "",
            "corrected": "",
            "summary": "",
            "document": "",
            "stages": {},
            "elapsed": {},
            "started_at": started_at,
            "finished_at": "",
            "total_elapsed": 0.0,
        }

        logger.info("=" * 60)
        logger.info("파이프라인 시작: topic=%s | doctype=%s | wav=%s",
                    topic, doc_type, wav_path)
        logger.info("=" * 60)

        # ----------------------------------------------------------------
        # Stage 1: STT (WAV → 텍스트)
        # ----------------------------------------------------------------
        try:
            transcript, elapsed = _run_stage(
                "STT",
                self._stt_stage,
                wav_path,
            )
            results["transcript"] = transcript
            results["stages"]["stt"] = "done"
            results["elapsed"]["stt"] = round(elapsed, 2)
        except Exception as exc:
            results["stages"]["stt"] = f"error: {exc}"
            results["elapsed"]["stt"] = 0.0
            logger.error("파이프라인 중단: STT 단계 실패")
            self._finalize(results, pipeline_start)
            return results

        # ----------------------------------------------------------------
        # Stage 2: 맞춤법 교정
        # ----------------------------------------------------------------
        try:
            corrected, elapsed = _run_stage(
                "맞춤법 교정",
                self._spell_stage,
                transcript,
            )
            results["corrected"] = corrected
            results["stages"]["spell"] = "done"
            results["elapsed"]["spell"] = round(elapsed, 2)
        except Exception as exc:
            # 맞춤법 실패 시 원문 그대로 진행
            logger.warning("맞춤법 교정 실패 — 원문으로 계속 진행: %s", exc)
            results["corrected"] = transcript
            results["stages"]["spell"] = f"skip: {exc}"
            results["elapsed"]["spell"] = 0.0

        # ----------------------------------------------------------------
        # Stage 3: LLM 요약
        # ----------------------------------------------------------------
        try:
            summary, elapsed = _run_stage(
                "LLM 요약",
                self._llm_stage,
                results["corrected"],
                topic,
            )
            results["summary"] = summary
            results["stages"]["llm"] = "done"
            results["elapsed"]["llm"] = round(elapsed, 2)
        except Exception as exc:
            results["stages"]["llm"] = f"error: {exc}"
            results["elapsed"]["llm"] = 0.0
            logger.error("파이프라인 중단: LLM 요약 단계 실패")
            self._finalize(results, pipeline_start)
            return results

        # 요약 중간 저장 (summaries 디렉토리)
        self._save_summary(results["summary"], topic)

        # ----------------------------------------------------------------
        # Stage 4: 문서 생성
        # ----------------------------------------------------------------
        try:
            doc_path, elapsed = _run_stage(
                "문서 생성",
                self._doc_stage,
                results["summary"],
                topic,
                doc_type,
                template_path,
            )
            results["document"] = doc_path
            results["stages"]["doc"] = "done"
            results["elapsed"]["doc"] = round(elapsed, 2)
        except Exception as exc:
            results["stages"]["doc"] = f"error: {exc}"
            results["elapsed"]["doc"] = 0.0
            logger.error("파이프라인 중단: 문서 생성 단계 실패")
            self._finalize(results, pipeline_start)
            return results

        self._finalize(results, pipeline_start)

        logger.info("=" * 60)
        logger.info("파이프라인 완료: 총 %.1fs | 문서: %s",
                    results["total_elapsed"], results["document"])
        logger.info("=" * 60)

        return results

    # ------------------------------------------------------------------
    # 각 Stage 실제 처리 메서드
    # ------------------------------------------------------------------

    def _stt_stage(self, wav_path: str) -> str:
        """WAV 파일을 텍스트로 변환합니다."""
        if not Path(wav_path).exists():
            raise FileNotFoundError(f"WAV 파일 없음: {wav_path}")

        # STTProcessor.transcribe() 또는 동등한 메서드 시도
        for method_name in ("transcribe", "process", "run"):
            method = getattr(self.stt, method_name, None)
            if method:
                result = method(wav_path)
                # 반환값이 dict 인 경우 텍스트 추출
                if isinstance(result, dict):
                    return result.get("text", result.get("transcript", str(result)))
                return str(result)

        raise AttributeError(
            f"STTProcessor에 transcribe/process/run 메서드가 없습니다: {type(self.stt)}"
        )

    def _spell_stage(self, text: str) -> str:
        """텍스트 맞춤법을 교정합니다."""
        for method_name in ("check", "correct", "run"):
            method = getattr(self.spell, method_name, None)
            if method:
                result = method(text)
                if isinstance(result, dict):
                    return result.get("checked", result.get("text", str(result)))
                return str(result)

        raise AttributeError(
            f"SpellChecker에 check/correct/run 메서드가 없습니다: {type(self.spell)}"
        )

    def _llm_stage(self, text: str, topic: str) -> str:
        """텍스트를 LLM으로 요약합니다."""
        for method_name in ("summarize", "run", "process"):
            method = getattr(self.llm, method_name, None)
            if method:
                # topic 인자 지원 여부에 따라 분기
                import inspect
                try:
                    sig = inspect.signature(method)
                    params = list(sig.parameters.keys())
                    if len(params) >= 2 and params[1] in ("topic", "title", "subject"):
                        result = method(text, topic)
                    elif len(params) >= 2:
                        result = method(text, topic)
                    else:
                        result = method(text)
                except (ValueError, TypeError):
                    result = method(text)

                if isinstance(result, dict):
                    return result.get("summary", result.get("text", str(result)))
                return str(result)

        raise AttributeError(
            f"LLMSummarizer에 summarize/run/process 메서드가 없습니다: {type(self.llm)}"
        )

    def _doc_stage(
        self,
        summary_md: str,
        topic: str,
        doc_type: str,
        template_path: str | None,
    ) -> str:
        """요약 Markdown → 문서 파일 생성."""
        return self.doc.generate(
            summary_md=summary_md,
            topic=topic,
            doc_type=doc_type,
            template_path=template_path,
        )

    # ------------------------------------------------------------------
    # 유틸
    # ------------------------------------------------------------------

    def _save_summary(self, summary: str, topic: str) -> None:
        """요약 텍스트를 summaries 디렉토리에 중간 저장합니다."""
        try:
            pipeline_dir = Path(__file__).resolve().parent
            summaries_dir = pipeline_dir.parent / "data" / "summaries"
            summaries_dir.mkdir(parents=True, exist_ok=True)

            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            import re
            safe_topic = re.sub(r'[\\/:*?"<>|]', "_", topic)
            out_path = summaries_dir / f"{date_str}_{safe_topic}.md"
            out_path.write_text(summary, encoding="utf-8")
            logger.info("[요약 저장] %s", out_path)
        except Exception as e:
            logger.warning("요약 중간 저장 실패 (계속 진행): %s", e)

    @staticmethod
    def _finalize(results: dict, pipeline_start: float) -> None:
        results["finished_at"] = datetime.now().isoformat(timespec="seconds")
        results["total_elapsed"] = round(time.perf_counter() - pipeline_start, 2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="WAV → STT → 맞춤법 → LLM 요약 → 문서 생성 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python pipeline_runner.py --file recording.wav --topic 주간회의 --doctype docx
  python pipeline_runner.py --file meeting.wav --topic 기획회의 --doctype pdf
  python pipeline_runner.py --file call.wav --topic 고객상담 --doctype xlsx
        """,
    )
    parser.add_argument("--file", required=True, help="입력 WAV 파일 경로")
    parser.add_argument("--topic", required=True, help="문서 주제 (파일명에 사용)")
    parser.add_argument(
        "--doctype", default="docx",
        choices=["docx", "pdf", "xlsx", "pptx", "hwpx"],
        help="출력 문서 형식 (기본: docx)",
    )
    parser.add_argument("--template", default=None, help="문서 템플릿 파일 경로 (선택)")
    args = parser.parse_args()

    runner = PipelineRunner()
    result = runner.run(
        wav_path=args.file,
        topic=args.topic,
        doc_type=args.doctype,
        template_path=args.template,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 비정상 종료 코드
    failed = [k for k, v in result["stages"].items() if str(v).startswith("error")]
    if failed:
        logger.error("실패한 단계: %s", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
