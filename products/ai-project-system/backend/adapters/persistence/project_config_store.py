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

from backend.domain.requirements.codes import (
    DOC_TYPE_CODES,
    DOMAIN_CODES,
    LAYER_CODES,
    NETWORK_ZONE_PRESETS,
)

# 04_PHASE0_PROJECT_REGISTRATION.md §2 STEP5 "정보 접근 정책" — workbase STEP 6 그대로 계승.
ACCESS_POLICIES = {"PERSONAL", "ROLE", "SHARED"}  # 개인별 / 역할별 / 전체공유

# [2026-07-25 §8-5] 보안 레벨 3단계 프리셋 — "자유입력"이 아니라 고정 enum(그냥 선택만 원함).
SECURITY_LEVELS = {"standard", "enhanced", "custom"}
PASSWORD_HASH_ALGOS = {"sha256", "bcrypt", "argon2id"}


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
    # [2026-07-25 §8-3] HA(이중화) 조건부 아키텍처 옵션 — 전부 옵셔널 기본값(단일 구성
    # 프로젝트는 아래 필드를 아예 안 채워도 회귀 없음, §8-3 하위호환).
    is_ha: bool = False
    ha_management: str | None = None       # "keepalived_vip" | "pacemaker_corosync" | "cloud_lb" | 자유입력
    uses_websocket: bool = False
    realtime_backplane: str | None = None  # "redis" | "nats" | None
    uses_grid: bool = False
    grid_solution: str | None = None
    grid_is_opensource: bool | None = None
    grid_guide_url: str | None = None
    has_ai_workload: bool = False
    llm_solution: str | None = None
    llm_server_info: str | None = None
    has_report: bool = False
    report_solution: str | None = None
    report_is_free: bool | None = None
    report_guide_url: str | None = None
    # [2026-07-25 §8-5] 보안 레벨 선택 — "그냥 선택만" 요청에 맞춘 3단계 프리셋.
    security_level: str = "standard"        # "standard" | "enhanced" | "custom"
    use_https: bool = False
    tls_cert_type: str | None = None        # "self_signed" | "public_ca"
    password_hash_algo: str = "sha256"      # "sha256" | "bcrypt" | "argon2id"
    session_based_login: bool = True        # 항상 True(끌 수 없음 — UI에도 비활성 표시)
    # [2026-07-25 §8-9] 인프라 존(네트워크 구성) — STEP3 신설. 사용자 명시 요청(2026-07-25
    # AskUserQuestion)에 따라 zone은 고정 enum이 아니라 사용자가 자유롭게 추가/삭제 가능한
    # 리스트다(NETWORK_ZONE_PRESETS는 최초 활성화 시 시드값일 뿐). 서버·허용규칙도 개수 제한 없이
    # 동적으로 추가 가능(list[dict], nested dataclass 미사용 — JSON 왕복 시 dict↔객체 비대칭
    # 문제 회피, CRZ: solution_stack과 동일하게 plain list로 유지).
    infra_configured: bool = False
    infra_zones: list[dict] = field(default_factory=list)         # [{code,label,exposed}]
    infra_servers: list[dict] = field(default_factory=list)       # [{name,zone,role,ip,ports:[int],https_only,description}]
    infra_allow_rules: list[dict] = field(default_factory=list)   # [{from_server,to_server,allowed_ports:[int],protocol}]
    enforce_https_external: bool = True
    relay_required: bool = True


def validate_project_config(config: ProjectConfig) -> list[str]:
    """04_PHASE0 §2 6단계 중 필수 항목이 채워졌는지 확인. 부족하면 사유 목록을 반환.

    STEP1(기본정보)·STEP2(분야선택)만 필수로 본다 — STEP3(인프라 구성)은 infra_configured=False가
    기본값이라 자체적으로 옵션이고, STEP4(문서유형)·STEP5(프레임워크)는 "권장"이지 진행을 막을
    만큼 필수는 아니다(과잉 강제 회피, 헌법 §4 취지). [2026-07-25 STEP3 인프라구성 신설로 구
    STEP3~6 → 4~7 순연 — 이 주석의 STEP 번호도 함께 갱신, 독립 코드리뷰 MINOR #3 대응]
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

    # [2026-07-25 §8-3/§8-5] ha_management/realtime_backplane/grid_solution/llm_solution/
    # report_solution은 §8-4 추천목록 + 자유입력을 함께 허용하는 설계라 enum 검증하지 않는다
    # (자유 텍스트 그대로 신뢰 — solution_stack 태그와 동일 원칙, CRZ). security_level/
    # password_hash_algo만 "그냥 선택만" 요청대로 고정 enum이라 검증한다.
    if config.security_level not in SECURITY_LEVELS:
        reasons.append(f"미등록 보안레벨: {config.security_level} (허용: {sorted(SECURITY_LEVELS)})")
    if config.password_hash_algo not in PASSWORD_HASH_ALGOS:
        reasons.append(f"미등록 비밀번호 해시 알고리즘: {config.password_hash_algo} (허용: {sorted(PASSWORD_HASH_ALGOS)})")

    # [2026-07-25 §8-9] 인프라 존 검증 — infra_configured=False(기본값)면 완전히 건너뛴다(§8-3
    # is_ha와 동일 원칙, 단일 구성 프로젝트는 이 절 자체가 무의미). zone "이름 자체"는 사용자가
    # 자유롭게 추가하므로(고정 enum 아님) 새 이름을 만드는 것 자체는 막지 않되, **서버가 참조하는
    # zone은 반드시 등록(프리셋 또는 infra_zones)되어 있어야 한다** — 등록되지 않은 zone 참조를
    # 그냥 통과시키면 "zone을 삭제해 고아 서버로 만들면 exposed 검사 자체가 스킵되는" 우회 경로가
    # 생긴다(2026-07-25 독립 코드리뷰 CRITICAL #1 실측 확인 — zone_exposed 딕셔너리에 없는 zone은
    # 검사 자체가 통째로 스킵됐던 이전 버전 버그). role도 마찬가지로 "값이 있으면 검사"가 아니라
    # 항상 필수 필드로 요구한다(비워서 DB 역할 검사를 회피하는 경로 차단, 독립 코드리뷰 MAJOR #2).
    if config.infra_configured:
        zone_exposed = {code: preset["exposed"] for code, preset in NETWORK_ZONE_PRESETS.items()}
        for z in config.infra_zones:
            if isinstance(z, dict) and z.get("code"):
                zone_exposed[z["code"]] = bool(z.get("exposed", False))

        server_by_name = {}
        for s in config.infra_servers:
            name = s.get("name") if isinstance(s, dict) else None
            if not name:
                reasons.append("인프라 서버 항목에 name이 비어있음")
                continue
            if name in server_by_name:
                reasons.append(f"인프라 서버명 중복: {name}")
            server_by_name[name] = s
            role = s.get("role")
            if not role:
                reasons.append(f"인프라 서버 '{name}': role이 필수입니다(DOMAIN_CODES 중 하나)")
            elif role not in DOMAIN_CODES:
                reasons.append(f"인프라 서버 '{name}'의 미등록 role: {role} (허용: {sorted(DOMAIN_CODES)})")
            zone = s.get("zone")
            if not zone or zone not in zone_exposed:
                reasons.append(f"인프라 서버 '{name}': 미등록 zone 참조({zone!r}) — 존을 먼저 등록하거나 삭제된 zone을 참조하고 있지 않은지 확인 필요")
            elif zone_exposed[zone] and role == "DB":
                reasons.append(f"인프라 서버 '{name}': 외부 노출 존({zone})에 DB 역할 서버를 배치할 수 없음(외부→DB 직접 접근 금지 정책)")

        for r in config.infra_allow_rules:
            if not isinstance(r, dict):
                continue
            from_name, to_name = r.get("from_server"), r.get("to_server")
            if not from_name or not to_name:
                reasons.append(f"인프라 허용규칙: from_server/to_server는 모두 필수입니다(from={from_name!r}, to={to_name!r})")
                continue
            if from_name == to_name:
                reasons.append(f"인프라 허용규칙: 자기참조 규칙은 허용되지 않음({from_name})")
            from_srv, to_srv = server_by_name.get(from_name), server_by_name.get(to_name)
            if not from_srv:
                reasons.append(f"인프라 허용규칙: 미등록 출발 서버 참조 {from_name}")
            if not to_srv:
                reasons.append(f"인프라 허용규칙: 미등록 도착 서버 참조 {to_name}")
            if config.relay_required and to_srv and to_srv.get("role") == "DB" and (not from_srv or from_srv.get("role") != "GW"):
                reasons.append(f"인프라 허용규칙 {from_name}→{to_name}: 중계서버(role=GW) 경유 없이 DB에 직접 접근하는 규칙은 금지(relay_required 정책)")
            allowed_ports = r.get("allowed_ports") or []
            to_ports = (to_srv or {}).get("ports") or []
            if to_srv and any(p not in to_ports for p in allowed_ports):
                reasons.append(f"인프라 허용규칙 {from_name}→{to_name}: allowed_ports가 도착 서버가 실제 리스닝하는 ports의 부분집합이 아님")

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
