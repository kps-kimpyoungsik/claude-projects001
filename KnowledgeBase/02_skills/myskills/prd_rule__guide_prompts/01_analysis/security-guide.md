# 분석 단계 - 보안 가이드

## 목적
프로젝트의 보안 현황을 종합적으로 분석하고, 취약점과 개선 영역을 식별합니다.

---

## 1️⃣ 웹 취약점 분석 (OWASP Top 10)

### Phase 1: OWASP 상위 10대 취약점 검토

```
당신은 프로젝트의 보안 분석가입니다.
다음 OWASP Top 10 취약점을 중심으로 코드베이스를 분석해주세요:

1. ❌ SQL Injection
   찾아야 할 것:
   - 사용자 입력을 직접 쿼리에 사용하는 부분
   - Parameterized Query 미사용 부분
   - 동적 쿼리 생성

   예시 (위험):
   ```javascript
   const query = `SELECT * FROM users WHERE id = ${userId}`;
   ```

   예시 (안전):
   ```javascript
   const query = 'SELECT * FROM users WHERE id = ?';
   db.query(query, [userId]);
   ```

2. ❌ XSS (Cross-Site Scripting)
   찾아야 할 것:
   - innerHTML 직접 할당
   - 사용자 입력의 자동 이스케이프 미실행
   - dangerouslySetInnerHTML 사용 (React)
   - 타사 라이브러리의 XSS 취약점

   예시 (위험):
   ```javascript
   document.getElementById('content').innerHTML = userInput;
   ```

   예시 (안전):
   ```javascript
   document.getElementById('content').textContent = userInput;
   // 또는 React에서
   <div>{userInput}</div> // 자동 이스케이프
   ```

3. ❌ CSRF (Cross-Site Request Forgery)
   찾아야 할 것:
   - 상태 변경 API에 CSRF 토큰 미사용
   - SameSite 쿠키 속성 미설정
   - Origin 검증 미실행

   확인 사항:
   - CSRF 토큰이 모든 POST/PUT/DELETE 요청에 포함되는가?
   - 쿠키에 SameSite=Strict 속성이 있는가?
   - 서버가 Origin/Referer를 검증하는가?

4. ❌ 인증/권한 취약점
   찾아야 할 것:
   - 약한 비밀번호 정책
   - 세션 만료 미설정
   - 권한 검증 부재
   - 민감한 정보 로그 기록

   확인 사항:
   - JWT 토큰의 만료시간이 설정되어 있는가?
   - 역할 기반 접근 제어(RBAC)가 구현되어 있는가?
   - 비밀번호는 bcrypt/argon2로 해시되는가?

5. ❌ 보안 미설정
   찾아야 할 것:
   - API 응답의 보안 헤더 부재
   - 기본 설정 미변경
   - 보안 패치 미적용
   - 민감한 설정 노출

   확인 사항:
   - X-Content-Type-Options 헤더?
   - X-Frame-Options 헤더?
   - Content-Security-Policy 헤더?
   - HSTS 헤더?

6. ❌ 민감정보 노출
   찾아야 할 것:
   - API 응답에 불필요한 정보 포함
   - 클라이언트 코드에 API 키/비밀 노출
   - 소스맵 배포
   - 엔러/스택 트레이스 노출

   확인 사항:
   - .env 파일이 .gitignore에 있는가?
   - API 응답이 최소 필요 정보만 반환하는가?
   - 프로덕션 빌드에 소스맵이 포함되는가?

7. ❌ 접근 제어 취약점
   찾아야 할 것:
   - API 엔드포인트에 권한 검증 부재
   - 사용자가 다른 사용자 데이터에 접근 가능
   - 관리자만 접근해야 하는 기능의 검증 부재

   확인 사항:
   - 모든 API 엔드포인트가 인증을 요구하는가?
   - 리소스 접근 시 소유권을 검증하는가?

8. ❌ 파일 업로드 취약점
   찾아야 할 것:
   - 파일 타입 검증 부재
   - 파일 크기 제한 없음
   - 업로드된 파일 실행 가능

   확인 사항:
   - 파일 확장자/MIME 타입을 검증하는가?
   - 업로드 크기 제한이 있는가?
   - 업로드 파일을 실행 가능한 경로에 저장하는가?

9. ❌ 컴포넌트 취약점
   찾아야 할 것:
   - 알려진 취약점이 있는 라이브러리 버전
   - 오래된 의존성

   확인 사항:
   ```bash
   npm audit
   npm outdated
   ```

10. ❌ 로깅/모니터링 부족
    찾아야 할 것:
    - 보안 이벤트 로깅 부재
    - 실패한 로그인 시도 미기록
    - 관리자 작업 미추적
```

### Phase 2: 취약점 심각도 평가

```
발견된 각 취약점을 다음 등급으로 분류해주세요:

🔴 CRITICAL (즉시 해결 필요)
- SQL Injection 구간 발견
- 인증 우회 가능
- 민감정보 직접 노출
- 악의적 코드 실행 가능

🟠 HIGH (다음 릴리스에 반드시 포함)
- XSS 취약점
- CSRF 취약점
- 약한 권한 검증
- 보안 헤더 부재

🟡 MEDIUM (가까운 미래에 해결)
- 약한 비밀번호 정책
- 불완전한 입력 검증
- 기본 설정 미변경

🟢 LOW (우선순위 낮음)
- 사소한 보안 설정
- 개선 가능한 로깅
```

---

## 2️⃣ 웹 접근성 분석 (WCAG 2.1)

### Phase 1: 웹 접근성 현황 파악

```
당신은 웹 접근성 전문가입니다.
다음 WCAG 2.1 기준을 중심으로 분석해주세요:

## A. 인지 가능성 (Perceivable)

1️⃣ 이미지 대체 텍스트
   확인 사항:
   - 모든 <img> 태그에 alt 속성이 있는가?
   - SVG 아이콘에 <title> 또는 aria-label이 있는가?
   - 장식용 이미지에 alt="" 처리되어 있는가?

   예시 (안전):
   ```html
   <!-- 정보 이미지 -->
   <img src="chart.png" alt="2024년 매출 추이: 1월 50만원, 2월 75만원">

   <!-- 장식용 이미지 -->
   <img src="divider.png" alt="" aria-hidden="true">

   <!-- SVG -->
   <svg>
     <title>사용자 프로필</title>
     <circle cx="50" cy="50" r="40"/>
   </svg>
   ```

2️⃣ 색상 대비
   확인 사항:
   - 일반 텍스트 대비율이 4.5:1 이상인가? (WCAG AA)
   - 큰 텍스트 대비율이 3:1 이상인가?
   - 색상만으로 정보를 전달하지 않는가?

   문제 예시:
   - 회색(#999) 텍스트는 흰 배경에서 대비 부족
   - 필수 필드를 빨간색으로만 표시

   해결책:
   ```css
   /* 좋음: 명확한 텍스트 색상 */
   color: #333; /* 대비율 12.6:1 */

   /* 필수 필드 표시 */
   label::after {
     content: " *";
     color: red;
   }
   ```

3️⃣ 텍스트 크기/확대
   확인 사항:
   - 페이지를 200%까지 확대 가능한가?
   - 텍스트가 가독성을 유지하는가?
   - 가로 스크롤이 생기지 않는가?

   예시 (안전):
   ```css
   /* 절대 픽셀 대신 상대 단위 사용 */
   body { font-size: 16px; } /* 기본 */
   h1 { font-size: 2rem; }   /* 32px, 유동적 */

   /* 고정 너비 대신 최대 너비 사용 */
   .container {
     max-width: 100%;
     padding: 0 1rem;
   }
   ```

## B. 조작 가능성 (Operable)

4️⃣ 키보드 네비게이션
   확인 사항:
   - 마우스 없이 모든 기능을 수행할 수 있는가?
   - Tab 키로 모든 대화형 요소에 접근 가능한가?
   - 포커스 순서가 논리적인가?
   - 포커스 표시가 명확한가?

   예시 (안전):
   ```html
   <!-- 버튼 포커스 스타일 -->
   <button
     style="outline: 3px solid #4A90E2; outline-offset: 2px;">
     클릭하기
   </button>

   <!-- 키보드 전용 링크 -->
   <a href="#main-content">주요 콘텐츠로 건너뛰기</a>
   ```

5️⃣ 충분한 시간
   확인 사항:
   - 자동 스크롤/회전이 있는가?
   - 타임아웃이 있는가?
   - 일시 정지 버튼이 있는가?

   예시:
   ```javascript
   // 자동 회전 슬라이드 + 일시정지
   <button onClick={() => setAutoPlay(!autoPlay)}>
     {autoPlay ? '일시정지' : '재생'}
   </button>
   ```

6️⃣ 플래시/동작 이슈
   확인 사항:
   - 초당 3회 이상 깜빡이는 콘텐츠가 있는가?
   - 움직이는 콘텐츠를 일시정지할 수 있는가?
   - 자동 재생되는 음성/비디오가 있는가?

   예시 (문제):
   ```javascript
   // 위험: 깜빡임
   setInterval(() => setVisible(!visible), 100); // 너무 빠름
   ```

## C. 이해 가능성 (Understandable)

7️⃣ 언어/텍스트 명확성
   확인 사항:
   - 복잡한 단어 설명이 있는가?
   - 약자를 처음 사용할 때 설명하는가?
   - 문장이 이해하기 쉬운가?

   예시:
   ```html
   <!-- 좋음: 명확한 표현 -->
   <abbr title="Hypertext Markup Language">HTML</abbr>

   <!-- 좋음: 단순한 문장 -->
   <label for="email">이메일 주소를 입력하세요</label>

   <!-- 피할 것: 복잡한 표현 -->
   <!-- <label>상기 임의의 인터넷 통신 수단을 활용하여... -->
   ```

8️⃣ 예측 가능한 동작
   확인 사항:
   - 버튼 동작이 예상대로인가?
   - 폼 자동 제출이 있는가?
   - 탭 전환으로 페이지가 변경되는가?

   예시 (피할 것):
   ```javascript
   // 나쁜 예: 선택으로 페이지 이동 (예상 밖)
   <select onChange={() => navigate(value)}>
     <option>선택하세요</option>
     <option value="/page1">페이지 1</option>
   </select>

   // 좋은 예: 버튼으로 명시적 동작
   <button onClick={() => navigate(value)}>이동</button>
   ```

9️⃣ 오류 방지 & 복구
   확인 사항:
   - 폼 오류 메시지가 명확한가?
   - 오류 필드가 시각적으로 표시되는가?
   - 중요한 작업에 확인이 있는가?

   예시 (안전):
   ```html
   <!-- 오류 표시 -->
   <input
     aria-invalid="true"
     aria-describedby="email-error"
   />
   <span id="email-error" role="alert">
     유효한 이메일을 입력하세요. 예: user@example.com
   </span>
   ```

## D. 견고함 (Robust)

🔟 적절한 마크업
   확인 사항:
   - 의미 있는 HTML 태그를 사용하는가? (div 남용 X)
   - ARIA 속성이 올바르게 사용되는가?
   - 중복된 ID가 없는가?

   예시 (안전):
   ```html
   <!-- 의미 있는 마크업 -->
   <nav>
     <ul>
       <li><a href="/home">홈</a></li>
       <li><a href="/about">소개</a></li>
     </ul>
   </nav>

   <!-- 버튼 역할을 하는 div -->
   <button>클릭</button> <!-- 좋음 -->
   <div role="button" onclick="...">클릭</div> <!-- 피할 것 -->
   ```
```

### Phase 2: 접근성 테스트 도구

```
다음 도구들로 접근성을 검증해주세요:

1. 자동 도구:
   - axe DevTools (Chrome 확장)
   - Lighthouse (Chrome DevTools)
   - WAVE (WebAIM)

2. 수동 테스트:
   - 키보드 네비게이션 (탭만 사용)
   - 스크린 리더 테스트 (NVDA, JAWS)
   - 색상 대비 검사 (WebAIM Contrast Checker)

3. 명령어:
   ```bash
   # 접근성 자동 검사
   npx axe-core <url>

   # Lighthouse 실행
   lighthouse <url> --view
   ```
```

---

## 3️⃣ 기술 스택 보안 분석

### Phase 1: 의존성 보안 검사

```
당신은 보안 엔지니어입니다.
프로젝트의 기술 스택을 분석해주세요:

## A. NPM/Node.js 의존성

1️⃣ 알려진 취약점 검사
   ```bash
   # npm 기본 감사
   npm audit

   # 상세 보고서
   npm audit --json

   # 특정 심각도만 표시
   npm audit --audit-level=moderate
   ```

   분석 항목:
   - CRITICAL 취약점: 즉시 업그레이드
   - HIGH 취약점: 다음 릴리스 포함
   - MODERATE: 계획된 업데이트 시 포함

2️⃣ 오래된 의존성 확인
   ```bash
   npm outdated
   ```

   확인 사항:
   - 메이저 버전 오래됨 (6개월 이상)
   - 마이너 버전 오래됨 (3개월 이상)
   - 보안 패치 미적용

3️⃣ 라이선스 확인
   ```bash
   npm ls --depth=0 # 직접 의존성만
   npx license-checker
   ```

   확인 사항:
   - GPL 라이선스 항목 (상업 사용 제약)
   - AGPL 라이선스 (소스 공개 의무)
   - 악의적인 패키지 (typosquatting)

## B. 보안 관련 라이브러리 검토

확인 사항:
- 암호화: crypto/bcrypt 사용 여부
- 인증: passport/JWT 라이브러리 버전
- 입력 검증: joi/yup 사용 여부
- XSS 방지: DOMPurify 포함 여부
- CORS 설정: cors 라이브러리 구성
```

### Phase 2: 빌드/배포 보안

```
빌드 설정의 보안을 확인해주세요:

1️⃣ 환경 변수 관리
   확인 사항:
   - API 키가 코드에 하드코딩되어 있는가?
   - .env 파일이 .gitignore에 있는가?
   - 환경 변수 문서에 테스트 값만 포함되는가?

   예시 (안전):
   ```
   .env (git 제외)
   - DATABASE_URL=postgresql://...
   - API_KEY=sk_live_...

   .env.example (git 포함)
   - DATABASE_URL=postgresql://user:pass@localhost/db
   - API_KEY=sk_test_...
   ```

2️⃣ 소스맵 관리
   확인 사항:
   - 프로덕션 빌드에 소스맵이 포함되는가?
   - 소스맵이 공개적으로 접근 가능한가?

   예시 (안전):
   ```javascript
   // webpack.config.js (프로덕션)
   module.exports = {
     mode: 'production',
     devtool: false, // 소스맵 비활성화
     // 또는
     devtool: 'hidden-source-map', // 맵 파일 분리
   };
   ```

3️⃣ 빌드 스크립트 보안
   확인 사항:
   - npm scripts에서 민감한 정보 노출 여부
   - 빌드 중간 생성물이 안전한가?

   예시:
   ```json
   {
     "scripts": {
       "build": "vite build",
       "build:prod": "vite build && rm -rf .cache"
     }
   }
   ```
```

---

## 4️⃣ 보안 분석 결과 형식

```
당신은 다음 형식으로 보안 분석 결과를 정리해주세요:

# 보안 분석 결과

## 1. 취약점 요약
- CRITICAL: [개수]개
- HIGH: [개수]개
- MEDIUM: [개수]개
- LOW: [개수]개

## 2. OWASP Top 10 분석
### A1: SQL Injection
- 상태: [안전/위험]
- 발견: [구체적 위치]
- 권고: [해결책]

[... 나머지 항목]

## 3. 웹 접근성 분석 (WCAG 2.1)
### 인지 가능성
- 이미지 대체 텍스트: [충족/미충족]
- 색상 대비: [충족/미충족]

[... 나머지 항목]

## 4. 기술 스택 보안
### 의존성
- 알려진 취약점: [개수]개
- 오래된 패키지: [개수]개

### 빌드 보안
- 환경 변수 관리: [충족/미충족]
- 소스맵 관리: [충족/미충족]

## 5. 우선순위 액션 아이템

### 즉시 해결 (CRITICAL)
1. [항목]
2. [항목]

### 다음 릴리스 (HIGH)
1. [항목]
2. [항목]

### 향후 개선 (MEDIUM/LOW)
1. [항목]
2. [항목]
```

---

## 📋 보안 분석 체크리스트

### OWASP 검토
- [ ] SQL Injection 검사
- [ ] XSS 취약점 검사
- [ ] CSRF 보호 확인
- [ ] 인증/권한 검증
- [ ] 보안 헤더 확인
- [ ] 민감정보 노출 확인
- [ ] 접근 제어 검증
- [ ] 파일 업로드 보안
- [ ] 컴포넌트 취약점 검사
- [ ] 로깅/모니터링 확인

### 웹 접근성 검토
- [ ] 이미지 alt 텍스트
- [ ] 색상 대비 검사
- [ ] 키보드 네비게이션
- [ ] 포커스 표시 확인
- [ ] 스크린 리더 호환성
- [ ] 폼 라벨링
- [ ] 오류 메시지 명확성
- [ ] 의미 있는 마크업

### 기술 스택 검토
- [ ] npm audit 실행
- [ ] 오래된 의존성 확인
- [ ] 라이선스 검토
- [ ] 환경 변수 관리
- [ ] 소스맵 관리
- [ ] 빌드 설정 검토
- [ ] 민감 정보 로깅 확인
