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

[2026-07-28 개별 잡 타임아웃 추가, directive D-82ebea85 — aegis-dev000 Experience Buffer
2026-07-28 항목("poison-pill" 위험) 해소] `max_workers=1`은 스토어 read-modify-write 경합을
막기 위한 의도적 설계였지만, 개별 잡에 타임아웃·취소가 전혀 없어 잡 1건이 예상보다 오래
걸리면(모델 최초 로딩 지연·네트워크 문제 등) 그 뒤에 제출된 모든 잡(가벼운 것 포함)이 유일한
워커 뒤에서 **무기한** 대기하는 갭이 있었다(실측 확인 — 전체 pytest 스위트 재실행에서
`test_documents_upload_api.py`의 wav 전사 테스트가 오래 걸리자 그 뒤에 대기하던 5개 테스트가
연쇄로 타임아웃/실패). Python 스레드는 강제 종료가 불가능하므로(Experience Buffer
2026-07-26 항목과 동일 제약) 여기서 "타임아웃 처리"는 실행 중인 스레드를 죽이는 게 아니라,
`JOB_TIMEOUT_SECONDS` 경과 시 그 잡의 상태를 즉시 `failed`(timeout)로 표시해 폴링 API가
무기한 대기 대신 유한 시간 안에 실패를 관측하게 만드는 것이다(§실측: 백그라운드 스레드
자체는 계속 돌 수 있고, `_JOBS`에 남아 있는 아직 시작조차 못한 "queued" 잡도 자신의 제출
시점 기준 타이머로 개별적으로 타임아웃되므로, 워커가 막혀도 뒤에 밀린 잡들이 각자 유한
시간 안에 "실패"로 보고된다). 워커 자체가 여전히 막혀 있는 근본 문제(다중 워커·잡
취소·스토어 락 보강)는 이번 범위 밖 — 후속 과제로 명시해 둔다(T108 NSP-9).
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

logger = logging.getLogger(__name__)

JobStatus = Literal["queued", "processing", "done", "failed"]

# 문서 파이프라인 전용 단일 워커 실행기 — upload/rechunk 두 엔드포인트가 이 하나를 공유해
# "한 번에 문서 1건만 실제로 처리"라는 기존(우연한) 직렬성 불변식을 유지한다(위 docstring
# 참고). 신규 프로세스·신규 서비스 등록 없음 — 현재 uvicorn 프로세스 안의 스레드 1개.
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="doc-pipeline")

# [2026-07-28 신규] 개별 잡 타임아웃(초, 설정 가능 — env override 지원).
#
# 실측 근거: 이 프로젝트에 "documents_api.py의 job 폴링 타임아웃"이라는 서버측 상수는
# 존재하지 않는다 — 실측 확인 결과 `frontend/views/documents.html`의 `pollUploadJob()`은
# `for (;;)` 무한 루프로 폴링하고(클라이언트측 타임아웃 없음), 유일하게 존재하는 구체적인
# "job 폴링 타임아웃" 값은 `tests/_job_polling.py`의 `poll_job_until_done(..., timeout:
# float = 150.0)`이다. 이 상수를 그 값에 맞춰 설계했다 — 실행측 타임아웃이 폴링측 타임아웃
# 이상이면 poison-pill 상황에서 테스트(및 실제 폴링 클라이언트)가 이 기능보다 먼저 자체
# 타임아웃/포기로 끊겨버려 무의미해지기 때문에, 10초 여유를 두고 그보다 작게 잡았다.
#
# 트레이드오프(정직하게 명시): 알려진 파이프라인 이론적 최대치는 LibreOffice 변환
# 최대 120초(`libreoffice_bridge.DEFAULT_TIMEOUT_SECONDS`) + Ollama 판단 1회 최대 60초
# (`ollama_semantic_judge.OllamaSemanticJudge.__init__`의 기본 `timeout=60`, 문서 1건당
# 1회 호출 — 청크마다 반복 호출 아님, `heading_splitter.py` 실측 확인)로 두 최악값이
# 겹치면 약 180초까지 이론상 가능하다. 140초는 그보다 작으므로 극단적으로 느리지만 정상
# 완료됐을 잡을 드물게 오탐 타임아웃시킬 위험이 있다 — 이는 "스레드를 강제 종료할 수
# 없다"는 근본 제약 안에서 폴링측과의 정합을 우선한 의도적 선택이며(§AVC 근거기반 완화),
# 운영 중 오탐이 실제로 관측되면 이 값과 `tests/_job_polling.py`의 폴링 타임아웃을
# 함께 상향 조정해야 한다(후속 과제로 명시, T108 NSP-9).
JOB_TIMEOUT_SECONDS = float(os.environ.get("AEGIS_DOC_JOB_TIMEOUT_SECONDS", "140"))

_LOCK = threading.Lock()
_JOBS: dict[str, "JobRecord"] = {}
# job_id -> 타임아웃 타이머. 잡이 정상 종료(성공/예외)하면 취소해 불필요한 콜백 발동과
# 그로 인한 혼란스러운 로그를 막는다(신규 동기화 프리미티브 발명 없음 — 표준 threading.Timer).
_TIMERS: dict[str, threading.Timer] = {}


@dataclass
class JobRecord:
    job_id: str
    kind: str  # "upload" | "rechunk" — 폴링 응답 구분·로그 가독성용, 신규 라우팅 분기 없음
    status: JobStatus = "queued"
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None  # {"code": ..., "message": ...} — requirements_api.error_envelope와 동일 shape
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


def _is_timed_out(record: "JobRecord | None") -> bool:
    """이미 타임아웃 타이머가 이 잡을 `failed`로 표시했는지 여부. 정상 실패(`fn()`이 던진
    예외)와 구별하기 위해 error code로 판별한다(신규 status 값 추가 없음 — `JobStatus`
    리터럴은 그대로 4종 유지, CRZ)."""
    if record is None or record.status != "failed":
        return False
    return bool(record.error) and record.error.get("code") == "AEGIS-JOB-TIMEOUT"


def _mark_timeout(job_id: str, timeout_seconds: float) -> None:
    """`threading.Timer` 콜백 — 제출 시점 기준 `timeout_seconds` 경과 후 호출된다. 잡이
    그때까지 `done`/`failed`로 정상 종결되지 않았으면(아직 "queued"거나 "processing"이면)
    `failed`(timeout)로 표시한다. 이미 정상 종결됐다면(타이머 취소가 경합적으로 놓친 극히
    드문 경우 포함) 아무것도 하지 않는다 — 정상 결과를 덮어쓰지 않는다."""
    with _LOCK:
        record = _JOBS.get(job_id)
        if record is None or record.status in ("done", "failed"):
            return
        record.status = "failed"
        record.error = {
            "code": "AEGIS-JOB-TIMEOUT",
            "message": f"작업이 {timeout_seconds:.0f}초 안에 끝나지 않아 타임아웃 처리되었습니다",
        }
        record.updated_at = time.time()
    # 워커 스레드 자체는 강제 종료할 수 없어(Python 제약, 위 모듈 docstring 참고) 이 잡의
    # 실행이 백그라운드에서 계속되고 있을 수 있다 — `max_workers=1`이라 그 스레드가 계속
    # 점유돼 있으면 뒤에 밀린 잡도 실제로 시작조차 못 한 채 각자의 타이머로 개별 타임아웃될
    # 것이다. 운영자가 "워커가 멈춘 것처럼 보이는" 상황을 로그로 바로 알아챌 수 있도록
    # WARNING으로 남긴다(T107 REP, 이번 작업 요구사항 1항).
    logger.warning(
        "job_registry: job %s exceeded %.0fs timeout -- marked failed (AEGIS-JOB-TIMEOUT). "
        "The background thread cannot be forcibly stopped and may still be running; "
        "the single doc-pipeline worker may remain occupied by it, delaying any queued jobs.",
        job_id, timeout_seconds,
    )


def _cancel_timer(job_id: str) -> None:
    with _LOCK:
        timer = _TIMERS.pop(job_id, None)
    if timer is not None:
        timer.cancel()


def submit_job(
    kind: str,
    fn: Callable[[], dict[str, Any]],
    timeout_seconds: float = JOB_TIMEOUT_SECONDS,
) -> str:
    """`fn`(인자 없는 클로저 — 호출부가 이미 필요한 값을 전부 캡처)을 백그라운드 스레드에서
    실행하고 즉시 `job_id`를 반환한다. `fn`은 성공 시 폴링 응답의 `data`로 그대로 노출될
    dict를 반환해야 하고, 실패 시 예외를 던지면 이 함수가 잡아 `error` 필드로 정규화한다
    (T98 AIP — 예외 메시지를 그대로 삼키지 않고 항상 기록).

    [2026-07-28 신규] `timeout_seconds`(기본 `JOB_TIMEOUT_SECONDS`) 경과 시 잡이 아직
    끝나지 않았으면 `failed`(`error.code == "AEGIS-JOB-TIMEOUT"`)로 표시된다 — 제출 시점
    기준으로 타이머가 시작되므로, 워커가 이전 잡에 막혀 이 잡이 실행조차 시작하지 못한
    "queued" 상태로 남아 있어도 동일하게 유한 시간 안에 타임아웃 처리된다(위 모듈 docstring
    "poison-pill" 참고). `timeout_seconds` 파라미터는 테스트가 짧은 값으로 override할 수
    있도록 노출한다(신규 테스트가 필요할 경우를 위한 훅 — 기존 3개 테스트 파일은 이 파라미터
    없이 기본값을 그대로 쓴다, CRZ)."""
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    with _LOCK:
        _JOBS[job_id] = JobRecord(job_id=job_id, kind=kind)

    timer = threading.Timer(timeout_seconds, _mark_timeout, args=(job_id, timeout_seconds))
    timer.daemon = True  # 프로세스 종료를 막지 않음 — 신규 비-데몬 스레드 등록 없음
    with _LOCK:
        _TIMERS[job_id] = timer
    timer.start()

    def _runner() -> None:
        with _LOCK:
            record = _JOBS.get(job_id)
            # 이미 타임아웃으로 failed 처리된 뒤라면(워커가 막혀 있다 뒤늦게 열린 경우)
            # "processing"으로 되돌리지 않는다 — 폴링 응답은 이미 고정된 실패로 확정됐다.
            if record is not None and not _is_timed_out(record):
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
                record = _JOBS.get(job_id)
                timed_out_already = _is_timed_out(record)
                if record is not None and not timed_out_already:
                    record.status = "failed"
                    record.error = {"code": code, "message": str(exc)}
                    record.updated_at = time.time()
            if timed_out_already:
                logger.warning(
                    "job_registry: job %s raised %s after it was already marked as timed out "
                    "-- keeping the timeout result, not overwriting.", job_id, code,
                )
            _cancel_timer(job_id)
            return
        with _LOCK:
            record = _JOBS.get(job_id)
            timed_out_already = _is_timed_out(record)
            if record is not None and not timed_out_already:
                record.status = "done"
                record.result = result
                record.updated_at = time.time()
        if timed_out_already:
            logger.warning(
                "job_registry: job %s finished successfully after it was already marked as "
                "timed out -- keeping the timeout(failed) result, not overwriting with success.",
                job_id,
            )
        _cancel_timer(job_id)

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
