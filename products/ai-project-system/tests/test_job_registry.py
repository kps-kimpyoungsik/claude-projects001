"""job_registry.py 단위 테스트 — 지금까지 전용 테스트 파일이 없었다(간접적으로만
documents_api 테스트를 통해 exercise됨, 87% 커버리지). 이 모듈이 다루는 핵심 위험(개별
잡 타임아웃 "poison-pill" 처리, 타임아웃 이후 늦게 완료/실패하는 잡의 결과를 덮어쓰지
않는 레이스 처리)은 이번 세션에서 whisper 전사 테스트가 실제로 겪은 것과 동일한 클래스의
문제라 직접 검증할 가치가 크다.

타이밍은 `time.sleep()`으로 결정적 지연을 주되(threading.Event 대신 단순 sleep으로 충분 —
fn은 별도 스레드에서 실행되므로 메인 스레드 타이머 진행을 막지 않는다), 타임아웃 값과 지연
값 사이에 충분한 배수 여유(4배 이상)를 둬 이 환경의 CPU 고부하(KH-2026-0783)에서도 안정적으로
재현되게 한다.
"""

import time

from backend.application.services import job_registry


def _poll_until(job_id, predicate, timeout=5.0, interval=0.02):
    deadline = time.time() + timeout
    while time.time() < deadline:
        record = job_registry.get_job(job_id)
        if predicate(record):
            return record
        time.sleep(interval)
    raise AssertionError(f"job {job_id} did not reach expected state within {timeout}s")


def test_get_job_unknown_returns_none():
    assert job_registry.get_job("job-does-not-exist") is None


def test_submit_job_completes_successfully():
    job_id = job_registry.submit_job("test", lambda: {"ok": True}, timeout_seconds=5.0)
    record = _poll_until(job_id, lambda r: r.status in ("done", "failed"))
    assert record.status == "done"
    assert record.result == {"ok": True}
    assert record.error is None


def test_submit_job_records_exception_as_failed():
    def _boom():
        raise ValueError("파싱 실패")

    job_id = job_registry.submit_job("test", _boom, timeout_seconds=5.0)
    record = _poll_until(job_id, lambda r: r.status in ("done", "failed"))
    assert record.status == "failed"
    assert record.error["code"] == "AEGIS-JOB-FAILED"
    assert "파싱 실패" in record.error["message"]


def test_submit_job_preserves_custom_error_code_from_exception_attribute():
    """호출부(documents_api 등)가 exc.aegis_error_code를 미리 붙이면 그 코드를 그대로 쓴다."""
    def _boom():
        exc = ValueError("검증 실패")
        exc.aegis_error_code = "AEGIS-VALIDATION"
        raise exc

    job_id = job_registry.submit_job("test", _boom, timeout_seconds=5.0)
    record = _poll_until(job_id, lambda r: r.status in ("done", "failed"))
    assert record.status == "failed"
    assert record.error["code"] == "AEGIS-VALIDATION"


def test_job_exceeding_timeout_is_marked_failed_with_timeout_code():
    """[poison-pill 핵심] fn이 timeout_seconds보다 오래 걸리면(여기선 절대 끝나지 않는 fn)
    타임아웃 타이머가 잡을 failed(AEGIS-JOB-TIMEOUT)로 표시해야 한다 — 워커 스레드 자체는
    죽지 않지만(Python 제약, 모듈 docstring 참고) 폴링 응답은 유한 시간 안에 실패를 관측한다."""
    done_flag = {"stop": False}

    def _never_finishes_until_flagged():
        while not done_flag["stop"]:
            time.sleep(0.01)
        return {"ok": True}

    job_id = job_registry.submit_job("test", _never_finishes_until_flagged, timeout_seconds=0.1)
    record = _poll_until(job_id, lambda r: r.status == "failed", timeout=3.0)
    assert record.error["code"] == "AEGIS-JOB-TIMEOUT"

    done_flag["stop"] = True  # 백그라운드 스레드 정리(테스트 간 누수 방지)


def test_job_finishing_successfully_after_timeout_keeps_timeout_result():
    """[레이스 핵심 — 이번 세션 whisper 실사례와 동일 클래스] fn이 실제로는 성공했지만
    timeout_seconds를 넘긴 뒤에야 끝나면, 이미 확정된 timeout(failed) 결과를 성공(done)으로
    덮어쓰지 않는다(정직성 — 폴링 클라이언트가 이미 실패로 확정한 결과를 뒤늦게 뒤집으면
    혼란을 유발, T98 AIP)."""
    def _slow_but_succeeds():
        time.sleep(0.4)  # timeout(0.1s)의 4배 여유 — 고부하 환경에서도 안정적으로 timeout 먼저 발생
        return {"ok": True}

    job_id = job_registry.submit_job("test", _slow_but_succeeds, timeout_seconds=0.1)
    timed_out_record = _poll_until(job_id, lambda r: r.status == "failed", timeout=3.0)
    assert timed_out_record.error["code"] == "AEGIS-JOB-TIMEOUT"

    # fn이 실제로 끝날 때까지 더 기다린 뒤에도 여전히 timeout(failed) 결과여야 한다 —
    # done으로 되돌아가면 안 된다.
    time.sleep(0.6)
    final_record = job_registry.get_job(job_id)
    assert final_record.status == "failed"
    assert final_record.error["code"] == "AEGIS-JOB-TIMEOUT"
    assert final_record.result is None


def test_job_raising_after_timeout_keeps_timeout_result():
    """위와 동일 레이스의 실패(예외) 버전 — fn이 timeout 이후 예외를 던져도 이미 확정된
    timeout 결과를 그 예외로 덮어쓰지 않는다."""
    def _slow_then_raises():
        time.sleep(0.4)
        raise RuntimeError("너무 늦게 실패함")

    job_id = job_registry.submit_job("test", _slow_then_raises, timeout_seconds=0.1)
    timed_out_record = _poll_until(job_id, lambda r: r.status == "failed", timeout=3.0)
    assert timed_out_record.error["code"] == "AEGIS-JOB-TIMEOUT"

    time.sleep(0.6)
    final_record = job_registry.get_job(job_id)
    assert final_record.status == "failed"
    assert final_record.error["code"] == "AEGIS-JOB-TIMEOUT"  # RuntimeError로 덮어써지지 않음


def test_mark_timeout_is_noop_when_job_already_finished():
    """[Line 133-134] `_mark_timeout()`은 원래 `_cancel_timer()`로 취소돼 실행되지 않는 게
    정상 경로지만, 타이머 취소와 정상 종료가 극히 드물게 경합하면 이미 완료된 잡에 대해
    콜백이 실행될 수 있다 — 그 경우 아무 것도 하지 않아야 한다(정상 결과를 절대 덮어쓰지
    않음). 실제 경합을 재현하기보다 이 불변식을 직접 검증한다(private 함수 직접 호출,
    레이스 자체는 재현 불가능할 정도로 드물어 타이밍 기반 테스트가 오히려 불안정해짐)."""
    job_id = job_registry.submit_job("test", lambda: {"ok": True}, timeout_seconds=5.0)
    record = _poll_until(job_id, lambda r: r.status in ("done", "failed"))
    assert record.status == "done"

    job_registry._mark_timeout(job_id, 5.0)  # 이미 done인 잡에 뒤늦게 타임아웃 콜백이 실행됨을 시뮬레이션

    unchanged = job_registry.get_job(job_id)
    assert unchanged.status == "done"
    assert unchanged.result == {"ok": True}


def test_mark_timeout_is_noop_when_job_unknown():
    """job_id가 아예 존재하지 않는 경우(예: 다른 테스트가 정리된 뒤)도 예외 없이 조용히
    반환한다."""
    job_registry._mark_timeout("job-does-not-exist-at-all", 5.0)  # 예외 없이 통과하면 성공


def test_get_job_returns_independent_copy():
    """get_job()이 내부 레코드의 얕은 복사본을 반환하는지 확인 — 호출부가 반환값을 변형해도
    내부 상태(_JOBS)에 영향을 주지 않아야 한다."""
    job_id = job_registry.submit_job("test", lambda: {"ok": True}, timeout_seconds=5.0)
    record = _poll_until(job_id, lambda r: r.status in ("done", "failed"))

    record.status = "tampered"  # 반환된 사본을 변형
    fresh = job_registry.get_job(job_id)
    assert fresh.status == "done"  # 내부 상태는 그대로
