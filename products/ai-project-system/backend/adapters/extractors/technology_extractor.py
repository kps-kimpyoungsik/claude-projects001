"""[Phase 3 §2-1 "기술"] FORMAT_STRATEGY + solution_stack 집계 → 실제 기술 스택 전체 목록.

설계 근거: `plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md` §2-1 "기술(스택)" 행 — "`ingestion/
router.py`의 `FORMAT_STRATEGY` 처럼 이미 있는 기술 목록 + 1차 `solution_stack` 태그를 합쳐
'이 프로젝트가 실제 쓰는 기술 스택 전체 목록'을 그래프 노드로".

리팩토링 이후 실제 경로는 `backend/adapters/parsers/router.py`(옛 `ingestion/router.py`).

**텍스트 스캔이 아니라 실제 import를 택한 이유(보고 의무 사항)**: `environment_extractor`/
`process_extractor`는 대상이 사람이 쓰는 문서(.env.example, .md)라 "정교한 파서 대신 단순
텍스트 스캔"이 맞는 선택이었다. 하지만 `FORMAT_STRATEGY`는 **Python 코드 안의 dict 상수
그 자체**이고, 이미 로드 가능한 같은 코드베이스 모듈이다. 이걸 정규식으로 다시 텍스트
스캔하면 ①dict literal 문법이 조금만 바뀌어도(줄바꿈, 따옴표 스타일, 주석 위치) 정규식이
깨지거나 조용히 값을 놓칠 위험이 있고 ②이미 정확한 소스(파이썬 인터프리터 자체)가 있는데
그걸 근사치 텍스트 파서로 재구현하는 건 불필요한 중복이다. `importlib.import_module`로
모듈을 그대로 불러와 `FORMAT_STRATEGY` 속성을 읽으면 100% 정확하고 코드도 더 짧다 —
그래서 이 청크만 예외적으로 "import 후 속성 읽기" 방식을 택했다.
"""

import importlib
from typing import Any

DEFAULT_ROUTER_MODULE_PATH = "backend.adapters.parsers.router"


def extract_technology_stack(
    router_module_path: str = DEFAULT_ROUTER_MODULE_PATH,
    solution_stack_usage: dict | None = None,
) -> dict:
    """`FORMAT_STRATEGY`(ingestion 포맷 전략) + solution_stack 집계를 합쳐 기술 스택을 반환한다.

    Args:
        router_module_path: `FORMAT_STRATEGY`를 가진 모듈의 dotted import 경로. 기본값은
            현재 실제 위치(`backend/adapters/parsers/router.py`).
        solution_stack_usage: `commonization_extractor.extract_solution_stack_usage()`가
            반환한 dict(`{"stack_usage": {...}}` 형태) 또는 그 안의 `stack_usage` dict를
            직접 넘겨도 된다 — 둘 다 방어적으로 처리한다. None이면 solution_stack 쪽은
            "데이터 미제공"으로 정직하게 비워둔다(크래시하지 않음, T98 AIP).

    반환:
        {
            "status": "OK" | "PARTIAL" | "NO_DATA",
            "ingestion_formats": {".hwp": "unstructured_parse", ...},
            "solution_stack_names": ["전자정부표준프레임워크", ...],
            "technology_stack": [".hwp(unstructured_parse)", "전자정부표준프레임워크", ...],
            "errors": [...],
        }
    """
    errors: list[str] = []
    ingestion_formats: dict[str, str] = {}

    try:
        module = importlib.import_module(router_module_path)
        format_strategy = getattr(module, "FORMAT_STRATEGY")
        ingestion_formats = dict(format_strategy)
    except (ImportError, AttributeError, TypeError) as exc:
        errors.append(
            f"{router_module_path}.FORMAT_STRATEGY 로드 실패: {exc.__class__.__name__}: {exc}"
        )

    stack_names = _extract_stack_names(solution_stack_usage)

    technology_stack: list[str] = [
        f"{ext}({strategy})" for ext, strategy in sorted(ingestion_formats.items())
    ]
    technology_stack.extend(sorted(stack_names))

    if not ingestion_formats and not stack_names:
        status = "NO_DATA" if not errors else "PARTIAL"
    elif errors or not stack_names:
        status = "PARTIAL"
    else:
        status = "OK"

    return {
        "status": status,
        "ingestion_formats": ingestion_formats,
        "solution_stack_names": sorted(stack_names),
        "technology_stack": technology_stack,
        "errors": errors,
    }


def _extract_stack_names(solution_stack_usage: dict | None) -> set[str]:
    """`extract_solution_stack_usage()`의 반환값 또는 그 안의 `stack_usage`를 방어적으로 읽는다."""
    if not solution_stack_usage:
        return set()

    candidate: Any = solution_stack_usage
    if "stack_usage" in solution_stack_usage:
        candidate = solution_stack_usage["stack_usage"]

    if not isinstance(candidate, dict):
        return set()

    return set(candidate.keys())
