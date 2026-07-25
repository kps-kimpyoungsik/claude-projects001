"""[Phase 2 후속, 2026-07-22] Ollama 기반 실제 LLM 의미청킹 판단 어댑터.

`SemanticJudgePort`의 실제 구현체 — 로컬 Ollama(127.0.0.1:11434, API 키 불요·인증 없음
로컬호스트라 SAFETY 비밀키 게이트 대상 아님)의 `qwen2.5:1.5b` 모델을 호출해 헤딩 기준
후보 섹션들 간의 의미적 관계(continues/references/elaborates/contradicts/summarizes)를
판단한다. 실측 확인(2026-07-22): `curl 127.0.0.1:11434/api/tags` → qwen2.5:1.5b(completion,
tools) + bge-m3(embedding) 설치 확인 후 채택 — 새 라이브러리·API 키 발급 없이 이미 떠 있는
로컬 인프라를 그대로 재사용한다(CRZ).

**출처 확실성 강제(사용자 지시 2026-07-22)**: LLM이 응답한 관계마다 `evidence`(원문 인용
문구)가 실제로 해당 섹션 본문에 문자 그대로 존재하는지 `str.find()`로 검증한다 — 존재하지
않으면(할루시네이션) 그 관계를 조용히 버린다(과장 없이 반려, 개수를 부풀리지 않음).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from backend.application.ports.semantic_judge_port import (
    ChunkRelationship,
    SemanticJudgePort,
    SemanticJudgment,
)

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:1.5b"
MAX_SECTION_CHARS_IN_PROMPT = 800  # 프롬프트 폭주 방지 — 관계판단엔 발췌로 충분
VALID_RELATION_TYPES = {"continues", "references", "elaborates", "contradicts", "summarizes"}


class OllamaUnavailableError(RuntimeError):
    """Ollama 서버 미기동/타임아웃 — 호출자가 폴백(관계 0건) 여부를 결정하도록 구분해서 던진다."""


class OllamaSemanticJudge(SemanticJudgePort):
    def __init__(self, model: str = DEFAULT_MODEL, timeout: int = 60, url: str = OLLAMA_URL):
        self._model = model
        self._timeout = timeout
        self._url = url

    def judge(self, sections: list[dict]) -> SemanticJudgment:
        if len(sections) < 2:
            # 섹션이 1개 이하면 "관계"라는 개념 자체가 성립하지 않는다 — LLM 호출 없이 정직 반환
            return SemanticJudgment(merged_boundaries=list(range(len(sections))), model_name=self._model)

        prompt = self._build_prompt(sections)
        raw_response = self._call_ollama(prompt)
        return self._parse_response(raw_response, sections)

    def _build_prompt(self, sections: list[dict]) -> str:
        numbered = "\n\n".join(
            f"[SECTION {i}] (heading: {' > '.join(s.get('heading_path') or []) or '(없음)'})\n"
            f"{s['content'][:MAX_SECTION_CHARS_IN_PROMPT]}"
            for i, s in enumerate(sections)
        )
        return (
            "다음은 한 문서를 헤딩 기준으로 나눈 섹션들이다. 섹션 간 의미적 관계를 분석하라.\n"
            "각 관계마다 반드시 원문에서 그 판단의 근거가 되는 정확한 문구(evidence)를 그대로 "
            "인용해야 한다(근거 없이 관계를 만들지 말 것 — 근거 문구는 반드시 from 섹션 본문에서 "
            "토씨 하나 틀리지 않게 가져올 것).\n\n"
            f"{numbered}\n\n"
            "아래 JSON 형식으로만 응답하라(다른 설명 텍스트 없이):\n"
            '{"relationships": [{"from": 0, "to": 1, '
            '"type": "continues|references|elaborates|contradicts|summarizes", '
            '"evidence": "원문에서 그대로 인용한 근거 문구", "confidence": 0.0}]}'
        )

    def _call_ollama(self, prompt: str) -> str:
        payload = json.dumps(
            {"model": self._model, "prompt": prompt, "stream": False, "format": "json"}
        ).encode("utf-8")
        req = urllib.request.Request(
            self._url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise OllamaUnavailableError(f"Ollama 호출 실패({self._url}): {exc}") from exc
        return body.get("response", "{}")

    def _parse_response(self, raw: str, sections: list[dict]) -> SemanticJudgment:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # LLM이 JSON 형식을 못 지켰을 때 — 관계 0건으로 정직 처리(추정으로 채우지 않음)
            return SemanticJudgment(
                merged_boundaries=list(range(len(sections))), model_name=self._model, raw_confidence=0.0
            )

        relationships: list[ChunkRelationship] = []
        for r in parsed.get("relationships", []):
            from_idx = r.get("from")
            to_idx = r.get("to")
            evidence = r.get("evidence", "") or ""
            if from_idx is None or to_idx is None:
                continue
            if not (0 <= from_idx < len(sections)) or not (0 <= to_idx < len(sections)):
                continue
            if not evidence:
                continue

            # 출처 확실성 검증(사용자 지시 핵심): evidence가 from 섹션 원문에 실제로 존재하는지 확인.
            # 실측(2026-07-22): qwen2.5:1.5b가 from/to를 가끔 뒤바꿔 응답하는 오류를 관찰(evidence는
            # to 섹션 것인데 from을 그 섹션 인덱스로 잘못 표기) — from에서 못 찾으면 to에서도 확인해
            # 실제 위치를 찾은 쪽을 채택한다(여전히 "원문에 문자 그대로 존재"만 통과, 완전 창작만 반려).
            pos = sections[from_idx]["content"].find(evidence)
            evidence_section_idx = from_idx
            if pos == -1:
                pos = sections[to_idx]["content"].find(evidence)
                evidence_section_idx = to_idx
            if pos == -1:
                continue  # 어느 섹션에도 문자 그대로 존재하지 않음 — 할루시네이션으로 판정, 반려

            base_char_start = sections[evidence_section_idx].get("char_start")
            evidence_char_start = (base_char_start + pos) if base_char_start is not None else pos
            evidence_char_end = evidence_char_start + len(evidence)

            # 실측(2026-07-22): 소형모델(1.5B)이 가끔 포맷 설명 문자열("a|b|c")을 그대로
            # 복사해 응답 — 유효 타입 집합에 없으면 "unclassified"로 정직 표기(과장 금지).
            relation_type = r.get("type", "")
            if relation_type not in VALID_RELATION_TYPES:
                relation_type = "unclassified"

            relationships.append(
                ChunkRelationship(
                    from_index=from_idx,
                    to_index=to_idx,
                    relation_type=relation_type,
                    evidence=evidence,
                    evidence_char_start=evidence_char_start,
                    evidence_char_end=evidence_char_end,
                    confidence=float(r.get("confidence", 0.0) or 0.0),
                )
            )

        return SemanticJudgment(
            merged_boundaries=list(range(len(sections))),
            relationships=relationships,
            model_name=self._model,
        )
