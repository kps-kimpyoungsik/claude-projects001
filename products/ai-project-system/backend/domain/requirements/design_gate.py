"""[Phase 1 §5-2] 디자인 시안 선행 게이트 판정 — 순수 로직(I/O 없음).

`backend/domain/requirements/conflict_detection.py`가 이미 "태스크 충분성·충돌"이라는
별개 관심사를 다루고 있어(파일 상단 주석 참조) 이 게이트 판정 로직을 그 파일에 얹지
않는다 — "요구사항 하나가 디자인 시안을 선행 조건으로 요구하는가"는 Task가 아니라
Requirement 단위 개념이고, `RequirementRecord`/`ProjectConfig` 두 스토어의 필드만 읽어
결정하는 순수 함수라 도메인 로직(backend/domain/requirements/)에 작은 전용 모듈로 두는
것이 "무엇을 계산하는지"가 파일명만 봐도 드러나 더 명확하다(CRZ — 기존 conflict_detection
을 억지로 재사용하면 오히려 "태스크 충분성"과 "요구사항 게이트"라는 서로 다른 개념이
한 파일에 뒤섞인다).

plans/_plan/01_PHASE1_DATA_MODEL.md §5-2 pseudocode를 그대로 옮긴 것 — 새 규칙 발명 없음.
"""

from backend.domain.requirements.codes import DESIGN_GATE_VALUES

# §5-2 게이트가 실제로 걸릴 수 있는 값(NOT_MANDATORY/None은 애초에 게이트 대상이 아님).
_GATED_VALUES = {"MANDATORY", "STRATEGIC_MANDATORY"}

# evaluate_design_draft_gate()의 반환값 3종.
PASS = "PASS"                        # 게이트 없음/자동 통과 — 배너 없음
BLOCK_MANDATORY = "BLOCK_MANDATORY"  # MANDATORY 선행 강제(차단은 아님 — 04_PHASE0 §7 "경고 후 진행 여부는 사람이 결정")
WARN_STRATEGIC = "WARN_STRATEGIC"    # STRATEGIC_MANDATORY 권장 배너(강제 아님)


def evaluate_design_draft_gate(
    design_draft_gate: str | None,
    design_draft_gate_override: bool,
    project_design_draft_confirmed: bool,
) -> str:
    """§5-2 판정 규칙을 그대로 구현한다:

    1) design_draft_gate가 MANDATORY/STRATEGIC_MANDATORY가 아니면(NOT_MANDATORY 또는
       미분류) → 애초에 게이트 대상이 아니다 → PASS
    2) design_draft_gate_override == True → project 확정 여부와 무관하게 원래 규칙(§5-2-A)
       그대로 적용 — override가 최우선(사용자가 이 요구사항만은 별도 화면/패턴이 필요하다고
       수기 지정한 경우)
    3) (override가 아니고) project_design_draft_confirmed == True → 게이트 자동 통과(이미
       확정된 프로젝트 공통 시안을 재사용) → PASS
    4) 그 외 → §5-2-A 원래 규칙 그대로 적용 — MANDATORY는 BLOCK_MANDATORY(선행 강제),
       STRATEGIC_MANDATORY는 WARN_STRATEGIC(권장 배너, 강제 아님)로 차등 처리

    반환값은 위 3종(PASS/BLOCK_MANDATORY/WARN_STRATEGIC) 중 하나 — 이 함수 자체는 "게이트가
    작동해야 하는가·어떤 수준으로 작동해야 하는가"만 판정하고, 실제 배너 렌더링·차단 여부는
    호출부(04_PHASE0 STEP 6 화면/Phase 1 착수 화면)의 몫이다(과장 금지, T98 AIP).
    """
    if design_draft_gate not in DESIGN_GATE_VALUES or design_draft_gate not in _GATED_VALUES:
        return PASS

    if not design_draft_gate_override and project_design_draft_confirmed:
        return PASS

    return BLOCK_MANDATORY if design_draft_gate == "MANDATORY" else WARN_STRATEGIC
