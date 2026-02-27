# 설계 단계 - 보안 가이드

## 목적
아키텍처 수준에서 보안을 설계하고, 개발 단계의 보안 취약점을 사전에 방지합니다.

---

## 1️⃣ 인증/권한 아키텍처 설계

### Phase 1: 인증 방식 선택

```
프로젝트의 인증 방식을 선택할 때 다음을 고려하세요:

## 1. 세션 기반 인증 (Session-based)

장점:
- 구현이 간단
- 서버에서 전체 제어 가능
- 로그아웃 즉시 적용

단점:
- 마이크로서비스 환경에서 복잡
- 확장성 제약

사용 시나리오:
- 모놀리식 웹 애플리케이션
- 전통적인 서버 기반 앱

설계 예시:
```
┌─────────────┐
│   Client    │
│ (세션 ID)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Server    │
│ (세션 저장) │
└─────────────┘
```

## 2. JWT (JSON Web Token) 기반 인증

장점:
- 상태 비저장 (Stateless)
- 마이크로서비스 친화적
- 모바일 앱에 적합

단점:
- 토큰 폐기 어려움 (만료 대기 필요)
- 토큰 크기 증가
- 복잡한 구현

사용 시나리오:
- API 기반 아키텍처
- 마이크로서비스
- 모바일 앱 백엔드

설계 예시:
```
┌─────────────┐
│   Client    │
│  (JWT)      │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Server    │
│  (검증만)   │
└─────────────┘
```

권장사항:
- Access Token: 15분 만료
- Refresh Token: 7일 만료
- Refresh Token은 HTTPS + HttpOnly 쿠키에 저장

## 3. OAuth 2.0 / OpenID Connect

장점:
- 타사 인증 제공자 활용
- SSO 구현 가능
- 사용자가 별도 비밀번호 관리 안 함

단점:
- 구현이 복잡
- 외부 의존성

사용 시나리오:
- 구글/페이스북 로그인
- 엔터프라이즈 SSO
- 다중 애플리케이션 통합

설계 예시:
```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Authorization │
│   Server    │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ Resource Server  │
│ (Google, etc)    │
└──────────────────┘
```
```

### Phase 2: 권한 관리 아키텍처

```
## 역할 기반 접근 제어 (RBAC)

설계:
```
User
├─ role: 'admin' | 'moderator' | 'user'
│
Role
├─ id: 'admin'
├─ permissions: ['user:create', 'user:delete', ...]
│
Permission
├─ resource: 'user' | 'post' | 'comment'
├─ action: 'create' | 'read' | 'update' | 'delete'
└─ condition: 'own_resource' | 'published' | etc
```

데이터베이스 스키마:
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR UNIQUE NOT NULL,
  password_hash VARCHAR NOT NULL,
  role_id UUID REFERENCES roles(id)
);

CREATE TABLE roles (
  id UUID PRIMARY KEY,
  name VARCHAR UNIQUE NOT NULL
);

CREATE TABLE role_permissions (
  role_id UUID REFERENCES roles(id),
  permission_id UUID REFERENCES permissions(id),
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE permissions (
  id UUID PRIMARY KEY,
  resource VARCHAR NOT NULL,
  action VARCHAR NOT NULL,
  UNIQUE(resource, action)
);
```

API 설계:
```javascript
// 엔드포인트별 권한 정의
const endpoints = {
  'GET /users': ['admin', 'moderator'],
  'POST /users': ['admin'],
  'DELETE /users/:id': ['admin'],
  'GET /posts': ['admin', 'moderator', 'user'],
  'POST /posts': ['admin', 'moderator', 'user'],
  'DELETE /posts/:id': ['admin', 'post_owner'],
};

// 미들웨어
const authorize = (requiredRoles) => {
  return (req, res, next) => {
    if (!requiredRoles.includes(req.user.role)) {
      return res.status(403).json({ error: 'Forbidden' });
    }
    next();
  };
};

// 사용
app.delete('/posts/:id',
  verifyToken,
  authorize(['admin', 'post_owner']),
  (req, res) => { ... }
);
```
```

---

## 2️⃣ 데이터 보안 아키텍처

### Phase 1: 데이터 분류 및 암호화 전략

```
## 데이터 분류

1️⃣ Public 데이터
   - 누구나 접근 가능
   - 암호화 불필요
   예: 공개 게시물, 사용자 이름

2️⃣ Internal 데이터
   - 인증된 사용자만 접근
   - 전송 시 암호화 (HTTPS)
   예: 사용자 프로필, 자신의 게시물

3️⃣ Confidential 데이터
   - 매우 제한된 접근
   - 전송 + 저장 시 암호화
   예: 비밀번호, API 키, 결제 정보

4️⃣ Sensitive 데이터
   - 최고 수준 보호
   - 암호화 + 접근 로그 기록
   예: 은행 계좌, 의료 정보, PII

## 암호화 전략

### 전송 계층 (Transport Layer)
- HTTPS/TLS 1.2 이상 사용
- 모든 트래픽 암호화

### 저장 계층 (Storage Layer)
- 민감한 필드 암호화
- 데이터베이스 레벨 암호화 (옵션)

암호화 필드 예시:
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR NOT NULL, -- 인덱싱 필요하므로 암호화 X
  password_hash VARCHAR NOT NULL, -- 해시 (복호화 불가)
  phone_encrypted BYTEA NOT NULL, -- 암호화
  ssn_encrypted BYTEA NOT NULL, -- 암호화
  payment_card_encrypted BYTEA NOT NULL -- 암호화
);
```

### 키 관리
```
┌──────────────────────┐
│  Key Management      │
│  Service (KMS)       │
└──────────────────────┘
         ▲
         │ (암호화/복호화 요청)
         │
┌──────────────────────┐
│  Application         │
│  (마스터 키 미보유)  │
└──────────────────────┘
         │
         ▼
┌──────────────────────┐
│  Database            │
│  (암호화된 데이터)   │
└──────────────────────┘
```

권장사항:
- AWS KMS, Azure Key Vault 등 클라우드 KMS 사용
- 로컬 저장 피하기
- 정기적 키 로테이션 (연 1회 이상)
```

### Phase 2: 데이터 접근 제어 (Data Access Control)

```
## 원칙

1️⃣ 최소 권한 원칙 (Principle of Least Privilege)
   - 필요한 최소한의 권한만 부여
   - 정기적 권한 검토

2️⃣ 데이터 격리 (Data Isolation)
   - 테넌트 간 데이터 분리 (멀티테넌시)
   - 행 수준 보안 (Row-Level Security)

## 설계 예시: Row-Level Security

사용자는 자신의 데이터만 조회 가능:

```sql
-- 정책 생성
CREATE POLICY user_isolation ON posts
  USING (user_id = current_user_id());

-- 효과
SELECT * FROM posts; -- 현재 사용자의 포스트만 반환

-- 다른 사용자 포스트는 쿼리해도 보이지 않음
SELECT * FROM posts WHERE user_id = 999;
-- (다른 사용자의 포스트: 보이지 않음)
```

## 설계 예시: API 레벨 접근 제어

```javascript
// 데이터 필터링
app.get('/posts', verifyToken, (req, res) => {
  // 현재 사용자의 포스트만 반환
  Post.findAll({
    where: { userId: req.userId },
    attributes: { exclude: ['internalField'] }
  });
});

// 다른 사용자 데이터 접근 시도
app.get('/posts/:id', verifyToken, async (req, res) => {
  const post = await Post.findByPk(req.params.id);

  // 소유권 검증
  if (post.userId !== req.userId && req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Forbidden' });
  }

  res.json(post);
});
```
```

---

## 3️⃣ 입력값 검증 & 출력 인코딩 전략

### Phase 1: 입력값 검증 계층 설계

```
## 검증 계층 아키텍처

```
┌─────────────┐
│   Client    │  ← 클라이언트 사이드 검증 (UX)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   API       │  ← 서버 사이드 검증 (보안 - 필수)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Database   │  ← 데이터베이스 제약 (마지막 방어선)
└─────────────┘
```

## 검증 전략

1️⃣ 화이트리스트 기반 (권장)
```javascript
// ✅ 허용된 값만 수용
const validRoles = ['admin', 'user', 'guest'];
if (!validRoles.includes(role)) {
  throw new Error('Invalid role');
}
```

2️⃣ 블랙리스트 기반 (피하기)
```javascript
// ❌ 위험: 새로운 악성 입력 패턴 대응 어려움
const bannedWords = ['admin', 'root', 'system'];
if (bannedWords.includes(input)) {
  throw new Error('Invalid input');
}
```

## 필드별 검증 규칙

```
Email:
- 정규표현식: /^[^\s@]+@[^\s@]+\.[^\s@]+$/
- 길이: 254자 이하
- 정규화: 소문자로 변환

Password:
- 최소 길이: 8자
- 복합성: 대문자 + 소문자 + 숫자 + 특수문자
- 금지 패턴: 일반적인 비밀번호 (password, 123456 등)

Phone:
- 정규표현식: /^[0-9\-\(\) ]+$/
- 길이: 7-15자
- 정규화: 숫자만 추출

Username:
- 정규표현식: /^[a-zA-Z0-9_\-]{3,20}$/
- 금지: 예약어 (admin, root 등)
```

## 검증 구현

```javascript
import { body, validationResult } from 'express-validator';

const userValidation = [
  body('email')
    .isEmail()
    .normalizeEmail()
    .trim(),

  body('password')
    .isLength({ min: 8, max: 128 })
    .matches(/[A-Z]/, { message: '대문자 포함' })
    .matches(/[a-z]/, { message: '소문자 포함' })
    .matches(/[0-9]/, { message: '숫자 포함' })
    .matches(/[!@#$%^&*]/, { message: '특수문자 포함' })
    .custom(value => {
      const banned = ['password', '123456', 'qwerty'];
      if (banned.includes(value.toLowerCase())) {
        throw new Error('너무 일반적인 비밀번호');
      }
      return true;
    }),

  body('username')
    .matches(/^[a-zA-Z0-9_\-]{3,20}$/)
    .custom(value => {
      const reserved = ['admin', 'root', 'system'];
      if (reserved.includes(value)) {
        throw new Error('예약어 불가');
      }
      return true;
    })
];

app.post('/users', userValidation, (req, res) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() });
  }
  // 유효한 데이터로 진행
});
```
```

### Phase 2: 출력 인코딩 전략

```
## 출력 인코딩 전략

### 1. HTML 이스케이프
```
입력:  <script>alert('XSS')</script>
출력:  &lt;script&gt;alert('XSS')&lt;/script&gt;
```

### 2. JavaScript 이스케이프
```
입력:  '; alert('XSS'); //
JSON:  \'; alert(\'XSS\'); //
```

### 3. URL 이스케이프
```
입력:  javascript:alert('XSS')
출력:  javascript%3Aalert%28%27XSS%27%29
```

### 4. CSS 이스케이프
```
입력:  background: url('data:...')
출력:  background: url('data%3A...')
```

## 구현 전략

```javascript
// 1️⃣ React (자동 이스케이프)
function Comment({ content }) {
  return <div>{content}</div>;
  // 자동으로 HTML 이스케이프됨
}

// 2️⃣ 필요시 DOMPurify
import DOMPurify from 'dompurify';

function BlogPost({ html }) {
  const sanitized = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'u', 'a', 'p', 'h1', 'h2'],
    ALLOWED_ATTR: ['href', 'title']
  });

  return <div dangerouslySetInnerHTML={{ __html: sanitized }} />;
}

// 3️⃣ 서버 사이드 (escapeHtml)
const escapeHtml = require('escape-html');
res.send('<h1>' + escapeHtml(title) + '</h1>');
```
```

---

## 4️⃣ 보안 통신 아키텍처

### Phase 1: HTTPS/TLS 설계

```
## 필수 요구사항

1️⃣ TLS 버전
- 최소: TLS 1.2
- 권장: TLS 1.3

2️⃣ 인증서
- 신뢰된 CA에서 발급
- 와일드카드 또는 SAN 인증서
- 연 1회 이상 갱신

3️⃣ 암호화 스위트
```
TLS 1.3 권장 스위트:
- TLS_AES_256_GCM_SHA384
- TLS_CHACHA20_POLY1305_SHA256
- TLS_AES_128_GCM_SHA256

TLS 1.2 권장 스위트:
- ECDHE-RSA-AES256-GCM-SHA384
- ECDHE-RSA-CHACHA20-POLY1305
- ECDHE-RSA-AES128-GCM-SHA256
```

4️⃣ HSTS (HTTP Strict Transport Security)
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload

의미:
- max-age=31536000: 1년 동안 HTTPS 강제
- includeSubDomains: 모든 서브도메인 포함
- preload: HSTS Preload 리스트에 추가 (권장)
```

## 설정 예시

```javascript
// Express
const https = require('https');
const fs = require('fs');

const options = {
  key: fs.readFileSync('private-key.pem'),
  cert: fs.readFileSync('certificate.pem')
};

https.createServer(options, app).listen(443);

// 또는 Helmet 사용
const helmet = require('helmet');
app.use(helmet.hsts({
  maxAge: 31536000,
  includeSubDomains: true,
  preload: true
}));
```
```

### Phase 2: CORS 설계

```
## CORS 정책 설계

```
┌─────────────────────────────────────┐
│     Client Origin: A                │
└──────────────┬──────────────────────┘
               │
               ▼ (preflight 요청)
        OPTIONS /api/data
        Origin: A
               │
               ▼
┌─────────────────────────────────────┐
│      Server                         │
│ Access-Control-Allow-Origin: A      │
│ Access-Control-Allow-Methods: GET   │
│ Access-Control-Allow-Headers: token │
└─────────────────────────────────────┘
               │
               ▼ (실제 요청)
        GET /api/data
        Origin: A
```

## 설계 규칙

```javascript
// ❌ 위험: 모든 출처 허용
app.use(cors({ origin: '*' }));

// ✅ 안전: 화이트리스트 기반
const whitelist = [
  'https://example.com',
  'https://app.example.com',
  'https://admin.example.com'
];

app.use(cors({
  origin: function(origin, callback) {
    if (!origin || whitelist.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  credentials: true, // 쿠키 포함
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));
```
```

---

## 5️⃣ API 보안 설계

### Phase 1: Rate Limiting 전략

```
## Rate Limiting 설계

```
요청 빈도 제한:
- 일반 사용자: 100 req/min
- 인증 사용자: 1000 req/min
- 관리자: 무제한
- 로그인 시도: 5 req/min (실패)

IP 기반 제한:
- 동일 IP에서 짧은 시간에 많은 요청
  → 5분 차단

토큰 기반 제한:
- 사용자 토큰당 요청 수 제한
- 토큰 재발급 간격 강제
```

## 구현

```javascript
const rateLimit = require('express-rate-limit');

// 일반 엔드포인트
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15분
  max: 100, // 100 요청
  message: 'Too many requests'
});

// 로그인 엔드포인트 (더 엄격)
const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 5, // 5 요청
  skipSuccessfulRequests: true, // 성공 요청은 카운팅 안 함
  message: 'Too many login attempts'
});

app.get('/api/data', limiter, (req, res) => { ... });
app.post('/login', loginLimiter, (req, res) => { ... });
```
```

---

## 📋 보안 설계 체크리스트

### 인증/권한
- [ ] 인증 방식 선택 (세션/JWT/OAuth)
- [ ] 권한 모델 정의 (RBAC/ABAC)
- [ ] 리소스 소유권 검증 계획
- [ ] 로그아웃 메커니즘 설계

### 데이터 보안
- [ ] 데이터 분류 완료
- [ ] 암호화 전략 수립
- [ ] 키 관리 계획
- [ ] 데이터 접근 제어 설계
- [ ] 감시 로깅 계획

### 입력/출력
- [ ] 입력값 검증 규칙 정의
- [ ] 출력 인코딩 전략 결정
- [ ] 에러 처리 방식 정의

### 통신 보안
- [ ] HTTPS/TLS 설정 계획
- [ ] HSTS 정책 정의
- [ ] CORS 정책 정의

### API 보안
- [ ] Rate Limiting 전략
- [ ] 타임아웃 설정
- [ ] 버전 관리 계획

### 모니터링
- [ ] 로깅 전략
- [ ] 알림 규칙
- [ ] 감시 메트릭
