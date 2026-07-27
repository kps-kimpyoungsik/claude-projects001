"""[2026-07-27 신규] `GET /documents/jobs/{job_id}` 폴링 테스트 헬퍼.

`test_documents_upload_api.py`·`test_documents_rechunk_api.py` 양쪽이 202+job_id 응답을
받은 뒤 완료까지 폴링하는 동일한 보일러플레이트가 필요해 공용 함수로 승격한다(CRZ, 신규
검증 로직 없음 — 단순 반복 GET + status 확인).
"""

import time

from fastapi.testclient import TestClient


def poll_job_until_done(test_client: TestClient, job_id: str, timeout: float = 150.0) -> dict:
    """job이 `"done"` 또는 `"failed"`가 될 때까지 폴링하고 최종 응답 body(`{ok, data, ...}`)를
    반환한다. `job_registry`의 실행기가 실제 스레드이므로(테스트 프로세스 안에서 진짜 백그라운드
    스레드 실행 — mock 아님) 여기서도 실제 벽시계 시간이 흐른다."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = test_client.get(f"/documents/jobs/{job_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        status = body["data"]["status"]
        if status in ("done", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")
