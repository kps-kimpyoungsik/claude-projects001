# Phase 1.1 — 이중화 인프라 토폴로지 (설계 문서, 실배포 아님)

> **범위 고지**: 이 문서는 **설계·포트 배정·폴더 뼈대**까지만 다룬다. 실제 다중 서버 기동·
> 방화벽 규칙 적용·프로세스 배포는 **서비스 배포(C등급)** 에 해당하여 평식 승인 없이는
> 수행하지 않는다 (T100 AACG §3). 이 파일 자체는 문서 작성이므로 B등급(가역)이다.

## 노드 구성

| 노드 | 역할 | 프로세스 | 포트(확정) | 노출 범위 |
|------|------|---------|-----------|----------|
| WEB-1 | 정적 자산 + 리버스 프록시 | (미정 — Phase 1 스캐폴딩 단계) | `8080` | 외부 |
| WEB-2 | WEB-1 이중화(HA) | 동일 | `8081` | 외부 |
| WAS-1 | `core_was_block` 비즈니스 로직 | Python/FastAPI(예정) | `8790` | 내부망 |
| WAS-2 | WAS-1 이중화(HA) | 동일 | `8791` | 내부망 |
| DB | SQLite(개발) → PostgreSQL+pgvector(운영) | — | 내부 표준 포트 | 내부망 한정 |

**포트 충돌 회피 근거**: workbase가 이미 `8787`을 점유(운영 중 서버, `_governance/SERVER-EXECUTION_POLICY.md`
확인됨) — 본 프로젝트는 `8080/8081/8790/8791` 대역을 사용해 실행 시점 충돌을 원천 차단한다.
실제 기동 전에는 SEP-1(`netstat -ano | findstr ":<port>"`)로 재확인 의무(governance/workflows/SERVER-EXECUTION_POLICY.md SEP-1).

## HA(이중화) 전략 — 이 단계는 "설계"만

- WEB-1/2, WAS-1/2는 **액티브-액티브** 전제(로드밸런서는 Phase 1 범위 밖 — 별도 인프라 결정 필요).
- DB는 단일 인스턴스 우선(Phase 1은 SQLite), 운영 전환 시 PostgreSQL 복제 구성은 별도 설계 필요.
- 헬스체크: 각 WAS 노드는 `core_was_block/adapters/api/health.py`의 `health_envelope()`(T99 AIOS
  표준 envelope)를 그대로 재사용 — 노드별 신규 헬스체크 로직을 만들지 않는다.

## 미결 사항 (다음 설계 라운드 대상)

- 로드밸런서 선택(nginx/Caddy 등) 및 실제 방화벽 규칙 — 실배포 시점에 평식 승인과 함께 확정.
- WAS 이중화 시 세션/락 상태 공유 방식(Phase 4의 Distributed Lock과 연동 필요).

## 단일 ↔ 이중화 전환 (2026-07-18 추가 — 설정만으로 바로 적용 가능)

지금은 **단일 구성으로 실행**한다(사용자 지시). 이중화가 필요해지면 코드 변경 없이 설정
파일만 교체하면 되도록 미리 준비해뒀다 — 전환 절차는 [`HA_SETUP_GUIDE.md`](./HA_SETUP_GUIDE.md)
참조, 실제 설정 로더는 [`config_loader.py`](./config_loader.py), 환경변수 템플릿은
[`env/.env.single.example`](./env/.env.single.example)·[`env/.env.ha.example`](./env/.env.ha.example),
nginx 템플릿은 [`nginx/nginx.single.conf.example`](./nginx/nginx.single.conf.example)·
[`nginx/nginx.ha.conf.example`](./nginx/nginx.ha.conf.example).

## WebSocket 실시간 알림 팬아웃 (2026-07-18 추가 — `plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md` §3-5 참조)

WAS-1(8790)/WAS-2(8791) 각각 `/ws/requirements` WS 엔드포인트를 두고, **NATS**를 백플레인
브로커로 두 노드 간 이벤트를 팬아웃한다(신규 인프라 의존성 — 상세 근거·조사출처는 §3-5
참조). 이 경우 로드밸런서는 **`least_conn` + WS tunnel timeout 연장**을 권고(브로커 팬아웃
덕에 sticky session 불필요) — 위 "로드밸런서 선택 미결" 항목에 대한 첫 구체적 근거.
