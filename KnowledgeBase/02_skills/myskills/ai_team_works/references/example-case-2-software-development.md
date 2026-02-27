# 사례 2: 신규 기능 개발 (REST API + 인증 시스템)

## 📌 프로젝트 개요

**프로젝트명:** 사용자 권한 관리 API 개발
**기간:** 2026-03-01 ~ 2026-03-21 (3주)
**목표:** REST API 개발 + 단위테스트 100% + 보안 감시 통과
**팀:** Technical Architect(기획) / Backend Developer(실행) / Code Reviewer(매니저) / QA Tester(검사)

---

## 🎯 초기 요청 (개발자)

```
"사용자 권한 관리 시스템을 구축해야 합니다.

요구사항:
1. REST API 엔드포인트 5개 (생성, 읽기, 수정, 삭제, 리스트)
2. 역할 기반 접근 제어 (RBAC)
3. 단위테스트 100% 커버리지
4. OWASP 상위 10개 보안 취약점 검증
5. 성능 테스트 (동시 요청 1000개 처리)

일정: 3주
예상 복잡도: 중간 (기존 아키텍처 기반)

AI 팀으로 처리해 주세요."
```

---

## 👥 Agent 팀 구성

```yaml
Agent #1 - Technical Architect (기획가)
├─ 역할: 기술 아키텍처 설계
├─ 책임: API 스펙 작성, DB 스키마, 보안 전략 수립
├─ 산출물: 기술 명세서

Agent #2 - Backend Developer (실행가)
├─ 역할: 실제 코드 작성
├─ 책임: API 구현, 단위테스트 작성, 문서화
├─ 산출물: 소스 코드, 테스트 코드

Agent #3 - Code Reviewer (매니저)
├─ 역할: 코드 품질 추적
├─ 책임: 변경사항 기록, 진행상황 관리, 코드리뷰 조율
├─ 산출물: 코드리뷰 로그, 기술 진행상황

Agent #4 - QA Tester (검사관)
├─ 역할: 품질 보증
├─ 책임: 기능테스트, 보안테스트, 성능테스트
├─ 산출물: 테스트 보고서
```

---

## 📊 팀 상호작용 시뮬레이션

### [Day 1 - 10:00 AM] 기술 아키텍처 설계

**Technical Architect → 기술 명세서 작성**

```
# 사용자 권한 관리 API - 기술 명세서

## 🏗️ 아키텍처 개요

```
┌─────────────────────────────┐
│   REST API Layer            │ ← Backend Developer 구현
├─────────────────────────────┤
│   Business Logic            │
├─────────────────────────────┤
│   Data Access Layer (DAO)   │
├─────────────────────────────┤
│   Database (PostgreSQL)     │
└─────────────────────────────┘

보안 계층:
- JWT Authentication
- Role-Based Access Control (RBAC)
- Input Validation
- SQL Injection 방지
```

## 📋 API 엔드포인트 명세

### Endpoint 1: 역할 생성 (POST /api/roles)
```
Request:
{
  "name": "admin",
  "description": "Administrator role",
  "permissions": ["user:create", "user:read", "user:update", "user:delete"]
}

Response (201 Created):
{
  "id": "role_123",
  "name": "admin",
  "created_at": "2026-03-01T10:00:00Z"
}

테스트 케이스:
- 정상 케이스: 역할 생성 성공
- 중복 이름: 400 Bad Request
- 권한 부족: 403 Forbidden
- 입력값 검증: 정규표현식으로 이름 검증
```

### Endpoint 2: 역할 조회 (GET /api/roles/{id})
```
Request: /api/roles/role_123

Response (200 OK):
{
  "id": "role_123",
  "name": "admin",
  "description": "Administrator role",
  "permissions": [...],
  "created_at": "2026-03-01T10:00:00Z",
  "updated_at": "2026-03-01T10:00:00Z"
}

테스트 케이스:
- 존재하는 역할: 200 OK
- 존재하지 않는 역할: 404 Not Found
- 접근 권한 없음: 403 Forbidden
```

### Endpoint 3: 역할 수정 (PUT /api/roles/{id})
### Endpoint 4: 역할 삭제 (DELETE /api/roles/{id})
### Endpoint 5: 역할 리스트 (GET /api/roles?limit=10&offset=0)

## 🗄️ 데이터베이스 스키마

```sql
-- Roles 테이블
CREATE TABLE roles (
  id UUID PRIMARY KEY,
  name VARCHAR(100) UNIQUE NOT NULL,
  description TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Permissions 테이블
CREATE TABLE permissions (
  id UUID PRIMARY KEY,
  role_id UUID REFERENCES roles(id),
  permission VARCHAR(100) NOT NULL,
  UNIQUE(role_id, permission)
);

-- 인덱스
CREATE INDEX idx_roles_name ON roles(name);
CREATE INDEX idx_permissions_role_id ON permissions(role_id);
```

## 🔐 보안 전략

```
✅ 인증:
- JWT 토큰 기반 인증
- 토큰 만료시간: 1시간
- Refresh Token: 7일

✅ 권한 (RBAC):
- 모든 엔드포인트에 권한 검증
- 역할별 권한 매핑

✅ 입력 검증:
- 모든 입력값 정규표현식 검증
- SQL Injection 방지: Parameterized Query 사용
- XSS 방지: 입력값 sanitization

✅ 에러 처리:
- 민감한 정보 로그에 기록 금지
- 일반적 에러 메시지 반환
```

## 📊 예상 일정 (3주)

### Phase 1: 설계 & 환경 구축 (3일)
- Task 1.1: API 스펙 최종화 (1일) ← 현재 진행 중
- Task 1.2: DB 스키마 설계 (1일)
- Task 1.3: 테스트 전략 수립 (1일)
- Task 1.4: 개발 환경 구축 (1일)

### Phase 2: API 구현 (7일)
- Task 2.1: Endpoint 1-3 구현 (3일)
- Task 2.2: Endpoint 4-5 구현 (2일)
- Task 2.3: 에러 처리 & 로깅 (2일)

### Phase 3: 테스트 (5일)
- Task 3.1: 단위테스트 (2일)
- Task 3.2: 통합테스트 (1.5일)
- Task 3.3: 보안테스트 (1.5일)

### Phase 4: 성능 & 배포 (5일)
- Task 4.1: 성능테스트 & 최적화 (2일)
- Task 4.2: 코드 정리 & 문서화 (2일)
- Task 4.3: 프로덕션 배포 준비 (1일)

## 🎯 정량적 목표

| 항목 | 목표 | 측정 방법 |
|------|------|---------|
| 테스트 커버리지 | 100% | Coverage Report |
| 평균 응답시간 | < 100ms | Load Test |
| 동시 요청 처리 | 1000 req/sec | JMeter |
| 버그 (심각도 High 이상) | 0개 | QA 검증 |
| 보안 취약점 (OWASP) | 0개 | Penetration Test |
```

**신호:** `planning-complete`

---

### [Day 1 - 11:30 AM] Code Reviewer: 메모리 초기화

```
신호: context-ready

생성된 문서:
- 01_tech_specification.md ← Architect 작성
- 02_implementation_notes.md ← 현재 설계 단계
- 03_development_checklist.md ← 진행상황 추적용
- 04_code_review_log.md ← 코드 리뷰 기록
```

---

### [Day 2-4] Phase 1: 환경 구축 & 설계

**Backend Developer → 개발 환경 구축**

```
신호: execution-start
기간: Day 2-4

[Day 2]
구축 항목:
- IDE: IntelliJ IDEA 설정
- Framework: Spring Boot 3.0 프로젝트 생성
- 데이터베이스: PostgreSQL Docker 컨테이너
- 테스트: JUnit 5, Mockito 설정
- 빌드: Gradle 설정

신호: execution-complete (환경 구축)
상태: ✅ 개발 준비 완료

[Day 3-4]
- DB 마이그레이션 스크립트 작성 (Flyway)
- Spring Security 초기 설정
- JWT 토큰 생성/검증 유틸 구현
- API Base Controller 작성

신호: execution-complete (기초 코드)
다음: Endpoint 구현 시작
```

---

### [Day 5-11] Phase 2: API 구현

**Backend Developer → Endpoint 1-5 구현 (병렬 + 순차)**

```
신호: execution-start
기간: Day 5-11

[Day 5-7] Task 2.1: Endpoint 1-3 구현

실행 계획:
- Day 5: POST /roles (역할 생성)
- Day 6: GET /roles/{id} (역할 조회)
- Day 6: PUT /roles/{id} (역할 수정)
- Day 7: 위 3개 엔드포인트 테스트 & 검증

코드 구조:
```
src/
├─ controller/
│  └─ RoleController.java (위 3개 엔드포인트)
├─ service/
│  └─ RoleService.java (비즈니스 로직)
├─ repository/
│  └─ RoleRepository.java (DB 접근)
└─ model/
   └─ Role.java (데이터 모델)
```

[Day 5 오후]
신호: execution-progress
상태: "POST /roles 구현 완료. 단위테스트 시작"

```java
// RoleController.java
@PostMapping
public ResponseEntity<RoleResponse> createRole(
    @Valid @RequestBody CreateRoleRequest request,
    @AuthenticationPrincipal UserDetails user) {

  // 권한 검증
  validatePermission(user, "role:create");

  // 역할 생성
  Role role = roleService.create(request);

  return ResponseEntity.status(201).body(toResponse(role));
}
```

[Day 6]
신호: execution-progress
상태: "GET & PUT 구현 완료"

결과:
- Task 2.1 구현 코드: 350줄
- 단위테스트: 45개 (커버리지 95%)

[Day 7]
신호: execution-complete (Task 2.1)

Code Reviewer에게 전달:
신호: code-review-request
파일: RoleController.java, RoleService.java, RoleRepository.java
상태: 리뷰 대기

---

[Day 8-9] Task 2.2: Endpoint 4-5 구현

[Day 8]
- DELETE /roles/{id} (역할 삭제)
- GET /roles (역할 리스트, 페이징 포함)

신호: execution-progress
상태: 80% 완료

[Day 9]
신호: execution-complete (Task 2.2)

[Day 10-11] Task 2.3: 에러 처리 & 로깅

```java
// GlobalExceptionHandler.java
@ControllerAdvice
public class GlobalExceptionHandler {

  @ExceptionHandler(AccessDeniedException.class)
  public ResponseEntity<ErrorResponse> handleAccessDenied(
      AccessDeniedException e) {
    return ResponseEntity.status(403).body(
      new ErrorResponse("Forbidden", "접근 권한이 없습니다")
    );
  }

  @ExceptionHandler(RoleNotFoundException.class)
  public ResponseEntity<ErrorResponse> handleNotFound(
      RoleNotFoundException e) {
    return ResponseEntity.status(404).body(
      new ErrorResponse("Not Found", "역할을 찾을 수 없습니다")
    );
  }
}
```

신호: execution-complete (Task 2.3)
전체 구현 라인: 1,200줄

다음: Code Review
```

---

### [Day 8-12] 병렬: Code Review 진행

**Code Reviewer (매니저) → 코드 리뷰**

```
신호: code-review-start
대상: Task 2.1, 2.2, 2.3
검증 항목:
- ✅ 아키텍처 일관성
- ✅ 네이밍 컨벤션
- ✅ 에러 처리
- ✅ 성능 (N+1 쿼리)
- ✅ 보안 (SQL Injection, XSS)
- ✅ 테스트 커버리지

[Day 8-9] Task 2.1 리뷰

Reviewer의 피드백:

Issue #1 (CRITICAL):
```
함수: createRole()
문제: 입력값 검증 부재
  @Valid가 있지만 Role 이름의 길이 제한 없음
  → Role 이름 100자 이상도 수용 (DB 컬럼 100)

권고:
@Size(min=1, max=100)
private String name;
```

Issue #2 (MEDIUM):
```
함수: getRoles()
문제: N+1 쿼리 이슈
  각 역할마다 권한 조회 쿼리 발생

권고:
@Query(쿼리 = "SELECT r FROM Role r LEFT JOIN FETCH r.permissions")
List<Role> findAllWithPermissions();
```

Issue #3 (LOW):
```
네이밍: 변수명 표준화
  private String desc → private String description
  private Date createdAt → private LocalDateTime createdAt
```

신호: review-feedback
피드백 수:
- CRITICAL: 1개 (반드시 수정)
- MEDIUM: 2개 (권장)
- LOW: 3개

Developer는 피드백을 받고 수정

[Day 9 오후]
Developer: "모든 CRITICAL 이슈 수정 완료"
신호: code-update-complete

Reviewer: 재리뷰 → ✅ 합격

[Day 10-11] Task 2.2 & 2.3 리뷰 (동일 방식)

최종 결과:
- Task 2.1: ✅ 합격 (1회 피드백)
- Task 2.2: ✅ 합격 (2회 피드백)
- Task 2.3: ✅ 합격 (1회 피드백)

신호: code-review-complete
판정: 모든 코드 품질 기준 충족
```

---

### [Day 12-16] Phase 3 & 4: 테스트 & 배포 준비

**QA Tester → 통합 테스트 & 보안 테스트**

```
신호: testing-start
기간: Day 12-16

[Day 12-13] 단위테스트 검증

현황:
- 구현된 단위테스트: 120개
- 커버리지: 98% (거의 100%)

테스트 결과:
- 성공: 120/120 (100%) ✅
- 실패: 0

[Day 14] 통합테스트

테스트 시나리오:
1. 역할 생성 → 조회 → 수정 → 삭제
2. 권한 검증: 일반 사용자는 DELETE 실패
3. 중복 역할명 생성 시도 → 400 에러
4. 페이징: limit=5, offset=10 → 정확한 결과

결과:
- 성공: 15/15 시나리오 통과 ✅

[Day 15] 보안테스트

OWASP 상위 10 검증:
✅ SQL Injection: Parameterized Query 사용 → 안전
✅ XSS: 입력값 sanitize → 안전
✅ CSRF: CSRF Token 사용 → 안전
✅ 인증/인가: JWT + RBAC → 안전
✅ 민감정보 노출: 로그에서 제외 → 안전
... (10개 전부 통과)

보안 등급: A+ (모든 취약점 제거)

[Day 15-16] 성능테스트

JMeter 부하테스트:
- 동시 사용자: 100 → 응답시간 평균 45ms ✅
- 동시 사용자: 500 → 응답시간 평균 78ms ✅
- 동시 사용자: 1000 → 응답시간 평균 95ms ✅
- 처리량: 1050 req/sec (목표: 1000 req/sec) ✅✅

모든 성능 목표 달성

신호: testing-complete
판정: ✅ 모든 테스트 통과 (0개 High 버그)
```

---

### [Day 17-18] 완료 & 배포

**Backend Developer → 최종 정리**

```
신호: finalization-complete

작업 항목:
- ✅ 코드 정리 & 포맷팅
- ✅ API 문서화 (Swagger/OpenAPI)
- ✅ 배포 가이드 작성
- ✅ 롤백 계획 수립
- ✅ 프로덕션 배포 준비

산출물:
- 소스 코드: GitHub 저장소
- API 문서: Swagger UI
- 테스트 결과: JaCoCo Coverage Report (98%)
- 성능 보고서: JMeter 결과 (1050 req/sec)
```

---

## 📊 최종 결과 보고서

### 프로젝트 완료 요약

```
프로젝트명: 사용자 권한 관리 API 개발
기간: 2026-03-01 ~ 2026-03-18 (18일, 예정: 21일)
팀: 4명 (Architect, Developer, Reviewer, QA Tester)

## ✅ 목표 달성

| 목표 | 목표값 | 달성값 | 달성율 |
|------|--------|--------|--------|
| API 엔드포인트 | 5개 | 5개 | 100% ✅ |
| 테스트 커버리지 | 100% | 98% | 98% ✅ |
| 응답시간 | < 100ms | 95ms | 95% ✅ |
| 동시요청 처리 | 1000 req/s | 1050 req/s | 105% ✅✅ |
| 보안취약점 | 0개 | 0개 | 100% ✅ |
| High 버그 | 0개 | 0개 | 100% ✅ |

**전체 달성율: 101% (목표 초과)**

## 📈 코드 메트릭

| 메트릭 | 값 |
|--------|-----|
| 총 코드 라인 | 1,200 줄 |
| 테스트 코드 | 400 줄 |
| 순환 복잡도 | 2.3 (낮음) |
| 테스트 커버리지 | 98% |
| 코드 리뷰 피드백 수 | 6개 (모두 반영) |

## 🎓 팀 성과

| Agent | 역할 | 평가 |
|-------|------|------|
| Architect | 스펙 작성 | ⭐⭐⭐⭐⭐ |
| Developer | 구현 | ⭐⭐⭐⭐⭐ |
| Code Reviewer | 품질 관리 | ⭐⭐⭐⭐⭐ |
| QA Tester | 검증 | ⭐⭐⭐⭐⭐ |

## ⏰ 일정 효율성

```
계획: 21일 (3주)
실제: 18일 (2.5주)
절감: 3일 (14%)

Phase별:
- Phase 1 (설계): 3일 (예정: 3일) ✅
- Phase 2 (구현): 7일 (예정: 7일) ✅
- Phase 3 (테스트): 5일 (예정: 5일) ✅
- Phase 4 (완료): 3일 (예정: 6일) ✅✅ (3일 단축)
```

## 💡 핵심 성공 요인

1. **명확한 스펙**: Architect가 상세한 API 명세를 처음부터 정의
2. **지속적 코드리뷰**: Developer와 Reviewer의 실시간 피드백 루프
3. **초기 테스트**: 개발과 동시에 단위테스트 (TDD 방식)
4. **자동 검증**: 모든 코드가 CI/CD 파이프라인 통과

## 📋 최종 체크리스트

```
✅ API 5개 엔드포인트 완성
✅ 단위테스트 120개 (98% 커버리지)
✅ 통합테스트 15개 시나리오 (100% 통과)
✅ 보안테스트 10개 항목 (OWASP A+)
✅ 성능테스트 (1050 req/sec)
✅ 코드리뷰 완료 (0개 미해결 이슈)
✅ 배포 준비 완료
✅ 문서화 완료

🎉 프로젝트 완료: SUCCESS
```

## 🚀 배포 후 모니터링 권고

- 프로덕션 성능 모니터링 (목표: 평균 100ms 이하)
- 에러 로그 모니터링 (Critical 로그 없음)
- 월간 보안 패치 체크
- 다음 분기 기능 추가 계획 (권한 임시 위임, 감사 로그 등)
```

---

## 핵심 결론

이 프로젝트에서 **AI 팀 오케스트레이션 시스템**을 적용한 결과:

### 정량적 효과
- 📅 **일정 단축**: 21일 → 18일 (3일/14% 단축)
- 🐛 **버그 제거**: High 심각도 버그 0개 (초기 6개 → 리뷰로 모두 제거)
- 📊 **성능 초과**: 1000 req/s → 1050 req/s (5% 초과)
- 📈 **커버리지**: 목표 100% → 달성 98% (거의 100%)

### 정성적 효과
- **아키텍처 일관성**: Architect의 스펙이 명확해서 Developer의 해석 오류 없음
- **코드 품질**: Code Reviewer의 실시간 피드백으로 처음부터 높은 수준 유지
- **신뢰도**: 완벽한 테스트 검증으로 프로덕션 배포 확신
- **문서화**: 모든 결정이 기록되어 유지보수 용이

---

**결론: 개발 팀도 명확한 역할 분담과 체계적 검증으로 3주 일정을 14% 단축하고 고품질 소프트웨어를 완성했습니다.**
