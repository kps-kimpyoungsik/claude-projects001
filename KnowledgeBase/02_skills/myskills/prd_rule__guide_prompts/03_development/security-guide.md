# 개발 단계 - 보안 가이드 (시큐어 코딩)

## 목적
안전한 코드를 작성하여 보안 취약점을 사전에 방지합니다.

---

## 1️⃣ 시큐어 코딩 기초

### Phase 1: 입력값 검증 (Input Validation)

```javascript
// ❌ 위험: 입력값 검증 없음
app.post('/user', (req, res) => {
  const email = req.body.email;
  const user = User.create({ email });
  res.json(user);
});

// ✅ 안전: 입력값 검증 포함
import validator from 'validator';
import { body, validationResult } from 'express-validator';

app.post('/user',
  body('email')
    .isEmail()
    .normalizeEmail()
    .trim(),
  body('password')
    .isLength({ min: 8 })
    .matches(/[A-Z]/) // 대문자 포함
    .matches(/[0-9]/) // 숫자 포함
    .matches(/[!@#$%^&*]/), // 특수문자 포함
  (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    const { email, password } = req.body;
    const user = User.create({ email, password });
    res.json(user);
  }
);
```

### Phase 2: SQL 쿼리 안전성 (Parameterized Queries)

```javascript
// ❌ 위험: SQL Injection 취약점
const userId = req.query.id;
const query = `SELECT * FROM users WHERE id = ${userId}`;
const user = db.query(query);

// ✅ 안전: Parameterized Query
const userId = req.query.id;
const query = 'SELECT * FROM users WHERE id = ?';
const user = db.query(query, [userId]);

// ✅ 안전: ORM 사용 (Sequelize, TypeORM)
const user = await User.findByPk(userId);

// ✅ 안전: 준비된 문장 (Prepared Statements)
const mysql = require('mysql');
const connection = mysql.createConnection({...});

connection.query('SELECT * FROM users WHERE id = ?', [userId], (error, results) => {
  if (error) throw error;
  console.log(results);
});
```

### Phase 3: XSS 방지 (Output Encoding)

```javascript
// ❌ 위험: dangerouslySetInnerHTML (React)
function Comment({ content }) {
  return <div dangerouslySetInnerHTML={{ __html: content }} />;
}

// ✅ 안전: 텍스트 노드
function Comment({ content }) {
  return <div>{content}</div>; // 자동 이스케이프
}

// ❌ 위험: 문자열 연결
function Profile({ name }) {
  return `<h1>Welcome, ${name}</h1>`;
}

// ✅ 안전: HTML 이스케이프
import escapeHtml from 'escape-html';

function Profile({ name }) {
  return `<h1>Welcome, ${escapeHtml(name)}</h1>`;
}

// ✅ 안전: DOM API 사용
function Comment({ content }) {
  const div = document.createElement('div');
  div.textContent = content; // 텍스트로 설정 (HTML 파싱 X)
  return div;
}

// ❌ 위험: innerHTML
document.getElementById('output').innerHTML = userInput;

// ✅ 안전: textContent
document.getElementById('output').textContent = userInput;
```

### Phase 4: CSRF 방지 (CSRF Tokens)

```javascript
// Express with CSRF protection
const csrf = require('csurf');
const cookieParser = require('cookie-parser');
const session = require('express-session');

// CSRF 미들웨어 설정
app.use(cookieParser());
app.use(session({ secret: 'secret', resave: false, saveUninitialized: true }));
app.use(csrf({ cookie: false })); // 세션 기반 CSRF

// GET 요청: CSRF 토큰 생성
app.get('/form', (req, res) => {
  res.render('form', { csrfToken: req.csrfToken() });
});

// POST 요청: CSRF 토큰 검증 (자동)
app.post('/form', (req, res) => {
  // csrf 미들웨어가 자동으로 검증
  res.send('Form data saved');
});

// HTML 폼
<form method="POST" action="/form">
  <input type="hidden" name="_csrf" value="<%= csrfToken %>">
  <input type="text" name="username">
  <button type="submit">전송</button>
</form>

// React 예시
function MyForm() {
  const [csrfToken, setCsrfToken] = useState('');

  useEffect(() => {
    fetch('/csrf-token')
      .then(r => r.json())
      .then(data => setCsrfToken(data.token));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const response = await fetch('/api/form', {
      method: 'POST',
      headers: {
        'X-CSRF-Token': csrfToken,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ /* 데이터 */ }),
    });
  };

  return <form onSubmit={handleSubmit}>...</form>;
}
```

---

## 2️⃣ 인증 & 권한 구현

### Phase 1: 비밀번호 보안

```javascript
// ❌ 위험: 평문 비밀번호 저장
const user = User.create({
  email: email,
  password: password, // 위험!
});

// ✅ 안전: bcrypt로 해시
const bcrypt = require('bcrypt');

// 회원가입
const hashedPassword = await bcrypt.hash(password, 10);
const user = User.create({
  email: email,
  password: hashedPassword,
});

// 로그인
const isValid = await bcrypt.compare(inputPassword, user.password);
if (!isValid) {
  throw new Error('Invalid password');
}

// ✅ 안전: Argon2 (더 강력)
const argon2 = require('argon2');

const hash = await argon2.hash(password);
const isValid = await argon2.verify(hash, inputPassword);
```

### Phase 2: JWT 토큰 관리

```javascript
// ❌ 위험: 토큰 만료 없음
const token = jwt.sign({ userId: user.id }, 'secret');

// ✅ 안전: 토큰 만료 설정
const token = jwt.sign(
  { userId: user.id },
  process.env.JWT_SECRET,
  { expiresIn: '1h' } // 1시간 만료
);

// ✅ 안전: Refresh Token
const accessToken = jwt.sign(
  { userId: user.id },
  process.env.JWT_SECRET,
  { expiresIn: '15m' }
);

const refreshToken = jwt.sign(
  { userId: user.id },
  process.env.REFRESH_TOKEN_SECRET,
  { expiresIn: '7d' }
);

// 토큰 검증 미들웨어
const verifyToken = (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1];

  if (!token) {
    return res.status(401).json({ error: 'No token' });
  }

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.userId = decoded.userId;
    next();
  } catch (error) {
    if (error.name === 'TokenExpiredError') {
      return res.status(401).json({ error: 'Token expired' });
    }
    res.status(401).json({ error: 'Invalid token' });
  }
};

// 라우트에 적용
app.get('/protected', verifyToken, (req, res) => {
  res.json({ userId: req.userId });
});
```

### Phase 3: 역할 기반 접근 제어 (RBAC)

```javascript
// ❌ 위험: 권한 검증 없음
app.delete('/users/:id', (req, res) => {
  User.destroy({ where: { id: req.params.id } });
  res.json({ success: true });
});

// ✅ 안전: 권한 검증
const authorize = (...roles) => {
  return (req, res, next) => {
    if (!roles.includes(req.user.role)) {
      return res.status(403).json({ error: 'Forbidden' });
    }
    next();
  };
};

app.delete('/users/:id',
  verifyToken,
  authorize('admin'), // 관리자만 가능
  (req, res) => {
    User.destroy({ where: { id: req.params.id } });
    res.json({ success: true });
  }
);

// ✅ 안전: 리소스 소유권 검증
app.delete('/posts/:id',
  verifyToken,
  async (req, res) => {
    const post = await Post.findByPk(req.params.id);

    // 자신의 게시물만 삭제 가능
    if (post.userId !== req.userId) {
      return res.status(403).json({ error: 'Forbidden' });
    }

    await post.destroy();
    res.json({ success: true });
  }
);
```

---

## 3️⃣ 데이터 보호

### Phase 1: 민감정보 제외

```javascript
// ❌ 위험: 비밀번호, 토큰 노출
res.json(user); // { id, email, password, token, ... }

// ✅ 안전: 필요한 정보만
res.json({
  id: user.id,
  email: user.email,
  name: user.name,
  // password, token 제외
});

// ✅ 안전: exclude 옵션 사용
const user = await User.findByPk(id, {
  attributes: { exclude: ['password', 'tokenSecret'] }
});

// ✅ 안전: 직렬화 메서드
class User {
  toJSON() {
    const { password, ...rest } = this;
    return rest;
  }
}

res.json(user); // password 자동 제외
```

### Phase 2: 데이터 암호화

```javascript
// 민감한 필드 암호화
const crypto = require('crypto');

const algorithm = 'aes-256-cbc';
const key = process.env.ENCRYPTION_KEY; // 32 bytes
const iv = crypto.randomBytes(16);

function encrypt(text) {
  const cipher = crypto.createCipheriv(algorithm, key, iv);
  let encrypted = cipher.update(text, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  return iv.toString('hex') + ':' + encrypted;
}

function decrypt(text) {
  const parts = text.split(':');
  const iv = Buffer.from(parts[0], 'hex');
  const decipher = crypto.createDecipheriv(algorithm, key, iv);
  let decrypted = decipher.update(parts[1], 'hex', 'utf8');
  decrypted += decipher.final('utf8');
  return decrypted;
}

// 사용 예
const phone = '01012345678';
const encrypted = encrypt(phone);
await User.create({ email, encryptedPhone: encrypted });

const user = await User.findByPk(1);
const phone = decrypt(user.encryptedPhone);
```

### Phase 3: HTTPS 강제

```javascript
// Express: HTTPS 리다이렉트
app.use((req, res, next) => {
  if (req.header('x-forwarded-proto') !== 'https') {
    res.redirect(`https://${req.header('host')}${req.url}`);
  } else {
    next();
  }
});

// 쿠키 보안 설정
app.use(session({
  secret: 'secret',
  cookie: {
    secure: true, // HTTPS만
    httpOnly: true, // JavaScript 접근 불가
    sameSite: 'strict', // CSRF 방지
    maxAge: 3600000, // 1시간
  }
}));
```

---

## 4️⃣ 보안 헤더 설정

```javascript
// Helmet 라이브러리 사용 (권장)
const helmet = require('helmet');
app.use(helmet());

// 수동 설정
app.use((req, res, next) => {
  // XSS 방지
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');

  // 콘텐츠 보안 정책 (CSP)
  res.setHeader(
    'Content-Security-Policy',
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://trusted.com; style-src 'self' 'unsafe-inline'"
  );

  // 클릭재킹 방지
  res.setHeader('X-Frame-Options', 'SAMEORIGIN');

  // HSTS (HTTPS 강제)
  res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');

  next();
});
```

---

## 5️⃣ 파일 업로드 보안

```javascript
const multer = require('multer');
const path = require('path');

// ❌ 위험: 제한 없음
const upload = multer({ dest: 'uploads/' });

// ✅ 안전: 제약 조건 설정
const upload = multer({
  dest: 'uploads/',
  fileFilter: (req, file, cb) => {
    // 파일 타입 검증
    const allowedMimes = ['image/jpeg', 'image/png', 'application/pdf'];
    if (!allowedMimes.includes(file.mimetype)) {
      return cb(new Error('Invalid file type'));
    }

    // 파일 확장자 검증
    const allowedExts = ['.jpg', '.jpeg', '.png', '.pdf'];
    const ext = path.extname(file.originalname).toLowerCase();
    if (!allowedExts.includes(ext)) {
      return cb(new Error('Invalid file extension'));
    }

    cb(null, true);
  },
  limits: {
    fileSize: 5 * 1024 * 1024, // 5MB
    files: 1 // 1개 파일만
  }
});

app.post('/upload', upload.single('file'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'No file' });
  }

  // ✅ 안전: 파일명 변경 (원본명 미사용)
  const newFilename = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  const ext = path.extname(req.file.originalname);
  const finalPath = path.join('uploads', newFilename + ext);

  // 파일 이동
  fs.renameSync(req.file.path, finalPath);

  res.json({ path: finalPath });
});

// ✅ 더 안전: 메모리 기반 처리
const uploadMemory = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 }
});

app.post('/upload', uploadMemory.single('file'), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file' });

  // 파일 콘텐츠 검증
  const fileSignature = req.file.buffer.slice(0, 4).toString('hex');
  if (fileSignature !== 'ffd8ffe0') { // JPEG
    return res.status(400).json({ error: 'Not a JPEG' });
  }

  // S3에 업로드 등
  await uploadToS3(req.file);
  res.json({ success: true });
});
```

---

## 6️⃣ 로깅 & 모니터링

```javascript
// ❌ 위험: 민감정보 로깅
console.log('User:', { email, password, apiKey });

// ✅ 안전: 민감정보 제외
console.log('User:', { email, id }); // password, apiKey 제외

// 보안 로깅
const securityLog = require('winston');
const logger = securityLog.createLogger({
  level: 'info',
  format: securityLog.format.json(),
  transports: [
    new securityLog.transports.File({ filename: 'security.log' })
  ]
});

// 실패한 로그인 시도 기록
app.post('/login', async (req, res) => {
  const user = await User.findOne({ email: req.body.email });

  if (!user || !(await bcrypt.compare(req.body.password, user.password))) {
    logger.warn('Failed login attempt', {
      email: req.body.email,
      ip: req.ip,
      timestamp: new Date()
    });
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  logger.info('Successful login', {
    userId: user.id,
    ip: req.ip,
    timestamp: new Date()
  });

  // 로그인 성공
});

// 관리자 작업 기록
app.delete('/users/:id', verifyToken, authorize('admin'), (req, res) => {
  logger.info('User deleted by admin', {
    deletedUserId: req.params.id,
    adminId: req.userId,
    timestamp: new Date()
  });

  User.destroy({ where: { id: req.params.id } });
  res.json({ success: true });
});
```

---

## 📋 시큐어 코딩 체크리스트

### 입력값 검증
- [ ] 모든 사용자 입력이 검증되는가?
- [ ] SQL 쿼리에 Parameterized Query를 사용하는가?
- [ ] 파일 업로드가 제한되는가 (크기, 타입)?
- [ ] 파일명이 변경되는가?

### 출력 인코딩
- [ ] XSS 취약점 없는가?
- [ ] dangerouslySetInnerHTML 사용 없는가?
- [ ] innerHTML 직접 할당 없는가?

### 인증/권한
- [ ] 비밀번호가 bcrypt/argon2로 해시되는가?
- [ ] JWT 토큰에 만료시간이 있는가?
- [ ] 모든 권한 검증 엔드포인트에 인증이 있는가?
- [ ] 리소스 소유권이 검증되는가?

### 데이터 보호
- [ ] 민감정보가 응답에서 제외되는가?
- [ ] HTTPS가 강제되는가?
- [ ] 쿠키가 HttpOnly/Secure로 설정되는가?
- [ ] 민감한 필드가 암호화되는가?

### CSRF/CORS
- [ ] CSRF 토큰이 사용되는가?
- [ ] CORS가 올바르게 설정되는가?
- [ ] SameSite 쿠키 속성이 설정되는가?

### 보안 헤더
- [ ] CSP 헤더가 설정되는가?
- [ ] X-Frame-Options가 설정되는가?
- [ ] X-Content-Type-Options가 설정되는가?
- [ ] HSTS가 설정되는가?

### 로깅
- [ ] 보안 이벤트가 기록되는가?
- [ ] 실패한 로그인이 기록되는가?
- [ ] 관리자 작업이 기록되는가?
- [ ] 민감정보가 로그에 포함되지 않는가?
