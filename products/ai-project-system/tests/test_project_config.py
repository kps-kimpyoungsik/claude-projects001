"""프로젝트 등록(0차) 설정 검증·영속화 회귀 테스트."""

import pytest

from backend.adapters.persistence.project_config_store import (
    ProjectConfig,
    ProjectConfigStore,
    ProjectConfigValidationError,
    validate_project_config,
)


def test_empty_config_fails_validation():
    reasons = validate_project_config(ProjectConfig(project_name="", goal="", selected_areas=[]))
    assert len(reasons) == 3


def test_valid_config_passes_and_persists(tmp_path):
    cfg = ProjectConfig(
        project_name="결제시스템 요구사항 관리",
        goal="요구사항 문서를 받아 영역별 태스크로 관리한다",
        selected_areas=["WEB", "SEC"],
        access_policy="SHARED",
    )
    store = ProjectConfigStore(tmp_path / "project_config.json")
    saved = store.save(cfg, created_by="pm@example.com")
    assert saved.created_by == "pm@example.com"
    assert saved.created_at

    loaded = store.load()
    assert loaded.project_name == cfg.project_name
    assert loaded.selected_areas == ["WEB", "SEC"]


def test_unknown_area_code_rejected(tmp_path):
    cfg = ProjectConfig(project_name="x", goal="y", selected_areas=["NOT_A_REAL_AREA"])
    store = ProjectConfigStore(tmp_path / "project_config.json")
    with pytest.raises(ProjectConfigValidationError):
        store.save(cfg, created_by="pm")


def test_load_returns_none_when_no_config_saved(tmp_path):
    store = ProjectConfigStore(tmp_path / "project_config.json")
    assert store.load() is None


def _base_infra_config(**overrides):
    fields = dict(
        project_name="인프라 구성 프로젝트",
        goal="네트워크 존 기반 인프라 구성 관리",
        selected_areas=["WEB", "GW"],
        infra_configured=True,
    )
    fields.update(overrides)
    return ProjectConfig(**fields)


def test_infra_disabled_skips_zone_validation():
    # infra_configured=False(기본값)면 아래처럼 정책 위반 데이터가 있어도 검증하지 않는다.
    cfg = ProjectConfig(
        project_name="x", goal="y", selected_areas=["WEB"],
        infra_servers=[{"name": "db1", "zone": "external", "role": "DB", "ip": "1.2.3.4", "ports": [5432]}],
    )
    assert validate_project_config(cfg) == []


def test_infra_db_in_exposed_zone_rejected():
    cfg = _base_infra_config(
        infra_servers=[{"name": "db1", "zone": "external", "role": "DB", "ip": "10.0.0.1", "ports": [5432]}],
    )
    reasons = validate_project_config(cfg)
    assert any("외부 노출 존" in r for r in reasons)


def test_infra_db_in_internal_zone_ok():
    cfg = _base_infra_config(
        infra_servers=[{"name": "db1", "zone": "internal", "role": "DB", "ip": "10.0.0.1", "ports": [5432]}],
    )
    assert validate_project_config(cfg) == []


def test_infra_relay_required_blocks_direct_external_to_db():
    cfg = _base_infra_config(
        infra_servers=[
            {"name": "ext1", "zone": "external", "role": "WEB", "ip": "1.2.3.4", "ports": [443]},
            {"name": "db1", "zone": "internal", "role": "DB", "ip": "10.0.0.1", "ports": [5432]},
        ],
        infra_allow_rules=[{"from_server": "ext1", "to_server": "db1", "allowed_ports": [5432]}],
    )
    reasons = validate_project_config(cfg)
    assert any("중계서버(role=GW) 경유" in r for r in reasons)


def test_infra_relay_via_gateway_ok():
    cfg = _base_infra_config(
        infra_servers=[
            {"name": "gw1", "zone": "dmz_inner", "role": "GW", "ip": "172.16.0.1", "ports": [8443]},
            {"name": "db1", "zone": "internal", "role": "DB", "ip": "10.0.0.1", "ports": [5432]},
        ],
        infra_allow_rules=[{"from_server": "gw1", "to_server": "db1", "allowed_ports": [5432]}],
    )
    assert validate_project_config(cfg) == []


def test_infra_allow_rule_port_not_in_target_listening_ports_rejected():
    cfg = _base_infra_config(
        infra_servers=[
            {"name": "gw1", "zone": "dmz_inner", "role": "GW", "ip": "172.16.0.1", "ports": [8443]},
            {"name": "was1", "zone": "internal", "role": "WAS", "ip": "10.0.0.5", "ports": [8080]},
        ],
        infra_allow_rules=[{"from_server": "gw1", "to_server": "was1", "allowed_ports": [9999]}],
    )
    reasons = validate_project_config(cfg)
    assert any("allowed_ports가 도착 서버가 실제 리스닝" in r for r in reasons)


def test_infra_custom_zone_not_in_presets_is_allowed_when_not_exposed():
    # zone은 고정 enum이 아니다 — 사용자가 임의 커스텀 존을 추가할 수 있고, exposed 플래그를
    # 명시하지 않은 커스텀 zone은 exposed=False로 취급되어 DB 배치가 막히지 않는다.
    cfg = _base_infra_config(
        infra_zones=[{"code": "partner_extranet", "label": "협력사 전용망", "exposed": False}],
        infra_servers=[{"name": "db1", "zone": "partner_extranet", "role": "DB", "ip": "10.1.1.1", "ports": [5432]}],
    )
    assert validate_project_config(cfg) == []


def test_infra_custom_zone_marked_exposed_blocks_db():
    cfg = _base_infra_config(
        infra_zones=[{"code": "partner_extranet", "label": "협력사 전용망", "exposed": True}],
        infra_servers=[{"name": "db1", "zone": "partner_extranet", "role": "DB", "ip": "10.1.1.1", "ports": [5432]}],
    )
    reasons = validate_project_config(cfg)
    assert any("외부 노출 존" in r for r in reasons)


def test_infra_server_referencing_unregistered_zone_rejected():
    # [2026-07-25 독립 코드리뷰 CRITICAL #1 재발방지] 존을 등록하지 않고(또는 등록 후 삭제하고)
    # 서버만 그 zone 이름을 참조하면, exposed 검사 자체가 통째로 스킵되는 우회가 예전 버전에
    # 있었다 — 이제는 "미등록 zone 참조" 자체가 하드 실패다.
    cfg = _base_infra_config(
        infra_servers=[{"name": "db1", "zone": "deleted_zone_ghost", "role": "DB", "ip": "10.1.1.1", "ports": [5432]}],
    )
    reasons = validate_project_config(cfg)
    assert any("미등록 zone 참조" in r for r in reasons)


def test_infra_server_missing_role_rejected():
    cfg = _base_infra_config(
        infra_servers=[{"name": "srv1", "zone": "internal", "ip": "10.1.1.1", "ports": [5432]}],
    )
    reasons = validate_project_config(cfg)
    assert any("role이 필수" in r for r in reasons)


def test_infra_allow_rule_missing_endpoints_rejected():
    cfg = _base_infra_config(
        infra_servers=[{"name": "srv1", "zone": "internal", "role": "WAS", "ip": "10.1.1.1", "ports": [8080]}],
        infra_allow_rules=[{"from_server": "", "to_server": "srv1", "allowed_ports": [8080]}],
    )
    reasons = validate_project_config(cfg)
    assert any("from_server/to_server는 모두 필수" in r for r in reasons)


def test_infra_allow_rule_self_reference_rejected():
    cfg = _base_infra_config(
        infra_servers=[{"name": "srv1", "zone": "internal", "role": "WAS", "ip": "10.1.1.1", "ports": [8080]}],
        infra_allow_rules=[{"from_server": "srv1", "to_server": "srv1", "allowed_ports": [8080]}],
    )
    reasons = validate_project_config(cfg)
    assert any("자기참조 규칙" in r for r in reasons)


# [2026-07-31 커버리지 보완] STEP1/2 필수값 이후에도 개별적으로 검증되는 나머지 필드들
# (layer/doc_type/access_policy/security_level/password_hash_algo) + 인프라 존 검증
# (§8-9, 독립 코드리뷰 CRITICAL #1/MAJOR #2 대응 로직)의 각 분기를 직접 검증한다.


def _base_config(**overrides):
    fields = dict(project_name="x", goal="y", selected_areas=["WEB"])
    fields.update(overrides)
    return ProjectConfig(**fields)


def test_unknown_layer_code_rejected():
    reasons = validate_project_config(_base_config(selected_layers=["NOT_A_LAYER"]))
    assert any("미등록 계층코드" in r for r in reasons)


def test_unknown_doc_type_code_rejected():
    reasons = validate_project_config(_base_config(selected_doc_types=["NOT_A_DOC_TYPE"]))
    assert any("미등록 문서유형코드" in r for r in reasons)


def test_unknown_access_policy_rejected():
    reasons = validate_project_config(_base_config(access_policy="NOT_A_POLICY"))
    assert any("미등록 접근정책" in r for r in reasons)


def test_unknown_security_level_rejected():
    reasons = validate_project_config(_base_config(security_level="not_a_level"))
    assert any("미등록 보안레벨" in r for r in reasons)


def test_unknown_password_hash_algo_rejected():
    reasons = validate_project_config(_base_config(password_hash_algo="md5"))
    assert any("미등록 비밀번호 해시 알고리즘" in r for r in reasons)


def test_infra_validation_skipped_when_not_configured():
    """infra_configured=False(기본값)면 infra_servers에 뭐가 들어있든 검증 자체가
    스킵된다(§8-9 의도적 skip 설계)."""
    reasons = validate_project_config(
        _base_config(infra_configured=False, infra_servers=[{"name": "x"}])  # role/zone 없음 -- 정상이면 에러났을 것
    )
    assert reasons == []


def test_infra_server_missing_name_rejected():
    reasons = validate_project_config(
        _base_config(infra_configured=True, infra_servers=[{"role": "WAS", "zone": "internal"}])
    )
    assert any("name이 비어있음" in r for r in reasons)


def test_infra_duplicate_server_name_rejected():
    reasons = validate_project_config(
        _base_config(
            infra_configured=True,
            infra_servers=[
                {"name": "srv1", "role": "WAS", "zone": "internal"},
                {"name": "srv1", "role": "DB", "zone": "internal"},
            ],
        )
    )
    assert any("인프라 서버명 중복: srv1" in r for r in reasons)


def test_infra_server_unregistered_role_rejected():
    reasons = validate_project_config(
        _base_config(infra_configured=True, infra_servers=[{"name": "srv1", "role": "NOT_A_ROLE", "zone": "internal"}])
    )
    assert any("미등록 role" in r for r in reasons)


def test_infra_server_exposed_zone_db_role_rejected():
    """[독립 코드리뷰 CRITICAL #1 재발방지] 외부 노출 존(exposed=True)에 DB 역할 서버를
    배치하면 거부돼야 한다 — zone_exposed 딕셔너리에 없는 zone이 통째로 스킵되던 버그의
    수정을 직접 검증."""
    reasons = validate_project_config(
        _base_config(infra_configured=True, infra_servers=[{"name": "db1", "role": "DB", "zone": "external"}])
    )
    assert any("외부 노출 존" in r and "DB 역할 서버를 배치할 수 없음" in r for r in reasons)


def test_infra_allow_rule_non_dict_entries_skipped():
    """infra_allow_rules에 dict가 아닌 항목이 섞여 있어도 예외 없이 건너뛴다."""
    reasons = validate_project_config(
        _base_config(
            infra_configured=True,
            infra_servers=[{"name": "srv1", "role": "WAS", "zone": "internal"}],
            infra_allow_rules=["NOT_A_DICT", None],
        )
    )
    # non-dict 항목 자체는 에러를 만들지 않음(그냥 스킵) — 다른 검증 에러가 없으면 빈 목록
    assert reasons == []


def test_infra_allow_rule_unregistered_from_server_reference_rejected():
    reasons = validate_project_config(
        _base_config(
            infra_configured=True,
            infra_servers=[{"name": "srv1", "role": "WAS", "zone": "internal"}],
            infra_allow_rules=[{"from_server": "ghost-server", "to_server": "srv1"}],
        )
    )
    assert any("미등록 출발 서버 참조 ghost-server" in r for r in reasons)


def test_infra_allow_rule_unregistered_server_reference_rejected():
    reasons = validate_project_config(
        _base_config(
            infra_configured=True,
            infra_servers=[{"name": "srv1", "role": "WAS", "zone": "internal"}],
            infra_allow_rules=[{"from_server": "srv1", "to_server": "ghost-server"}],
        )
    )
    assert any("미등록 도착 서버 참조 ghost-server" in r for r in reasons)


def test_config_with_valid_infra_setup_passes():
    """정상적인 인프라 구성(내부망 WAS→DB, relay 없이 직접 DB 접근 없음)은 통과한다."""
    reasons = validate_project_config(
        _base_config(
            infra_configured=True,
            infra_servers=[
                {"name": "was1", "role": "WAS", "zone": "internal", "ports": [8080]},
                {"name": "db1", "role": "DB", "zone": "internal", "ports": [5432]},
            ],
            infra_allow_rules=[
                {"from_server": "was1", "to_server": "db1", "allowed_ports": [5432]},
            ],
            relay_required=False,
        )
    )
    assert reasons == []


def test_design_draft_confirmed_stamps_confirmed_by_and_at_on_save(tmp_path):
    """[커버리지 보완] project_design_draft_confirmed=True + confirmed_by 미지정 상태로
    save()하면, created_by/created_at과 같은 시점에 confirmed_by/at도 자동 채워진다."""
    cfg = _base_config(project_design_draft_confirmed=True)
    store = ProjectConfigStore(tmp_path / "project_config.json")
    saved = store.save(cfg, created_by="designer@example.com")
    assert saved.project_design_draft_confirmed_by == "designer@example.com"
    assert saved.project_design_draft_confirmed_at == saved.created_at
