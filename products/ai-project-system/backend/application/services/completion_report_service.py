"""[Phase 3 Ext] 완료 보고서 — 요구사항별 상태 + 파일별 변경 내역 (설계:
plans/_plan/06_AGENT_DISPATCH_REPORTING.md §6).

`git diff --stat` **텍스트 출력을 파싱**하는 함수만 둔다 — 실제 git 호출(subprocess 등)은
호출자 책임으로 분리한다(이 서비스는 순수 문자열 파싱, I/O 없음).
"""

import re
from dataclasses import dataclass, field

# git diff --stat 표준 출력 라인 예:
#  " backend/domain/entities/task.py | 12 +++++--"
#  " docs/x.md | 3 +-"
# 요약 라인(" 2 files changed, 10 insertions(+), 5 deletions(-)")은 이 패턴과 매칭되지 않는다.
_STAT_LINE_RE = re.compile(r"^\s*(?P<path>.+?)\s+\|\s+(?P<count>\d+|Bin)\b")


@dataclass
class CompletionReport:
    task_id: str
    source_req_ids: list[str]
    files_changed: list[dict] = field(default_factory=list)
    requirement_status_updates: dict = field(default_factory=dict)
    generated_at: str = ""


def _parse_git_diff_stat(git_diff_stat_output: str) -> list[dict]:
    """`git diff --stat` 출력을 파싱해 files_changed 리스트를 만든다.

    change_type(added/modified/deleted)은 `git diff --stat`만으로는 구분할 수 없는 경우가
    있다(신규/삭제 파일도 그냥 " N +++/---" 형태로만 나오고, rename 이 아닌 이상 명시적
    add/delete 마커가 라인에 없다) — 구분 안 되면 "modified"로 기본값 처리한다(과장 금지,
    T98 AIP). Bin(바이너리) 파일은 라인 수 대신 "Bin"으로 표기되므로 summary는 그 값을 그대로 쓴다.
    """
    files_changed = []
    for line in git_diff_stat_output.splitlines():
        match = _STAT_LINE_RE.match(line)
        if not match:
            continue  # 요약 라인·빈 줄 등은 건너뜀
        path = match.group("path").strip()
        count = match.group("count")
        files_changed.append(
            {
                "path": path,
                # NOTE: git diff --stat 텍스트만으로는 added/deleted를 확정할 수 없어
                # 기본값 "modified"로 처리한다(추정으로 added/deleted 단정하지 않음, T98 AIP).
                "change_type": "modified",
                "summary": f"Bin diff" if count == "Bin" else f"{count} line(s) changed",
            }
        )
    return files_changed


def build_completion_report(
    task_id: str,
    source_req_ids: list[str],
    git_diff_stat_output: str,
    generated_at: str,
    requirement_status_updates: dict | None = None,
) -> CompletionReport:
    """git diff --stat 출력을 파싱해 완료 보고서를 만든다 (실제 git 호출은 호출자 책임)."""
    return CompletionReport(
        task_id=task_id,
        source_req_ids=list(source_req_ids),
        files_changed=_parse_git_diff_stat(git_diff_stat_output),
        requirement_status_updates=requirement_status_updates or {},
        generated_at=generated_at,
    )
