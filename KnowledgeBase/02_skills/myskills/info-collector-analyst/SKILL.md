---
name: info-collector-analyst
description: "프로젝트 규모(Level 1~4)를 사전 판정하고, 다양한 소스에서 정보를 수집하여 RAG 및 멀티 에이전트 아키텍처 설계를 위한 심층 분석 리포트를 구조화합니다."
version: 1.0.0
created: 2026-02-21
platforms: [claude-code]
category: analysis
tags: [analysis, rag, multi-agent, scale-assessment, scaffolding]
metadata:
  model: opus
---

# info-collector-analyst

## Purpose

프로젝트 시작 전 규모를 체계적으로 판정하고, 다양한 소스(로컬 문서, 웹, 사용자 입력)에서 정보를 수집하여 하위 설계 에이전트(Architect, Builder)에게 전달할 수 있는 구조화된 분석 리포트를 생성합니다. LLM 추론을 극대화하여 표면적 요구사항 이면의 잠재적 문제점까지 도출합니다.

## When to Use This Skill

- 새 프로젝트를 시작할 때 규모와 아키텍처 방향을 결정해야 할 때
- 기획 문서, PDF, PPT 등에서 요구사항을 체계적으로 수집/분석해야 할 때
- RAG 파이프라인이나 멀티 에이전트 시스템 설계를 위한 사전 분석이 필요할 때
- 프로젝트의 기능/비기능 요구사항을 구조화된 형태로 정리해야 할 때

## Do Not Use This Skill

- 이미 아키텍처가 결정된 프로젝트에서 단순 코딩 작업을 할 때
- 소규모 버그 수정이나 단일 기능 추가 작업일 때
- 프로젝트 컨텍스트 없이 일반적인 기술 질문을 할 때

## Instructions

### Phase 0: 프로젝트 규모 사전 판정 (Scale Assessment)

이 단계는 **필수 진입 단계**입니다. `AskUserQuestion` 도구를 사용하여 다음 5가지 항목에 대해 사용자에게 질문하고 점수를 합산합니다.

#### 질문 항목

| # | 항목 | 1점 | 3점 | 5점 | 7점 | 10점 |
|---|------|-----|-----|-----|-----|------|
| 1 | **예상 사용자 수 및 트래픽** | 100명 이하 | 1,000명 | 1만명 | 10만명 이상 | 100만명 이상 |
| 2 | **개발 팀 규모** | 1-2명 | 3-5명 | 6-15명 | 16-50명 | 50명 이상 |
| 3 | **시스템 복잡도** | 단순 CRUD | 중간 비즈니스 로직 | 복잡한 워크플로우 | 실시간 처리 | AI 및 분산 시스템 |
| 4 | **확장성 요구사항** | 확장 불필요 | 수직 확장 | 수평 확장 | 마이크로서비스 고려 | 글로벌 분산 |
| 5 | **개발 기간 및 예산** | 1-2주 | 1-3개월 | 3-6개월 | 6-12개월 | 12개월 이상 |

#### 판정 기준

| 총점 | Level | 분류 | 권장 아키텍처 |
|------|-------|------|--------------|
| **5-15점** | Level 1 | Small | Monolithic, Simple SDD + TDD |
| **16-30점** | Level 2 | Medium | Layered, Standard SDD + TDD + DDD(Light) |
| **31-45점** | Level 3 | Large | Hexagonal, Full SDD + TDD + DDD |
| **46-50점** | Level 4 | Enterprise | Microservices, Event-Driven + CQRS |

### Phase 1: 다중 소스 정보 수집 (Information Gathering)

Phase 0에서 결정된 Level에 맞춰 정보를 수집합니다.

1. **로컬 문서 탐색**: `Read`, `Glob` 도구를 활용하여 프로젝트 디렉토리 내 기획 문서, PDF, PPT 등을 탐색합니다.
2. **웹 리서치**: `WebSearch`, `WebFetch` 도구를 활용하여 관련 기술 스택, 유사 시스템 사례를 조사합니다.
3. **사용자 질의**: `AskUserQuestion`으로 Phase 0에서 결정된 Level에 맞는 추가 인프라/보안 요구사항을 확인합니다.

### Phase 2: 심층 추론 및 컨텍스트 증류 (Deep Inference & Distillation)

수집된 데이터를 바탕으로 심층 분석을 수행합니다.

1. **Sequential Thinking**: 표면적 요구사항 이면에 있는 잠재적 문제점을 분석합니다.
2. **GAP 분석**: 현재 상태와 목표 상태 사이의 차이를 식별합니다.
3. **RAG 구조화**: 방대한 자료를 벡터 DB에 임베딩하기 적합하도록 논리적 청크(Chunk) 단위로 구조화합니다.

### Phase 3: 구조화된 분석 결과 도출 (Structured Output)

모든 출력은 **한국어**로 제공하며, 실무에서 즉시 활용 가능한 마크다운 표와 체크리스트 형태로 출력합니다.

#### 분석 리포트 필수 포함 항목

1. **프로젝트 규모 및 아키텍처 방향**
   - Phase 0에서 도출된 총점, Level, 권장 아키텍처
   - 선택 근거 및 대안 비교

2. **도메인 및 시스템 개요**
   - 분야, 사용자 유형, 주요 보안 사항
   - 핵심 도메인 용어 정의

3. **핵심 기능 및 비기능 정의**
   - 판정된 Level에 부합하는 수준의 기능/비기능 명세
   - 우선순위 매트릭스 (Must/Should/Could/Won't)

4. **UI/UX 화면 영역 정의**
   - GNB, LNB, 주요 컴포넌트 목록
   - 화면 간 네비게이션 플로우

## Output Format

### 리포트 형식 규칙

- 비교 항목, 스펙 등은 **반드시 표(Table)로 정리**하며 헤더는 굵게 처리합니다.
- 각 섹션 사이에는 `---` 구분선을 삽입합니다.
- 에이전트 간 소통을 위해 요약본(증류된 컨텍스트)을 결과물 하단에 JSON 형태로 덧붙입니다.

### 증류된 컨텍스트 JSON 예시

```json
{
  "projectScale": {
    "totalScore": 35,
    "level": 3,
    "classification": "Large",
    "recommendedArchitecture": "Hexagonal"
  },
  "domain": {
    "field": "금융 감사 시스템",
    "userTypes": ["감사관", "관리자", "시스템 운영자"],
    "securityLevel": "High"
  },
  "techStack": {
    "frontend": "React + TypeScript",
    "backend": "Node.js / NestJS",
    "database": "PostgreSQL",
    "infra": "Docker + K8s"
  },
  "keyFeatures": ["실시간 이상 탐지", "감사 보고서 생성", "자금 흐름 분석"],
  "nonFunctional": {
    "availability": "99.9%",
    "responseTime": "< 2s",
    "concurrentUsers": 10000
  }
}
```

## Self-Correction Checklist

분석 완료 후 다음 항목을 자가 검증합니다.

- [ ] Phase 0의 5가지 질문을 통해 총점과 Level을 명확히 도출했는가?
- [ ] 제안된 설계 방향이 판정된 프로젝트 Level과 논리적으로 일치하는가?
- [ ] 요구사항 분석이 하위 설계 에이전트(Architect, Builder)에게 전달할 수 있을 만큼 구조화되었는가?
- [ ] 출력 포맷이 표, 체크리스트, JSON 증류 컨텍스트를 모두 포함하는가?

## Safety

- 사용자로부터 수집된 민감 정보(API 키, 비밀번호 등)는 리포트에 포함하지 않습니다.
- 판정 결과에 대해 과도한 확신을 표현하지 않으며, 항상 대안을 함께 제시합니다.
- 실제 인프라 변경이나 배포 작업은 수행하지 않으며, 분석과 권고만 제공합니다.

## Example Interactions

- "새 프로젝트를 시작하려고 하는데 규모 판정부터 해줘"
- "이 기획서를 분석해서 아키텍처 방향을 잡아줘"
- "프로젝트 요구사항을 정리해서 개발팀에 전달할 리포트를 만들어줘"
- "RAG 시스템 설계를 위한 사전 분석을 해줘"
- "우리 프로젝트가 마이크로서비스가 필요한 규모인지 판단해줘"
