"""DocTypeRegistry(doc_type_registry.py) 단위 테스트 — "프로젝트 배경 문서유형을
동적으로 추가 가능하게" 고도화의 핵심."""

import pytest

from backend.adapters.persistence.doc_type_registry import DocTypeRegistry, DocTypeValidationError
from backend.domain.requirements.codes import DOC_TYPE_CODES


def test_list_all_codes_includes_builtin_defaults_when_empty(tmp_path):
    registry = DocTypeRegistry(tmp_path / "doc_types.json")
    codes = registry.list_all_codes()
    for builtin in DOC_TYPE_CODES:
        assert builtin in codes


def test_create_custom_type_with_auto_derived_code(tmp_path):
    registry = DocTypeRegistry(tmp_path / "doc_types.json")
    created = registry.create("회의록", actor="tester")
    assert created.code not in DOC_TYPE_CODES
    assert created.label == "회의록"

    codes = registry.list_all_codes()
    assert codes[created.code] == "회의록"


def test_create_custom_type_with_explicit_code(tmp_path):
    registry = DocTypeRegistry(tmp_path / "doc_types.json")
    created = registry.create("착수보고서 v2", actor="tester", code="KICKOFF")
    assert created.code == "KICKOFF"


def test_create_rejects_duplicate_code(tmp_path):
    registry = DocTypeRegistry(tmp_path / "doc_types.json")
    registry.create("A", actor="tester", code="ABC")
    with pytest.raises(DocTypeValidationError):
        registry.create("B", actor="tester", code="ABC")


def test_create_rejects_builtin_code_collision(tmp_path):
    registry = DocTypeRegistry(tmp_path / "doc_types.json")
    with pytest.raises(DocTypeValidationError):
        registry.create("중복 시도", actor="tester", code="BIZ")


def test_create_rejects_empty_label(tmp_path):
    registry = DocTypeRegistry(tmp_path / "doc_types.json")
    with pytest.raises(DocTypeValidationError):
        registry.create("   ", actor="tester")


def test_create_rejects_invalid_explicit_code_format(tmp_path):
    registry = DocTypeRegistry(tmp_path / "doc_types.json")
    with pytest.raises(DocTypeValidationError):
        registry.create("숫자로 시작하는 코드", actor="tester", code="1BAD")


def test_derived_code_collision_uses_letters_not_digits(tmp_path):
    """회귀 방지(2026-07-23 실측 발견): REQ ID의 문서유형 세그먼트는 숫자를 허용하지
    않는다(id_format.REQ_ID_PATTERN `[A-Z]+`) — 충돌 회피 코드에 숫자가 섞이면
    `build_req_id()`가 즉시 형식 위반으로 거부한다. 같은 라벨을 두 번 등록해 실제로
    충돌을 유발하고, 유도된 두 코드 모두 순수 영문자로만 구성됨을 확인한다."""
    registry = DocTypeRegistry(tmp_path / "doc_types.json")
    first = registry.create("회의록", actor="tester")
    second = registry.create("회의록", actor="tester")
    assert first.code != second.code
    assert first.code.isalpha() and first.code.isupper()
    assert second.code.isalpha() and second.code.isupper()


def test_persists_across_reload(tmp_path):
    path = tmp_path / "doc_types.json"
    DocTypeRegistry(path).create("녹취록", actor="tester")
    reloaded = DocTypeRegistry(path).list_custom()
    assert len(reloaded) == 1
    assert reloaded[0].label == "녹취록"


def test_derive_code_raises_when_all_collision_suffixes_exhausted():
    """[커버리지 보완] base + 알파벳 접미사 26개 조합이 모두 이미 사용 중이면(극단적
    상황) 코드 유도를 포기하고 사용자에게 직접 code 지정을 요구하는 명시적 에러를 낸다."""
    from backend.adapters.persistence.doc_type_registry import _COLLISION_SUFFIXES, _derive_code

    base = "CUST"
    existing = {base} | {base + _COLLISION_SUFFIXES[: i + 1] for i in range(len(_COLLISION_SUFFIXES))}
    with pytest.raises(DocTypeValidationError, match="code를 직접 지정하세요"):
        _derive_code("Custom Label", existing)
