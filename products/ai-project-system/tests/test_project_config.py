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
