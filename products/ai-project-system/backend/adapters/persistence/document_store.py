"""[Phase 2] 원본 문서(정규화 마크다운) 저장소 — 미리보기 화면이 참조하는 근거.

지금까지는 청크의 200자 발췌(`RequirementRecord.description`)만 저장했다 — "이 요구사항이
원문 어느 블록에서 나왔는지"를 보여주려면 발췌가 아니라 **문서 전문**이 필요하다(사용자
요청: "내용과 출처 정보가 오른쪽 미리보기에 나와서 확인이 실시간 가능해야 됩니다"). 이
모듈이 그 전문을 doc_id로 저장·조회한다 — 새 DB 없이 파일 1개당 문서 1개(플레인 텍스트),
가장 단순한 방식(CRZ, over-engineering 회피).
"""

import re
from pathlib import Path

from backend.adapters.persistence.file_lock import write_lock as _write_lock

# [2026-07-24 보안수정] doc_id가 API 경로 파라미터로 그대로 유입되어 검증 없이
# `f"{doc_id}.md"` 경로 조합에 쓰이면 경로 순회(CWE-22)가 가능해진다(5-agent 진단
# 실측 확인). save/load/export_for_preview 3개 진입점 전부가 doc_id를 받으므로 여기서
# 한 번만 검증하면 모든 호출부(document_upload_service·documents_api·requirements_api)가
# 방어된다.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class InvalidDocIdError(ValueError):
    """doc_id가 안전 문자셋(영숫자·-·_)을 벗어남 — 경로 순회 방지."""


def _validate_doc_id(doc_id: str) -> None:
    if not _SAFE_ID.fullmatch(doc_id):
        raise InvalidDocIdError(f"허용되지 않는 doc_id 형식: {doc_id!r}")


class DocumentStore:
    def __init__(self, store_dir: Path):
        self._dir = store_dir

    def save(self, doc_id: str, markdown_content: str) -> Path:
        """저장 시 개행을 있는 그대로 보존한다 — `newline=""` 없이 쓰면 Windows에서
        `\\n`이 `\\r\\n`으로 자동 치환되어(Path.write_text 기본 동작) 파일 글자수가
        늘어난다. 그러면 chunking.py의 char_start/char_end(원본 문자열 기준 오프셋)가
        디스크에 저장된 파일과 어긋나 미리보기 하이라이트가 밀린다 — 실제로 이 프로젝트에서
        발견한 버그(Windows에서만 재현). `newline=""`로 원본 바이트를 그대로 유지해 오프셋과
        파일 내용이 항상 일치하게 만든다.
        """
        _validate_doc_id(doc_id)
        # [2026-07-28, ai-project-system 2번 작업] doc_id는 업로드 시점에 uuid로 채번돼
        # 정상 경로에서는 서로 다른 스레드가 같은 doc_id로 동시에 save()를 부르지 않는다 —
        # 하지만 이 스토어를 쓰는 다른 API(project_scope 공유 디렉터리)나 미래 호출부가
        # 그 가정을 깰 가능성까지 방어하기 위해 `RequirementStore`와 동일한 공유
        # `file_lock.write_lock`(RLock)으로 디렉터리 생성 + 파일쓰기 구간을 감싼다(신규 락
        # 프리미티브 발명 없음, CRZ).
        with _write_lock:
            self._dir.mkdir(parents=True, exist_ok=True)
            path = self._dir / f"{doc_id}.md"
            # Path.write_text()는 이 프로젝트가 지원하는 Python 버전에서 newline 인자를 받지
            # 않아(3.13 이전) open()을 직접 써서 newline="" 을 강제한다.
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(markdown_content)
            return path

    def load(self, doc_id: str) -> str | None:
        _validate_doc_id(doc_id)
        path = self._dir / f"{doc_id}.md"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8", newline="") as f:
            return f.read()

    def export_for_preview(self, doc_id: str, export_dir: Path) -> Path | None:
        """agent-view가 fetch할 수 있는 위치로 그대로 복사(화면은 정적 파일만 fetch 가능)."""
        content = self.load(doc_id)
        if content is None:
            return None
        export_dir.mkdir(parents=True, exist_ok=True)
        out_path = export_dir / f"{doc_id}.md"
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        return out_path
