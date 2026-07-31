"""ProjectDomainSnapshot(§2, 1번째 청크 — 프로젝트 구조만) 회귀 테스트.

대용량 스캔(전체 backend/) hang 위험(T38 PAP·DES-027)을 피하기 위해, 스캔 대상을 이
프로젝트의 최소 서브셋(`backend/domain/entities/task.py` 한 개 파일이 있는 디렉터리)으로
좁혀서 검증한다 — 전체 backend/ 스캔은 별도 수동/느린 테스트 대상이지 여기서 강제하지 않는다.
"""

from pathlib import Path

from backend.adapters.persistence.project_domain_snapshot_store import ProjectDomainSnapshotStore
from backend.application.services.project_domain_snapshot_service import (
    build_project_domain_snapshot,
    diff_snapshots,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_build_snapshot_scans_narrow_subdir():
    snapshot = build_project_domain_snapshot(
        PROJECT_ROOT, scan_subdir="backend/domain/entities", max_files=50
    )

    assert snapshot["project_root"] == str(PROJECT_ROOT)
    structure = snapshot["structure"]
    assert structure["truncated"] is False
    assert structure["file_count"] >= 1
    assert "backend/domain/entities/task.py" in structure["files_scanned"]
    assert structure["function_count"] >= 1


def test_build_snapshot_all_5_chunks_implemented_no_data_injected():
    """5/5 청크 전부 구현 완료 — requirements/tasks 미주입 시에도 크래시 없이 정직한 상태로 채워진다."""
    snapshot = build_project_domain_snapshot(
        PROJECT_ROOT, scan_subdir="backend/domain/entities", max_files=50
    )

    # commonization: requirements/tasks 미주입 -> NO_DATA (NOT_IMPLEMENTED 아님)
    assert snapshot["commonization"]["status"] == "NO_DATA"
    assert snapshot["commonization"]["stack_usage"] == {}

    # technology: router_module_path 기본값이 실제 경로를 가리키므로 정상 채워진다
    assert snapshot["technology"]["status"] in ("OK", "PARTIAL")
    assert ".hwp" in snapshot["technology"]["ingestion_formats"]
    assert snapshot["technology"]["ingestion_formats"][".hwp"] == "unstructured_parse"


def test_build_snapshot_commonization_aggregates_injected_requirements_and_tasks():
    from backend.adapters.persistence.requirement_store import RequirementRecord
    from backend.domain.entities.task import Task

    req = RequirementRecord(
        req_id="REQ-BIZ-SEC-002",
        doc_type_code="BIZ",
        area_code="SEC",
        description="desc",
        source_ref="src",
        doc_type_confidence=0.9,
        area_confidence=0.9,
        solution_stack=["전자정부표준프레임워크"],
    )
    task = Task(
        task_id="TASK-SEC-001",
        domain_code="SEC",
        title="title",
        description="desc",
        solution_stack=["전자정부표준프레임워크", "FastAPI"],
    )

    snapshot = build_project_domain_snapshot(
        PROJECT_ROOT,
        scan_subdir="backend/domain/entities",
        max_files=50,
        requirements=[req],
        tasks=[task],
    )

    commonization = snapshot["commonization"]
    assert commonization["status"] == "OK"
    assert commonization["stack_usage"]["전자정부표준프레임워크"]["count"] == 2
    assert set(commonization["stack_usage"]["전자정부표준프레임워크"]["used_by"]) == {
        "REQ-BIZ-SEC-002",
        "TASK-SEC-001",
    }
    assert commonization["stack_usage"]["FastAPI"]["count"] == 1

    technology = snapshot["technology"]
    assert technology["status"] == "OK"
    assert "전자정부표준프레임워크" in technology["solution_stack_names"]
    assert "FastAPI" in technology["solution_stack_names"]
    assert any(t.startswith(".hwp(") for t in technology["technology_stack"])
    assert "전자정부표준프레임워크" in technology["technology_stack"]


def test_technology_extractor_handles_bad_router_module_path_without_crash():
    from backend.adapters.extractors.technology_extractor import extract_technology_stack

    result = extract_technology_stack(router_module_path="backend.does.not.exist")

    assert result["status"] in ("NO_DATA", "PARTIAL")
    assert result["ingestion_formats"] == {}
    assert result["errors"]


def test_commonization_extractor_handles_dict_shaped_records():
    from backend.adapters.extractors.commonization_extractor import extract_solution_stack_usage

    result = extract_solution_stack_usage(
        requirements=[{"req_id": "REQ-X-1", "solution_stack": ["Spring"]}],
        tasks=[{"task_id": "TASK-X-1", "solution_stack": ["Spring"]}],
    )

    assert result["status"] == "OK"
    assert result["stack_usage"]["Spring"]["count"] == 2


def test_build_snapshot_process_scans_governance_workflows_dir():
    snapshot = build_project_domain_snapshot(
        PROJECT_ROOT, scan_subdir="backend/domain/entities", max_files=50
    )

    process = snapshot["process"]
    assert process["workflows_dir"] == "governance/workflows"
    assert process["file_count"] >= 1

    paths = [f["path"] for f in process["files"]]
    assert any(p.endswith("SERVER-EXECUTION_POLICY.md") for p in paths)

    for entry in process["files"]:
        assert set(entry.keys()) == {"path", "title", "sections"}
        assert entry["title"] is not None
        assert entry["sections"], f"{entry['path']}: sections 비어 있음"
        # title은 sections의 첫 항목과 같아야 한다(첫 heading)
        assert entry["title"] == entry["sections"][0]


def test_process_missing_workflows_dir_reports_error_not_crash():
    snapshot = build_project_domain_snapshot(
        PROJECT_ROOT,
        scan_subdir="backend/domain/entities",
        max_files=50,
        workflows_subdir="governance/workflows_does_not_exist",
    )

    process = snapshot["process"]
    assert process["file_count"] == 0
    assert process["errors"]


def test_build_snapshot_environment_scans_infrastructure_dir():
    snapshot = build_project_domain_snapshot(
        PROJECT_ROOT, scan_subdir="backend/domain/entities", max_files=50
    )

    environment = snapshot["environment"]
    assert environment["infra_dir"] == "infrastructure"
    assert environment["file_count"] >= 1

    env_example_files = [f for f in environment["files"] if f["type"] == "env_example"]
    assert env_example_files, "infrastructure/env/.env.*.example 파일이 스캔되어야 한다"
    for entry in env_example_files:
        assert "DEPLOY_MODE" in entry["keys"] or "WEB_PORTS" in entry["keys"]

    markdown_files = [f for f in environment["files"] if f["type"] == "markdown_doc"]
    assert any(f["path"].endswith("topology.md") for f in markdown_files)

    conf_files = [f for f in environment["files"] if f["type"] == "nginx_conf_example"]
    assert conf_files, "infrastructure/nginx/*.conf.example 파일이 스캔되어야 한다"
    for entry in conf_files:
        assert entry["size_bytes"] is not None and entry["size_bytes"] > 0


def test_build_snapshot_environment_never_leaks_secret_values():
    snapshot = build_project_domain_snapshot(
        PROJECT_ROOT, scan_subdir="backend/domain/entities", max_files=50
    )

    environment = snapshot["environment"]
    serialized = str(environment)

    # .env.single.example / .env.ha.example의 실제 값(포트 숫자·전략 문자열 등)이
    # "값 형태"로 결과에 노출되면 안 된다 — 키 이름만 남아야 한다(보안 검증).
    for leaked_value in ("=8080", "=8790", "=single", "=none"):
        assert leaked_value not in serialized

    env_example_files = [f for f in environment["files"] if f["type"] == "env_example"]
    for entry in env_example_files:
        assert set(entry.keys()) == {"path", "type", "keys"}
        for key in entry["keys"]:
            assert "=" not in key


def test_environment_missing_infra_dir_reports_error_not_crash():
    snapshot = build_project_domain_snapshot(
        PROJECT_ROOT,
        scan_subdir="backend/domain/entities",
        max_files=50,
        infra_subdir="infrastructure_does_not_exist",
    )

    environment = snapshot["environment"]
    assert environment["file_count"] == 0
    assert environment["errors"]


def test_build_snapshot_missing_dir_reports_error_not_crash():
    snapshot = build_project_domain_snapshot(
        PROJECT_ROOT, scan_subdir="backend/does_not_exist", max_files=50
    )

    structure = snapshot["structure"]
    assert structure["file_count"] == 0
    assert structure["errors"]


def test_max_files_limit_marks_truncated():
    snapshot = build_project_domain_snapshot(PROJECT_ROOT, scan_subdir="backend", max_files=1)

    assert snapshot["structure"]["truncated"] is True
    assert snapshot["structure"]["file_count"] == 1


def test_snapshot_save_and_reload(tmp_path):
    store_path = tmp_path / "project_domain_snapshot.json"
    store = ProjectDomainSnapshotStore(store_path)

    assert store.load() is None

    snapshot = build_project_domain_snapshot(
        PROJECT_ROOT, scan_subdir="backend/domain/entities", max_files=50
    )
    store.save(snapshot)

    reloaded = store.load()
    assert reloaded is not None
    assert reloaded["structure"]["file_count"] == snapshot["structure"]["file_count"]


def test_load_previous_returns_none_on_first_run(tmp_path):
    store_path = tmp_path / "project_domain_snapshot.json"
    store = ProjectDomainSnapshotStore(store_path)

    assert store.load_previous() is None


def test_load_previous_returns_last_saved_snapshot_before_overwrite(tmp_path):
    store_path = tmp_path / "project_domain_snapshot.json"
    store = ProjectDomainSnapshotStore(store_path)

    first = build_project_domain_snapshot(
        PROJECT_ROOT, scan_subdir="backend/domain/entities", max_files=50
    )
    store.save(first)

    previous = store.load_previous()
    assert previous is not None
    assert previous["structure"]["file_count"] == first["structure"]["file_count"]

    second = build_project_domain_snapshot(PROJECT_ROOT, scan_subdir="backend", max_files=1)
    store.save(second)

    # save() 이후에도 load_previous()는 항상 "지금 저장된 최신"을 반환한다(별도 이력
    # 파일이 없는 스토어 설계 — 호출 시점이 diff 비교 타이밍을 결정한다).
    assert store.load_previous()["structure"]["truncated"] is True


def test_diff_snapshots_initial_run_marks_all_chunks_added():
    new_snapshot = build_project_domain_snapshot(
        PROJECT_ROOT, scan_subdir="backend/domain/entities", max_files=50
    )

    diff = diff_snapshots(None, new_snapshot)

    assert diff["status"] == "INITIAL"
    for key in ("structure", "environment", "process", "commonization", "technology"):
        assert diff["chunks"][key]["status"] == "ADDED"


def test_diff_snapshots_no_change_between_identical_snapshots():
    snapshot = build_project_domain_snapshot(
        PROJECT_ROOT, scan_subdir="backend/domain/entities", max_files=50
    )

    diff = diff_snapshots(snapshot, snapshot)

    assert diff["status"] == "UNCHANGED"
    for key in ("structure", "environment", "process", "commonization", "technology"):
        assert diff["chunks"][key]["status"] == "UNCHANGED"
        assert diff["chunks"][key]["changed_keys"] == []


def test_diff_snapshots_detects_changed_chunk():
    old_snapshot = build_project_domain_snapshot(
        PROJECT_ROOT, scan_subdir="backend/domain/entities", max_files=50
    )
    new_snapshot = build_project_domain_snapshot(PROJECT_ROOT, scan_subdir="backend", max_files=1)

    diff = diff_snapshots(old_snapshot, new_snapshot)

    assert diff["status"] == "CHANGED"
    structure_diff = diff["chunks"]["structure"]
    assert structure_diff["status"] == "CHANGED"
    assert "truncated" in structure_diff["changed_keys"]
    assert "file_count" in structure_diff["changed_keys"]

    # process/environment는 scan_subdir을 바꿔도 영향받지 않으므로 UNCHANGED로 남아야 한다
    assert diff["chunks"]["process"]["status"] == "UNCHANGED"
    assert diff["chunks"]["environment"]["status"] == "UNCHANGED"


# [2026-07-31 커버리지 보완] AST 스캔 중 손상 파일 처리 + diff_snapshots()의 나머지 분기
# (양쪽 다 None 스킵·ADDED·REMOVED·non-dict 청크 비교)를 직접 검증한다.


def test_build_snapshot_scan_records_syntax_error_without_crashing(tmp_path):
    """[Line 99-102] 스캔 대상 디렉터리에 문법 오류가 있는 .py 파일이 섞여 있어도 크래시
    없이 errors 목록에 기록하고 나머지 파일은 정상 스캔한다(T98 AIP 정직 기록)."""
    scan_dir = tmp_path / "backend"
    scan_dir.mkdir()
    (scan_dir / "broken.py").write_text("def broken(:\n    pass", encoding="utf-8")
    (scan_dir / "ok.py").write_text("def works():\n    pass", encoding="utf-8")

    snapshot = build_project_domain_snapshot(tmp_path, scan_subdir="backend", max_files=50)
    structure = snapshot["structure"]
    assert structure["file_count"] == 1  # ok.py만 스캔 성공
    assert "backend/ok.py" in structure["files_scanned"]
    assert len(structure["errors"]) == 1
    assert "broken.py" in structure["errors"][0]
    assert "SyntaxError" in structure["errors"][0]


def test_diff_snapshots_skips_chunk_missing_from_both_sides():
    """[Line 209] old/new 양쪽 모두 해당 청크가 없으면 diff 결과에서 그냥 건너뛴다."""
    old = {"structure": {"a": 1}}
    new = {"structure": {"a": 1}}
    result = diff_snapshots(old, new)
    for key in ("environment", "process", "commonization", "technology"):
        assert key not in result["chunks"]


def test_diff_snapshots_detects_newly_added_chunk():
    """[Line 212-217] old에는 없던 청크가 new에 새로 생기면 ADDED로 표시된다."""
    old = {"structure": {"a": 1}}
    new = {"structure": {"a": 1}, "environment": {"zones": ["dmz"]}}
    result = diff_snapshots(old, new)
    assert result["chunks"]["environment"]["status"] == "ADDED"
    assert result["chunks"]["environment"]["changed_keys"] == ["zones"]


def test_diff_snapshots_detects_removed_chunk():
    """[Line 220-225] old에는 있던 청크가 new에서 사라지면 REMOVED로 표시된다."""
    old = {"structure": {"a": 1}, "environment": {"zones": ["dmz"]}}
    new = {"structure": {"a": 1}}
    result = diff_snapshots(old, new)
    assert result["chunks"]["environment"]["status"] == "REMOVED"
    assert result["chunks"]["environment"]["changed_keys"] == ["zones"]


def test_diff_snapshots_non_dict_chunk_reports_generic_change():
    """[Line 238] 청크 값이 dict가 아닌 이례적 형태(예: 리스트)로 바뀌면 키 단위 비교 대신
    통째로 변경(<non-dict-chunk>)으로 표시한다."""
    old = {"structure": ["a", "b"]}
    new = {"structure": ["a", "b", "c"]}
    result = diff_snapshots(old, new)
    assert result["chunks"]["structure"]["status"] == "CHANGED"
    assert result["chunks"]["structure"]["changed_keys"] == ["<non-dict-chunk>"]
