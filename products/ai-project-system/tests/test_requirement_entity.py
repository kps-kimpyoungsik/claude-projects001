"""backend/domain/entities/requirement.py(make_requirement_node/make_implements_edge) 단위
테스트 — 지금까지 전용 테스트 파일이 없었다(간접적으로만 tasks_api/requirements_api 테스트를
통해 exercise됨)."""

import pytest

from backend.domain.entities.requirement import make_implements_edge, make_requirement_node
from backend.domain.graph.entities import EdgeKind, NodeKind


def test_make_requirement_node_builds_expected_node():
    node = make_requirement_node("REQ-BIZ-SEC-001", description="보안 요건", source_ref="doc1::child:0")
    assert node.node_id == "REQ-BIZ-SEC-001"
    assert node.kind == NodeKind.REQUIREMENT
    assert node.label == "보안 요건"
    assert node.source_ref == "doc1::child:0"


def test_make_requirement_node_rejects_empty_source_ref():
    """[커버리지 보완] source_ref 없는 요구사항 노드는 근거 불명이라 생성이 거부된다
    (00_PROJECT_CONSTITUTION.md §5 "추정 요구사항 생성 금지")."""
    with pytest.raises(ValueError, match="source_ref 없는 요구사항 노드"):
        make_requirement_node("REQ-BIZ-SEC-001", description="보안 요건", source_ref="")


def test_make_implements_edge_builds_expected_edge():
    edge = make_implements_edge("TASK-SEC-001", "REQ-BIZ-SEC-001")
    assert edge.edge_id == "TASK-SEC-001::IMPLEMENTS::REQ-BIZ-SEC-001"
    assert edge.kind == EdgeKind.IMPLEMENTS
    assert edge.source_id == "TASK-SEC-001"
    assert edge.target_id == "REQ-BIZ-SEC-001"
    assert edge.confidence == 1.0
