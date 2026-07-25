"""[Phase 6.1] 실패 패턴 기반 자가학습 루프 — 좁게 스코프된 읽기전용 분석.

**드리프트 재확인(00_PROJECT_CONSTITUTION.md §1·§4)**: 원래 Phase 6.1 "자가학습 루프"는
범용 AEGIS류 자율성장 엔진(코드 자동수정·스킬 자동승격)으로 해석될 위험이 있다 — §1이
"자가진화 Growth DNA"를 명시적 반예시로 든다. 이 모듈은 **그 위험을 피해 좁게 스코프**한다:
- 자동으로 분류기(classifier.py)나 태스크 판정 로직을 고쳐 쓰지 않는다(자율 코드 자기수정 0).
- 이미 각 레코드가 갖고 있던 신호(RequirementRecord.lifecycle_status="UNDER_REVIEW",
  Task.needs_escalation/escalation_reasons)를 **집계·표면화**만 한다 — 사람이 그 리포트를
  보고 분류 규칙(codes.py 키워드 등)을 개선할지 판단하는 것까지가 이 시스템의 책임.
- §1 목표("요구사항→구조화→태스크 관리")에 직접 기여: 반복되는 오분류·불충분 패턴을 찾아내면
  이 시스템 자체(분류 정확도·태스크 완성도)가 개선된다 — 그 개선 실행은 사람 몫.

즉 "자가학습"은 데이터 기반 사람 인사이트 제공이지, 자율 자기수정이 아니다(과장 금지 T98 AIP).
"""

from collections import defaultdict

from backend.adapters.persistence.requirement_store import RequirementRecord
from backend.domain.entities.task import Task


def analyze_requirement_review_patterns(requirements: list[RequirementRecord]) -> list[dict]:
    """UNDER_REVIEW(분류기가 자신 없어 사람 확인 대기 중)로 남아있는 요구사항을
    (doc_type_code, area_code) 조합별로 집계한다 — 어떤 조합에서 분류가 반복적으로
    애매한지 표면화(분류 키워드 보강 대상 후보를 사람에게 제시)."""
    groups: dict[tuple[str, str], list[RequirementRecord]] = defaultdict(list)
    for req in requirements:
        if req.lifecycle_status == "UNDER_REVIEW":
            groups[(req.doc_type_code, req.area_code)].append(req)

    patterns = []
    for (doc_type_code, area_code), records in groups.items():
        patterns.append(
            {
                "doc_type_code": doc_type_code,
                "area_code": area_code,
                "count": len(records),
                "avg_doc_type_confidence": round(sum(r.doc_type_confidence for r in records) / len(records), 3),
                "avg_area_confidence": round(sum(r.area_confidence for r in records) / len(records), 3),
                "example_req_ids": [r.req_id for r in records[:5]],
            }
        )
    patterns.sort(key=lambda p: p["count"], reverse=True)
    return patterns


def analyze_task_escalation_patterns(tasks: list[Task]) -> list[dict]:
    """needs_escalation=True(불충분·서킷브레이커 트립)로 남아있는 Task를 (domain_code, reason)
    조합별로 집계한다 — 어떤 도메인에서 어떤 사유가 반복되는지 표면화."""
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for task in tasks:
        if not task.needs_escalation:
            continue
        for reason in task.escalation_reasons or ["(사유 미기재)"]:
            groups[(task.domain_code, reason)].append(task.task_id)

    patterns = []
    for (domain_code, reason), task_ids in groups.items():
        patterns.append(
            {
                "domain_code": domain_code,
                "reason": reason,
                "count": len(task_ids),
                "example_task_ids": task_ids[:5],
            }
        )
    patterns.sort(key=lambda p: p["count"], reverse=True)
    return patterns
