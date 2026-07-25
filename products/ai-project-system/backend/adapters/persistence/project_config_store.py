"""[Phase 0] 프로젝트 등록·분야 선택 설정 — plans/_plan/04_PHASE0_PROJECT_REGISTRATION.md 구현.

사용자 원 요청 1번("프로젝트 관리 영역부터 먼저 어느 분야부터 선택")을 실제로 처리하는
데이터 모델. `agent-view/project-setup.html`(0차 마법사 UI)이 만든 JSON을 이 모듈이
검증·영속화한다.

이 설정이 확정돼야 이후 청크 분류기(classifier.py)가 "이 프로젝트가 다루는 영역"으로
1차 필터링할 근거가 생긴다(04_PHASE0 §2, "이 선택이 분류기의 1차 필터가 됨") — 그 연결은
후속 작업(분류기가 ProjectConfig를 optional로 받아 selected_areas 밖은 신뢰도를 낮추는
로직)이며, 이 모듈은 아직 그 연결 자체를 구현하지 않는다(과장 금지, T98 AIP) — 지금은
설정을 받고 검증·저장하는 것까지만.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from backend.domain.requirements.codes import DOC_TYPE_CODES, DOMAIN_CODES, LAYER_CODES

# 04_PHASE0_PROJECT_REGISTRATION.md §2 STEP5 "정보 접근 정책" — workbase STEP 6 그대로 계승.
ACCESS_POLICIES = {"PERSONAL", "ROLE", "SHARED"}  # 개인별 / 역할별 / 전체공유


class ProjectConfigValidationError(ValueError):
    pass


@dataclass
class ProjectConfig:
    project_name: str
    goal: str
    selected_areas: list[str] = field(default_factory=list)       # §5 area_code 중 다중선택
    selected_layers: list[str] = field(default_factory=list)      # §5-B layer_code 중 다중선택
    selected_doc_types: list[str] = field(default_factory=list)   # §5-A doc_type_code 중 다중선택
    solution_stack: list[str] = field(default_factory=list)       # 1차 §2-4 초기 태그
    access_policy: str = "SHARED"
    created_by: str = ""
    created_at: str = ""
    # plans/_plan/01_PHASE1_DATA_MODEL.md §5-1 / 04_PHASE0_PROJECT_REGISTRATION.md §7-A —
    # "프로젝트 전체 UI/UX 시안이 이미 확정됨" 플래그. STEP 6(완료 확인)에서 사람이 명시
    # 체크해야만 True가 된다(자동 추정 금지, 0-N No-Skip 원칙).
    project_design_draft_confirmed: bool = False
    project_design_draft_confirmed_by: str = ""
    project_design_draft_confirmed_at: str = ""


def validate_project_config(config: ProjectConfig) -> list[str]:
    """04_PHASE0 §2 6단계 중 필수 항목이 채워졌는지 확인. 부족하면 사유 목록을 반환.

    STEP1(기본정보)·STEP2(분야선택)만 필수로 본다 — STEP3(문서유형)·STEP4(프레임워크)는
    "권장"이지 진행을 막을 만큼 필수는 아니다(과잉 강제 회피, 헌법 §4 취지).
    """
    reasons = []
    if not config.project_name.strip():
        reasons.append("프로젝트명(STEP1)이 비어있음")
    if not config.goal.strip():
        reasons.append("목표 한 문장(STEP1)이 비어있음")
    if not config.selected_areas:
        reasons.append("분야 선택(STEP2)이 비어있음 — 사용자 원 요청의 핵심 첫 단계")

    unknown_areas = [a for a in config.selected_areas if a not in DOMAIN_CODES]
    if unknown_areas:
        reasons.append(f"미등록 영역코드: {unknown_areas} (허용: {sorted(DOMAIN_CODES)})")
    unknown_layers = [l for l in config.selected_layers if l not in LAYER_CODES]
    if unknown_layers:
        reasons.append(f"미등록 계층코드: {unknown_layers} (허용: {sorted(LAYER_CODES)})")
    unknown_doc_types = [d for d in config.selected_doc_types if d not in DOC_TYPE_CODES]
    if unknown_doc_types:
        reasons.append(f"미등록 문서유형코드: {unknown_doc_types} (허용: {sorted(DOC_TYPE_CODES)})")
    if config.access_policy not in ACCESS_POLICIES:
        reasons.append(f"미등록 접근정책: {config.access_policy} (허용: {sorted(ACCESS_POLICIES)})")

    return reasons


class ProjectConfigStore:
    """단일 프로젝트 설정 저장소 — 이 저장소 자체가 이 ai-project-system 인스턴스의
    "완료 확인"(04_PHASE0 §2 STEP6) 결과다. 여러 프로젝트를 한 인스턴스에서 관리하지 않는다
    (00_PROJECT_CONSTITUTION.md 스코프 — "프로젝트 하나"를 다루는 도구).
    """

    def __init__(self, store_path: Path):
        self._path = store_path

    def save(self, config: ProjectConfig, created_by: str) -> ProjectConfig:
        reasons = validate_project_config(config)
        if reasons:
            raise ProjectConfigValidationError("; ".join(reasons))
        config.created_by = created_by
        config.created_at = datetime.now(timezone.utc).isoformat()
        # §5-1/§7-A — STEP 6에서 체크박스가 True로 저장되면 created_by/created_at과
        # 동일한 저장 시점에 확정자·확정시각을 함께 기록한다(별도 API 호출 추가 없음).
        if config.project_design_draft_confirmed and not config.project_design_draft_confirmed_by:
            config.project_design_draft_confirmed_by = created_by
            config.project_design_draft_confirmed_at = config.created_at
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")
        return config

    def load(self) -> ProjectConfig | None:
        if not self._path.exists():
            return None
        return ProjectConfig(**json.loads(self._path.read_text(encoding="utf-8")))
