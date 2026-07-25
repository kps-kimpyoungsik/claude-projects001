"""[Phase 3 §2-1 "환경"] infrastructure/ 하위 설정 파일 단순 텍스트 스캔.

설계 근거: `plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md` §2-1 "환경" 행 —
`infrastructure/topology.md` · `infrastructure/env/.env.*.example` ·
`infrastructure/nginx/*.conf.example` 등 설정 파일을 파싱해 Policy/노드로 등록.

**의도적 단순화(과잉설계 회피)**: 정교한 파서가 아니라 단순 텍스트 스캔.
- `.env.*.example` → `^([A-Z_][A-Z0-9_]*)=` 정규식으로 **키 이름만** 추출한다.
  값(비밀번호·API 키·토큰 등)은 절대 추출·반환하지 않는다 — 보안 원칙(T99 AIOS),
  이 파일 존재 자체가 "예시(example)" 파일이라도 습관적으로 값까지 긁는 코드를
  만들지 않는다.
- `.md` 파일 → 첫 heading(`# ...`) 한 줄만.
- `.conf.example` 파일 → 파일 존재 여부와 크기(바이트)만.
- 그 외 나머지 파일(`schema.py`, `requirements.txt`, `config_loader.py` 등) →
  조용히 무시(silent drop)하지 않고 `type="other"`로 경로만 정직하게 기록한다
  (T98 AIP — 과장도 축소도 하지 않는다).
"""

import re
from pathlib import Path

# 대용량/무한 스캔 회피(T38 PAP · DES-027) — 기존 structure extractor와 동일 원칙.
DEFAULT_MAX_FILES = 200

_ENV_KEY_PATTERN = re.compile(r"^([A-Z_][A-Z0-9_]*)=")


def _classify(path: Path) -> str:
    name = path.name
    if name.endswith(".example") and ".env" in name:
        return "env_example"
    if name.endswith(".conf.example"):
        return "nginx_conf_example"
    if path.suffix == ".md":
        return "markdown_doc"
    return "other"


def _extract_env_keys(path: Path) -> tuple[list[str], list[str]]:
    """`.env.*.example` 파일에서 키 이름만 추출한다 — 값은 절대 반환하지 않는다.

    반환: (키 이름 목록, 에러 목록). 값(등호 뒤 문자열)은 어떤 경로로도 반환값에
    포함되지 않는다 — 정규식 자체가 키 이름 그룹만 캡처한다.
    """
    keys: list[str] = []
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        errors.append(f"{path.name}: {exc.__class__.__name__}: {exc}")
        return keys, errors

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENV_KEY_PATTERN.match(stripped)
        if match:
            keys.append(match.group(1))
    return keys, errors


def _extract_markdown_heading(path: Path) -> str | None:
    """`.md` 파일의 첫 heading(`#`로 시작하는 첫 줄)만 추출한다."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped
    return None


def _scan_infra_files(infra_dir: Path, max_files: int) -> tuple[list[Path], bool]:
    files: list[Path] = []
    truncated = False
    for path in sorted(infra_dir.rglob("*")):
        if not path.is_file():
            continue
        if len(files) >= max_files:
            truncated = True
            break
        files.append(path)
    return files, truncated


def extract_environment_config(
    project_root: Path,
    infra_subdir: str = "infrastructure",
    max_files: int = DEFAULT_MAX_FILES,
) -> dict:
    """`infrastructure/` 하위 설정 파일을 단순 스캔해 "환경" 도메인 정보를 추출한다.

    반환 dict의 `files` 리스트 각 항목은 `type`에 따라 형태가 다르다:
    - env_example: `{"path", "type", "keys": [...]}"` (값 없음, 키 이름만)
    - nginx_conf_example: `{"path", "type", "size_bytes"}`
    - markdown_doc: `{"path", "type", "heading"}`
    - other: `{"path", "type"}` (내용 파싱 없음)
    """
    project_root = Path(project_root)
    infra_dir = project_root / infra_subdir

    if not infra_dir.exists():
        return {
            "infra_dir": str(infra_dir),
            "file_count": 0,
            "files": [],
            "errors": [f"스캔 대상 디렉터리 없음: {infra_dir}"],
            "truncated": False,
        }

    paths, truncated = _scan_infra_files(infra_dir, max_files)

    files: list[dict] = []
    errors: list[str] = []

    for path in paths:
        rel_path = str(path.relative_to(project_root)).replace("\\", "/")
        file_type = _classify(path)

        if file_type == "env_example":
            keys, file_errors = _extract_env_keys(path)
            errors.extend(file_errors)
            files.append({"path": rel_path, "type": file_type, "keys": keys})
        elif file_type == "nginx_conf_example":
            try:
                size_bytes = path.stat().st_size
            except OSError as exc:
                errors.append(f"{rel_path}: {exc.__class__.__name__}: {exc}")
                size_bytes = None
            files.append({"path": rel_path, "type": file_type, "size_bytes": size_bytes})
        elif file_type == "markdown_doc":
            heading = _extract_markdown_heading(path)
            files.append({"path": rel_path, "type": file_type, "heading": heading})
        else:
            files.append({"path": rel_path, "type": file_type})

    return {
        "infra_dir": str(infra_dir.relative_to(project_root)).replace("\\", "/"),
        "file_count": len(files),
        "files": files,
        "errors": errors,
        "truncated": truncated,
    }
