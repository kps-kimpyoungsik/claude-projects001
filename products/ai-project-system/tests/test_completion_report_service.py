"""completion_report_service — git diff --stat 샘플 텍스트 파싱 검증."""

from backend.application.services.completion_report_service import build_completion_report

SAMPLE_DIFF_STAT = """\
 backend/domain/entities/task.py                        | 12 +++++++++---
 backend/application/services/task_dispatch_service.py  | 45 +++++++++++++++++++
 docs/README.md                                          |  3 +--
 3 files changed, 57 insertions(+), 3 deletions(-)
"""

BINARY_DIFF_STAT = """\
 assets/logo.png | Bin 0 -> 1024 bytes
 1 file changed, 0 insertions(+), 0 deletions(-)
"""


def test_build_completion_report_parses_files_changed():
    report = build_completion_report(
        task_id="T1",
        source_req_ids=["REQ-BIZ-SEC-001"],
        git_diff_stat_output=SAMPLE_DIFF_STAT,
        generated_at="2026-07-19T00:00:00+00:00",
    )
    assert report.task_id == "T1"
    assert len(report.files_changed) == 3
    paths = [f["path"] for f in report.files_changed]
    assert "backend/domain/entities/task.py" in paths
    assert all(f["change_type"] == "modified" for f in report.files_changed)


def test_build_completion_report_ignores_summary_line():
    report = build_completion_report(
        task_id="T1",
        source_req_ids=[],
        git_diff_stat_output=SAMPLE_DIFF_STAT,
        generated_at="2026-07-19T00:00:00+00:00",
    )
    for f in report.files_changed:
        assert "files changed" not in f["path"]


def test_build_completion_report_handles_binary_file():
    report = build_completion_report(
        task_id="T2",
        source_req_ids=[],
        git_diff_stat_output=BINARY_DIFF_STAT,
        generated_at="2026-07-19T00:00:00+00:00",
    )
    assert len(report.files_changed) == 1
    assert report.files_changed[0]["path"] == "assets/logo.png"
    assert "Bin" in report.files_changed[0]["summary"]


def test_build_completion_report_carries_requirement_status_updates():
    report = build_completion_report(
        task_id="T1",
        source_req_ids=["REQ-BIZ-SEC-001"],
        git_diff_stat_output="",
        generated_at="2026-07-19T00:00:00+00:00",
        requirement_status_updates={"REQ-BIZ-SEC-001": "IMPLEMENTED"},
    )
    assert report.requirement_status_updates == {"REQ-BIZ-SEC-001": "IMPLEMENTED"}
    assert report.files_changed == []
