# Skills Automation Setup Guide

**Setup Date**: 2026-02-27
**Version**: 1.0.0
**Status**: ✅ Ready for Use

---

## 🎯 Quick Start (5분)

### 1. 필수 도구 설치

```bash
# jq 설치 (필수)
sudo apt-get install jq    # Linux
brew install jq             # macOS
```

### 2. 훅 활성화

```bash
cd D:\gitlab\project\KnowledgeBase\02_skills

# 훅 실행 권한 설정
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/post-merge
chmod +x myskills/scripts/*.sh

# 확인
ls -la .git/hooks/pre-commit  # -rwxr-xr-x 확인
```

### 3. 테스트

```bash
# 드라이런 (변경 없음)
./myskills/scripts/update-index.sh --dry-run

# 결과: 스크립트가 작동하면 성공!
```

---

## 📁 설치된 파일 목록

### Git Hooks (자동 트리거)
```
.git/hooks/
├── pre-commit    (커밋 직전에 자동 실행)
└── post-merge    (merge/pull 후 자동 실행)
```

### 자동화 스크립트
```
myskills/scripts/
├── update-index.sh  (skills_index.json 생성)
├── sync-claude.sh   (CLAUDE.md 동기화)
├── README.md        (상세 문서)
└── [이 파일]
```

### 생성되는 메타데이터
```
myskills/
├── skills_index.json  (자동 생성, git 추적)
└── [기존 스킬들]
```

### 업데이트되는 문서
```
CLAUDE.md  (자동 동기화, git 추적)
```

---

## 🔄 동작 원리

### Pre-commit Hook (커밋 직전)

```
git add myskills/*/SKILL.md
    ↓
git commit -m "Update skill"
    ↓
[pre-commit hook 자동 실행]
    ├─ myskills 변경 감지
    ├─ update-index.sh 실행 → skills_index.json 재생성
    ├─ sync-claude.sh 실행 → CLAUDE.md 동기화
    ├─ 변경된 파일 자동 스테이징
    └─ 커밋 진행
    ↓
✅ 커밋 완료 (모든 파일 동기화됨)
```

### Post-merge Hook (merge/pull 후)

```
git pull origin main
    ↓
[post-merge hook 자동 실행]
    ├─ merge된 myskills 변경 감지
    ├─ update-index.sh 실행 → 인덱스 업데이트
    ├─ sync-claude.sh 실행 → CLAUDE.md 동기화
    ├─ 변경사항 요약 표시
    └─ 사용자에게 다음 단계 안내
    ↓
👤 사용자 검토 & 커밋
    ↓
✅ 커밋 완료
```

---

## 💡 일상적인 사용법

### 새 스킬 추가

```bash
# 1. 스킬 디렉토리 생성
mkdir myskills/my-awesome-skill

# 2. SKILL.md 작성
cat > myskills/my-awesome-skill/SKILL.md <<'EOF'
---
name: my-awesome-skill
description: What this skill does
version: 1.0.0
created: 2026-02-27
category: development
platforms: [claude-code]
tags: [example, new]
---

# My Awesome Skill
[내용...]
EOF

# 3. git에 추가 & 커밋
git add myskills/my-awesome-skill/SKILL.md
git commit -m "Add my-awesome-skill"

# 🎉 결과: 자동으로 다음이 수행됨:
# - skills_index.json 생성/업데이트
# - CLAUDE.md에 스킬 정보 추가
# - 변경된 파일 자동 스테이징
```

### 스킬 버전 업데이트

```bash
# 1. SKILL.md 수정
vi myskills/ai-team-works/SKILL.md
# version: 2.0.0 → version: 2.1.0

# 2. 커밋
git add myskills/ai-team-works/SKILL.md
git commit -m "Update ai-team-works to v2.1.0"

# 🎉 결과: 버전 번호 자동으로 모든 문서에 반영됨
```

### 팀원 스킬 가져오기

```bash
# 1. 원격에서 pull
git pull origin main

# ℹ️ 자동으로 post-merge 훅이 실행되고:
# [post-merge] === myskills merge 후 자동 동기화 ===
# ✓ 스킬 인덱스 업데이트 완료
# ✓ CLAUDE.md 동기화 완료
#
# 다음 단계:
#   1️⃣  변경사항 확인: git diff myskills/skills_index.json
#   2️⃣  변경사항이 정확하면: git add ... && git commit -m "Update skills"

# 2. 변경사항 검토
git diff myskills/skills_index.json
git diff CLAUDE.md

# 3. 승인 및 커밋
git add myskills/skills_index.json CLAUDE.md
git commit -m "Update skills after merge"
```

---

## 📊 자동화 범위

### 자동 생성되는 파일

| 파일 | 생성 방식 | 업데이트 시점 | 추적 |
|------|---------|-------------|------|
| `skills_index.json` | update-index.sh | pre-commit/post-merge | ✅ git |
| `CLAUDE.md` (일부) | sync-claude.sh | pre-commit/post-merge | ✅ git |

### 감지하는 변경사항

- ✅ 새 스킬 추가 (SKILL.md 생성)
- ✅ 스킬 메타데이터 변경 (version, category, tags 등)
- ✅ 스킬 설명 변경 (description)
- ✅ 플랫폼/카테고리 변경
- ✅ CHANGELOG 변경

### 동기화되는 섹션

**CLAUDE.md에서:**
1. **Key Directories** - myskills 개요
2. **Custom Skills in myskills/** - 스킬 상세 정보
3. **Statistics** - 마지막 업데이트 날짜

---

## ⚙️ 고급 사용법

### 수동 실행 (훅 없이)

```bash
# 1. 인덱스만 재생성
./myskills/scripts/update-index.sh

# 2. CLAUDE.md만 동기화
./myskills/scripts/sync-claude.sh

# 3. 특정 섹션만 동기화
./myskills/scripts/sync-claude.sh --section architecture
```

### 훅 임시 비활성화

```bash
# 특정 커밋에서 훅 무시
git commit --no-verify -m "WIP: Skip hooks"

# 또는 환경 변수
SKIP_HOOKS=1 git commit -m "message"
```

### 드라이런 모드

```bash
# 변경 없이 미리보기
./myskills/scripts/update-index.sh --dry-run
./myskills/scripts/sync-claude.sh --dry-run
```

### 파일 변경 모니터링

```bash
# 연속 감시 (inotifywait 필요)
./myskills/scripts/update-index.sh --watch

# 결과: SKILL.md 파일이 변경될 때마다 자동으로 인덱스 생성
```

---

## 🐛 문제 해결

### 훅이 실행되지 않음

```bash
# 1. 권한 확인
ls -la .git/hooks/pre-commit
# -rwxr-xr-x 확인 (x = executable)

# 2. 권한 설정
chmod +x .git/hooks/pre-commit .git/hooks/post-merge

# 3. 다시 시도
git commit -m "test"
```

### "jq not found" 에러

```bash
# jq 설치
sudo apt-get install jq    # Linux
brew install jq             # macOS
# Windows: WSL 또는 Git Bash에서 위 명령어 사용
```

### skills_index.json 업데이트 안 됨

```bash
# 수동으로 재생성
./myskills/scripts/update-index.sh

# 변경사항 확인
git diff myskills/skills_index.json

# 커밋
git add myskills/skills_index.json
git commit -m "Regenerate skills index"
```

### CLAUDE.md 동기화 실패

```bash
# 수동으로 동기화
./myskills/scripts/sync-claude.sh

# 드라이런으로 문제 확인
./myskills/scripts/sync-claude.sh --dry-run

# 변경사항 검토
git diff CLAUDE.md
```

---

## 📋 체크리스트

설치 후 다음을 확인하세요:

- [ ] jq 설치됨 (`which jq`)
- [ ] 훅 실행 권한 설정됨 (`ls -la .git/hooks/`)
- [ ] update-index.sh 테스트 성공 (`./myskills/scripts/update-index.sh --dry-run`)
- [ ] sync-claude.sh 테스트 성공 (`./myskills/scripts/sync-claude.sh --dry-run`)
- [ ] skills_index.json이 git 추적 중 (`git status`)
- [ ] CLAUDE.md가 git 추적 중 (`git status`)

---

## 📚 추가 문서

- **상세 가이드**: `myskills/scripts/README.md`
- **프로젝트 가이드**: `CLAUDE.md`
- **메모리**: `C:\Users\wskyl\.claude\projects\D--gitlab-project\memory\skills-automation.md`
- **훅 소스**: `.git/hooks/pre-commit`, `.git/hooks/post-merge`

---

## 🎉 완료!

자동화 시스템이 설치되었습니다!

이제 스킬을 추가하거나 수정할 때마다:
1. **자동으로** skills_index.json이 생성/업데이트됨
2. **자동으로** CLAUDE.md가 동기화됨
3. **수동으로** 변경사항을 커밋하면 끝!

더 이상 수동으로 여러 파일을 업데이트할 필요가 없습니다! 🚀

---

**Setup Date**: 2026-02-27
**Status**: ✅ Production Ready
**Support**: See `myskills/scripts/README.md` for detailed documentation
