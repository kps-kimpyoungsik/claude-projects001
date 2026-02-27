# 테스트 단계 - 보안 가이드

## 목적
보안 테스트를 통해 개발 단계에서 놓친 취약점을 발견하고 검증합니다.

---

## 1️⃣ 기능 테스트 (Functional Security Tests)

### Phase 1: 인증 테스트

```javascript
// 테스트 프레임워크: Jest + Supertest

describe('Authentication', () => {
  // ✅ 정상 로그인
  test('should login successfully with valid credentials', async () => {
    const response = await request(app)
      .post('/login')
      .send({
        email: 'user@example.com',
        password: 'ValidPass123!@#'
      });

    expect(response.status).toBe(200);
    expect(response.body).toHaveProperty('token');
    expect(response.body.token).toBeTruthy();
  });

  // ✅ 잘못된 비밀번호
  test('should reject login with invalid password', async () => {
    const response = await request(app)
      .post('/login')
      .send({
        email: 'user@example.com',
        password: 'WrongPassword'
      });

    expect(response.status).toBe(401);
    expect(response.body.error).toMatch(/invalid/i);
  });

  // ✅ 존재하지 않는 사용자
  test('should reject login for non-existent user', async () => {
    const response = await request(app)
      .post('/login')
      .send({
        email: 'nonexistent@example.com',
        password: 'AnyPassword123!@#'
      });

    expect(response.status).toBe(401);
  });

  // ✅ 토큰 없이 보호된 엔드포인트 접근
  test('should reject protected endpoint without token', async () => {
    const response = await request(app)
      .get('/protected');

    expect(response.status).toBe(401);
    expect(response.body.error).toMatch(/token|unauthorized/i);
  });

  // ✅ 유효하지 않은 토큰
  test('should reject protected endpoint with invalid token', async () => {
    const response = await request(app)
      .get('/protected')
      .set('Authorization', 'Bearer invalid-token');

    expect(response.status).toBe(401);
  });

  // ✅ 만료된 토큰
  test('should reject expired token', async () => {
    const expiredToken = jwt.sign(
      { userId: 1 },
      process.env.JWT_SECRET,
      { expiresIn: '-1h' } // 이미 만료됨
    );

    const response = await request(app)
      .get('/protected')
      .set('Authorization', `Bearer ${expiredToken}`);

    expect(response.status).toBe(401);
    expect(response.body.error).toMatch(/expired/i);
  });
});
```

### Phase 2: 권한 제어 테스트

```javascript
describe('Authorization', () => {
  let userToken, adminToken;

  beforeAll(async () => {
    // 일반 사용자 토큰
    const userRes = await request(app)
      .post('/login')
      .send({ email: 'user@example.com', password: 'Pass123!@#' });
    userToken = userRes.body.token;

    // 관리자 토큰
    const adminRes = await request(app)
      .post('/login')
      .send({ email: 'admin@example.com', password: 'Pass123!@#' });
    adminToken = adminRes.body.token;
  });

  // ✅ 권한 있음: 성공
  test('admin can delete users', async () => {
    const response = await request(app)
      .delete('/users/123')
      .set('Authorization', `Bearer ${adminToken}`);

    expect(response.status).toBe(200);
  });

  // ✅ 권한 없음: 실패
  test('regular user cannot delete users', async () => {
    const response = await request(app)
      .delete('/users/123')
      .set('Authorization', `Bearer ${userToken}`);

    expect(response.status).toBe(403);
    expect(response.body.error).toMatch(/forbidden|permission/i);
  });

  // ✅ 리소스 소유권 검증
  test('user can only delete own posts', async () => {
    // 다른 사용자의 게시물 삭제 시도
    const response = await request(app)
      .delete('/posts/999')
      .set('Authorization', `Bearer ${userToken}`);

    expect(response.status).toBe(403);
  });

  // ✅ 사용자 데이터 접근 제한
  test('user cannot access other users data', async () => {
    const response = await request(app)
      .get('/users/999/profile')
      .set('Authorization', `Bearer ${userToken}`);

    expect(response.status).toBe(403);
  });
});
```

---

## 2️⃣ 입력값 검증 테스트

### Phase 1: SQL Injection 테스트

```javascript
describe('SQL Injection Prevention', () => {
  test('should prevent SQL injection in login', async () => {
    const maliciousInput = "' OR '1'='1";

    const response = await request(app)
      .post('/login')
      .send({
        email: maliciousInput,
        password: maliciousInput
      });

    // 쿼리 실행 실패 또는 비어있는 결과
    expect(response.status).toBe(401);
  });

  test('should prevent SQL injection in search', async () => {
    const maliciousQuery = "'; DROP TABLE users; --";

    const response = await request(app)
      .get(`/search?q=${encodeURIComponent(maliciousQuery)}`)
      .set('Authorization', `Bearer ${token}`);

    // 테이블이 삭제되지 않아야 함
    const usersStill = await User.findAll();
    expect(usersStill.length).toBeGreaterThan(0);
  });

  test('should sanitize database queries', async () => {
    // 특수문자가 포함된 정상 입력
    const validInput = "O'Reilly"; // 작은따옴표 포함

    const response = await request(app)
      .get(`/search?q=${encodeURIComponent(validInput)}`)
      .set('Authorization', `Bearer ${token}`);

    expect(response.status).toBe(200);
  });
});
```

### Phase 2: XSS 테스트

```javascript
describe('XSS Prevention', () => {
  test('should prevent XSS in user input', async () => {
    const xssPayload = '<script>alert("XSS")</script>';

    const response = await request(app)
      .post('/comments')
      .set('Authorization', `Bearer ${token}`)
      .send({
        postId: 1,
        content: xssPayload
      });

    expect(response.status).toBe(201);

    // 저장된 콘텐츠 검증
    const comment = await Comment.findByPk(response.body.id);
    expect(comment.content).not.toContain('<script>');
  });

  test('should encode special characters', async () => {
    const response = await request(app)
      .get(`/search?q=${encodeURIComponent('<img src=x>')}`)
      .set('Authorization', `Bearer ${token}`);

    expect(response.status).toBe(200);
    // HTML 응답이 안전한지 확인
    expect(response.text).not.toContain('<img src=x>');
  });

  test('should prevent event handler injection', async () => {
    const xssPayload = '"><svg/onload=alert(1)>';

    const response = await request(app)
      .post('/profile')
      .set('Authorization', `Bearer ${token}`)
      .send({ bio: xssPayload });

    const user = await User.findByPk(response.body.id);
    expect(user.bio).not.toContain('onload=');
  });
});
```

### Phase 3: CSRF 테스트

```javascript
describe('CSRF Protection', () => {
  test('should reject POST without CSRF token', async () => {
    const response = await request(app)
      .post('/form')
      .send({ data: 'value' });

    expect(response.status).toBe(403);
    expect(response.body.error).toMatch(/csrf|token/i);
  });

  test('should accept POST with valid CSRF token', async () => {
    // 1단계: CSRF 토큰 받기
    const getResponse = await request(app)
      .get('/form');
    const csrfToken = getResponse.body.csrfToken;

    // 2단계: CSRF 토큰으로 POST
    const postResponse = await request(app)
      .post('/form')
      .send({
        _csrf: csrfToken,
        data: 'value'
      });

    expect(postResponse.status).toBe(200);
  });

  test('should reject POST with invalid CSRF token', async () => {
    const response = await request(app)
      .post('/form')
      .send({
        _csrf: 'invalid-token',
        data: 'value'
      });

    expect(response.status).toBe(403);
  });
});
```

---

## 3️⃣ 보안 헤더 검증

```javascript
describe('Security Headers', () => {
  test('should include X-Content-Type-Options header', async () => {
    const response = await request(app).get('/');

    expect(response.headers['x-content-type-options']).toBe('nosniff');
  });

  test('should include X-Frame-Options header', async () => {
    const response = await request(app).get('/');

    expect(response.headers['x-frame-options']).toMatch(/DENY|SAMEORIGIN/);
  });

  test('should include Content-Security-Policy header', async () => {
    const response = await request(app).get('/');

    expect(response.headers['content-security-policy']).toBeTruthy();
  });

  test('should include HSTS header', async () => {
    const response = await request(app).get('/');

    expect(response.headers['strict-transport-security']).toBeTruthy();
  });

  test('should set secure cookie flags', async () => {
    const response = await request(app).post('/login').send({
      email: 'user@example.com',
      password: 'Pass123!@#'
    });

    const setCookie = response.headers['set-cookie'];
    expect(setCookie).toBeDefined();
    expect(setCookie[0]).toMatch(/Secure/);
    expect(setCookie[0]).toMatch(/HttpOnly/);
    expect(setCookie[0]).toMatch(/SameSite/);
  });
});
```

---

## 4️⃣ 파일 업로드 보안 테스트

```javascript
describe('File Upload Security', () => {
  test('should reject non-image files', async () => {
    const response = await request(app)
      .post('/upload')
      .set('Authorization', `Bearer ${token}`)
      .attach('file', 'path/to/malicious.exe');

    expect(response.status).toBe(400);
    expect(response.body.error).toMatch(/invalid|type/i);
  });

  test('should reject oversized files', async () => {
    // 10MB 파일 생성
    const largeFile = Buffer.alloc(10 * 1024 * 1024);

    const response = await request(app)
      .post('/upload')
      .set('Authorization', `Bearer ${token}`)
      .attach('file', largeFile, 'large.jpg');

    expect(response.status).toBe(413);
  });

  test('should validate file content', async () => {
    // JPEG 확장자이지만 실제로는 다른 파일
    const response = await request(app)
      .post('/upload')
      .set('Authorization', `Bearer ${token}`)
      .attach('file', 'path/to/malware.jpg');

    // MIME 타입 검증에 의해 거부되어야 함
    expect(response.status).toBe(400);
  });

  test('should randomize uploaded filenames', async () => {
    const response1 = await request(app)
      .post('/upload')
      .set('Authorization', `Bearer ${token}`)
      .attach('file', 'path/to/test.jpg');

    const response2 = await request(app)
      .post('/upload')
      .set('Authorization', `Bearer ${token}`)
      .attach('file', 'path/to/test.jpg');

    // 같은 파일을 업로드해도 다른 이름으로 저장되어야 함
    expect(response1.body.path).not.toBe(response2.body.path);
  });
});
```

---

## 5️⃣ API 응답 보안 테스트

```javascript
describe('API Response Security', () => {
  let userToken;

  beforeAll(async () => {
    const res = await request(app)
      .post('/login')
      .send({ email: 'user@example.com', password: 'Pass123!@#' });
    userToken = res.body.token;
  });

  test('should not expose password in user data', async () => {
    const response = await request(app)
      .get('/users/1')
      .set('Authorization', `Bearer ${userToken}`);

    expect(response.body).not.toHaveProperty('password');
  });

  test('should not expose API keys', async () => {
    const response = await request(app)
      .get('/settings')
      .set('Authorization', `Bearer ${userToken}`);

    expect(response.body).not.toHaveProperty('apiKey');
    expect(response.body).not.toHaveProperty('secretKey');
  });

  test('should not expose internal IDs unnecessarily', async () => {
    const response = await request(app)
      .get('/posts')
      .set('Authorization', `Bearer ${userToken}`);

    // 권한이 없어야 할 정보는 없어야 함
    response.body.posts.forEach(post => {
      if (post.authorId !== userToken.userId) {
        expect(post).not.toHaveProperty('authorEmail');
      }
    });
  });

  test('should not expose stack traces in production', async () => {
    const response = await request(app)
      .get('/invalid-endpoint');

    expect(response.status).toBe(404);
    expect(response.body).not.toMatch(/at /); // 스택 트레이스 없음
  });
});
```

---

## 6️⃣ 의존성 보안 테스트

```javascript
// package.json에서 npm audit 실행
describe('Dependency Security', () => {
  test('should have no critical vulnerabilities', async () => {
    // npm audit 실행
    const result = execSync('npm audit --json', { encoding: 'utf8' });
    const audit = JSON.parse(result);

    expect(audit.metadata.vulnerabilities.critical).toBe(0);
  });

  test('should minimize high severity vulnerabilities', async () => {
    const result = execSync('npm audit --json', { encoding: 'utf8' });
    const audit = JSON.parse(result);

    // HIGH 취약점이 3개 이하여야 함
    expect(audit.metadata.vulnerabilities.high).toBeLessThanOrEqual(3);
  });

  test('should use updated dependencies', async () => {
    const result = execSync('npm outdated --json', { encoding: 'utf8' });
    const outdated = JSON.parse(result);

    // 패치 업데이트가 20개 이상 없어야 함
    const patchUpdates = Object.keys(outdated).filter(
      pkg => outdated[pkg].type === 'patch'
    ).length;

    expect(patchUpdates).toBeLessThan(20);
  });
});
```

---

## 7️⃣ 성능 & 리소스 테스트 (DoS 방지)

```javascript
describe('DoS Prevention', () => {
  test('should enforce rate limiting', async () => {
    const requests = [];

    // 100개의 빠른 요청 보내기
    for (let i = 0; i < 100; i++) {
      requests.push(
        request(app).get('/api/data')
      );
    }

    const responses = await Promise.all(requests);

    // 일부 요청이 429 (Too Many Requests)로 거부되어야 함
    const tooManyRequests = responses.filter(r => r.status === 429);
    expect(tooManyRequests.length).toBeGreaterThan(0);
  });

  test('should have timeout on long-running queries', async () => {
    const startTime = Date.now();

    const response = await request(app)
      .get('/expensive-query?delay=10000')
      .timeout(5000); // 5초 타임아웃

    const duration = Date.now() - startTime;

    // 5초 이상 걸리지 않아야 함
    expect(duration).toBeLessThan(5000);
  });

  test('should limit query result size', async () => {
    const response = await request(app)
      .get('/records?limit=100000')
      .set('Authorization', `Bearer ${token}`);

    // 합리적인 수의 결과만 반환해야 함 (기본값으로 제한됨)
    expect(response.body.records.length).toBeLessThanOrEqual(1000);
  });
});
```

---

## 📋 보안 테스트 체크리스트

### 인증/권한
- [ ] 토큰 검증 테스트
- [ ] 토큰 만료 테스트
- [ ] 권한 검증 테스트
- [ ] 리소스 소유권 검증 테스트
- [ ] 실패한 인증 처리 테스트

### 입력값 검증
- [ ] SQL Injection 테스트
- [ ] XSS 테스트
- [ ] CSRF 테스트
- [ ] 파일 업로드 보안 테스트
- [ ] 입력값 길이 제한 테스트

### 데이터 보호
- [ ] 민감정보 노출 테스트
- [ ] API 응답 검증 테스트
- [ ] 암호화 적용 테스트
- [ ] 스택 트레이스 노출 테스트

### 보안 헤더
- [ ] CSP 헤더 검증
- [ ] X-Frame-Options 검증
- [ ] X-Content-Type-Options 검증
- [ ] HSTS 검증
- [ ] 쿠키 플래그 검증

### 성능/리소스
- [ ] Rate Limiting 테스트
- [ ] 타임아웃 테스트
- [ ] 리소스 사용량 제한 테스트

### 의존성
- [ ] npm audit 실행
- [ ] 취약점 심각도 확인
- [ ] 보안 패치 적용 확인
