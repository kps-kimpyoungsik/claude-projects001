"""[Phase 3 §2] ProjectDomainSnapshot — 실측된 프로젝트 도메인 정보를 스냅샷으로 추출.

설계 근거: `plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md` §1·§2 — 사용자가 "가장 중요한 기능"이라
명시한 항목("실측된 현재 프로젝트 구조·기능·환경·프로세스·공통화·기술을 graphify에 저장해서
프로젝트별 도메인 정보를 최신 상태로 관리").

**1번째 청크(2026-07-19) 범위 — "프로젝트 구조"만.** 완료됨.

**2번째 청크(2026-07-19) 범위 — "환경"만 추가.** 완료됨.

**3번째 청크(2026-07-19) 범위 — "프로세스"만 추가.** 설계서 §2-1 "프로세스" 행이 지목한
`governance/workflows/*.md`는 이 프로젝트에 실제로 존재함을 실측 확인
(`governance/workflows/SERVER-EXECUTION_POLICY.md`,
`governance/workflows/RECALL_UNIVERSAL_SEARCH_GUIDE.md`) — 설계서 가정 그대로 유효하므로
대체 후보 없이 그 경로를 그대로 스캔한다.

**4·5번째 청크(2026-07-19) 범위 — "공통화"·"기술" 추가로 5개 청크 전부 구현 완료.**
- 공통화: `commonization_extractor.extract_solution_stack_usage()` — `RequirementRecord.
  solution_stack`/`Task.solution_stack`(이미 메모리에 있는 데이터) 재사용 빈도 집계. 파일
  스캔이 아니므로 `requirements`/`tasks`를 호출자가 주입해야 값이 채워진다(하위호환: 기본값
  None → "데이터 미제공"으로 스킵, 크래시하지 않음).
- 기술: `technology_extractor.extract_technology_stack()` — `backend/adapters/parsers/
  router.py`의 `FORMAT_STRATEGY`(실제 모듈 import로 읽음, 텍스트 스캔 아님 — 근거는 그
  모듈 docstring 참조) + 위 공통화 집계를 합쳐 "실제 쓰는 기술 스택 전체 목록"을 만든다.

**이력(diff) 관리 청크(2026-07-20) — 구현 완료.** 설계서 §2-2 docstring이 언급한 "이전
스냅샷과 diff"를 `diff_snapshots()`로 구현. `build_project_domain_snapshot()` 자체는
건드리지 않고(하위호환 유지), 호출자가 원할 때만 별도로 부르는 순수 함수로 분리했다 — 청크별
(구조·환경·프로세스·공통화·기술) 얕은 키 비교 수준(정교한 구조적 diff 아님, 과잉설계 회피).
"""

import ast
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from backend.adapters.extractors.ast_extractor import extract_functions_and_calls
from backend.adapters.extractors.commonization_extractor import extract_solution_stack_usage
from backend.adapters.extractors.environment_extractor import extract_environment_config
from backend.adapters.extractors.process_extractor import extract_process_docs
from backend.adapters.extractors.technology_extractor import (
    DEFAULT_ROUTER_MODULE_PATH,
    extract_technology_stack,
)

# 대용량/무한 스캔 회피(T38 PAP · DES-027) — 파일 수 상한을 두고 그 이상은 truncated=True로
# 정직하게 표기한다(자동으로 조용히 잘라내고 "다 됐다"고 하지 않는다, T98 AIP).
DEFAULT_MAX_FILES = 500
DEFAULT_MAX_INFRA_FILES = 200


def _scan_python_files(scan_dir: Path, max_files: int) -> tuple[list[Path], bool]:
    """scan_dir 하위 .py 파일 목록을 max_files 상한 내에서 수집한다.

    반환: (파일 목록, truncated 여부). rglob 자체가 제너레이터라 상한 도달 즉시 중단해
    대형 트리에서도 전체를 다 순회하지 않는다(hang 회피).
    """
    files: list[Path] = []
    truncated = False
    for path in scan_dir.rglob("*.py"):
        if len(files) >= max_files:
            truncated = True
            break
        files.append(path)
    return files, truncated


def _extract_structure(project_root: Path, scan_subdir: str, max_files: int) -> dict:
    """"프로젝트 구조" 실측 — 기존 ast_extractor.extract_functions_and_calls 재사용.

    scan_subdir(기본 "backend") 하위 .py 파일들을 스캔해 Function 노드 + CALLS 엣지를
    하나의 구조 요약으로 모은다. 파일 단위 구문 오류(SyntaxError 등)는 그 파일만 건너뛰고
    error 목록에 기록한다 — 한 파일 오류로 전체 스캔이 죽지 않도록(안정성).
    """
    scan_dir = project_root / scan_subdir
    if not scan_dir.exists():
        return {
            "scan_dir": str(scan_dir),
            "file_count": 0,
            "function_count": 0,
            "call_edge_count": 0,
            "files_scanned": [],
            "errors": [f"스캔 대상 디렉터리 없음: {scan_dir}"],
            "truncated": False,
        }

    files, truncated = _scan_python_files(scan_dir, max_files)

    all_nodes = []
    all_edges = []
    errors: list[str] = []
    files_scanned: list[str] = []

    for path in files:
        rel_path = str(path.relative_to(project_root)).replace("\\", "/")
        try:
            source = path.read_text(encoding="utf-8")
            nodes, edges = extract_functions_and_calls(source, rel_path)
        except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
            # 실측 불가 파일은 조용히 무시하지 않고 명시적으로 기록(과장 금지, T98 AIP)
            errors.append(f"{rel_path}: {exc.__class__.__name__}: {exc}")
            continue
        all_nodes.extend(nodes)
        all_edges.extend(edges)
        files_scanned.append(rel_path)

    return {
        "scan_dir": str(scan_dir.relative_to(project_root)).replace("\\", "/"),
        "file_count": len(files_scanned),
        "function_count": len(all_nodes),
        "call_edge_count": len(all_edges),
        "files_scanned": files_scanned,
        "nodes": [asdict(n) for n in all_nodes],
        "edges": [asdict(e) for e in all_edges],
        "errors": errors,
        "truncated": truncated,
    }


# "기능"(feature)만 여전히 확장 지점(파라미터 자리)으로 남는다 — 설계서 §2-1이 "기능"은
# 이미 구현된 Requirement<->Task IMPLEMENTS 엣지로 추적 가능하다고 명시했고, 이 스냅샷
# 함수 자체가 그 엣지를 다시 만들 필요는 없다고 판단했다(중복 방지, CRZ) — 그래도 "아직
# 이 함수가 채우지 않는다"는 사실은 정직하게 남긴다.
_NOT_IMPLEMENTED = {
    "status": "NOT_IMPLEMENTED",
    "note": "다음 청크에서 구현 예정 — 설계서 03_PHASE3_AGENT_GRAPHIFY.md §2-1 참조",
}


def build_project_domain_snapshot(
    project_root: Path,
    scan_subdir: str = "backend",
    max_files: int = DEFAULT_MAX_FILES,
    infra_subdir: str = "infrastructure",
    max_infra_files: int = DEFAULT_MAX_INFRA_FILES,
    workflows_subdir: str = "governance/workflows",
    max_workflow_files: int = 100,
    requirements: list | None = None,
    tasks: list | None = None,
    router_module_path: str = DEFAULT_ROUTER_MODULE_PATH,
) -> dict:
    """AST(구조) + 환경설정 + 정책문서(프로세스) + solution_stack(공통화) + FORMAT_STRATEGY(기술)
    기반 프로젝트 도메인 스냅샷을 생성한다 — 설계서 §2-1의 5개 청크(구조·환경·프로세스·
    공통화·기술) 전부 구현 완료.

    `requirements`/`tasks`는 신규 선택적 파라미터다(기본값 None) — 하위호환 유지: 호출자가
    넘기지 않으면 "commonization" 청크는 크래시 없이 "데이터 미제공"(`NO_DATA`) 상태로만
    채워진다. `router_module_path`도 선택적이며 기본값이 이 프로젝트의 실제 경로를 가리키므로
    보통은 호출자가 아무것도 넘기지 않아도 "technology" 청크가 정상 채워진다.

    "기능"(feature)만 여전히 확장 지점(파라미터 자리)으로 남는다(위 `_NOT_IMPLEMENTED`
    상수 주석 참조).

    diff(이전 스냅샷과 비교)가 필요하면 이 함수의 반환값과 `ProjectDomainSnapshotStore.
    load_previous()` 결과를 `diff_snapshots()`에 넘겨 별도로 호출한다(관심사 분리 유지 —
    이 함수 자체는 여전히 diff를 하지 않는다).
    """
    project_root = Path(project_root)

    commonization = extract_solution_stack_usage(requirements, tasks)
    technology = extract_technology_stack(router_module_path, solution_stack_usage=commonization)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "structure": _extract_structure(project_root, scan_subdir, max_files),
        "environment": extract_environment_config(project_root, infra_subdir, max_infra_files),
        "process": extract_process_docs(project_root, workflows_subdir, max_workflow_files),
        "commonization": commonization,
        "technology": technology,
    }


# diff 대상 청크 — 스냅샷의 메타 필드(generated_at/project_root)는 매 호출마다 항상 달라지므로
# (generated_at은 타임스탬프) diff 비교에서 제외한다. 이 목록은 build_project_domain_snapshot()
# 반환 dict의 5개 청크 키와 그대로 맞춘다(CRZ — 새 이름 발명 금지).
_DIFF_CHUNK_KEYS = ("structure", "environment", "process", "commonization", "technology")


def diff_snapshots(old: dict | None, new: dict) -> dict:
    """이전 스냅샷(`old`)과 새 스냅샷(`new`)을 청크 단위로 비교한다.

    정교한 구조적 diff(예: AST 노드 단위 add/remove)는 하지 않는다 — 각 청크(dict)의
    최상위 키 값을 얕게(shallow) 비교해 "무엇이 바뀌었는지"만 표시한다(설계서 §2-2 docstring이
    요구한 수준: "각 청크별로 무엇이 추가/삭제/변경됐는지").

    `old`가 None이면(최초 실행 — 이전 스냅샷 없음) 모든 청크를 status="ADDED"로 표시한다.
    `build_project_domain_snapshot()` 자체는 변경하지 않는다 — 호출자가 원할 때만 쓰는
    별도 함수(하위호환 유지).
    """
    if old is None:
        return {
            "status": "INITIAL",
            "chunks": {
                key: {"status": "ADDED", "changed_keys": sorted((new.get(key) or {}).keys())}
                for key in _DIFF_CHUNK_KEYS
                if key in new
            },
        }

    chunks_diff: dict = {}
    any_changed = False

    for key in _DIFF_CHUNK_KEYS:
        old_chunk = old.get(key)
        new_chunk = new.get(key)

        if old_chunk is None and new_chunk is None:
            continue

        if old_chunk is None:
            chunks_diff[key] = {
                "status": "ADDED",
                "changed_keys": sorted((new_chunk or {}).keys()) if isinstance(new_chunk, dict) else [],
            }
            any_changed = True
            continue

        if new_chunk is None:
            chunks_diff[key] = {
                "status": "REMOVED",
                "changed_keys": sorted((old_chunk or {}).keys()) if isinstance(old_chunk, dict) else [],
            }
            any_changed = True
            continue

        if old_chunk == new_chunk:
            chunks_diff[key] = {"status": "UNCHANGED", "changed_keys": []}
            continue

        if isinstance(old_chunk, dict) and isinstance(new_chunk, dict):
            changed_keys = sorted(
                k for k in (set(old_chunk.keys()) | set(new_chunk.keys()))
                if old_chunk.get(k) != new_chunk.get(k)
            )
        else:
            # dict가 아닌 청크(이례적 형태)는 키 단위 비교가 불가하므로 통째로 변경 표시만 한다.
            changed_keys = ["<non-dict-chunk>"]

        chunks_diff[key] = {"status": "CHANGED", "changed_keys": changed_keys}
        any_changed = True

    return {
        "status": "CHANGED" if any_changed else "UNCHANGED",
        "chunks": chunks_diff,
    }
