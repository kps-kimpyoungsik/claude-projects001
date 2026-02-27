# 리뷰 단계 - 보안 가이드

## 목적
코드 리뷰를 통해 보안 취약점을 최종 검증하고 배포 전에 제거합니다.

---

## 1️⃣ 보안 코드 리뷰 체크리스트

### Phase 1: 입력값 처리 리뷰

```
코드 리뷰 시 다음을 확인해주세요:

❌ 위험 패턴 - 거부 (Reject)
─────────────────────────────

1️⃣ 직접 SQL 조합
   ```javascript
   // ❌ REJECT
   const query = `SELECT * FROM users WHERE id = ${id}`;
   db.query(query);
   ```

2️⃣ 입력값 검증 부재
   ```javascript
   // ❌ REJECT
   app.post('/user', (req, res) => {
     // req.body.email 검증 없음
     User.create(req.body);
   });
   ```

3️⃣ 의존성을 사용하지 않은 암호 해시
   ```javascript
   // ❌ REJECT
   const hashed = sha1(password); // 약한 해시
   ```

✅ 안전 패턴 - 승인 (Approve)
──────────────────────────────

1️⃣ Parameterized Query
   ```javascript
   // ✅ APPROVE
   const query = 'SELECT * FROM users WHERE id = ?';
   db.query(query, [id]);
   ```

2️⃣ 입력값 검증
   ```javascript
   // ✅ APPROVE
   app.post('/user',
     body('email').isEmail(),
     (req, res) => {
       const errors = validationResult(req);
       if (!errors.isEmpty()) {
         return res.status(400).json({ errors: errors.array() });
       }
     }
   );
   ```

3️⃣ bcrypt 사용
   ```javascript
   // ✅ APPROVE
   const hashed = await bcrypt.hash(password, 10);
   ```
```

### Phase 2: XSS 방지 리뷰

```
XSS 취약점을 찾기 위해 다음을 검토해주세요:

❌ 거부 (Reject)
───────────────

1️⃣ React에서 dangerouslySetInnerHTML
   ```javascript
   // ❌ REJECT
   <div dangerouslySetInnerHTML={{ __html: userContent }} />
   ```

2️⃣ 바닐라 JS에서 innerHTML
   ```javascript
   // ❌ REJECT
   document.getElementById('output').innerHTML = userInput;
   ```

3️⃣ innerHTML + 문자열 연결
   ```javascript
   // ❌ REJECT
   el.innerHTML = '<p>' + userInput + '</p>';
   ```

✅ 승인 (Approve)
────────────────

1️⃣ React에서 자동 이스케이프
   ```javascript
   // ✅ APPROVE
   <div>{userContent}</div>
   ```

2️⃣ textContent 사용
   ```javascript
   // ✅ APPROVE
   document.getElementById('output').textContent = userInput;
   ```

3️⃣ HTML 이스케이프 라이브러리
   ```javascript
   // ✅ APPROVE
   import escapeHtml from 'escape-html';
   el.innerHTML = '<p>' + escapeHtml(userInput) + '</p>';
   ```

조심스러운 경우 (검토 필요)
────────────────────────

1️⃣ DOMPurify 사용 (신뢰할 수 있는 HTML만)
   ```javascript
   // ⚠️ 검토 필요
   import DOMPurify from 'dompurify';
   <div dangerouslySetInnerHTML={{
     __html: DOMPurify.sanitize(htmlContent)
   }} />
   ```
   - Whitelist가 명확한가?
   - 신뢰할 수 있는 소스인가?
```

### Phase 3: 인증/권한 리뷰

```
인증 및 권한 관련 코드를 검토해주세요:

❌ 거부 (Reject)
───────────────

1️⃣ 권한 검증 부재
   ```javascript
   // ❌ REJECT
   app.delete('/users/:id', verifyToken, (req, res) => {
     // 권한 검증 없음
     User.destroy({ where: { id: req.params.id } });
   });
   ```

2️⃣ 리소스 소유권 검증 부재
   ```javascript
   // ❌ REJECT
   app.put('/posts/:id', verifyToken, (req, res) => {
     // 로그인된 사용자가 해당 포스트 소유자인지 확인 없음
     Post.update(req.body, { where: { id: req.params.id } });
   });
   ```

3️⃣ 토큰 만료 없음
   ```javascript
   // ❌ REJECT
   const token = jwt.sign(
     { userId: user.id },
     process.env.JWT_SECRET
     // expiresIn 없음
   );
   ```

4️⃣ 평문 비밀번호
   ```javascript
   // ❌ REJECT
   User.create({ email, password }); // 해시 없음
   ```

✅ 승인 (Approve)
────────────────

1️⃣ 권한 검증
   ```javascript
   // ✅ APPROVE
   app.delete('/users/:id',
     verifyToken,
     authorize('admin'),
     (req, res) => {
       User.destroy({ where: { id: req.params.id } });
     }
   );
   ```

2️⃣ 리소스 소유권 검증
   ```javascript
   // ✅ APPROVE
   app.put('/posts/:id', verifyToken, async (req, res) => {
     const post = await Post.findByPk(req.params.id);
     if (post.userId !== req.userId) {
       return res.status(403).json({ error: 'Forbidden' });
     }
     await post.update(req.body);
   });
   ```

3️⃣ 토큰 만료
   ```javascript
   // ✅ APPROVE
   const token = jwt.sign(
     { userId: user.id },
     process.env.JWT_SECRET,
     { expiresIn: '1h' }
   );
   ```

4️⃣ bcrypt 사용
   ```javascript
   // ✅ APPROVE
   const hashedPassword = await bcrypt.hash(password, 10);
   User.create({ email, password: hashedPassword });
   ```
```

### Phase 4: 민감정보 리뷰

```
민감정보 노출을 확인해주세요:

❌ 거부 (Reject)
───────────────

1️⃣ 응답에 민감정보 포함
   ```javascript
   // ❌ REJECT
   res.json(user); // password, apiKey 포함
   ```

2️⃣ 로그에 민감정보
   ```javascript
   // ❌ REJECT
   console.log('Login:', { email, password, apiKey });
   ```

3️⃣ 환경 변수 하드코딩
   ```javascript
   // ❌ REJECT
   const apiKey = 'sk_live_abcd1234efgh5678';
   ```

4️⃣ 에러 메시지에 스택 트레이스
   ```javascript
   // ❌ REJECT
   res.status(500).json({ error: err.stack });
   ```

✅ 승인 (Approve)
────────────────

1️⃣ 필요한 정보만 반환
   ```javascript
   // ✅ APPROVE
   res.json({
     id: user.id,
     email: user.email,
     name: user.name
     // password, apiKey 제외
   });
   ```

2️⃣ 민감정보 제외한 로그
   ```javascript
   // ✅ APPROVE
   logger.info('Login successful', { userId: user.id, ip: req.ip });
   ```

3️⃣ 환경 변수 사용
   ```javascript
   // ✅ APPROVE
   const apiKey = process.env.API_KEY;
   ```

4️⃣ 안전한 에러 메시지
   ```javascript
   // ✅ APPROVE
   res.status(500).json({ error: 'Internal server error' });
   logger.error('Internal error', { error: err.stack }); // 로그에만 상세 정보
   ```
```

---

## 2️⃣ 보안 헤더 및 설정 리뷰

```
보안 관련 설정을 확인해주세요:

❌ 거부 (Reject)
───────────────

1️⃣ CSRF 보호 미설정
   ```javascript
   // ❌ REJECT
   app.post('/form', (req, res) => {
     // CSRF 토큰 검증 없음
   });
   ```

2️⃣ CORS 과도하게 개방
   ```javascript
   // ❌ REJECT
   app.use(cors({ origin: '*' })); // 모든 출처 허용
   ```

3️⃣ 쿠키 보안 플래그 부재
   ```javascript
   // ❌ REJECT
   app.use(session({
     cookie: {}
     // secure, httpOnly, sameSite 없음
   }));
   ```

4️⃣ 보안 헤더 부재
   ```javascript
   // ❌ REJECT
   app.get('/', (req, res) => {
     // X-Content-Type-Options, X-Frame-Options 등 미설정
     res.send('Hello');
   });
   ```

✅ 승인 (Approve)
────────────────

1️⃣ CSRF 보호
   ```javascript
   // ✅ APPROVE
   app.use(csrf());
   app.post('/form', (req, res) => {
     // csrf 미들웨어가 검증
   });
   ```

2️⃣ CORS 제한
   ```javascript
   // ✅ APPROVE
   app.use(cors({
     origin: ['https://example.com', 'https://app.example.com'],
     credentials: true
   }));
   ```

3️⃣ 쿠키 보안 플래그
   ```javascript
   // ✅ APPROVE
   app.use(session({
     cookie: {
       secure: true,    // HTTPS만
       httpOnly: true,  // JS 접근 불가
       sameSite: 'strict' // CSRF 방지
     }
   }));
   ```

4️⃣ 보안 헤더 (Helmet)
   ```javascript
   // ✅ APPROVE
   const helmet = require('helmet');
   app.use(helmet());
   ```
```

---

## 3️⃣ 웹 접근성 리뷰

```
웹 접근성(WCAG 2.1)을 확인해주세요:

❌ 거부 (Reject)
───────────────

1️⃣ 이미지 alt 텍스트 부재
   ```javascript
   // ❌ REJECT
   <img src="chart.png" />
   ```

2️⃣ 색상으로만 정보 전달
   ```javascript
   // ❌ REJECT
   <span style={{ color: 'red' }}>필수</span>
   ```

3️⃣ 키보드 네비게이션 불가능
   ```javascript
   // ❌ REJECT
   <div onClick={handleClick}>클릭</div>
   ```

4️⃣ 포커스 표시 제거
   ```javascript
   // ❌ REJECT
   button { outline: none; }
   ```

5️⃣ 낮은 색상 대비
   ```javascript
   // ❌ REJECT
   <span style={{ color: '#999', background: '#fff' }}>텍스트</span>
   // 대비율 2:1 (기준: 4.5:1)
   ```

✅ 승인 (Approve)
────────────────

1️⃣ alt 텍스트
   ```javascript
   // ✅ APPROVE
   <img src="chart.png" alt="2024년 월별 매출" />
   ```

2️⃣ 텍스트 + 시각 표시
   ```javascript
   // ✅ APPROVE
   <label>
     필수
     <span style={{ color: 'red' }}>*</span>
   </label>
   ```

3️⃣ 시맨틱 버튼
   ```javascript
   // ✅ APPROVE
   <button onClick={handleClick}>클릭</button>
   ```

4️⃣ 포커스 표시 유지
   ```javascript
   // ✅ APPROVE
   button {
     outline: 2px solid #4A90E2;
     outline-offset: 2px;
   }
   ```

5️⃣ 높은 색상 대비
   ```javascript
   // ✅ APPROVE
   <span style={{ color: '#333', background: '#fff' }}>텍스트</span>
   // 대비율 12.6:1
   ```

6️⃣ aria 속성
   ```javascript
   // ✅ APPROVE
   <input
     type="email"
     aria-label="이메일 주소"
     aria-invalid={hasError}
     aria-describedby="error-message"
   />
   {hasError && <span id="error-message">유효한 이메일을 입력하세요</span>}
   ```

7️⃣ 의미 있는 마크업
   ```javascript
   // ✅ APPROVE
   <nav>
     <ul>
       <li><a href="/">홈</a></li>
       <li><a href="/about">소개</a></li>
     </ul>
   </nav>
   ```
```

---

## 4️⃣ 의존성 보안 리뷰

```
npm 의존성을 확인해주세요:

❌ 거부 (Reject)
───────────────

1️⃣ CRITICAL 취약점
   npm audit 결과에 CRITICAL이 있음
   ```bash
   npm audit --json | grep '"severity":"critical"'
   ```
   → 즉시 업그레이드 또는 패치 필요

2️⃣ 알려지지 않은 패키지
   ```json
   {
     "dependencies": {
       "xlibhg2": "^1.0.0" // 누가 이걸 추가했는가?
     }
   }
   ```

3️⃣ 라이선스 위반
   ```json
   {
     "dependencies": {
       "gpl-package": "^1.0.0" // GPL은 상업 사용 제약
     }
   }
   ```

✅ 승인 (Approve)
────────────────

1️⃣ npm audit 통과
   ```bash
   npm audit
   # "0 vulnerabilities"
   ```

2️⃣ 알려진 패키지만 사용
   ```json
   {
     "dependencies": {
       "express": "^4.18.0",
       "bcrypt": "^5.1.0"
     }
   }
   ```

3️⃣ 적절한 라이선스
   ```bash
   npx license-checker
   # MIT, Apache-2.0, ISC 등 확인
   ```
```

---

## 5️⃣ 보안 리뷰 기록

```
PR 리뷰 코멘트 예시:

❌ SECURITY ISSUE - CRITICAL
──────────────────────────

**파일:** src/auth.js (Line 45)
**문제:** SQL Injection 취약점

```javascript
const query = `SELECT * FROM users WHERE email = '${email}'`;
```

**이유:** 사용자 입력이 SQL 쿼리에 직접 포함됨

**권고:** Parameterized Query 사용
```javascript
const query = 'SELECT * FROM users WHERE email = ?';
const user = await db.query(query, [email]);
```

**참고:** OWASP Top 10 #1 - SQL Injection

---

⚠️ SECURITY ISSUE - HIGH
──────────────────────

**파일:** src/profile.js (Line 78)
**문제:** XSS 취약점

```javascript
<div dangerouslySetInnerHTML={{ __html: bio }} />
```

**이유:** 사용자 입력이 HTML로 렌더링됨

**권고:** 자동 이스케이프 사용
```javascript
<div>{bio}</div>
```

---

✅ SECURITY GOOD PRACTICE
──────────────────────

**파일:** src/api.js (Line 120)
**칭찬:** 좋은 권한 검증

```javascript
if (post.userId !== req.userId) {
  return res.status(403).json({ error: 'Forbidden' });
}
```

리소스 소유권을 올바르게 검증하고 있습니다.
```

---

## 📋 보안 리뷰 체크리스트

### 입력/출력
- [ ] SQL 쿼리 Parameterized Query 사용?
- [ ] 입력값 검증 있는가?
- [ ] XSS 방지 (innerHTML 사용 안 함)?
- [ ] 민감정보 응답에서 제외?
- [ ] 에러 메시지에 스택 트레이스 없는가?

### 인증/권한
- [ ] 모든 보호 엔드포인트에 인증 있는가?
- [ ] 권한 검증이 있는가?
- [ ] 리소스 소유권 검증이 있는가?
- [ ] 비밀번호 bcrypt/argon2 해시?
- [ ] JWT 토큰에 만료시간 있는가?

### 데이터 보호
- [ ] HTTPS 강제?
- [ ] 쿠키 secure/httpOnly/sameSite?
- [ ] 환경 변수에 민감정보?
- [ ] CSRF 토큰 사용?
- [ ] CORS 적절히 설정?

### 웹 접근성
- [ ] 이미지 alt 텍스트?
- [ ] 색상 대비 충분한가 (4.5:1)?
- [ ] 키보드 네비게이션 가능한가?
- [ ] 포커스 표시 명확한가?
- [ ] 스크린 리더 호환성?

### 의존성
- [ ] npm audit 통과?
- [ ] CRITICAL 취약점 없는가?
- [ ] 알려진 패키지만 사용?
- [ ] 라이선스 확인?

### 보안 헤더
- [ ] CSP 설정?
- [ ] X-Frame-Options 설정?
- [ ] X-Content-Type-Options 설정?
- [ ] HSTS 설정?

### 로깅/모니터링
- [ ] 민감정보 로깅 안 함?
- [ ] 실패한 로그인 기록?
- [ ] 관리자 작업 기록?
