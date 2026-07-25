"""[Phase 3 §2-1 "프로세스"] governance/workflows/*.md 단순 텍스트 스캔.

설계 근거: `plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md` §2-1 "프로세스" 행 —
`governance/workflows/*.md`(예: SERVER-EXECUTION_POLICY.md) 같은 정책 문서를
Policy 노드로 등록.

**실측(2026-07-19)**: 이 프로젝트에는 설계서가 가정한 `governance/workflows/` 디렉터리가
실제로 존재한다(리팩토링 이전 가정이 아니라 그대로 유효) —
`governance/workflows/SERVER-EXECUTION_POLICY.md`,
`governance/workflows/RECALL_UNIVERSAL_SEARCH_GUIDE.md` 확인됨. 따라서 별도 대체 후보
(00_PROJECT_CONSTITUTION.md 등)를 쓰지 않고 설계서 그대로 `governance/workflows/*.md`를
스캔 대상으로 삼는다.

**의도적 단순화(과잉설계 회피)**: `environment_extractor.py`와 동일 원칙 — 정교한 마크다운
파서가 아니라 단순 텍스트 스캔.
- 제목(title): 파일의 첫 heading(`#`로 시작하는 첫 줄) 한 줄.
- 섹션 목록(sections): 파일 내 모든 heading 줄(레벨 무관, `#`으로 시작하는 모든 줄)을
  순서대로 나열 — heading_path 수준의 목차만, 본문 내용은 추출하지 않는다.
"""

from pathlib import Path

# 대용량/무한 스캔 회피(T38 PAP · DES-027) — 기존 extractor들과 동일 원칙.
DEFAULT_MAX_FILES = 100


def _extract_title_and_sections(path: Path) -> tuple[str | None, list[str], list[str]]:
    """`.md` 파일의 첫 heading(title)과 전체 heading 목록(sections)을 추출한다.

    반환: (title, sections, errors). 본문 내용은 읽지 않고 `#`로 시작하는 줄만 모은다.
    """
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        errors.append(f"{path.name}: {exc.__class__.__name__}: {exc}")
        return None, [], errors

    sections: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            sections.append(stripped)

    title = sections[0] if sections else None
    return title, sections, errors


def _scan_workflow_files(workflows_dir: Path, max_files: int) -> tuple[list[Path], bool]:
    """workflows_dir 하위 `*.md` 파일 목록을 max_files 상한 내에서 수집한다."""
    files: list[Path] = []
    truncated = False
    for path in sorted(workflows_dir.glob("*.md")):
        if len(files) >= max_files:
            truncated = True
            break
        files.append(path)
    return files, truncated


def extract_process_docs(
    project_root: Path,
    workflows_subdir: str = "governance/workflows",
    max_files: int = DEFAULT_MAX_FILES,
) -> dict:
    """`governance/workflows/` 하위 정책 문서를 단순 스캔해 "프로세스" 도메인 정보를 추출한다.

    반환 dict의 `files` 리스트 각 항목: `{"path", "title", "sections": [...]}`.
    본문 내용·값은 추출하지 않는다 — 제목과 heading 목록만(T99 AIOS·보안 원칙과 동일하게
    최소 노출 원칙을 따름, 다만 이 대상은 비밀값이 아니라 문서 목차 수준).
    """
    project_root = Path(project_root)
    workflows_dir = project_root / workflows_subdir

    if not workflows_dir.exists():
        return {
            "workflows_dir": str(workflows_dir),
            "file_count": 0,
            "files": [],
            "errors": [f"스캔 대상 디렉터리 없음: {workflows_dir}"],
            "truncated": False,
        }

    paths, truncated = _scan_workflow_files(workflows_dir, max_files)

    files: list[dict] = []
    errors: list[str] = []

    for path in paths:
        rel_path = str(path.relative_to(project_root)).replace("\\", "/")
        title, sections, file_errors = _extract_title_and_sections(path)
        errors.extend(file_errors)
        files.append({"path": rel_path, "title": title, "sections": sections})

    return {
        "workflows_dir": str(workflows_dir.relative_to(project_root)).replace("\\", "/"),
        "file_count": len(files),
        "files": files,
        "errors": errors,
        "truncated": truncated,
    }
