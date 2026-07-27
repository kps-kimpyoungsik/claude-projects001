"""[2026-07-27 신규] 문서 업로드/재청킹 파이프라인용 최소 인프로세스 백그라운드 잡 레지스트리.

배경(사용자 결정 — 범위 고정): `POST /documents/upload`와 `POST /documents/{doc_id}/rechunk`가
파싱→(LibreOffice 변환 최대 120초)→SPCEngine 청킹(Ollama 최대 60초)→분류·채번까지 전부를
FastAPI 요청 코루틴 안에서 동기·블로킹으로 실행해, 단일 uvicorn 워커의 이벤트 루프를 그
시간만큼 통째로 막는다(다른 요청도 함께 대기). Redis/arq/celery 등 신규 외부 인프라는 이번
범위에서 명시적으로 배제됐다(사용자 지시) — Python 표준 `concurrent.futures.ThreadPoolExecutor`
하나만으로 "즉시 202 + job_id 반환, 실제 파이프라인은 백그라운드 스레드에서 진행" 패턴을
구현한다.

**동시성 설계(핵심 결정, 왜 max_workers=1인가)**: `RequirementStore`/`DocumentStore`는 자체
내부 락이 없다(실측 확인 — `backend/adapters/persistence/file_lock.py`의 `write_lock`은
`documents_api.py`가 그래프 동기화 구간에만 선택적으로 감싸 쓰는 것이지, 스토어 자체의
read-modify-write를 항상 보호하지 않는다). 지금까지는 요청 자체가 이벤트 루프를 완전히
블로킹했기 때문에 사실상 "한 번에 문서 1건만 처리"가 우연히 보장돼 있었다 — 이 잡 큐를
멀티스레드로 만들면 그 암묵적 직렬성이 깨지고, 두 문서가 동시에 처리될 때
`requirements_store.json`에 대한 두 개의 겹치는 read-modify-write가 서로를 덮어쓰는 새로운
경합 버그가 생긴다(SPECIALIST.md S10 error_kb DES-080과 동일 계열 위험 — 이번 세션 범위가
아닌 스토어 자체의 락 보강까지 손대지 않기 위해, 실행기 크기를 1로 고정해 기존 안전성을
그대로 보존한다). LibreOffice headless 변환도 기본 사용자 프로파일을 공유해 동시 실행 시
프로파일 락 충돌 위험이 있다(실측 미확인 — 방어적으로 동일하게 max_workers=1로 회피).

향후 처리량이 실제로 문제가 되면(§AVC 근거 기반 판단) 스토어에 자체 락을 추가한 뒤에만
worker 수를 늘리는 것이 옳은 순서다 — 이 문서에 그 후속 과제를 명시해 둔다(T108 NSP-9,
미해결 항목 표면화).
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

JobStatus = Literal["queued", "processing", "done", "failed"]

# 문서 파이프라인 전용 단일 워커 실행기 — upload/rechunk 두 엔드포인트가 이 하나를 공유해
# "한 번에 문서 1건만 실제로 처리"라는 기존(우연한) 직렬성 불변식을 유지한다(위 docstring
# 참고). 신규 프로세스·신규 서비스 등록 없음 — 현재 uvicorn 프로세스 안의 스레드 1개.
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="doc-pipeline")

_LOCK = threading.Lock()
_JOBS: dict[str, "JobRecord"] = {}


@dataclass
class JobRecord:
    job_id: str
    kind: str  # "upload" | "rechunk" — 폴링 응답 구분·로그 가독성용, 신규 라우팅 분기 없음
    status: JobStatus = "queued"
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None  # {"code": ..., "message": ...} — requirements_api.error_envelope와 동일 shape
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


def submit_job(kind: str, fn: Callable[[], dict[str, Any]]) -> str:
    """`fn`(인자 없는 클로저 — 호출부가 이미 필요한 값을 전부 캡처)을 백그라운드 스레드에서
    실행하고 즉시 `job_id`를 반환한다. `fn`은 성공 시 폴링 응답의 `data`로 그대로 노출될
    dict를 반환해야 하고, 실패 시 예외를 던지면 이 함수가 잡아 `error` 필드로 정규화한다
    (T98 AIP — 예외 메시지를 그대로 삼키지 않고 항상 기록)."""
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    with _LOCK:
        _JOBS[job_id] = JobRecord(job_id=job_id, kind=kind)

    def _runner() -> None:
        with _LOCK:
            record = _JOBS[job_id]
            record.status = "processing"
            record.updated_at = time.time()
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001 — 잡 실행기 경계, 예외 종류 무관하게 폴링으로 표면화해야 함(T107 REP P4)
            # 호출부(예: documents_api._run_upload_job)가 `exc.aegis_error_code`를 미리
            # 붙였으면 그 코드를 그대로 쓴다(기존 동기 경로의 "AEGIS-VALIDATION" 등과 동일한
            # 코드 유지) — 없으면 잡 실행기 자체의 예상치 못한 예외로 분류.
            code = getattr(exc, "aegis_error_code", "AEGIS-JOB-FAILED")
            with _LOCK:
                record = _JOBS[job_id]
                record.status = "failed"
                record.error = {"code": code, "message": str(exc)}
                record.updated_at = time.time()
            return
        with _LOCK:
            record = _JOBS[job_id]
            record.status = "done"
            record.result = result
            record.updated_at = time.time()

    _EXECUTOR.submit(_runner)
    return job_id


def get_job(job_id: str) -> JobRecord | None:
    with _LOCK:
        record = _JOBS.get(job_id)
        if record is None:
            return None
        # 얕은 복사본 반환 — 호출부가 읽는 동안 백그라운드 스레드가 같은 객체를 변형하는
        # 경합을 피한다(락 보유 구간을 짧게 유지, 신규 동기화 프리미티브 발명 없음).
        return JobRecord(
            job_id=record.job_id,
            kind=record.kind,
            status=record.status,
            result=record.result,
            error=record.error,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
