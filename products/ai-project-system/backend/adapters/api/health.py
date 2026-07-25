"""표준 헬스체크 응답 뼈대.

workbase/backend/internal/handlers/health.go 패턴 계승 +
T99 AIOS 공통 envelope({ok, data, error, meta}) 적용.
"""


def health_envelope(version: str) -> dict:
    return {
        "ok": True,
        "data": {"status": "ok", "version": version},
        "error": None,
        "meta": {"degraded": False, "stub": True},
    }
