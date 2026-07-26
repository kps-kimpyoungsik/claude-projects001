"""ProjectRegistry(project_registry.py) 단위 테스트 — "여러 프로젝트 관리" 고도화의 핵심.

무마이그레이션 원칙(레지스트리가 비어 있어도 DEFAULT_PROJECT_ID가 항상 보임)과
신규 프로젝트 생성·채번을 검증한다.
"""

import json

from backend.adapters.persistence.project_registry import (
    DEFAULT_PROJECT_ID,
    PROJECT_STATUSES,
    ProjectRegistry,
    ProjectValidationError,
)


def test_list_all_always_includes_default_when_registry_empty(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    projects = registry.list_all()
    assert any(p.id == DEFAULT_PROJECT_ID for p in projects)
    assert len(projects) == 1


def test_create_project_persists_and_reloads(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("테스트 프로젝트")
    assert created.id != DEFAULT_PROJECT_ID
    assert created.status == "IMPLEMENTING"

    reloaded = ProjectRegistry(tmp_path / "projects_registry.json")
    projects = reloaded.list_all()
    ids = [p.id for p in projects]
    assert DEFAULT_PROJECT_ID in ids
    assert created.id in ids


def test_create_project_empty_name_raises():
    registry = ProjectRegistry(None)
    import pytest
    with pytest.raises(ProjectValidationError):
        registry.create("   ")


def test_create_project_assigns_unique_sequential_ids(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    p1 = registry.create("A")
    p2 = registry.create("B")
    assert p1.id != p2.id


def test_get_returns_none_for_unknown_id(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    assert registry.get("proj-999") is None
    assert registry.get(DEFAULT_PROJECT_ID) is not None


# [2026-07-26 고도화] ON_HOLD(보류)/ARCHIVED(삭제=soft-delete 라벨) 상태 확장.


def test_project_statuses_include_on_hold_and_archived():
    assert {"ON_HOLD", "ARCHIVED"} <= PROJECT_STATUSES


def test_update_status_allows_on_hold_and_archived(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("보류될 프로젝트")

    on_hold = registry.update_status(created.id, "ON_HOLD")
    assert on_hold.status == "ON_HOLD"

    archived = registry.update_status(created.id, "ARCHIVED")
    assert archived.status == "ARCHIVED"

    # ARCHIVED는 라벨일 뿐 — 레코드는 파일에 그대로 남아있어야 한다(물리 삭제 금지).
    raw = json.loads((tmp_path / "projects_registry.json").read_text(encoding="utf-8"))
    assert any(r["id"] == created.id for r in raw)


def test_update_status_rejects_unknown_status(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("x")
    import pytest
    with pytest.raises(ProjectValidationError):
        registry.update_status(created.id, "DELETED_FOREVER")


# [2026-07-26 고도화] start_date/end_date 필드.


def test_create_with_start_and_end_date_persists(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("일정 있는 프로젝트", start_date="2026-08-01", end_date="2026-12-31")
    assert created.start_date == "2026-08-01"
    assert created.end_date == "2026-12-31"

    reloaded = ProjectRegistry(tmp_path / "projects_registry.json")
    fetched = reloaded.get(created.id)
    assert fetched.start_date == "2026-08-01"
    assert fetched.end_date == "2026-12-31"


def test_create_with_invalid_date_format_raises(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    import pytest
    with pytest.raises(ProjectValidationError):
        registry.create("x", start_date="2026/08/01")


def test_create_without_dates_defaults_to_none(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("날짜 없는 프로젝트")
    assert created.start_date is None
    assert created.end_date is None


def test_backward_compat_loads_legacy_record_without_date_fields(tmp_path):
    """이 필드가 생기기 전에 저장된 실제 형식(created_at/id/name/status만 있는 레코드)이
    필드 추가 후에도 그대로 로드되는지 확인 — 실제 data/projects_registry.json의 기존
    5건(default/proj-002~005)과 동일한 구조."""
    path = tmp_path / "projects_registry.json"
    path.write_text(
        json.dumps([
            {
                "id": "proj-002",
                "name": "레거시 프로젝트",
                "status": "WAITING",
                "created_at": "2026-07-26T12:31:32.620258+00:00",
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    registry = ProjectRegistry(path)
    projects = registry.list_all()
    legacy = next(p for p in projects if p.id == "proj-002")
    assert legacy.start_date is None
    assert legacy.end_date is None
    assert legacy.status == "WAITING"


def test_update_fields_changes_name_and_dates(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("원래 이름")

    updated = registry.update_fields(created.id, name="바뀐 이름", start_date="2026-09-01", end_date="2026-10-01")
    assert updated.name == "바뀐 이름"
    assert updated.start_date == "2026-09-01"
    assert updated.end_date == "2026-10-01"
    assert updated.status == "IMPLEMENTING"  # status는 update_fields가 건드리지 않음


def test_update_fields_clears_date_with_explicit_none(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("프로젝트", start_date="2026-01-01")

    cleared = registry.update_fields(created.id, start_date=None)
    assert cleared.start_date is None


def test_update_fields_without_args_keeps_existing_values(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("프로젝트", start_date="2026-01-01", end_date="2026-02-01")

    unchanged = registry.update_fields(created.id)
    assert unchanged.name == "프로젝트"
    assert unchanged.start_date == "2026-01-01"
    assert unchanged.end_date == "2026-02-01"


def test_update_fields_unknown_project_raises(tmp_path):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    import pytest
    with pytest.raises(ProjectValidationError):
        registry.update_fields("proj-999", name="x")
