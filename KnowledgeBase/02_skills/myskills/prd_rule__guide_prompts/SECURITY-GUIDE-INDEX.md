# PRD 규칙 & 가이드 - 보안 완벽 가이드 (종합)

## 📋 개요

PRD(Product Requirement Document) 프로세스의 **모든 단계**에서 보안, 웹 접근성, 시큐어 코딩을 고려한 종합 가이드입니다.

각 단계별로 다음을 포함합니다:
- 🔒 **웹 취약점 방지** (OWASP Top 10)
- 🌐 **웹 접근성** (WCAG 2.1)
- 🛡️ **시큐어 코딩** (Secure Coding)
- 🔧 **기술 스택 보안**

---

## 📁 폴더 구조

```
prd_rule__guide_prompts/
├── 01_analysis/
│   ├── README.md (기존)
│   ├── patterns.md (기존)
│   └── security-guide.md ← NEW
│       ├─ OWASP Top 10 분석
│       ├─ WCAG 2.1 분석
│       ├─ 기술 스택 보안 검증
│       └─ 보안 분석 결과 형식
│
├── 02_design/
│   ├── README.md (기존)
│   ├── patterns.md (기존)
│   └── security-guide.md ← NEW
│       ├─ 인증/권한 아키텍처
│       ├─ 데이터 보안 아키텍처
│       ├─ 입력값 검증 & 출력 인코딩
│       ├─ HTTPS/TLS 설계
│       └─ API 보안 설계
│
├── 03_development/
│   ├── README.md (기존)
│   ├── patterns.md (기존)
│   └── security-guide.md ← NEW
│       ├─ 시큐어 코딩 기초
│       ├─ 입력값 검증
│       ├─ XSS 방지
│       ├─ CSRF 방지
│       ├─ 인증 & 권한 구현
│       ├─ 데이터 보호
│       ├─ 파일 업로드 보안
│       └─ 로깅 & 모니터링
│
├── 04_testing/
│   ├── README.md (기존)
│   ├── patterns.md (기존)
│   └── security-guide.md ← NEW
│       ├─ 인증 테스트
│       ├─ 권한 제어 테스트
│       ├─ SQL Injection 테스트
│       ├─ XSS 테스트
│       ├─ CSRF 테스트
│       ├─ 파일 업로드 테스트
│       ├─ 보안 헤더 검증
│       ├─ API 응답 보안 테스트
│       ├─ 의존성 보안 테스트
│       └─ DoS 방지 테스트
│
├── 05_review/
│   ├── README.md (기존)
│   └── security-guide.md ← NEW
│       ├─ 입력값 처리 리뷰
│       ├─ XSS 방지 리뷰
│       ├─ 인증/권한 리뷰
│       ├─ 민감정보 리뷰
│       ├─ 보안 헤더 리뷰
│       ├─ 웹 접근성 리뷰
│       ├─ 의존성 보안 리뷰
│       └─ 보안 리뷰 기록 방식
│
└── SECURITY-GUIDE-INDEX.md ← 이 파일
```

---

## 🎯 각 단계별 보안 포인트

### 1️⃣ 분석 단계 (`01_analysis/security-guide.md`)

**목표**: 현재 프로젝트의 보안 현황 파악

| 영역 | 주요 내용 | 검증 도구 |
|------|---------|---------|
| **OWASP Top 10** | SQL Injection, XSS, CSRF, 인증/권한, 보안 설정, 민감정보 노출, 접근 제어, 파일 업로드, 컴포넌트, 로깅 | - |
| **WCAG 2.1** | 이미지 alt, 색상 대비, 키보드 네비게이션, 포커스, 플래시, 언어/텍스트, 예측 가능성, 오류 방지, 마크업 | axe DevTools, Lighthouse, WAVE |
| **기술 스택** | npm audit, 오래된 의존성, 라이선스, 환경 변수, 소스맵, 빌드 설정 | npm audit, npm outdated |

**체크리스트**: 40개 항목

**산출물**: 보안 분석 결과 보고서

---

### 2️⃣ 설계 단계 (`02_design/security-guide.md`)

**목표**: 보안을 고려한 아키텍처 설계

| 영역 | 주요 내용 |
|------|---------|
| **인증/권한** | 세션/JWT/OAuth 선택, RBAC 설계, 토큰 관리 |
| **데이터 보안** | 데이터 분류, 암호화 전략, 키 관리, Row-Level Security |
| **입력/출력** | 입력값 검증 계층, 화이트리스트 기반 검증, 출력 인코딩 |
| **통신 보안** | HTTPS/TLS 1.2+, HSTS, CORS 정책 |
| **API 보안** | Rate Limiting, 타임아웃, 버전 관리 |

**체크리스트**: 35개 항목

**산출물**: 보안 아키텍처 설계 문서

---

### 3️⃣ 개발 단계 (`03_development/security-guide.md`)

**목표**: 실제 코드 작성 시 보안 취약점 방지

| 영역 | 주요 내용 |
|------|---------|
| **시큐어 코딩** | 입력값 검증, Parameterized Query, XSS 방지, CSRF 방지 |
| **인증 구현** | 비밀번호 해시 (bcrypt/argon2), JWT 토큰 관리 |
| **권한 구현** | RBAC, 리소스 소유권 검증 |
| **데이터 보호** | 민감정보 제외, 데이터 암호화 |
| **파일 업로드** | 파일 타입/크기 검증, 파일명 변경, 메모리 기반 처리 |
| **로깅** | 민감정보 제외, 실패 시도 기록, 관리자 작업 기록 |

**체크리스트**: 45개 항목

**산출물**: 안전한 소스 코드

---

### 4️⃣ 테스트 단계 (`04_testing/security-guide.md`)

**목표**: 보안 테스트를 통한 검증

| 테스트 유형 | 주요 내용 |
|-----------|---------|
| **기능 테스트** | 인증, 권한, 입력값 검증, XSS, CSRF |
| **API 테스트** | 응답 보안, 민감정보 제외, 보안 헤더 |
| **성능 테스트** | Rate Limiting, 타임아웃, DoS 방지 |
| **의존성 테스트** | npm audit, 취약점 심각도 |

**테스트 도구**: Jest + Supertest, npm audit

**체크리스트**: 50개 항목

**산출물**: 보안 테스트 결과 보고서

---

### 5️⃣ 리뷰 단계 (`05_review/security-guide.md`)

**목표**: 코드 리뷰를 통한 최종 보안 검증

| 리뷰 영역 | 체크 항목 |
|----------|---------|
| **입력값** | SQL Injection 예방, XSS 예방, 입력값 검증 |
| **출력값** | 민감정보 제외, 에러 메시지 보안 |
| **인증/권한** | 토큰 검증, 권한 검증, 리소스 소유권 |
| **보안 헤더** | CSP, X-Frame-Options, HSTS, 쿠키 플래그 |
| **접근성** | alt 텍스트, 색상 대비, 키보드 네비게이션 |

**리뷰 기록**: PR 코멘트 형식으로 문서화

**체크리스트**: 40개 항목

---

## 🔒 3가지 보안 영역 통합 가이드

### A. OWASP Top 10 (웹 취약점 방지)

```
단계별 대응:

분석   → OWASP Top 10 항목별 확인
설계   → 아키텍처 수준의 대응책 설계
개발   → 코드 수준의 방지 (시큐어 코딩)
테스트 → 각 취약점 테스트 케이스 작성
리뷰   → 코드 리뷰 체크리스트 확인

예: SQL Injection
分析: 직접 SQL 조합 부분 찾기
設計: Parameterized Query 전략 수립
開発: ORM/Prepared Statement 구현
テスト: SQL Injection 테스트 케이스
レビュー: Parameterized Query 사용 확인
```

### B. WCAG 2.1 (웹 접근성)

```
단계별 대응:

분석   → 접근성 준수 현황 파악 (axe DevTools)
설계   → 접근성 요구사항 정의
개발   → ARIA 속성, 의미 있는 마크업 적용
테스트 → 스크린 리더, 키보드 네비게이션 테스트
리뷰   → WCAG 2.1 기준 코드 리뷰

예: 색상 대비
分析: 현재 대비율 측정 (4.5:1 이상 필요)
設計: 색상 시스템 설계 (충분한 대비)
開発: CSS 변수로 색상 적용
テスト: WebAIM Contrast Checker 검증
レビュー: 대비율 확인
```

### C. 시큐어 코딩 (소스코드 보안)

```
단계별 대응:

분석   → 보안 코딩 규칙 현황 파악
設計   → 보안 패턴 결정 (bcrypt vs argon2, 등)
開発   → 안전한 코드 작성
テスト: 보안 테스트 (unit, integration)
レビュー: 코드 리뷰 체크리스트

예: 비밀번호 해시
分析: 현재 암호화 방식 확인
設計: bcrypt/argon2 선택
開発: bcrypt.hash() 구현
テスト: 비밀번호 검증 테스트
レビュー: bcrypt 사용 확인
```

---

## 💡 실제 사용 시나리오

### 시나리오 1: 새 API 엔드포인트 개발

```
Step 1: 분석 (01_analysis)
- 이 API에 어떤 보안 취약점이 가능한가?
- SQL Injection, XSS, CSRF, 인증 우회 가능성?
→ security-guide.md의 OWASP Top 10 섹션 참고

Step 2: 설계 (02_design)
- 이 API에 필요한 인증/권한은?
- 입력값 검증 규칙은?
- 응답에서 제외해야 할 데이터는?
→ security-guide.md의 아키텍처 설계 섹션 참고

Step 3: 개발 (03_development)
- Parameterized Query 사용했는가?
- 입력값 검증 구현했는가?
- 민감정보 응답에서 제외했는가?
→ security-guide.md의 시큐어 코딩 섹션 참고

Step 4: 테스트 (04_testing)
- SQL Injection 테스트했는가?
- 권한 검증 테스트했는가?
- API 응답 보안 검증했는가?
→ security-guide.md의 보안 테스트 섹션 참고

Step 5: 리뷰 (05_review)
- PR 리뷰: 입력값 검증 체크?
- PR 리뷰: 인증/권한 체크?
- PR 리뷰: 민감정보 체크?
→ security-guide.md의 코드 리뷰 체크리스트 참고
```

### 시나리오 2: 접근성 개선

```
Step 1: 분석
- 현재 WCAG 2.1 준수 현황?
- axe DevTools 실행

Step 2: 설계
- 색상 시스템 재설계 (대비 4.5:1 이상)
- ARIA 속성 추가 계획

Step 3: 개발
- alt 텍스트 추가
- ARIA 속성 구현
- 시맨틱 마크업 적용

Step 4: 테스트
- 스크린 리더 테스트
- 키보드 네비게이션 테스트
- 색상 대비 검증

Step 5: 리뷰
- WCAG 2.1 기준 확인
- 접근성 체크리스트 통과
```

---

## 📊 체크리스트 요약

| 단계 | 파일 | 항목 수 | 초점 |
|------|------|--------|------|
| 분석 | 01_analysis/security-guide.md | 40 | 현황 파악 |
| 설계 | 02_design/security-guide.md | 35 | 아키텍처 |
| 개발 | 03_development/security-guide.md | 45 | 코드 |
| 테스트 | 04_testing/security-guide.md | 50 | 검증 |
| 리뷰 | 05_review/security-guide.md | 40 | 최종 확인 |
| **합계** | - | **210** | - |

---

## 🎯 권장 사용 방법

### 1️⃣ 새 프로젝트 시작 시
```
1. 01_analysis/security-guide.md 읽기
   → 분석 체크리스트 완료

2. 02_design/security-guide.md 읽기
   → 보안 아키텍처 설계

3. 팀과 공유 및 승인
```

### 2️⃣ 개발 진행 중
```
1. 03_development/security-guide.md 참고
   → 시큐어 코딩 적용

2. 04_testing/security-guide.md 참고
   → 보안 테스트 작성
```

### 3️⃣ PR 리뷰 시
```
1. 05_review/security-guide.md 참고
   → 코드 리뷰 체크리스트 사용

2. OWASP/WCAG 항목 확인
```

---

## 📚 추가 자료

### OWASP Top 10 참고
- [OWASP Top 10 2021](https://owasp.org/www-project-top-ten/)
- [OWASP Cheat Sheet](https://cheatsheetseries.owasp.org/)

### WCAG 2.1 참고
- [W3C WCAG 2.1](https://www.w3.org/WAI/WCAG21/quickref/)
- [WebAIM WCAG 체크리스트](https://webaim.org/articles/wcag2checklist/)

### 시큐어 코딩 참고
- [OWASP Secure Coding](https://owasp.org/www-community/controls/)
- [CWE/SANS Top 25](https://cwe.mitre.org/top25/)

---

## ✅ 최종 체크리스트

모든 단계별 security-guide.md가 준비되었습니다:

- ✅ 01_analysis/security-guide.md (OWASP + WCAG + 기술스택)
- ✅ 02_design/security-guide.md (아키텍처 보안)
- ✅ 03_development/security-guide.md (시큐어 코딩)
- ✅ 04_testing/security-guide.md (보안 테스트)
- ✅ 05_review/security-guide.md (코드 리뷰)

**총 210개의 체크리스트 항목** ✨

---

이제 PRD 프로세스의 **모든 단계**에서 보안, 접근성, 시큐어 코딩을 체계적으로 적용할 수 있습니다!
