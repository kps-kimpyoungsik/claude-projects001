"""
post_pipeline.py
녹음 완료 후 파이프라인: transcript.txt → LLM 요약 → 문서 생성

Go 서버 subprocess로 호출됨. 진행 상황을 JSON 줄로 stdout에 출력.

사용법:
    python pipeline/post_pipeline.py \\
        --transcript recordings/topic/transcript.txt \\
        --topic 회의 \\
        --doctype docx \\
        --outdir recordings/topic
"""
from __future__ import annotations

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import argparse
import json
import os
import re
import time
from pathlib import Path

# pipeline/ 폴더를 sys.path에 추가
_PIPELINE_DIR = Path(__file__).resolve().parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))


# ── 이벤트 출력 ──────────────────────────────────────────────

def emit(event: str, **kw):
    """Go 서버가 읽는 JSON 한 줄 이벤트."""
    print(json.dumps({"event": event, **kw}, ensure_ascii=False), flush=True)


# ── 메인 ─────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="transcript → LLM 요약 → 문서 생성")
    p.add_argument("--transcript", required=True, help="transcript.txt 경로")
    p.add_argument("--topic",      required=True, help="문서 주제")
    p.add_argument("--doctype",    default="docx",
                   choices=["docx", "pdf", "xlsx", "pptx", "hwpx"],
                   help="출력 문서 형식 (기본: docx)")
    p.add_argument("--outdir",     required=True, help="출력 디렉토리")
    args = p.parse_args()

    tx_path = Path(args.transcript)
    out_dir = Path(args.outdir)

    # ── 전처리 검증 ──
    if not tx_path.exists():
        emit("error", message=f"transcript.txt 없음: {tx_path}")
        sys.exit(1)

    text = tx_path.read_text(encoding="utf-8").strip()
    if not text:
        emit("error", message="transcript.txt가 비어 있습니다")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Markdown 헤더 제거 (# 회의 전사 기록 같은 줄) — 순수 대화만 추출
    clean_lines = []
    for line in text.splitlines():
        # 헤더/날짜 줄 제거, 내용만 유지
        stripped = re.sub(r"\*\*\[[\d:]+\]\s*화자\d+\*\*", "", line).strip()
        stripped = re.sub(r"^#+\s.*", "", stripped).strip()
        if stripped:
            clean_lines.append(stripped)
    clean_text = "\n".join(clean_lines) if clean_lines else text

    emit("progress", step="summarizing", message="LLM 요약 시작...",
         char_count=len(clean_text))

    # ── Stage 1: LLM 요약 ──
    t0 = time.perf_counter()
    try:
        from llm_summarizer import LLMSummarizer
        summarizer = LLMSummarizer()
        result = summarizer.summarize(clean_text, args.topic, "stt")
        summary_md = result["summary"]
        elapsed_sum = round(time.perf_counter() - t0, 1)
    except Exception as e:
        emit("error", message=f"LLM 요약 실패: {e}")
        sys.exit(1)

    # 요약 저장
    sum_path = out_dir / "summary.md"
    sum_path.write_text(summary_md, encoding="utf-8")
    emit("progress", step="generating",
         message=f"요약 완료 ({elapsed_sum}s), 문서 생성 중...",
         sum_path=str(sum_path))

    # ── Stage 2: 문서 생성 ──
    t1 = time.perf_counter()
    try:
        from doc_generator import DocumentGenerator
        gen = DocumentGenerator()
        doc_path = gen.generate(
            summary_md=summary_md,
            topic=args.topic,
            doc_type=args.doctype,
            output_dir=str(out_dir),
        )
        elapsed_doc = round(time.perf_counter() - t1, 1)
    except Exception as e:
        emit("error", message=f"문서 생성 실패: {e}")
        sys.exit(1)

    total_elapsed = round(time.perf_counter() - t0, 1)
    emit("done",
         sum_path=str(sum_path),
         doc_path=doc_path,
         elapsed=total_elapsed,
         message=f"완료! 요약 {elapsed_sum}s + 문서 {elapsed_doc}s = 총 {total_elapsed}s")


if __name__ == "__main__":
    main()
