"""[Phase 3 후속 — D-0993d22f] Recency 가중치 — 지식 수명 관리.

00_DESIGN_TOC.md Phase 3 리스크 대응 항목("지식 수명 관리(Recency 가중치) → 미구현,
설계 문서에만 존재")을 구현한다. 오래된 지식(노드)일수록 탐색·랭킹에서 가중치가
지수적으로 감쇠하도록 한다 — 삭제하지 않고 순위만 낮춘다(자산 손실 0, T96 AISI 정신).
"""

from __future__ import annotations

from datetime import datetime, timezone

DEFAULT_HALF_LIFE_DAYS = 30.0  # 이 일수가 지나면 가중치가 절반으로 감쇠


def compute_recency_weight(
    created_at_iso: str | None,
    reference_time: datetime,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """created_at_iso 기준 경과일에 따른 지수감쇠 가중치(0.0 초과 ~ 1.0) 계산.

    created_at_iso가 없으면(과거 데이터 — merge_into_graph 배선 전 생성된 노드처럼
    타임스탬프가 없는 레거시) 1.0(중립·불이익 없음)을 반환한다 — 타임스탬프 부재를
    "오래됨"으로 추정하지 않는다(추정 금지, T98 AIP).
    """
    if not created_at_iso:
        return 1.0
    created_at = datetime.fromisoformat(created_at_iso)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (reference_time - created_at).total_seconds() / 86400.0)
    return 0.5 ** (age_days / half_life_days)
