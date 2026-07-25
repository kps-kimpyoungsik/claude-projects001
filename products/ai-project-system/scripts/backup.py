"""[WORK-A 2026-07-25] data/*.json + .graphify-out/graph.json 증분 백업.

AEGIS 전역 IBP(INCREMENTAL-BACKUP-POLICY, T84) 구조(MIRROR + VERSIONS + 이력 인덱스)를
프로젝트 로컬 스케일로 재사용한다(신규 구조 발명 없음, CRZ) — robocopy 대신 표준 라이브러리
shutil만 쓰는 이유는 이 프로젝트가 Windows 전용이 아니라 POSIX(git-bash)에서도 그대로
동작해야 하기 때문(restart.sh/stop.sh와 동일 실행 환경 전제).

사용법: python scripts/backup.py
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_ROOT = PROJECT_ROOT / "backup"
HISTORY_FILE = BACKUP_ROOT / "BACKUP_HISTORY.jsonl"

# 백업 대상 — 코드가 아니라 "재현 불가능한 상태"만 (요구사항/태스크/그래프).
# 코드는 git이 이미 이력을 보존하므로 이중 백업하지 않는다(CRZ, T84 IBP §IBP-CORE 정신).
TARGETS = [
    "data/requirements_store.json",
    "data/tasks_store.json",
    "data/task_locks.json",
    "data/projects_registry.json",
    "data/.graphify-out/graph.json",  # project_scope.resolve_project_data_dir() 기준 실경로(§W-5 확인)
]


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def run_backup() -> dict:
    ts = _timestamp()
    version_dir = BACKUP_ROOT / "VERSIONS" / ts
    version_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    skipped = []
    for rel in TARGETS:
        src = PROJECT_ROOT / rel
        if not src.exists():
            skipped.append(rel)
            continue
        dst = version_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)

    record = {
        "timestamp": ts,
        "copied": copied,
        "skipped_not_found": skipped,
        "version_dir": str(version_dir),
    }
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


if __name__ == "__main__":
    result = run_backup()
    print(json.dumps(result, ensure_ascii=False, indent=2))
