"""PostgreSQL 커넥션 헬퍼 (2026-07-24 신설) — ⚠ 검증 미확정, README.md 참조.

이 세션에는 실제 PostgreSQL 연결 정보(호스트·포트·계정)가 전혀 없었다 — 하드코딩된
기본값을 두지 않고 `DATABASE_URL` 환경변수를 그대로 psycopg2에 넘긴다(값이 없으면
명시적으로 실패시켜, "조용히 잘못된 기본값에 연결"되는 상황을 막는다 — T99 AIOS
경계검증 정신과 동일: 비표준/누락 입력은 침묵 통과가 아니라 즉시 오류).
"""

import os

import psycopg2
import psycopg2.extras


def get_connection():
    """`DATABASE_URL` 환경변수(예: postgresql://user:pass@host:5432/dbname)로 연결한다.

    미설정 시 `RuntimeError`로 즉시 실패 — 연결 정보 부재를 기본값으로 얼버무리지 않는다.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL 환경변수가 설정되지 않았습니다 — PostgreSQL 어댑터를 쓰려면 "
            "먼저 실행 중인 PostgreSQL과 연결 문자열이 필요합니다(schema.sql 적용 후 사용)."
        )
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
