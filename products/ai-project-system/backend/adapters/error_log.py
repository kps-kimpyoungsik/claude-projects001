"""[Phase 2] 파싱 실패 로컬 기록 — AEGIS error_kb 직접 쓰기 금지 (T64 KAAG).

사용자 제안("파싱 중 인코딩 에러 시 Error KB 노드를 생성하고 다음 파싱 시
/recall <Error_KB> 호출로 회피")은 방향은 맞지만, **이 프로젝트(상품 프로젝트)가
AEGIS 관리자 영역(base/04_memory/error_kb)에 직접 쓰는 것은 T64 KAAG가 금지**한다.
따라서 실패는 이 프로젝트 로컬 로그(`ingestion/data/parse_failures.jsonl`)에만 기록하고,
AEGIS error_kb로의 승격은 `hmsav`/`assetize` 파이프라인(사용자 "자산화 승인" 트리거)을
거치도록 분리한다 — 직접 파일 쓰기로 우회하지 않는다.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ParseFailure:
    file_ext: str
    filename: str
    error_message: str
    parser_strategy: str


def log_parse_failure(log_path: Path, failure: ParseFailure) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(failure), ensure_ascii=False) + "\n")


def has_known_failure(log_path: Path, file_ext: str, parser_strategy: str) -> bool:
    """동일 (확장자, 파서전략) 조합의 과거 실패가 로컬 로그에 있는지 확인.

    "동일 파싱 방식을 자동 회피"의 최소 구현 — 실제 회피 로직(대체 파서 선택)은
    라우터(ingestion/router.py) 쪽에서 이 함수의 반환값을 보고 판단하도록 분리한다.
    """
    if not log_path.exists():
        return False
    with log_path.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec["file_ext"] == file_ext and rec["parser_strategy"] == parser_strategy:
                return True
    return False
