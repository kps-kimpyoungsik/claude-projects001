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


# [2026-07-30 커버리지 보완] 아래 4개 테스트는 그동안 실행되지 않던 분기(delete() False
# 경로, create()의 seq 충돌 재시도 루프, update_status()/update_fields()의 DEFAULT_PROJECT_ID
# materialize 경로 + 존재하지 않는 project_id에 대한 최종 raise)를 다룬다 — 순수 커버리지
# 목적이며 프로덕션 로직은 변경하지 않는다(테스트 전용 추가).


def test_delete_unknown_project_returns_false(tmp_path):
    """[Line 160] 존재하지 않는 project_id는 예외 없이 False를 반환한다(이미 없는 것도
    목표 상태이므로) — 지금까지 이 분기를 실행하는 테스트가 없었다."""
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("삭제용 프로젝트")
    assert registry.delete(created.id) is True  # 실제 삭제 성공(len 달라짐) 경로도 함께 확인
    assert registry.delete("proj-999") is False


def test_create_retries_sequence_number_on_id_collision(tmp_path):
    """[Line 136-137] `seq = len(records) + 1`로 계산한 다음 번호가 이미 존재하는 id와
    충돌하면 while 루프가 seq를 증가시키며 재시도한다 — 레코드 1건을 지운 뒤 새로 만들면
    `len(records)+1`이 기존에 남아있는 더 큰 번호와 충돌하는 상황을 재현한다."""
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    p1 = registry.create("A")  # proj-001
    p2 = registry.create("B")  # proj-002
    registry.delete(p1.id)  # proj-001 삭제 -> len(records)==1 상태에서 다음 seq 계산이 1+1=2로
    # proj-002(p2)와 충돌하도록 만든다 -> while 루프가 3으로 재시도해야 한다.
    p3 = registry.create("C")
    assert p3.id == "proj-003"
    assert p3.id != p2.id


def test_update_status_materializes_default_project_when_absent(tmp_path):
    """[Line 182-191] DEFAULT_PROJECT_ID는 파일에 레코드가 없어도 list_all()에서 가상으로
    보이는데, 그 상태에서 update_status()를 호출하면 파일에 실제로 구체화(materialize)돼야
    한다."""
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    updated = registry.update_status(DEFAULT_PROJECT_ID, "ON_HOLD")
    assert updated.id == DEFAULT_PROJECT_ID
    assert updated.status == "ON_HOLD"

    raw = json.loads((tmp_path / "projects_registry.json").read_text(encoding="utf-8"))
    assert any(r["id"] == DEFAULT_PROJECT_ID and r["status"] == "ON_HOLD" for r in raw)


def test_update_status_unknown_non_default_project_raises(tmp_path):
    """[Line 193] DEFAULT_PROJECT_ID가 아니면서 파일에도 없는 project_id는 최종 raise로
    떨어진다."""
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    import pytest
    with pytest.raises(ProjectValidationError):
        registry.update_status("proj-999", "ON_HOLD")


def test_update_fields_rejects_whitespace_only_name(tmp_path):
    """[Line 210] name이 공백 문자로만 구성돼 strip() 후 빈 문자열이면 거부한다."""
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    created = registry.create("원래 이름")
    import pytest
    with pytest.raises(ProjectValidationError):
        registry.update_fields(created.id, name="   ")


def test_update_fields_materializes_default_project_when_absent(tmp_path):
    """[Line 228-242] update_status()와 동일한 materialize 패턴 — update_fields()도
    DEFAULT_PROJECT_ID가 파일에 없으면 그 시점에 구체화한다."""
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    updated = registry.update_fields(
        DEFAULT_PROJECT_ID, name="바뀐 기본 프로젝트", start_date="2026-09-01", end_date="2026-12-31"
    )
    assert updated.id == DEFAULT_PROJECT_ID
    assert updated.name == "바뀐 기본 프로젝트"
    assert updated.start_date == "2026-09-01"
    assert updated.end_date == "2026-12-31"

    raw = json.loads((tmp_path / "projects_registry.json").read_text(encoding="utf-8"))
    assert any(r["id"] == DEFAULT_PROJECT_ID and r["name"] == "바뀐 기본 프로젝트" for r in raw)
