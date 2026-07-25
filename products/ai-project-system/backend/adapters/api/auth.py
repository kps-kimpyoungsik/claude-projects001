"""[2026-07-25 §D-b83768b2] 최소 API 인증 게이트 — X-API-Key 헤더 기반.

2026-07-23 UPGRADE_PLAN 감사에서 "인증/인가 전무"가 P1로 지적됐고, 2026-07-25 실측
크로스체크에서 그 발견이 이미 `D-b83768b2` directive로 등록돼 있었음을 확인했다("배포전
예약 — 다른 작업 안정화 후 진행"). 이번 세션에서 STEP2/3 UI+API 작업이 커밋·검증
완료됐으므로("다른 작업 안정화") 사용자 직접 지시로 지금 착수한다(0-5 "직접 지시 우선"
원칙 — 누적 임계값 대기가 아니라 명시적 지시가 게이트).

**기본값은 인증 비활성(opt-in)** — `AIPS_API_KEY` 환경변수가 설정되지 않으면(로컬 개발
기본 상태) 인증을 전혀 요구하지 않는다. 기존 로컬 개발 워크플로우를 깨지 않는 안전한
기본값이다(회귀 0 원칙). 배포 환경에서 `AIPS_API_KEY`를 설정하면 그 순간부터 모든 API
요청에 일치하는 `X-API-Key` 헤더가 필요해진다.

적용 범위: API 라우터에만 dependency로 부착한다(각 `APIRouter(...)` 생성부). 정적
프론트(StaticFiles 마운트)·헬스체크(`/health`)는 이 게이트 대상이 아니다 — 브라우저가
정적 파일을 받아오는 것 자체를 막을 이유가 없고, 헬스체크는 모니터링 도구가 키 없이도
호출 가능해야 한다(관례).
"""

import hmac
import os

from fastapi import Header, HTTPException


def _configured_api_key() -> str | None:
    key = os.environ.get("AIPS_API_KEY", "").strip()
    return key or None


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = _configured_api_key()
    if expected is None:
        return  # 인증 비활성(기본값) — 로컬 개발 워크플로우 그대로 동작
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
