"""[Phase 3 x Phase 4 연결] REQ ID 파싱/채번 + 그래프 실재 검증 (순수 ID 로직).

헥사고날 리팩토링(2026-07-19, plans/_plan/05_REFACTOR_BACKEND_FRONTEND_STRUCTURE.md)으로
Requirement 노드/엣지 팩토리(make_requirement_node/make_implements_edge)는
`backend/domain/entities/requirement.py`로 분리했다 — 이 파일은 REQ ID 문자열 형식
검증·채번·그래프 참조 검증만 담당한다(CRZ — 재복제 없음).
"""

import re

from backend.domain.graph.entities import NodeKind
from backend.domain.requirements.codes import DOC_TYPE_CODES, DOMAIN_CODES

# REQ-{문서유형코드}-{영역코드}-{3자리 일련번호} — 00_PROJECT_CONSTITUTION.md §5(2026-07-18 갱신)
REQ_ID_PATTERN = re.compile(r"^REQ-(?P<doc_type>[A-Z]+)-(?P<area>[A-Z0-9]+)-(?P<seq>\d{3})$")


def parse_req_id(req_id: str, extra_doc_types: set[str] | None = None) -> dict:
    """REQ ID를 문서유형코드·영역코드·일련번호로 분해하며 형식을 검증한다.

    미등록 코드나 형식 위반은 여기서 즉시 거부한다(추정 요구사항 생성 금지 원칙의 연장).

    [2026-07-23 고도화] `extra_doc_types` — "프로젝트 배경 문서유형을 동적으로 추가 가능하게"
    (사용자 지시) 대응. 이 도메인 모듈은 헥사고날 규칙상 영속 계층(동적 문서유형 레지스트리)을
    import할 수 없으므로, 이미 검증된 코드 집합을 **호출자(API 레이어)가 주입**하는 방식으로
    확장한다 — `codes.py`의 `DOC_TYPE_CODES`(SSOT, 내장 8종)는 그대로 두고 합집합만 검사.
    미지정 시 기존과 100% 동일하게 동작(하위호환, 회귀 0)."""
    match = REQ_ID_PATTERN.match(req_id)
    if not match:
        raise ValueError(
            f"{req_id}: 'REQ-{{문서유형코드}}-{{영역코드}}-{{3자리번호}}' 형식 위반 "
            f"(예: REQ-BIZ-SEC-003)"
        )
    doc_type, area, seq = match["doc_type"], match["area"], match["seq"]
    known_doc_types = DOC_TYPE_CODES if not extra_doc_types else (set(DOC_TYPE_CODES) | extra_doc_types)
    if doc_type not in known_doc_types:
        raise ValueError(f"{req_id}: 미등록 문서유형코드 '{doc_type}' (허용: {sorted(known_doc_types)})")
    if area not in DOMAIN_CODES:
        raise ValueError(f"{req_id}: 미등록 영역코드 '{area}' (허용: {sorted(DOMAIN_CODES)})")
    return {"doc_type_code": doc_type, "area_code": area, "seq": seq}


def build_req_id(doc_type_code: str, area_code: str, seq: int, extra_doc_types: set[str] | None = None) -> str:
    """문서유형코드+영역코드+일련번호로 REQ ID를 채번한다(형식은 즉시 자기검증)."""
    req_id = f"REQ-{doc_type_code}-{area_code}-{seq:03d}"
    parse_req_id(req_id, extra_doc_types=extra_doc_types)
    return req_id


def verify_task_requirement_links(task_source_req_ids: list[str], graph: dict) -> tuple[bool, list[str]]:
    """태스크의 source_req_ids가 그래프상 실제 Requirement 노드로 존재하는지 확인.

    존재하지 않는 REQ 코드를 참조하는 태스크는 "근거 없는 태스크"이므로 이 함수가
    False + 누락 목록을 반환 — backend.domain.requirements.conflict_detection.check_sufficiency()
    와는 별개로, "그래프에 실제로 등록된 요구사항인가"까지 확인하는 더 강한 검증이다.
    """
    req_node_ids = {n["node_id"] for n in graph.get("nodes", []) if n.get("kind") == NodeKind.REQUIREMENT.value}
    missing = [rid for rid in task_source_req_ids if rid not in req_node_ids]
    return (len(missing) == 0, missing)
