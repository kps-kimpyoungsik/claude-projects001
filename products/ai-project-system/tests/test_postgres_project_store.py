"""`PostgresProjectStore` 단위 테스트 — fake in-memory connection(`tests/_fake_pg.py`)으로
SQL 생성·파라미터 바인딩·JSON 어댑터(`ProjectRegistry`)와 동일 계약 준수 여부를 검증한다.

⚠ 이 테스트는 실제 PostgreSQL 서버 없이 동작한다 — `backend/adapters/db/postgres/README.md`가
명시한 "검증 미확정"(실제 PostgreSQL 문법·타입 호환) 상태를 해소하지 않는다. 여기서 검증하는
것은 (a) 이 클래스가 실행하는 SQL 문자열이 예상대로 생성되는지, (b) 그 SQL이 반환한 행을
올바르게 `Project` 엔티티로 역직렬화하는지, (c) `ProjectValidationError` 등 JSON 어댑터와
동일한 검증 로직이 그대로 동작하는지다.
"""

import pytest

from backend.adapters.db.postgres.postgres_project_store import PostgresProjectStore
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID, ProjectValidationError
from tests._fake_pg import FakeConnection


@pytest.fixture
def store():
    return PostgresProjectStore(conn=FakeConnection())


def test_list_all_includes_virtual_default_project_when_no_rows(store):
    projects = store.list_all()
    assert any(p.id == DEFAULT_PROJECT_ID for p in projects)


def test_create_then_get_roundtrip(store):
    created = store.create("신규 프로젝트", start_date="2026-01-01", end_date="2026-12-31")
    assert created.id != DEFAULT_PROJECT_ID
    assert created.status == "IMPLEMENTING"

    fetched = store.get(created.id)
    assert fetched is not None
    assert fetched.name == "신규 프로젝트"
    assert fetched.start_date == "2026-01-01"
    assert fetched.end_date == "2026-12-31"


def test_create_rejects_blank_name(store):
    with pytest.raises(ProjectValidationError):
        store.create("   ")


def test_create_assigns_sequential_ids(store):
    p1 = store.create("A")
    p2 = store.create("B")
    assert p1.id != p2.id


def test_update_status_materializes_default_project(store):
    updated = store.update_status(DEFAULT_PROJECT_ID, "VERIFIED")
    assert updated.status == "VERIFIED"
    # 구체화(materialize) 후에는 list_all()에도 실제 행으로 반영된다.
    fetched = store.get(DEFAULT_PROJECT_ID)
    assert fetched.status == "VERIFIED"


def test_update_status_rejects_unknown_status(store):
    with pytest.raises(ProjectValidationError):
        store.update_status(DEFAULT_PROJECT_ID, "NOT_A_REAL_STATUS")


def test_update_status_unknown_project_raises(store):
    with pytest.raises(ProjectValidationError):
        store.update_status("proj-does-not-exist", "VERIFIED")


def test_update_fields_partial_update_preserves_other_fields(store):
    created = store.create("원래이름", start_date="2026-01-01")
    updated = store.update_fields(created.id, end_date="2026-06-30")
    assert updated.name == "원래이름"
    assert updated.start_date == "2026-01-01"
    assert updated.end_date == "2026-06-30"


def test_update_fields_rejects_blank_name(store):
    created = store.create("원래이름")
    with pytest.raises(ProjectValidationError):
        store.update_fields(created.id, name="   ")


def test_update_fields_on_default_project_materializes(store):
    updated = store.update_fields(DEFAULT_PROJECT_ID, name="가상 프로젝트 개명")
    assert updated.name == "가상 프로젝트 개명"


def test_update_fields_unknown_project_raises(store):
    with pytest.raises(ProjectValidationError):
        store.update_fields("proj-does-not-exist", name="x")


def test_get_returns_none_for_unknown_project(store):
    assert store.get("proj-does-not-exist") is None
