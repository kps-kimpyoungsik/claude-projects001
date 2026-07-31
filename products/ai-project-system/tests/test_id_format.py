"""id_format.py 단위 테스트 — 지금까지 전용 테스트 파일이 없었다(간접적으로만
requirements_api 테스트를 통해 exercise됨)."""

import pytest

from backend.domain.graph.entities import NodeKind
from backend.domain.requirements.id_format import (
    build_req_id,
    parse_req_id,
    verify_task_requirement_links,
)


def test_parse_req_id_valid_format():
    parsed = parse_req_id("REQ-BIZ-SEC-003")
    assert parsed == {"doc_type_code": "BIZ", "area_code": "SEC", "seq": "003"}


def test_parse_req_id_invalid_pattern_raises():
    with pytest.raises(ValueError, match="형식 위반"):
        parse_req_id("NOT-A-VALID-ID")


def test_parse_req_id_unknown_doc_type_raises():
    with pytest.raises(ValueError, match="미등록 문서유형코드"):
        parse_req_id("REQ-ZZZ-SEC-001")


def test_parse_req_id_unknown_area_code_raises():
    with pytest.raises(ValueError, match="미등록 영역코드"):
        parse_req_id("REQ-BIZ-ZZZ-001")


def test_parse_req_id_accepts_extra_doc_type_when_provided():
    parsed = parse_req_id("REQ-CUSTOM-SEC-001", extra_doc_types={"CUSTOM"})
    assert parsed["doc_type_code"] == "CUSTOM"


def test_parse_req_id_rejects_extra_doc_type_when_not_provided():
    with pytest.raises(ValueError, match="미등록 문서유형코드"):
        parse_req_id("REQ-CUSTOM-SEC-001")


def test_build_req_id_produces_valid_formatted_string():
    req_id = build_req_id("BIZ", "SEC", 3)
    assert req_id == "REQ-BIZ-SEC-003"


def test_build_req_id_rejects_unknown_doc_type():
    with pytest.raises(ValueError, match="미등록 문서유형코드"):
        build_req_id("ZZZ", "SEC", 1)


def _graph_with(node_ids):
    return {"nodes": [{"node_id": nid, "kind": NodeKind.REQUIREMENT.value} for nid in node_ids]}


def test_verify_task_requirement_links_all_present():
    graph = _graph_with(["REQ-BIZ-SEC-001", "REQ-BIZ-SEC-002"])
    ok, missing = verify_task_requirement_links(["REQ-BIZ-SEC-001"], graph)
    assert ok is True
    assert missing == []


def test_verify_task_requirement_links_reports_missing():
    graph = _graph_with(["REQ-BIZ-SEC-001"])
    ok, missing = verify_task_requirement_links(["REQ-BIZ-SEC-001", "REQ-BIZ-SEC-999"], graph)
    assert ok is False
    assert missing == ["REQ-BIZ-SEC-999"]


def test_verify_task_requirement_links_ignores_non_requirement_nodes():
    """kind가 Requirement가 아닌 노드(예: Task)는 근거로 인정되지 않는다."""
    graph = {"nodes": [{"node_id": "TASK-WEB-001", "kind": NodeKind.TASK.value}]}
    ok, missing = verify_task_requirement_links(["TASK-WEB-001"], graph)
    assert ok is False
    assert missing == ["TASK-WEB-001"]
