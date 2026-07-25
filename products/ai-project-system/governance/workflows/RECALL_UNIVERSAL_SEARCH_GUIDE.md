---
role: POLICY
domain: 작업방법론
sub_task: 범용 지식 검색 통합
topic: [recall, 하네스루프, 자산화, 재발방지, 다차원검증]
context: ai-project-system 전 Phase(설계·구현·검증·자산화) 착수·검증 시점마다 적용
source: 기존 AEGIS `/recall` 스킬(graphify·hmrecall·error_kb·acn 4채널) 재사용 — 신규 검색엔진 발명 아님
updated: 2026-07-17
---

# /recall 범용 검색 지침 (Recall-Harness Cycle)

> **원칙**: 새로운 검색 인프라를 만들지 않는다. AEGIS가 이미 가진 `/recall <질의>` 스킬
> (graphify + hmrecall + error_kb + acn 4채널 통합)을 **작업 루프의 필수 단계**로 문서화한다.

## 1. 검색 트리거 (언제 호출하는가)

| 트리거 시점 | 호출 예시 |
|---|---|
| 작업 시작(Task Start) | `/recall <작업 도메인 + 적용 헌법>` |
| 가설 설정(Hypothesis) | `/recall <유사 과거 사례>` |
| 검증(Verification) | `/recall <검증 기준·성공 패턴>` |
| 오류 수정(Self-Healing) | `/recall <해당 오류 해결 패턴>` |

## 2. 우선순위 (여러 질의가 겹칠 때)

1. **안전 우선** — 파일 무결성·삭제 방지 관련 (T90 DELP·T79 CCP 계열)
2. **맥락 파악** — 현재 작업 상태·claim 동기화
3. **지식 학습** — 과거 유사 실패 패턴(error_kb) — 재발 방지
4. **규칙 적용** — 디자인 토큰·코딩 표준 등 세부 규칙

## 3. 지식 오염 방지 (Context Pruning)

검색 결과 전량을 프롬프트에 투입하지 않는다. **연관성 상위 결과만 선별 요약**해 투입한다
(원문 덤프 금지 — T40 LPP 토큰 최적화 원칙과 동일). 이는 이미 `/ao`의 S0 프로파일러
(0-2~0-4)가 구현한 규칙이며, 본 문서는 그 규칙을 ai-project-system 작업 루프에도
동일 적용한다는 것을 명시할 뿐, 새 메커니즘을 추가하지 않는다.

## 4. 출처 신뢰성

`/recall` 결과는 반드시 `[출처]` 라벨(KH-id / error_id / node_id)과 함께 인용한다.
출처가 불명확한 정보는 "정보 출처 불분명"으로 표기하고 자동 확정하지 않는다 — 이는
기존 T98 AIP(답변 무결성) 4기둥 중 정직성 원칙 그대로다.

## 5. 자산화 연동 (신규 발명 없음)

작업 완료 후 성공/실패 패턴은 기존 T56 ACP + T100 AACG 경로로 등재한다.
"Curator 에이전트가 즉시 병합" 같은 별도 컴포넌트는 **아직 존재하지 않으며**, 실제로는
`hmsav`/`assetize` 스킬 + `ao_experience_record.py`(Growth DNA 캡슐)가 이 역할을 수행한다.
새 이름의 가상 컴포넌트를 만든 것처럼 기술하지 않는다(과장 금지, T98 AIP).

## 6. Phase 적용 예 (ai-project-system Phase 2)

| 단계 | 착수 전 recall 질의 예시 |
|---|---|
| 2.1 Ingestion 라우터 | `/recall 파일 인코딩·BOM 무결성 정책` |
| 2.2 SPC 청킹 | `/recall 청킹 임계치 관련 과거 실패 사례` |
| 2.3(→Phase3) Graphify | `/recall God Node 방지 · 중복 노드 처리 규칙` |

이 표는 **각 단계 착수 시 실제로 무엇을 질의해야 하는지의 체크리스트**이며, 자동 트리거
스크립트가 아니다 — 호출 자체는 세션에서 `/recall <질의>`를 직접 실행해 수행한다.
