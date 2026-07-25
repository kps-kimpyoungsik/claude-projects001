"""배포 형상관리 — 실측 diff 기반 증분 배포 + 버전 이력 관리.

AEGIS SkillNet `57_deploy_manifest_history_skill`의 실행 구현체. 이전 배포 상태
(`deploy_config/manifest_current.json`)와 현재 소스를 파일 단위 sha256 해시로 실측
비교해 변경분만 배포 대상으로 추린다 — 최초 실행(manifest 없음)은 자동으로 전체(FULL)
배포로 판정된다(비교 기준 자체가 없으므로 당연한 귀결).

버전ID는 `{YYYYMMDD}_{당일순번}_{배포설명 slug}` 형식으로 채번한다 — 순번만으로는
나중에 "그 배포가 무엇이었는지" 알 수 없는 문제(평식 지적, 2026-07-23)를 해결하기 위해
배포 설명을 필수 입력으로 요구하고 그 설명을 버전ID 자체에 포함시킨다.

폴더 구조 (T84 IBP의 MIRROR/VERSIONS/HISTORY.jsonl 구조를 배포 컨텍스트로 그대로 채용,
CRZ — 신규 구조 발명 없음):
    deploy_config/
        MIRROR/                     최근 배포된 상태의 물리적 사본(항상 최신)
        manifest_current.json       MIRROR의 파일별 sha256 해시 인덱스(diff 기준)
        VERSIONS/{version_id}/      그 배포 시점에 변경되기 "직전" 파일들의 아카이브
        DEPLOY_HISTORY.jsonl        append-only 배포 이력 인덱스

graphify 색인은 이 스크립트의 책임이 아니다 — DEPLOY_HISTORY.jsonl에 append된 레코드를
호출 세션(AEGIS agent)이 별도로 graphify에 ingest한다(관심사 분리, SKILL.md 설계 그대로).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_EXCLUDE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "deploy_config",
    ".pytest_cache", ".server.pid",
}
DEFAULT_EXCLUDE_FILES = {"server.log", ".server.pid"}


def _slugify(message: str, max_len: int = 40) -> str:
    """배포 설명을 버전ID(폴더명)에 넣을 수 있는 slug로 변환.

    [2026-07-23 실측 수정] ASCII로만 변환하면 한글 배포 설명(실사용에서 가장 흔한 경우)이
    전부 "deploy"라는 무의미한 폴백으로 뭉개져, 애초에 이 기능이 해결하려던 "순번만으로는
    이력을 알 수 없는 문제"가 그대로 재발했다(스모크 테스트 실측으로 발견). 파일시스템에서
    금지된 문자(`<>:"/\\|?*`)와 공백류만 하이픈으로 치환하고, 한글 등 유니코드 문자는 그대로
    보존한다 — Windows/대부분 파일시스템은 유니코드 폴더명을 지원한다.
    """
    slug = re.sub(r'[<>:"/\\|?*\s]+', "-", message.strip()).strip("-").lower()
    if not slug:
        slug = "deploy"
    return slug[:max_len]


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _walk_source(source: Path, exclude_dirs: set[str], exclude_files: set[str]) -> dict[str, str]:
    """소스 트리를 실측 스캔해 {상대경로: sha256} 맵을 만든다(추정 없음, 파일 그대로 읽음)."""
    manifest: dict[str, str] = {}
    for path in source.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(source)
        if any(part in exclude_dirs for part in rel.parts[:-1]) or rel.parts[0] in exclude_dirs:
            continue
        if path.name in exclude_files:
            continue
        manifest[rel.as_posix()] = _hash_file(path)
    return manifest


def _next_version_id(versions_dir: Path, message: str) -> tuple[str, str, int]:
    """{YYYYMMDD}_{당일순번}_{slug} 버전ID를 채번한다(평식 교정: 순번만이 아닌 명확한 배포명)."""
    today = datetime.now().strftime("%Y%m%d")
    existing = [p.name for p in versions_dir.glob(f"{today}_*")] if versions_dir.exists() else []
    seq = len(existing) + 1
    slug = _slugify(message)
    return f"{today}_{seq}_{slug}", today, seq


def run_deploy(
    source: Path,
    project_root: Path,
    message: str,
    exclude_dirs: set[str] | None = None,
    exclude_files: set[str] | None = None,
) -> dict:
    """배포 형상관리 1회 실행 — 실측 diff → 버전ID 채번 → MIRROR/VERSIONS 갱신 → 이력 append.

    반환값은 이번 배포의 요약(version_id·mode·changed_files 등) — 호출자가 이 값을
    그대로 graphify ingest 또는 후속 배포 단계(06_deploy_skill)에 넘길 수 있다.
    """
    if not message or not message.strip():
        raise ValueError("배포 설명(message)은 필수입니다 — 빈 값으로 배포할 수 없습니다")

    exclude_dirs = exclude_dirs or DEFAULT_EXCLUDE_DIRS
    exclude_files = exclude_files or DEFAULT_EXCLUDE_FILES

    deploy_config = project_root / "deploy_config"
    mirror_dir = deploy_config / "MIRROR"
    versions_dir = deploy_config / "VERSIONS"
    manifest_path = deploy_config / "manifest_current.json"
    history_path = deploy_config / "DEPLOY_HISTORY.jsonl"

    current_manifest = _walk_source(source, exclude_dirs, exclude_files)

    is_first_deploy = not manifest_path.exists()
    mode = "FULL" if is_first_deploy else "INCREMENTAL"
    previous_manifest: dict[str, str] = {}
    if not is_first_deploy:
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if mode == "FULL":
        added = sorted(current_manifest.keys())
        modified: list[str] = []
        deleted: list[str] = []
    else:
        added = sorted(rel for rel in current_manifest if rel not in previous_manifest)
        modified = sorted(
            rel for rel in current_manifest
            if rel in previous_manifest and current_manifest[rel] != previous_manifest[rel]
        )
        deleted = sorted(rel for rel in previous_manifest if rel not in current_manifest)

    changed = added + modified
    version_id, date_str, seq = _next_version_id(versions_dir, message)

    version_snapshot_dir = versions_dir / version_id
    version_snapshot_dir.mkdir(parents=True, exist_ok=True)

    # 변경되기 "직전" 상태를 VERSIONS에 먼저 아카이빙(T84 IBP 순서 — 갱신 전 백업).
    for rel in modified + deleted:
        prev_file = mirror_dir / rel
        if prev_file.exists():
            dest = version_snapshot_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(prev_file, dest)

    (version_snapshot_dir / "changed_files.json").write_text(
        json.dumps({"added": added, "modified": modified, "deleted": deleted}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # MIRROR 갱신: 추가/수정분 반영, 삭제분 제거.
    for rel in changed:
        src_file = source / rel
        dest_file = mirror_dir / rel
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
    for rel in deleted:
        dead_file = mirror_dir / rel
        if dead_file.exists():
            dead_file.unlink()

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(current_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    record = {
        "version_id": version_id,
        "date": date_str,
        "seq": seq,
        "message": message,
        "mode": mode,
        "added_count": len(added),
        "modified_count": len(modified),
        "deleted_count": len(deleted),
        "changed_files_count": len(changed) + len(deleted),
        "total_files_count": len(current_manifest),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {**record, "added": added, "modified": modified, "deleted": deleted}


def main() -> int:
    parser = argparse.ArgumentParser(description="배포 형상관리 — 실측 diff 기반 증분 배포")
    parser.add_argument("--message", required=True, help="배포 설명(필수, 버전ID에 slug로 포함됨)")
    parser.add_argument("--source", default=".", help="배포 대상 소스 루트(기본: 현재 디렉터리)")
    parser.add_argument("--project-root", default=".", help="deploy_config/를 둘 프로젝트 루트")
    args = parser.parse_args()

    result = run_deploy(Path(args.source).resolve(), Path(args.project_root).resolve(), args.message)
    print(f"[Deploy Manifest] 모드: {result['mode']} | 버전ID: {result['version_id']}")
    print(f"[변경분] 추가 {len(result['added'])} · 수정 {len(result['modified'])} · 삭제 {len(result['deleted'])} / 전체 {result['total_files_count']}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
