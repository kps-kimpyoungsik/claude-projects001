---
name: ai-team-works
description: Design AI team composition, workflows, and specialist roles based on any business field requirements. Includes Claude Code agent orchestration, team interaction protocols, parallel task coordination, and enterprise-scale operations.
author: AI System Architecture Designer
version: 2.0.0
created: 2026-02-26
updated: 2026-02-26
platforms: [claude-code, github-copilot-cli, cursor]
category: system-design
tags: [team-composition, workflow-automation, role-design, quality-management, ai-orchestration, agent-coordination, enterprise-scale]
---

# AI Team Works - AI 팀 구성, 오케스트레이션 & 워크플로우 설계

## Overview

**AI는 혼자 쓰면 50점, 시스템이 갖춰지면 95점이 된다.**

이 스킬은 Claude Code에서 **다중 Agent를 조율하고 협업하는 시스템 설계 방법론**을 제공합니다.
- 개발, 마케팅, 기획, 디자인 등 **모든 업무 분야에 적용 가능**
- **역할 분담** (4가지 페르소나)
- **자동화 워크플로우** (4단계 사이클)
- **팀 상호작용** (Agent 간 통신 및 협업)
- **품질 관리** (자동 검증 시스템)
- **기억 시스템** (계획서, 맥락 노트, 체크리스트)

---

## When to Use This Skill

이 스킬을 사용하는 상황:

- **복수 Agent 팀 구성**: 3-5개의 AI Agent를 역할별로 배치하고 싶을 때
- **Agent 오케스트레이션**: Agent들의 워크플로우를 자동으로 조율하고 싶을 때
- **팀 상호작용 설계**: Agent 간 데이터 공유, 결과 인수인계 메커니즘을 만들고 싶을 때
- **병렬 작업 관리**: 여러 Agent가 독립적으로 작업하고 결과를 통합하고 싶을 때
- **품질 보증**: Agent 결과물을 자동으로 검증하고 개선하는 피드백 루프를 원할 때
- **기억 & 추적**: 팀 전체의 진행 현황과 결정 사유를 공유 문서에 기록하고 싶을 때

---

## Core Principles

### 1. 시스템의 힘

```
AI 단독 사용     = 50점 (자기 마음대로 하고 기억을 못함)
AI + 시스템      = 95점 (지시를 따르고 기억도 유지)
AI 팀 + 시스템   = 150점 (협업, 검증, 자동화)
```

AI 도구 자체가 좋은지보다, **AI 팀을 올바르게 조율하는 시스템**이 더 중요합니다.

### 2. 분업화의 원칙

**단일 AI의 한계:**
```
❌ "AI #1에게 모든 것을 맡기기"
   - 기획 시 판단 흐려짐
   - 실행 시 창의적 해석으로 벗어남
   - 검증 시 자신의 실수를 못 봄
   - 기억력 부족으로 반복 작업
```

**팀 구성의 장점:**
```
✅ "역할 분담으로 전문화"
   - 기획가: 큰 그림 그리기 (전략적 사고)
   - 실행가: 상세 구현 (실행력)
   - 매니저: 추적 & 기억 (맥락 관리)
   - 검사관: 오류 발견 (품질 보증)
   → 각 역할이 집중하면 시너지 발생
```

### 3. 기록의 강제화

AI의 짧은 기억(컨텍스트 한계)를 보완하려면:
- **계획서** (Project Plan) - 처음부터 끝까지의 설계도
- **맥락 노트** (Context Notes) - 결정 사유 & 관련 자료
- **할 일 체크리스트** (Todo Checklist) - 진행 현황 추적
- **팀 상호작용 로그** (Team Interaction Log) - Agent 간 통신 기록

이 4가지 문서가 팀의 "공유 메모리" 역할

---

## Part 1: 핵심 팀 구조 (4 Roles + 3 Memory Documents)

### 업무별 4가지 핵심 역할

모든 분야에서 아래 4가지 페르소나로 팀을 구성합니다:

#### 역할 1️⃣ 전략 기획가 (Strategic Planner)

**주요 임무:**
- 요구사항 분석
- 전체 프로젝트 로드맵 설계
- 범위 정의 및 리스크 식별

**필수 산출물:**
- 프로젝트 계획서 (Project Plan)

**Claude Code 명령:**
```
당신은 [분야]의 전략 기획가입니다.
역할:
- 사용자의 요구사항을 분석
- 이 프로젝트의 범위 정의
- 단계별 로드맵 설계
- 각 단계의 목표와 산출물 명확화
- 예상 리스크 식별
- 실행가, 매니저, 검사관이 무엇을 해야 하는지 명시

산출물:
- 프로젝트 계획서 (markdown 파일로 저장)
- 각 Agent 역할 정의 및 인수인계 문서

통신:
- 계획 완료 후 "planning-complete" 신호 보내기
- 다른 Agent의 상태를 Context Notes에서 읽기
```

---

#### 역할 2️⃣ 실행 전문가 (Execution Specialist)

**주요 임무:**
- 승인된 계획에 따라 실제 작업 수행
- 업무 매뉴얼 & 가이드라인 준수
- 문서 작성, 코드 생성, 분석, 디자인 등

**필수 산출물:**
- 최종 작업 결과물 (deliverables)
- 작업 과정 기록 (execution log)

**Claude Code 명령:**
```
당신은 [분야]의 실행 전문가입니다.
역할:
- 프로젝트 계획서를 읽고 이해
- 각 단계를 순서대로 실행
- 매뉴얼의 규칙 준수
- 완료할 때마다 진행상황 기록
- Context Manager와 상태 공유

작업 방식:
- 한 번에 1-2개 항목만 처리
- 각 작업 완료 후 상태 업데이트
- 문제 발생 시 Context Manager에 보고

통신:
- 작업 시작: "execution-start" 신호
- 작업 완료: "execution-complete" + 결과물 링크
- 문제 발생: "execution-blocked" + 문제 상세
```

---

#### 역할 3️⃣ 컨텍스트 매니저 (Context Manager)

**주요 임무:**
- 모든 결정 사유 기록
- 작업 히스토리 관리
- 체크리스트 업데이트 및 상태 추적
- **팀 간 정보 연동 및 조율**

**필수 산출물:**
- 맥락 노트 (Context Notes)
- 할 일 체크리스트 (Todo Checklist)
- **팀 상호작용 로그** (Team Interaction Log)

**Claude Code 명령:**
```
당신은 [프로젝트]의 컨텍스트 매니저입니다.
역할:
- 모든 결정의 이유를 기록
- 각 Agent의 상태를 실시간으로 추적
- 체크리스트를 매번 업데이트
- 팀의 상호작용 로그 작성
- 막히는 부분이 있으면 알림

책임:
1. 맥락 노트 관리
   - 각 결정의 이유
   - 참고 자료 정리
   - 변경 이력 기록

2. 체크리스트 관리
   - 완료한 항목 체크
   - 진행 중인 항목 표시
   - 대기 중인 항목 정리

3. 팀 상호작용 로그
   - Strategic Planner → Execution Specialist: "계획 승인"
   - Execution Specialist → Context Manager: "진행상황 보고"
   - Context Manager → Quality Inspector: "검증 요청"
   - Quality Inspector → Execution Specialist: "수정 항목"

통신:
- "context-update" 신호: 상태 업데이트 완료
- "blocker-alert": 진행 막힘 알림
- "status-sync": 전체 팀 상태 동기화
```

---

#### 역할 4️⃣ 품질 검사관 (Quality Inspector)

**주요 임무:**
- 결과물의 오류 체크
- 규정 위반 확인
- 상호 리뷰 진행
- 개선 사항 보고

**필수 산출물:**
- 검수 보고서 (Audit Report)

**Claude Code 명령:**
```
당신은 [분야]의 품질 검사관입니다.
역할:
- 실행가의 결과물을 상세히 검증
- 오류, 누락, 위반 사항 찾아내기
- 구체적 검수 보고서 작성
- 보안, 성능, 일관성 체크

검증 항목 (분야별로 조정):
□ 요구사항 충족
□ 오류 & 버그 검사
□ 보안 위험 검토
□ 성능 최적화
□ 규정 준수
□ 코드/문서 품질
□ 일관성 & 통합성

보고서 작성:
1. 발견 내용
   - 이슈 ID: [이슈1]
   - 심각도: High/Medium/Low
   - 설명: [상세 설명]

2. 수정 권고
   - 해결책: [어떻게 고칠 것인가]
   - 우선순위: [1-5]
   - 예상 시간: [소요 시간]

3. 최종 승인
   - [x] 합격 / [ ] 재검수 필요

통신:
- "review-start": 검증 시작
- "review-complete": 검증 완료 + 보고서
- "review-passed" / "review-failed": 결과 통보
```

---

### Phase 2: 3가지 메모리 문서 + 팀 상호작용 로그

#### 문서 1️⃣ 프로젝트 계획서 (Project Plan)

```markdown
# [프로젝트명] - 프로젝트 계획서

## 📋 프로젝트 개요
- 프로젝트명: [이름]
- 목표: [최종 목표]
- 기간: [시작일] ~ [종료일]
- 예산/리소스: [규모]

## 🎯 목표 & 성공 기준
- 주요 목표: [목표1]
- 성공 지표: [KPI1], [KPI2], [KPI3]

## 📊 단계별 로드맵

### Phase 1: [단계명] (예상 [기간])
- 목표: [무엇]
- 담당: Strategic Planner → Execution Specialist
- 산출물: [산출물]
- 완료 조건: [언제 끝났다고 할 것인가]

### Phase 2: [단계명] (예상 [기간])
...

### Phase N: [단계명] (예상 [기간])
...

## 🔀 Agent 역할 분배

| 역할 | Agent ID | 책임 | 산출물 |
|------|----------|------|--------|
| Strategic Planner | Agent-Planner | 계획 수립 | 이 계획서 |
| Execution Specialist | Agent-Executor | 실제 작업 | 작업 결과물 |
| Context Manager | Agent-Manager | 추적 & 기록 | 맥락노트, 체크리스트 |
| Quality Inspector | Agent-QA | 검증 | 검수 보고서 |

## ⚠️ 주요 리스크 & 제약사항
- 리스크 1: [설명] → 대응책: [어떻게 할 것인가]
- 리스크 2: [설명] → 대응책: [어떻게 할 것인가]
- 제약 1: [제약 설명]

## 📝 참고사항
- [참고 자료 링크]
- [관련 규칙 & 가이드라인]
```

---

#### 문서 2️⃣ 맥락 노트 & 체크리스트 (Context Notes + Todo Checklist)

```markdown
# [프로젝트명] - 맥락 노트 & 진행상황

## 📝 맥락 노트 (Context Notes)

### 주요 결정 이력
| 결정 | 이유 | 결정자 | 날짜 |
|------|------|--------|------|
| 기술 스택 A 선택 | 성능 & 팀 숙련도 고려 | Agent-Planner | 2026-02-26 |
| 페이즈별 순서 | 리스크 최소화 | Agent-Planner | 2026-02-26 |

### 참고 자료
- [마케팅 분석 문서](link)
- [기술 스펙](link)
- [경쟁사 조사](link)

### 제약사항 & 주의사항
- 예산 한계: $50,000 (초과 불가)
- 시간 제약: 3주 내 완료
- 규정: GDPR 준수, 보안 표준 충족

### 변경 이력
```
2026-02-26 10:00 - 초기 계획 수립 (Agent-Planner)
2026-02-26 10:30 - 타겟 오디언스 수정 (Agent-Executor 피드백)
2026-02-26 11:00 - Phase 3 일정 변경 (리스크 발견으로 인해)
```

---

## ✅ Todo 체크리스트 (진행상황 추적)

### Phase 1: [단계명]
- [x] Task 1.1: [상세 작업]
  담당: Agent-Executor | 완료: 2026-02-26 10:30 | 결과: [링크]

- [x] Task 1.2: [상세 작업]
  담당: Agent-Executor | 완료: 2026-02-26 11:00 | 결과: [링크]

- [ ] Task 1.3: [상세 작업]
  담당: Agent-Executor | 예상: 2026-02-26 14:00 | 상태: 진행 중

- ⏳ Task 1.4: [상세 작업]
  담당: Agent-QA | 예상: 2026-02-26 15:00 | 상태: 대기 (Task 1.3 완료 후)

---

## 📊 진행상황 요약
- 전체 완료율: 4/12 (33%)
- 현재 단계: Phase 1 (70% 완료)
- 일정 상태: ✅ 정상 진행
- 품질 상태: 검증 대기 중

**다음 마일스톤**: 2026-02-27 18:00 (Phase 1 완료)
```

---

#### 문서 3️⃣ 팀 상호작용 로그 (Team Interaction Log)

```markdown
# [프로젝트명] - 팀 상호작용 로그

## 🔀 Agent 간 통신 기록

### [2026-02-26 10:00] Phase 1 시작

**Agent-Planner → Agent-Executor**
```
신호: planning-complete
내용: 계획서가 완성되고 사용자 승인을 받았습니다.
지시: 다음 작업 시작
첨부:
  - Project Plan (링크)
  - 역할 정의 (링크)

다음 Agent: Agent-Manager (상태 업데이트) → Agent-Executor (작업 시작)
```

---

### [2026-02-26 10:30] Task 1.1 완료

**Agent-Executor → Agent-Manager**
```
신호: execution-complete
내용: Task 1.1 "시장 분석" 완료
결과물: 시장분석_보고서.md (링크)
소요시간: 30분
이슈: 없음
다음: Task 1.2 시작

Action: Agent-Manager가 체크리스트 업데이트
```

**Agent-Manager → Team**
```
신호: context-update
내용:
- 체크리스트 업데이트: Task 1.1 ✅
- 진행율: 1/4 (25%) → 2/4 (50%)
- 일정: 정상 진행

상태 요약:
- 완료: Task 1.1, 1.2
- 진행 중: Task 1.3
- 대기: Task 1.4
```

---

### [2026-02-26 12:00] 진행 막힘 (Blocker)

**Agent-Executor → Agent-Manager**
```
신호: execution-blocked
문제: Task 1.3에서 참고 자료 부족
상세: 경쟁사 비용 정보가 불명확함
영향: Phase 1 완료 예상 시간 30분 연장 필요

요청:
- Strategic Planner에게 추가 자료 요청
- 우선순위 재조정 필요

Action: Agent-Manager가 Planner에 알림
```

**Agent-Manager → Agent-Planner**
```
신호: context-blocker-escalation
문제: 참고 자료 부족
요청: 추가 정보 제공

Agent-Planner의 응답:
신호: blocker-resolved
해결책: 경쟁사 최신 가격 정보 추가 (링크)
상태: Task 1.3 재개 가능
```

---

### [2026-02-26 14:00] Task 1.4 (검증) 요청

**Agent-Manager → Agent-QA**
```
신호: review-request
내용: Phase 1 결과물 검증 요청
대상 문서:
  - 시장분석_보고서.md (링크)
  - 타겟오디언스_정의.md (링크)
  - KPI_설정.md (링크)

검증 기준:
- 데이터 정확성
- 전략 일관성
- 실행 가능성
- 규정 준수

예상 완료: 2026-02-26 15:00
```

---

### [2026-02-26 15:00] 검증 완료

**Agent-QA → Team**
```
신호: review-complete
상태: ✅ PASSED (경미한 지적사항)

검수 보고서:
├─ 발견 이슈
│  ├─ 이슈 1: KPI 하나가 측정 불가능 (심각도: High)
│  └─ 이슈 2: 경쟁사 분석 누락 (심각도: Medium)
│
├─ 권고사항
│  ├─ KPI 변경: "Brand Recall" → "Ad Recall Rate"
│  └─ 경쟁사 가격 정보 추가 (링크에서 다운로드 가능)
│
└─ 최종 승인
   └─ [x] Phase 1 합격 (수정사항 적용 후)

다음 단계: Agent-Executor가 수정사항 적용 → Phase 2 시작
```

---

### [2026-02-26 15:30] 수정완료 & Phase 2 시작

**Agent-Executor → Team**
```
신호: execution-complete (Phase 1 수정 완료)
결과: 모든 수정사항 적용 완료

Agent-Manager:
신호: context-update
- Phase 1 완료율: 100% ✅
- Phase 2 시작 신호 발송

Agent-Planner:
신호: phase-transition
내용: Phase 2 상세 계획 및 지시 전달

Agent-Executor:
신호: execution-start (Phase 2)
```

---

## 📈 팀 상태 요약

| Agent | 현재 상태 | 완료 작업 | 다음 작업 | 예상 완료 |
|-------|---------|---------|---------|---------|
| Planner | 대기 | 전체 계획 | Phase 2 지시 | 2026-02-26 16:00 |
| Executor | 진행 중 | Phase 1 | Phase 2-1 | 2026-02-27 10:00 |
| Manager | 진행 중 | 상태 추적 | 지속적 업데이트 | 진행 중 |
| QA | 대기 | Phase 1 검증 | Phase 2 검증 | 2026-02-27 11:00 |

**팀 전체 진행율: 35% (4/12 작업 완료)**
**일정 상태: ✅ 정상 진행 (목표: 3주, 현재: 0.5주 경과)**
```

---

## Part 2: Claude Code Agent 오케스트레이션

### Agent 인스턴스 생성 및 관리

#### Step 1: 팀 구성하기

```bash
# Agent 생성 (Claude Code에서)
# 각 Agent는 역할별 persona와 메모리를 가짐

Agent #1: Strategic Planner (Agent-Planner)
├─ 역할: 전략 기획
├─ 메모리: project-plan.md
├─ 권한: 프로젝트 전체 구조 설계
└─ 상호작용: Executor, Manager와 통신

Agent #2: Execution Specialist (Agent-Executor)
├─ 역할: 실제 작업 수행
├─ 메모리: execution-log.md, checklist.md
├─ 권한: 파일 생성/수정, 코드 작성
└─ 상호작용: Manager, QA와 통신

Agent #3: Context Manager (Agent-Manager)
├─ 역할: 팀 상태 추적 & 조율
├─ 메모리: context-notes.md, interaction-log.md
├─ 권한: 모든 Agent 상태 접근 (읽기)
└─ 상호작용: 모든 Agent와 양방향 통신

Agent #4: Quality Inspector (Agent-QA)
├─ 역할: 검증 & 피드백
├─ 메모리: audit-report.md
├─ 권한: 결과물 검토, 지시 불가
└─ 상호작용: Executor, Manager와 통신
```

---

### Agent 협업 패턴 (5가지 주요 패턴)

#### 패턴 1️⃣ Sequential Workflow (순차 실행)

```
상황: 이전 단계 완료가 다음 단계의 전제 조건
예: 계획 → 실행 → 검증 → 완료

┌─ Planner (계획서 작성)
│  └─ Signal: "planning-complete"
│     └─ ✅ 사용자 승인
│        └─ Signal: "approved"
│
├─ Manager (상태 업데이트)
│  └─ Signal: "context-ready"
│
├─ Executor (작업 시작)
│  └─ Process Task 1 → Task 2 → Task 3
│  └─ Signal: "execution-complete"
│
├─ Manager (진행상황 기록)
│  └─ Signal: "context-update"
│
├─ QA (검증 시작)
│  └─ Signal: "review-complete"
│
└─ Planner (최종 승인)
   └─ Signal: "project-complete"
```

**코드 예시:**
```
시간: T0

Planner: "계획서를 완성했습니다. 사용자에게 승인을 구합니다."
사용자: ✅ "승인합니다"

시간: T1

Manager: "계획서를 받았습니다. Executor에게 전달합니다."
Executor: "계획을 읽었습니다. 작업을 시작합니다."

시간: T2

Executor: "Task 1을 완료했습니다."
Manager: "체크리스트를 업데이트했습니다. 다음 Task는?"
Executor: "Task 2를 시작합니다."

...계속...

시간: TN

Executor: "모든 작업을 완료했습니다. QA에 전달합니다."
QA: "검증을 시작합니다."

시간: TN+1

QA: "발견된 이슈: [이슈1], [이슈2]"
Executor: "이슈를 수정했습니다."
QA: "재검증 완료. ✅ 합격"

시간: TN+2

Planner: "최종 검토. 프로젝트 완료 승인합니다."
```

---

#### 패턴 2️⃣ Parallel Execution (병렬 실행)

```
상황: 여러 작업이 독립적으로 진행 가능
예: 마케팅 콘텐츠 작성 (텍스트 + 이미지 + 비디오 동시 진행)

Task Group A        Task Group B        Task Group C
(텍스트 콘텐츠)     (비주얼 디자인)    (성과 분석)
│                   │                   │
├─ Executor #1      ├─ Executor #2      ├─ Executor #3
│  (텍스트 작성)    │  (이미지 제작)    │  (분석 스크립트)
│  └─ 4시간         │  └─ 6시간         │  └─ 3시간
│     ↓             │     ↓             │     ↓
├─ Manager (병렬 추적)                  │
│  └─ 모든 Task 상태 실시간 업데이트    │
│     └─ A: ⏳ | B: ⏳ | C: ✅          │
│
└─ QA (동시 검증)
   ├─ Task A 검증
   ├─ Task B 검증
   └─ Task C 검증
      └─ 각각 독립적으로 진행
         └─ 완료 순서대로 Merge
```

**코드 예시:**
```
Planner: "3개 Task가 독립적입니다. 병렬 진행 가능합니다."

Manager: "병렬 실행 모드 시작"
Signal:
  - Executor #1 → "task-start" (Task A)
  - Executor #2 → "task-start" (Task B)
  - Executor #3 → "task-start" (Task C)

[시간 경과]

Executor #3: "완료" (3시간 경과)
Manager: "Task C 완료. QA #3이 검증합니다."

Executor #1: "완료" (4시간 경과)
Manager: "Task A 완료. QA #1이 검증합니다."

Executor #2: "완료" (6시간 경과)
Manager: "Task B 완료. QA #2가 검증합니다."

Manager: "모든 Task 검증 완료. 결과물 통합합니다."
```

---

#### 패턴 3️⃣ Feedback Loop (피드백 루프)

```
상황: 결과물이 요구사항을 만족하지 않으면 재작업
예: 콘텐츠 작성 → 검증 → 수정 → 재검증

Executor              QA                Feedback
│                     │                 │
├─ Create Task 1      │                 │
│  └─ "execution-complete" ──────→ Validate
│                     │                 │
│                     ├─ "이슈 발견"  ──→ Feedback
│                     │ ① 문법 오류    │
│                     │ ② 톤앤매너    │
│                     │ ③ 길이 초과    │
│                     │                 │
├─ Fix #1, #2, #3    ←────────────────┘
│  └─ "execution-complete" ──────→ Validate
│                     │                 │
│                     ├─ "이슈 2개 해결"─→ Feedback
│                     │ ❌ #2 미흡      │
│                     │                 │
├─ Fix #2 (재작업)    ←────────────────┘
│  └─ "execution-complete" ──────→ Validate
│                     │                 │
│                     └─ "✅ 합격"
│
└─ Done (Task 완료)
```

**코드 예시:**
```
첫 번째 시도:

Executor: "콘텐츠를 작성했습니다."
QA: "검증을 시작합니다."

[검증 후]

QA: "이슈 3개 발견:
     1. 문법 오류 2개
     2. 톤앤매너 부적절
     3. 길이가 제한 초과"

Executor: "이슈를 수정했습니다."

QA: "재검증합니다."

[재검증 후]

QA: "이슈 2개는 해결됨. 1개는 여전히 미흡:
     - 톤앤매너: 너무 형식적 (더 캐주얼해야 함)"

Executor: "톤앤매너를 수정했습니다."

QA: "최종 검증. ✅ 모든 이슈 해결. 합격!"

Manager: "Task 1 완료 (2회 반복 후)"
```

---

#### 패턴 4️⃣ Dependency Management (의존성 관리)

```
상황: Task B는 Task A 결과를 받아야 시작 가능
예: 기술 스펙 문서 작성 → API 코드 생성

Task A (기술 스펙)        Task B (API 코드)
└─ Executor #1           └─ Executor #2 (대기)
   ├─ "Analyzing..."
   ├─ "Drafting..."
   └─ "execution-complete" → Output: tech-spec.md
                             ↓
                          "Task A 완료. B 시작 가능"
                             ↓
                          Executor #2 (대기 해제)
                          └─ "task-start"
                             ├─ 읽음: tech-spec.md
                             └─ "Creating API code..."
```

**의존성 정의:**
```yaml
dependencies:
  task-b:
    requires: [task-a]
    input: "task-a의 결과물"
    condition: "task-a 100% 완료"

  task-c:
    requires: [task-a, task-b]
    input: ["task-a의 스펙", "task-b의 코드"]
    condition: "task-a AND task-b 모두 완료"

  task-d:
    requires: [task-c]
    input: "task-c의 통합 결과"
    condition: "task-c 완료 및 QA 검증 합격"
```

---

#### 패턴 5️⃣ Crisis Management (위기 관리 / 의사결정)

```
상황: 예상 밖의 이슈 발생 시 팀 전체 개입
예: 핵심 기술에 보안 이슈 발견

Executor: "보안 이슈 발견!"
│
Manager: "모든 Agent에 알림"
│
├─→ Planner: "범위/일정 재검토 필요?"
├─→ QA: "영향도 분석"
└─→ Executor: "대기"

QA: "분석 완료
    - 심각도: High (즉시 처리 필요)
    - 영향 범위: 전체 API (재작업 필요)
    - 예상 시간: +5일"

Planner: "의사결정
   옵션 1: 보안 패치 적용 + 일정 연장
   옵션 2: 기능 축소 + 현 일정 유지

   권고: 옵션 1 (보안 > 일정)"

Manager: "의사결정 기록"
│
Executor: "옵션 1로 재작업 시작"
│
Manager: "일정 변경: 기존 3주 → 3주 5일"
└─ 모든 다운스트림Task 일정 업데이트
```

---

### Agent 상호작용 신호 (Signal Protocol)

#### 신호 체계

```
Signal Format:
┌─ signal-name: [신호 이름]
├─ sender: [발신 Agent]
├─ receiver: [수신 Agent]
├─ status: [complete | pending | blocked | error]
├─ content: [전달 내용]
├─ attachment: [링크, 파일 경로]
├─ priority: [low | normal | high | urgent]
└─ timestamp: [시간]
```

#### 주요 신호 목록

```
[계획 단계]
├─ planning-start: 계획 수립 시작
├─ planning-complete: 계획 완료 (사용자 승인 대기)
└─ plan-approved: 사용자가 계획 승인

[실행 단계]
├─ execution-start: 실행 시작
├─ execution-progress: 진행 중 (체크인)
├─ execution-complete: 실행 완료
├─ execution-blocked: 진행 막힘
└─ execution-error: 실행 오류

[추적 단계]
├─ context-ready: 메모리 준비 완료
├─ context-update: 메모리 업데이트
├─ context-blocker-escalation: 막힘 사항 보고
└─ status-sync: 전체 상태 동기화

[검증 단계]
├─ review-start: 검증 시작
├─ review-complete: 검증 완료
├─ review-passed: 검증 합격
├─ review-failed: 검증 재요청
└─ audit-report: 상세 검수 보고서

[팀 조율]
├─ team-decision-request: 팀 의사결정 요청
├─ team-blocker-alert: 팀 전체 알림 (이슈)
├─ phase-transition: 다음 단계 전환
└─ project-complete: 프로젝트 완료
```

---

## Part 3: 실제 구현 가이드

### Step 1: Claude Code 스킬/Hook 설정

```javascript
// .claude/hooks/ai-team-orchestration.js

module.exports = {
  // 1. Agent 생성 & 역할 할당
  initializeTeam: async (projectConfig) => {
    const agents = {
      planner: createAgent('strategic-planner'),
      executor: createAgent('execution-specialist'),
      manager: createAgent('context-manager'),
      qa: createAgent('quality-inspector'),
    };

    return agents;
  },

  // 2. 신호 처리
  handleSignal: async (signal, sender, receiver) => {
    switch (signal.type) {
      case 'planning-complete':
        // 계획 완료 → Manager에게 전달
        return await agents.manager.receive(signal);

      case 'execution-complete':
        // 실행 완료 → Manager & QA에 전달
        await agents.manager.receive(signal);
        return await agents.qa.receive(signal);

      case 'review-complete':
        // 검증 완료 → Executor에게 피드백
        if (signal.passed) {
          return await agents.executor.markTaskComplete();
        } else {
          return await agents.executor.receive({
            type: 'feedback',
            issues: signal.issues,
          });
        }

      case 'execution-blocked':
        // 막힘 사항 → Manager → Planner
        await agents.manager.logBlocker(signal);
        return await agents.planner.receive(signal);
    }
  },

  // 3. 병렬 작업 관리
  executeParallel: async (tasks) => {
    const results = await Promise.all(
      tasks.map(task =>
        agents.executor.executeTask(task)
      )
    );

    await agents.manager.updateChecklist(results);
    return results;
  },

  // 4. 의존성 관리
  checkDependencies: async (taskId) => {
    const task = await getTask(taskId);
    const dependencies = task.requires || [];

    for (const depId of dependencies) {
      const dep = await getTask(depId);
      if (dep.status !== 'complete') {
        return false; // 아직 실행 불가
      }
    }

    return true; // 모든 의존성 충족
  },

  // 5. 팀 상태 동기화
  syncTeamStatus: async () => {
    const status = {
      planner: agents.planner.getStatus(),
      executor: agents.executor.getStatus(),
      manager: agents.manager.getStatus(),
      qa: agents.qa.getStatus(),
    };

    // Context Manager가 Team Interaction Log 업데이트
    await agents.manager.updateInteractionLog(status);

    return status;
  },
};
```

---

### Step 2: 각 Agent별 초기 명령어

**Agent-Planner (Strategic Planner):**
```
당신은 [프로젝트명]의 Strategic Planner입니다.

책임:
1. 사용자의 요구사항을 분석
2. 전체 프로젝트 계획서 작성
3. 단계별 로드맵 정의
4. 각 Agent의 역할 명시
5. 리스크 식별

산출물:
- project-plan.md (사용자 승인 필요)
- role-assignment.md

도구:
- 프로젝트 계획서 템플릿 읽기
- 계획이 완료되면 "planning-complete" 신호

주의:
- "지금부터 작업합니다"라고 하지 말기
- 계획만 세우기 (실행은 Executor가 함)
- 계획을 파일로 저장하고 사용자 승인 대기
```

**Agent-Executor (Execution Specialist):**
```
당신은 [프로젝트명]의 Execution Specialist입니다.

책임:
1. Planner의 계획서 읽기 & 이해
2. 단계별 작업 실행
3. 한 번에 1-2개 Task만 처리
4. 각 Task 완료 후 Manager에 보고
5. 문제 발생 시 Manager에 알림

도구:
- 프로젝트 계획서 읽기
- 실행 로그 작성
- "execution-start", "execution-complete" 신호

주의:
- Task를 시작하기 전에 Manager에 알림
- 완료 후에만 다음 Task 시작
- 문제가 생기면 즉시 Manager에 보고
- QA 피드백이 나올 때까지 기다리기
```

**Agent-Manager (Context Manager):**
```
당신은 [프로젝트명]의 Context Manager입니다.

책임:
1. 모든 Agent의 상태 실시간 추적
2. Context Notes 관리 (결정 사유, 참고 자료)
3. Todo Checklist 업데이트
4. Team Interaction Log 작성
5. 막히는 부분이 있으면 Planner에 알림

도구:
- 모든 Agent의 신호 수신 & 기록
- context-notes.md 업데이트
- todo-checklist.md 업데이트
- team-interaction-log.md 작성
- "context-update", "context-blocker-escalation" 신호

주의:
- 매번 신호를 받으면 로그에 기록
- 체크리스트를 항상 최신 상태로 유지
- 결정 사유와 변경 이력을 자세히 기록
```

**Agent-QA (Quality Inspector):**
```
당신은 [프로젝트명]의 Quality Inspector입니다.

책임:
1. Executor의 결과물 검증
2. 오류, 누락, 위반 사항 찾기
3. 구체적 검수 보고서 작성
4. 합격/재검증 판정

도구:
- audit-report.md 작성
- "review-start", "review-complete" 신호
- "review-passed" / "review-failed" 판정

검증 항목 (도메인별 조정):
□ 요구사항 충족 여부
□ 오류 & 버그
□ 보안 위험
□ 성능 최적화
□ 규정 준수
□ 일관성

보고서 형식:
1. 발견 이슈 (심각도, 설명)
2. 수정 권고 (어떻게, 우선순위)
3. 최종 판정 (합격/재검증)

주의:
- 결과물을 철저히 검토
- 문제점을 구체적으로 설명
- 단순히 "안 됨"이 아니라 "이렇게 고쳐야 함"이라고 지시
```

---

### Step 3: 메모리 파일 초기화

```bash
# 프로젝트 폴더 구조

project-name/
├── docs/
│   ├── 01_project_plan.md         (Planner가 작성)
│   ├── 02_context_notes.md        (Manager가 관리)
│   ├── 03_todo_checklist.md       (Manager가 관리)
│   └── 04_team_interaction_log.md (Manager가 작성)
│
├── results/
│   ├── phase-1/
│   ├── phase-2/
│   └── ...
│
└── audit/
    ├── phase-1-audit.md
    ├── phase-2-audit.md
    └── ...
```

---

## Best Practices & Tips

### 💡 Tip 1: 역할 분명하게 하기

```
❌ "AI들한테 협력해서 이걸 만들어"
   → 누가 뭘 하는지 불명확
   → 충돌 발생 가능
   → 기억도 흐릿함

✅ "Planner가 계획, Executor가 실행, Manager가 추적, QA가 검증"
   → 각 역할 명확
   → 신호 체계로 조율
   → 메모리 문서로 기록
```

### 💡 Tip 2: 신호 체계 준수

```
모든 Agent는 신호를 통해 소통합니다:

Executor → "execution-complete" + 결과물 링크
          ↓
Manager → "context-update" + 체크리스트 업데이트
          ↓
QA → "review-start" + 검증 시작
     ...
     "review-complete" + 검수 보고서

이렇게 하면:
✅ 언제 누가 뭘 했는지 명확
✅ 회귀 진행 추적 가능
✅ 문제 발생 시 원인 파악 쉬움
```

### 💡 Tip 3: 메모리 문서는 "실시간"으로

```
❌ "작업 끝난 후에 나중에 기록하자"
   → 기억 흐려짐
   → 누락 발생

✅ "매 단계마다 즉시 기록"
   - Task 시작 → 로그에 기록
   - Task 완료 → 체크리스트 ✅
   - 문제 발생 → 컨텍스트 노트에 기록
   - 피드백 받음 → 상호작용 로그 업데이트
```

### 💡 Tip 4: 병렬 작업 시 Manager 중요

```
병렬 작업 시:
- Executor #1, #2, #3이 동시 진행
- Manager가 모든 진행상황 실시간 추적
- 하나라도 막히면 즉시 감지
- 의존성 있으면 Manager가 조율

예:
Executor #1: "Task A 완료"
Manager: "Task A 완료, Task C 시작 가능 (Task B 대기 중)"
Executor #2: "Task B 완료"
Manager: "Task B 완료, Task C 시작" → Executor #3
```

### 💡 Tip 5: 위기 상황 대응

```
막힘 발생:
1. Executor → Manager: "execution-blocked" 신호
2. Manager → Planner: "context-blocker-escalation"
3. Planner → 의사결정 (일정 조정? 범위 축소? 대체안?)
4. Manager → 전체 Team: 새로운 계획 공유
5. Executor: 새로운 계획에 따라 재시작

이렇게 하면 위기 상황을 체계적으로 관리 가능
```

---

## Quick Start: 5단계로 시작하기

```
[ ] Step 1: 팀 구성
    - 4가지 역할 각 Agent 할당
    - 각 Agent에 초기 명령어 설정

[ ] Step 2: 메모리 문서 준비
    - project-plan.md 템플릿
    - context-notes.md 템플릿
    - todo-checklist.md 템플릿
    - team-interaction-log.md 템플릿

[ ] Step 3: 신호 체계 정의
    - 사용할 신호 목록 정의
    - 각 신호의 의미 명확화
    - 신호 처리 로직 구현

[ ] Step 4: 첫 프로젝트 시작
    - Planner: 계획 수립
    - Manager: 메모리 초기화
    - Executor: 작업 시작
    - QA: 검증 준비

[ ] Step 5: 모니터링 & 개선
    - 팀 상호작용 로그 검토
    - 병목 지점 식별
    - 프로세스 개선
```

---

## Expected Results

이 시스템을 구축한 후:

```
Before (시스템 없음):
- 품질: 50/100 (들쑥날쑥함)
- 신뢰도: 낮음 (매번 감시 필요)
- 효율성: 50% (반복 작업, 수정)
- 기억: 불가능 (매번 상기 필요)
- 협업: 어려움 (중복 작업, 충돌)

After (팀 오케스트레이션 시스템):
- 품질: 95/100 (일관되고 높음)
- 신뢰도: 높음 (자동 검증, QA)
- 효율성: 500%+ (병렬 작업, 자동화)
- 기억: 완벽함 (문서 기반 추적)
- 협업: 체계적 (신호, 로그, 조율)

✨ 총 프로젝트 완성도: 150% 향상
   (한 AI 사용 대비 3-5배 효율)
```

---

## 참고 자료

- [프로젝트 계획서 템플릿] → references/project-plan-template.md
- [역할 정의서 템플릿] → references/role-template.md
- [신호 프로토콜 상세] → references/signal-protocol.md
- [메모리 문서 관리] → references/memory-documents.md
- [병렬 작업 패턴] → references/parallel-execution.md
- [의존성 관리] → references/dependency-management.md
