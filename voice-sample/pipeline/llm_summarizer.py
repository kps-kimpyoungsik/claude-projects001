"""
llm_summarizer.py
교정된 텍스트 → Claude API로 주제별 LLM 요약 (map-reduce 방식)

사용법:
    python llm_summarizer.py --file ../data/corrected/파일_corrected.txt --topic 회의 --doctype docx
"""

import sys
# P02: UTF8-FORCE — Windows cp949 인코딩 오류 방지
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

import anthropic

# Claude Code OAuth 인증 — CLI subprocess 방식 (ANTHROPIC_API_KEY 불필요)
from claude_auth import ask_claude

# ---------------------------------------------------------------------------
# 상수 정의
# ---------------------------------------------------------------------------

MODEL = "claude-opus-4-5"  # 요청 모델명 (실제 배포 시 최신 모델로 교체)
CHUNK_SIZE = 3000           # 청크 분할 단위 (자)
MAX_TOKENS = 4096           # 요약 응답 최대 토큰

# 주제 키워드 → 스타일 매핑 (정규식 패턴)
TOPIC_STYLES: dict[str, str] = {
    r"회의|미팅|보고|회의록": "meeting_minutes",
    r"강의|교육|세미나|수업": "lecture_notes",
    r"인터뷰|면담": "interview",
    r"발표|브리핑|프레젠테이션": "presentation",
    r"데이터|분석|통계": "data_analysis",
}
DEFAULT_STYLE = "general"

# 문서 유형별 섹션 템플릿
DOC_TEMPLATES: dict[str, dict] = {
    "meeting_minutes": {
        "sections": ["개요", "참석자", "안건", "주요내용", "결론", "Action Items"],
        "description": "회의록 형식으로 안건·결론·Action Items 중심 정리",
    },
    "lecture_notes": {
        "sections": ["주제", "핵심개념", "요약", "중요포인트", "Q&A"],
        "description": "강의 노트 형식으로 핵심개념과 학습 포인트 정리",
    },
    "interview": {
        "sections": ["개요", "인터뷰이 소개", "주요 질문", "핵심 답변", "인사이트", "결론"],
        "description": "Q&A 형식으로 인터뷰 내용 정리",
    },
    "presentation": {
        "sections": ["제목", "개요", "본론1", "본론2", "본론3", "결론"],
        "description": "슬라이드 구조 기반으로 발표 내용 정리",
    },
    "data_analysis": {
        "sections": ["분석목적", "주요지표", "결과", "인사이트", "권고사항"],
        "description": "표·수치 중심으로 데이터 분석 결과 정리",
    },
    "general": {
        "sections": ["개요", "주요내용", "핵심포인트", "결론"],
        "description": "일반 문서 형식으로 핵심 내용 요약",
    },
}

# 문서 유형 레이블 (--doctype 인자 표시용)
DOC_TYPE_LABELS: dict[str, str] = {
    "docx": "Word 문서",
    "pdf": "PDF 문서",
    "txt": "텍스트 파일",
    "stt": "STT 변환본",
}


# ---------------------------------------------------------------------------
# LLMSummarizer 클래스
# ---------------------------------------------------------------------------


class LLMSummarizer:
    """
    Claude API를 활용한 텍스트 요약기.

    - 3000자 단위 청크 분할 → 개별 요약 → 최종 통합 (map-reduce)
    - 주제 키워드 기반 자동 스타일 감지
    - 스타일별 섹션 템플릿 적용 Markdown 출력
    """

    def __init__(self) -> None:
        pass  # Claude Code CLI subprocess 방식 — 별도 클라이언트 초기화 불필요

    # ------------------------------------------------------------------
    # 공개 메서드
    # ------------------------------------------------------------------

    def summarize(self, text: str, topic: str, doc_type: str = "docx") -> dict:
        """
        텍스트 요약 전체 파이프라인.

        Args:
            text:     요약할 전체 텍스트
            topic:    주제 키워드 (예: "회의", "강의")
            doc_type: 원본 문서 유형 (예: "docx", "pdf", "stt")

        Returns:
            {
                "topic": str,
                "style": str,
                "doc_type": str,
                "sections": list[str],
                "summary": str,         # Markdown 전문
                "chunk_count": int,
                "summarized_at": str    # ISO8601
            }
        """
        if not text or not text.strip():
            raise ValueError("요약할 텍스트가 비어 있습니다.")

        style = self._detect_style(topic)
        template = DOC_TEMPLATES[style]
        doc_label = DOC_TYPE_LABELS.get(doc_type, doc_type)

        chunks = self._split_chunks(text)
        print(
            f"[llm_summarizer] 요약 시작 | 주제: {topic} | 스타일: {style} "
            f"| 청크: {len(chunks)}개"
        )

        if len(chunks) == 1:
            # 단일 청크: 바로 최종 요약
            chunk_summaries = [self._summarize_single(chunks[0], style, topic, doc_label, is_final=True)]
            final_summary = chunk_summaries[0]
        else:
            # map 단계: 청크별 중간 요약
            chunk_summaries = self._chunk_summarize(text, style)
            # reduce 단계: 중간 요약 통합
            final_summary = self._merge_summaries(chunk_summaries, style, topic, doc_label)

        return {
            "topic": topic,
            "style": style,
            "doc_type": doc_type,
            "sections": template["sections"],
            "summary": final_summary,
            "chunk_count": len(chunks),
            "summarized_at": datetime.now(timezone.utc).isoformat(),
        }

    def summarize_file(self, txt_path: str, topic: str, doc_type: str = "docx") -> str:
        """
        텍스트 파일 → 요약 → Markdown 저장.

        Returns:
            저장된 요약 파일 경로 (str)
        """
        src = Path(txt_path)
        if not src.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {txt_path}")

        text = src.read_text(encoding="utf-8")
        result = self.summarize(text, topic, doc_type)

        # 저장 디렉터리
        out_dir = src.parent.parent / "data" / "summaries"
        out_dir.mkdir(parents=True, exist_ok=True)

        # 파일명 생성 (stem에서 _corrected 제거)
        stem = re.sub(r"_corrected$", "", src.stem)
        safe_topic = re.sub(r"[^\w가-힣]", "_", topic)
        out_path = out_dir / f"{stem}_{safe_topic}_summary.md"

        out_path.write_text(result["summary"], encoding="utf-8")

        print(f"[llm_summarizer] 요약 저장 완료: {out_path}")
        return str(out_path)

    # ------------------------------------------------------------------
    # 내부 메서드
    # ------------------------------------------------------------------

    def _detect_style(self, topic: str) -> str:
        """
        주제 키워드를 정규식 패턴으로 매칭하여 스타일 반환.
        매칭 실패 시 DEFAULT_STYLE 반환.
        """
        for pattern, style in TOPIC_STYLES.items():
            if re.search(pattern, topic):
                return style
        return DEFAULT_STYLE

    def _chunk_summarize(self, text: str, style: str) -> list[str]:
        """
        map 단계: 텍스트를 청크로 분할하여 각각 중간 요약.

        Returns:
            청크별 중간 요약 리스트
        """
        chunks = self._split_chunks(text)
        summaries: list[str] = []

        for i, chunk in enumerate(chunks, 1):
            print(f"[llm_summarizer] 청크 {i}/{len(chunks)} 요약 중...")
            summary = self._summarize_single(
                chunk, style, topic="", doc_label="", is_final=False, chunk_idx=i, total_chunks=len(chunks)
            )
            summaries.append(summary)

        return summaries

    def _merge_summaries(
        self, chunks: list[str], style: str, topic: str, doc_label: str
    ) -> str:
        """
        reduce 단계: 청크별 중간 요약을 하나의 최종 요약으로 통합.

        Returns:
            최종 통합 요약 (Markdown 문자열)
        """
        template = DOC_TEMPLATES[style]
        sections_str = "\n".join(f"- {s}" for s in template["sections"])
        combined = "\n\n---\n\n".join(
            f"[부분 요약 {i + 1}]\n{s}" for i, s in enumerate(chunks)
        )

        system_prompt = self._build_system_prompt(style, template)

        user_prompt = f"""다음은 긴 문서를 청크로 나누어 요약한 부분 요약들입니다.
이 부분 요약들을 하나의 완성된 최종 요약으로 통합해 주세요.

문서 주제: {topic}
원본 문서 유형: {doc_label}
요약 스타일: {template['description']}

출력 형식:
- Markdown 형식
- 다음 섹션 구조 사용:
{sections_str}
- 각 섹션은 ## 헤더로 시작
- 문서 상단에 메타 정보 포함 (주제, 원본 유형, 작성일)
- 중복 내용 제거 후 핵심만 통합

--- 부분 요약 시작 ---
{combined}
--- 부분 요약 끝 ---

위 부분 요약들을 통합하여 완성된 최종 요약을 작성해 주세요."""

        print("[llm_summarizer] 최종 통합 요약 생성 중...")
        return self._call_api(system_prompt, user_prompt)

    def _summarize_single(
        self,
        chunk: str,
        style: str,
        topic: str,
        doc_label: str,
        is_final: bool,
        chunk_idx: int = 1,
        total_chunks: int = 1,
    ) -> str:
        """
        단일 청크 또는 단일 문서 요약 (Claude API 호출).

        Args:
            is_final: True면 최종 Markdown 출력, False면 중간 요약 텍스트
        """
        template = DOC_TEMPLATES[style]
        sections_str = "\n".join(f"- {s}" for s in template["sections"])
        system_prompt = self._build_system_prompt(style, template)

        if is_final:
            user_prompt = f"""다음 텍스트를 요약해 주세요.

문서 주제: {topic}
원본 문서 유형: {doc_label}
요약 스타일: {template['description']}

출력 형식:
- Markdown 형식
- 다음 섹션 구조 사용:
{sections_str}
- 각 섹션은 ## 헤더로 시작
- 문서 상단에 메타 정보 포함 (주제, 원본 유형, 작성일)

--- 텍스트 시작 ---
{chunk}
--- 텍스트 끝 ---"""
        else:
            user_prompt = f"""다음은 전체 문서의 일부입니다 ({chunk_idx}/{total_chunks} 부분).
핵심 내용을 간결하게 추출해 주세요. (이후 통합 요약에 사용됩니다)

요약 스타일: {template['description']}
추출 항목: {', '.join(template['sections'])}

--- 텍스트 시작 ---
{chunk}
--- 텍스트 끝 ---

핵심 내용을 bullet point 형식으로 추출해 주세요."""

        return self._call_api(system_prompt, user_prompt)

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Claude Code CLI subprocess로 단일 호출."""
        return ask_claude(
            prompt=user_prompt,
            model=MODEL,
            system=system_prompt,
            timeout=180,
        )

    @staticmethod
    def _build_system_prompt(style: str, template: dict) -> str:
        """스타일별 시스템 프롬프트 생성."""
        base = (
            "당신은 한국어 문서 요약 전문가입니다. "
            "STT(음성 인식) 변환 텍스트를 포함한 다양한 형식의 문서를 "
            "명확하고 구조화된 형태로 요약합니다.\n\n"
            "요약 원칙:\n"
            "1. 원문의 핵심 내용을 빠짐없이 포함\n"
            "2. 불필요한 반복·필러 단어 제거\n"
            "3. 전문 용어는 그대로 유지\n"
            "4. 숫자·날짜·고유명사는 정확하게 기재\n"
            "5. 한국어로 작성 (영문 용어는 병기 가능)\n"
        )
        style_specific = {
            "meeting_minutes": "6. Action Items는 담당자·기한과 함께 명시\n7. 결론은 합의 사항 중심으로 작성",
            "lecture_notes": "6. 핵심개념은 정의와 함께 작성\n7. 중요포인트는 강조 표시",
            "interview": "6. 질문과 답변을 명확히 구분\n7. 인터뷰이의 주요 견해 강조",
            "presentation": "6. 각 본론 섹션은 독립적으로 이해 가능하게 작성\n7. 핵심 메시지를 굵게 표시",
            "data_analysis": "6. 수치는 단위와 함께 명시\n7. 인사이트는 데이터 근거 포함",
            "general": "6. 읽는 사람이 원문 없이도 내용을 파악할 수 있게 작성",
        }
        return base + style_specific.get(style, style_specific["general"])

    @staticmethod
    def _split_chunks(text: str) -> list[str]:
        """문장 경계를 유지하면서 CHUNK_SIZE 단위로 분할."""
        chunks: list[str] = []
        pos = 0
        length = len(text)

        while pos < length:
            end = pos + CHUNK_SIZE
            if end >= length:
                chunks.append(text[pos:])
                break

            # 청크 끝에서 가장 가까운 문장 부호 탐색 (역방향)
            split_pos = end
            for i in range(end, max(pos + CHUNK_SIZE // 2, pos), -1):
                if text[i - 1] in (".", "!", "?", "\n"):
                    split_pos = i
                    break

            chunks.append(text[pos:split_pos])
            pos = split_pos

        return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Claude API 기반 한국어 텍스트 요약기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시:\n"
            "  python llm_summarizer.py --file ../data/corrected/sample_corrected.txt --topic 회의 --doctype docx\n"
            "  python llm_summarizer.py --file ../data/corrected/lecture.txt --topic 강의 --doctype stt"
        ),
    )
    parser.add_argument(
        "--file",
        required=True,
        metavar="PATH",
        help="요약할 텍스트 파일 경로",
    )
    parser.add_argument(
        "--topic",
        required=True,
        metavar="TOPIC",
        help="문서 주제 키워드 (예: 회의, 강의, 인터뷰, 발표, 데이터)",
    )
    parser.add_argument(
        "--doctype",
        default="docx",
        metavar="TYPE",
        choices=list(DOC_TYPE_LABELS.keys()),
        help=f"원본 문서 유형 (기본값: docx) — 선택: {', '.join(DOC_TYPE_LABELS.keys())}",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    summarizer = LLMSummarizer()
    out_path = summarizer.summarize_file(args.file, args.topic, args.doctype)
    print(f"[llm_summarizer] 완료 → {out_path}")


if __name__ == "__main__":
    main()
