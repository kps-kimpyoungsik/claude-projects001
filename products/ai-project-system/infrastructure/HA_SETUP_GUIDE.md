# 단일 → 이중화(HA) 전환 가이드

> 지금 이 프로젝트는 **단일 구성으로 실행**한다(사용자 지시 2026-07-18). 이 문서는 나중에
> 이중화가 필요해졌을 때 **설정만 바꾸면 바로 적용 가능**하도록 미리 준비해둔 가이드다 —
> 코드를 다시 설계하지 않는다(`infrastructure/config_loader.py`가 두 모드를 이미 지원).

## 지금 상태 (단일 구성)

```bash
cp infrastructure/env/.env.single.example .env
```

- WEB 1개(8080), WAS 1개(8790), NATS 불필요, 로드밸런서 불필요.
- `infrastructure/config_loader.py`의 `load_deployment_config()`가 이 `.env`를 읽으면
  `DeploymentConfig(mode="single", is_ha=False)`를 돌려준다.

## 이중화가 필요해지면 (전환 절차 — 4단계, 코드 변경 0)

### 1단계 — NATS 준비

이중화 시 REQ 상태변경 실시간 알림(`plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md` §3-5)이
NATS 백플레인으로 WAS-1↔WAS-2 사이를 팬아웃한다. 단일 바이너리라 별도 클러스터 구성 없이도
시작 가능(§3-5 조사결과 — Kafka/RabbitMQ보다 이 프로젝트 규모에 적합).

```bash
# 예시(실제 실행은 이 문서의 범위 밖 — 서비스 기동은 평식 승인 필요, T100 AACG §3)
# nats-server -p 4222
```

### 2단계 — 환경설정 교체

```bash
cp infrastructure/env/.env.ha.example .env
```

`DEPLOY_MODE=ha`, `WAS_PORTS=8790,8791`, `WEB_PORTS=8080,8081`,
`NATS_URLS=nats://localhost:4222`, `LB_STRATEGY=least_conn`로 한 번에 바뀐다 — 개별 값을
하나씩 고칠 필요 없이 파일 하나만 교체하면 된다.

### 3단계 — 로드밸런서 설정 적용

```bash
# infrastructure/nginx/nginx.ha.conf.example 내용을 실제 nginx.conf에 반영
# 적용 전 반드시 SEP-1(governance/workflows/SERVER-EXECUTION_POLICY.md)로 포트 충돌 재확인
```

`least_conn` + WS timeout 연장이 이미 템플릿에 들어있다(§3-5 최신기술 조사 반영, sticky
session 불필요 — NATS 팬아웃이 그 역할을 대신함).

### 4단계 — WAS 노드 2개 기동

WAS-1(8790)·WAS-2(8791) 각각 같은 코드를 실행하되 `.env`(2단계에서 이미 `ha` 모드로
바뀜)를 읽으면 두 노드 모두 `config_loader.load_deployment_config()`에서
`config.is_ha == True`를 확인하고 서로 NATS로 이벤트를 주고받는다.

## 검증(전환 후 최소 확인)

`plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md` §3-5가 정의한 최소 스모크 테스트: 브라우저 두
탭을 WAS-1/WAS-2 각각에 붙여, 한쪽에서 REQ 상태를 바꾸면 반대쪽 탭도 즉시 갱신되는지 확인.

## 되돌리기(HA → 단일로 원복)

```bash
cp infrastructure/env/.env.single.example .env
```

NATS·이중 WAS·로드밸런서를 내려도 코드는 그대로 동작한다(`is_ha=False`로 자동 인식) —
전환이 양방향 가역이라는 점이 이 설계의 핵심(B등급 유지, T100 AACG).

## 관련 설계 문서

- `infrastructure/topology.md` — 포트·노드 구성 원 설계
- `plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md` §3-5 — NATS 백플레인·WebSocket 팬아웃 설계 + 최신기술 조사 근거
- `infrastructure/config_loader.py` — 이 가이드가 참조하는 실제 설정 로더 코드
