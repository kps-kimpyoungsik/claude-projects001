"""[Phase 2] SPC(Semantics-Preserving Chunking) 엔진 — 경계 분할 전략 + 오케스트레이션.

헥사고날 리팩토링(2026-07-19)으로 `backend/domain/chunk.py`에서 분리했다 — Chunk 엔티티는
`backend/domain/chunking/chunk.py`에 남기고, 실제 "논리적 경계 분할"(LLM이 주제 전환
지점을 식별)은 LLM 호출이 필요한 부분이라 이 스캐폴딩에서는 인터페이스만 정의하고
NotImplementedError로 명시한다 — 추정 구현으로 채우지 않는다(T98 AIP 정직성 원칙).

**2026-07-22 실제 구현 완료(사용자 지시: "LLM 연동해서 청킹 퀄리티를 끌어올려야 한다 /
문서 안 관계 판단도 해야 한다 / 출처가 확실해야 한다")**: SemanticBoundarySplitter가
`SemanticJudgePort`(주입형, Port/Adapter — docx_adapter.py와 동일 패턴)를 통해 실제 LLM
판단을 호출한다. 실구현체 `backend/adapters/llm/ollama_semantic_judge.py`는 로컬 Ollama
(127.0.0.1:11434, API 키 불요)의 qwen2.5:1.5b를 사용 — 실측(2026-07-22) 확인 후 채택.
judge 미주입 시에는 관계 판단 없이 HeadingBoundarySplitter와 동일하게 동작한다(과장 금지).
"""

import logging

from backend.application.ports.semantic_judge_port import SemanticJudgePort
from backend.domain.chunking.chunk import Chunk, inject_global_context

logger = logging.getLogger(__name__)


class SemanticBoundarySplitter:
    """헤딩 기준 경계(HeadingBoundarySplitter)를 뼈대로 삼고, 주입된 SemanticJudgePort로
    섹션 간 의미 관계(continues/references/elaborates/contradicts/summarizes)를 판단해
    각 섹션의 `relationships` 필드에 부착한다.

    judge=None이면 관계 판단을 생략하고 HeadingBoundarySplitter와 동일하게 동작한다
    ("의미를 이해해서 분할했다"고 과장하지 않는다, T98 AIP).
    """

    def __init__(self, judge: SemanticJudgePort | None = None):
        self._base = HeadingBoundarySplitter()
        self._judge = judge

    def split(self, markdown: str) -> list[str]:
        return [s["content"] for s in self.split_with_spans(markdown)]

    def split_with_spans(self, markdown: str) -> list[dict]:
        sections = self._base.split_with_spans(markdown)
        for s in sections:
            s.setdefault("relationships", [])

        if not sections or self._judge is None:
            return sections

        try:
            judgment = self._judge.judge(sections)
        except Exception as exc:
            # LLM 판단 실패(서비스 다운·타임아웃 등)는 업로드 파이프라인 전체를 막지 않는다 —
            # 관계정보 없이 헤딩 기준 분할 결과만 정직하게 반환한다(T99 AIOS 우아한 성능저하,
            # meta.degraded는 이 결과를 소비하는 상위 계층이 필요시 표기).
            # [2026-07-26 배선] 조용한 폴백이 아니라 최소 한 줄 로그는 남긴다 — 동작(폴백)
            # 자체는 그대로 유지, 관측 가능성만 추가(T98 AIP — 무로깅 실패 은폐 금지).
            logger.warning("semantic judge 실패 — heading 기준 폴백: %s", exc)
            return sections

        for rel in judgment.relationships:
            if 0 <= rel.from_index < len(sections):
                sections[rel.from_index]["relationships"].append(
                    {
                        "to_index": rel.to_index,
                        "type": rel.relation_type,
                        "evidence": rel.evidence,
                        "evidence_char_start": rel.evidence_char_start,
                        "evidence_char_end": rel.evidence_char_end,
                        "confidence": rel.confidence,
                        "model_name": judgment.model_name,
                    }
                )
        return sections


class HeadingBoundarySplitter:
    """마크다운 헤딩(#, ##, ...) 기준 결정론적 경계 분할기.

    "LLM이 주제 전환을 판단"하는 진짜 의미 분할은 아니지만, 정규화된 마크다운은
    이미 논리적 절 구분을 헤딩으로 표현하는 경우가 많아 실용적인 기본 전략이다.
    LLM 기반 SemanticBoundarySplitter가 준비되기 전까지의 결정론적 대체재이며,
    "의미를 이해해서 분할했다"고 과장하지 않는다(T98 AIP).
    """

    def split(self, markdown: str) -> list[str]:
        if not markdown.strip():
            return []
        lines = markdown.split("\n")
        sections: list[list[str]] = [[]]
        for line in lines:
            if line.lstrip().startswith("#") and sections[-1]:
                sections.append([])
            sections[-1].append(line)
        return ["\n".join(s).strip() for s in sections if "\n".join(s).strip()]

    def split_with_spans(self, markdown: str) -> list[dict]:
        """§1-2 SourceLocation용 — 같은 경계 분할 로직에 문자 오프셋·헤딩 경로를 함께 붙인다.

        미리보기 화면이 "이 요구사항이 원문 몇 번째 글자에서 나왔는지"를 하이라이트하려면
        분할 시점에 위치를 잃지 않고 들고 있어야 한다 — split() 이후에 원문을 다시 검색해서
        위치를 추정하면 중복 텍스트가 있을 때 틀릴 수 있어(예: "보안 요건"이 여러 곳에 반복),
        분할하는 바로 그 순간의 오프셋을 기록하는 것이 유일하게 정확한 방법이다.
        """
        if not markdown.strip():
            return []
        lines = markdown.split("\n")
        sections: list[dict] = []
        offset = 0
        heading_stack: list[str] = []
        current: dict | None = None

        for line in lines:
            line_start = offset
            offset += len(line) + 1  # +1 : split("\n")으로 사라진 개행 문자 보정
            stripped = line.lstrip()
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                heading_text = stripped[level:].strip()
                heading_stack = heading_stack[: max(level - 1, 0)] + [heading_text]
                if current is not None and current["lines"]:
                    sections.append(current)
                current = {"lines": [], "start": line_start, "heading_path": list(heading_stack)}
            if current is None:
                current = {"lines": [], "start": line_start, "heading_path": list(heading_stack)}
            current["lines"].append(line)

        if current is not None and current["lines"]:
            sections.append(current)

        results = []
        for s in sections:
            joined = "\n".join(s["lines"])
            content = joined.strip()
            if not content:
                continue
            results.append({
                "content": content,
                "char_start": s["start"],
                "char_end": s["start"] + len(joined),
                "heading_path": s["heading_path"],
            })
        return results


class SPCEngine:
    """의미 보존 청킹 엔진 — Parent(전체 맥락) + Child(세부 절) 계층 생성 + 맥락 강화.

    splitter 미지정 시 HeadingBoundarySplitter(결정론적)를 기본 사용한다.
    recall_hook은 착수 전 `/recall <Contextual_Retrieval_Rules>` 같은 조회를
    실제로 호출하고 싶을 때 주입하는 콜백이다 — 미주입 시 조회를 생략하고
    "recall 미실행"으로 정직하게 기록한다(가짜로 호출한 척 하지 않음).
    """

    def __init__(self, splitter: SemanticBoundarySplitter | HeadingBoundarySplitter | None = None,
                 recall_hook=None):
        self._splitter = splitter or HeadingBoundarySplitter()
        self._recall_hook = recall_hook

    def process_document(self, markdown_content: str, context_label: str, doc_id: str) -> list[Chunk]:
        recall_note = self._recall_hook("Contextual_Retrieval_Rules") if self._recall_hook else "recall 미실행(hook 미주입)"

        parent = Chunk(
            chunk_id=f"{doc_id}::parent",
            content=markdown_content[:500],  # 전체 맥락 대표 발췌(전문 아님 — 부모는 요약 성격)
            global_context={"role": "parent", "recall": recall_note},
            doc_id=doc_id,
        )

        # split_with_spans가 있으면(HeadingBoundarySplitter/SemanticBoundarySplitter 둘 다
        # 2026-07-22부터 지원) 위치정보+관계정보 포함, 없으면(구식 splitter) split()만 호출.
        if hasattr(self._splitter, "split_with_spans"):
            sections = self._splitter.split_with_spans(markdown_content)
        else:
            sections = [{"content": s, "char_start": None, "char_end": None, "heading_path": [],
                         "relationships": []}
                        for s in self._splitter.split(markdown_content)]

        children = [
            inject_global_context(
                Chunk(
                    chunk_id=f"{doc_id}::child:{i}",
                    content=section["content"],
                    parent_id=parent.chunk_id,
                    doc_id=doc_id,
                    heading_path=section["heading_path"],
                    char_start=section["char_start"],
                    char_end=section["char_end"],
                    # 2026-07-22: SemanticBoundarySplitter가 부착한 문서내 관계(출처 포함)를
                    # global_context에 그대로 보존한다(신규 필드 추가 없이 기존 dict 재사용, CRZ).
                    global_context={"relationships": section.get("relationships", [])},
                ),
                context_label,
            )
            for i, section in enumerate(sections)
        ]
        return [parent, *children]
