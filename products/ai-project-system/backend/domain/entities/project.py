from dataclasses import dataclass
from datetime import datetime


@dataclass
class Project:
    id: str
    name: str
    status: str  # WAITING, IMPLEMENTING, VERIFIED, ON_HOLD, ARCHIVED
    created_at: datetime
    # [2026-07-26 고도화] 프로젝트 대시보드용 일정 필드 — 선택값(ISO "YYYY-MM-DD" 문자열).
    # 기존 레코드(이 필드가 없던 시절 저장분)와 하위호환을 위해 항상 optional 기본값 None을
    # 갖는다(project_registry.py `_from_record()`가 `.get()`으로 채워 넣는다).
    start_date: str | None = None
    end_date: str | None = None
