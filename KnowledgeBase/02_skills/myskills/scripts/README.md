# myskills 자동화 시스템

스킬이 변경될 때 `skills_index.json`과 `CLAUDE.md`를 자동으로 동기화하는 이벤트 기반 자동화 시스템입니다.

## 📋 목차

1. [개요](#개요)
2. [설치](#설치)
3. [사용 방법](#사용-방법)
4. [자동화 시나리오](#자동화-시나리오)
5. [문제 해결](#문제-해결)

---

## 개요

### 문제점

기존 방식에서는:
- 새 스킬 추가 후 `skills_index.json` 수동 업데이트
- CLAUDE.md의 스킬 목록도 수동 업데이트
- 버전 변경, 카테고리 수정 시 여러 파일 동시 수정
- 휴먼 에러로 인한 불일치 발생 가능

### 솔루션

**3가지 자동화 스크립트 + 2가지 git 훅**으로 완전 자동화:

```
스킬 변경 감지
    ↓
[pre-commit 훅] → update-index.sh → skills_index.json 자동 생성
                → sync-claude.sh → CLAUDE.md 자동 동기화
    ↓
파일 자동 스테이징 & 커밋 진행
```

---

## 설치

### 1단계: 필수 도구 설치

```bash
# Linux
sudo apt-get install jq

# macOS
brew install jq

# Windows (Git Bash / WSL)
# jq를 이미 설치했다면 스킵
```

### 2단계: git 훅 활성화

```bash
cd D:\gitlab\project\KnowledgeBase\02_skills

# 훅 스크립트 실행 권한 설정
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/post-merge

# myskills 스크립트 권한 설정
chmod +x myskills/scripts/update-index.sh
chmod +x myskills/scripts/sync-claude.sh
```

### 3단계: 설치 확인

```bash
# 훅이 설치되었는지 확인
ls -la .git/hooks/pre-commit
ls -la .git/hooks/post-merge

# 실행 권한 확인
file .git/hooks/pre-commit
# 출력: ... shell script ... executable
```

---

## 사용 방법

### 시나리오 1: 새 스킬 추가

```bash
# 1. 새 스킬 디렉토리 생성
mkdir myskills/my-new-skill

# 2. SKILL.md 작성
cat > myskills/my-new-skill/SKILL.md <<'EOF'
---
name: my-new-skill
description: My awesome new skill
version: 1.0.0
created: 2026-02-27
category: development
platforms: [claude-code]
tags: [example, new]
---

# My New Skill
...
EOF

# 3. git에 추가
git add myskills/my-new-skill/SKILL.md

# 4. 커밋 (자동 훅 실행)
git commit -m "Add new skill: my-new-skill"

# 결과: 자동으로 skills_index.json과 CLAUDE.md 업데이트됨
```

### 시나리오 2: 스킬 버전 업데이트

```bash
# 1. SKILL.md 수정
vi myskills/ai-team-works/SKILL.md
# version: 2.0.0 → version: 2.1.0로 변경

# 2. git 스테이징
git add myskills/ai-team-works/SKILL.md

# 3. 커밋
git commit -m "Update ai-team-works to v2.1.0"

# 결과: skills_index.json 자동 업데이트, CLAUDE.md 버전 동기화
```

### 시나리오 3: 원격 저장소에서 pull

```bash
# 원격 저장소에서 다른 팀원이 추가한 스킬 가져오기
git pull origin main

# 결과: post-merge 훅이 자동 실행
# - myskills 변경 감지
# - skills_index.json 업데이트
# - CLAUDE.md 동기화
# - 사용자 알림 표시
```

### 시나리오 4: 스킬 카테고리 변경

```bash
# 카테고리 변경
vi myskills/info-collector-analyst/SKILL.md
# category: analysis → category: system-design

git add myskills/info-collector-analyst/SKILL.md
git commit -m "Change info-collector-analyst category to system-design"

# 결과: CLAUDE.md의 카테고리도 자동 업데이트
```

---

## 자동화 시나리오

### 📌 Pre-commit 훅 (커밋 직전)

**트리거:**
- `myskills/*/SKILL.md` 파일 변경
- `myskills/*/CHANGELOG.md` 파일 변경
- 새 스킬 디렉토리 추가

**실행 순서:**
1. 변경된 스킬 감지
2. `update-index.sh` 실행 → `skills_index.json` 재생성
3. `sync-claude.sh` 실행 → `CLAUDE.md` 동기화
4. 변경된 파일 자동 스테이징
5. 커밋 진행

**예시:**
```bash
$ git commit -m "Update skill version"

[pre-commit] === myskills 변경 감지 & 자동 업데이트 ===
[pre-commit] 스킬 인덱스 업데이트 중...
✓ 스킬 인덱스 업데이트 완료
[pre-commit] CLAUDE.md 동기화 중...
✓ CLAUDE.md 동기화 완료
✓ 2개 파일 스테이징

[main 1a2b3c4] Update skill version
 3 files changed, 15 insertions(+), 10 deletions(-)
```

### 📌 Post-merge 훅 (merge/pull 후)

**트리거:**
- `git merge`
- `git pull`
- 원격의 myskills 변경사항 가져옴

**실행 순서:**
1. merge된 파일 확인
2. myskills 변경사항 표시
3. `update-index.sh` 실행
4. `sync-claude.sh` 실행
5. 변경사항 요약 및 사용자 알림

**예시:**
```bash
$ git pull origin main

Updating 1a2b3c4..d5e6f7g
Fast-forward
 myskills/ai-team-works/SKILL.md | 2 +-
 myskills/skills_index.json      | 10 +++++-----
 1 file changed, 6 insertions(+), 4 deletions(-)

[post-merge] === myskills merge 후 자동 동기화 ===
[post-merge] 스킬 인덱스 업데이트 중...
✓ 스킬 인덱스 업데이트 완료
[post-merge] CLAUDE.md 동기화 중...
✓ CLAUDE.md 동기화 완료

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠  myskills 변경 감지됨
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

다음 단계:
  1️⃣  변경사항 확인:
     git diff myskills/skills_index.json
     git diff CLAUDE.md

  2️⃣  변경사항이 정확하면 커밋:
     git add myskills/skills_index.json CLAUDE.md
     git commit -m "Update skills index after merge"
```

---

## 스크립트 상세 사용법

### update-index.sh

**목적:** SKILL.md 파일들을 스캔하여 `skills_index.json` 자동 생성

```bash
# 전체 인덱스 생성
./myskills/scripts/update-index.sh

# 드라이런 (변경 없음, 미리보기만)
./myskills/scripts/update-index.sh --dry-run

# 파일 변경 모니터링 (연속 감시)
./myskills/scripts/update-index.sh --watch
```

**출력:**
```
[2026-02-27 10:30:45] === myskills 인덱스 업데이터 시작 ===
[2026-02-27 10:30:45] 스킬 인덱스 생성 시작...
[2026-02-27 10:30:45]   파싱 중: ai_team_works
[2026-02-27 10:30:45]   파싱 중: skill-creator
[2026-02-27 10:30:45]   파싱 중: skill-creator-ext
[2026-02-27 10:30:45]   파싱 중: info-collector-analyst
✓ 인덱스 생성 완료: myskills/skills_index.json
✓ 스킬 수: 4개
```

### sync-claude.sh

**목적:** `skills_index.json` 기반으로 CLAUDE.md 자동 동기화

```bash
# 전체 동기화
./myskills/scripts/sync-claude.sh

# 드라이런
./myskills/scripts/sync-claude.sh --dry-run

# 특정 섹션만 동기화
./myskills/scripts/sync-claude.sh --section key-dirs      # Key Directories
./myskills/scripts/sync-claude.sh --section architecture  # Architecture
./myskills/scripts/sync-claude.sh --section stats         # Statistics
```

**동기화되는 섹션:**
1. **Key Directories** - myskills 개요
2. **Architecture** - 스킬 상세 설명
3. **Statistics** - 최종 업데이트 날짜

---

## 고급 사용법

### 훅 임시 비활성화

특정 커밋에서 훅을 실행하지 않으려면:

```bash
# pre-commit 훅 우회
git commit --no-verify -m "WIP: Skip hook"

# 또는 환경 변수로 비활성화
SKIP_HOOKS=1 git commit -m "message"
```

### 수동 업데이트

자동 훅 없이 수동으로 업데이트:

```bash
# 1. 인덱스 수동 생성
cd myskills/scripts
bash ./update-index.sh

# 2. CLAUDE.md 수동 동기화
bash ./sync-claude.sh

# 3. 변경사항 확인
git diff myskills/skills_index.json
git diff CLAUDE.md

# 4. 커밋 (훅 실행 안 함)
git add myskills/skills_index.json CLAUDE.md
git commit --no-verify -m "Manual update"
```

### 스킬 대량 추가

여러 스킬을 한 번에 추가:

```bash
# 1. 스킬들 생성
mkdir -p myskills/{skill-1,skill-2,skill-3}
# ... SKILL.md 작성 ...

# 2. 한 번에 추가
git add myskills/skill-{1,2,3}/SKILL.md

# 3. 커밋 (자동으로 한 번만 update-index 실행)
git commit -m "Add 3 new skills"
```

---

## 문제 해결

### Q1: "jq를 찾을 수 없습니다" 에러

```bash
# 설치
# Linux:
sudo apt-get install jq

# macOS:
brew install jq

# Windows (WSL):
sudo apt-get install jq
```

### Q2: 훅이 실행되지 않음

```bash
# 훅 실행 권한 확인
ls -la .git/hooks/
# 출력: -rwxr-xr-x (x 확인)

# 권한 설정
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/post-merge
```

### Q3: "git 저장소 없음" 에러

프로젝트가 git 저장소여야 합니다:

```bash
cd D:\gitlab\project\KnowledgeBase\02_skills
git init  # 이미 되어있어야 함
```

### Q4: skills_index.json이 업데이트되지 않음

수동으로 실행:

```bash
./myskills/scripts/update-index.sh --dry-run
# 문제 확인

./myskills/scripts/update-index.sh
# 강제 재생성
```

### Q5: CLAUDE.md 동기화 실패

```bash
# 에러 메시지 확인
./myskills/scripts/sync-claude.sh --dry-run

# 문제가 있으면 수동 수정 후:
git add CLAUDE.md
git commit -m "Manual CLAUDE.md update"
```

---

## 모니터링 & 로깅

### 훅 로그 확인

```bash
# 마지막 커밋 메시지 확인
git log -1

# 변경사항 확인
git diff HEAD~1

# 스테이징된 파일 확인
git diff --cached
```

### 자동 갱신 로그 (옵션)

로그를 파일에 저장하려면 훅 스크립트 수정:

```bash
# pre-commit 훅에 추가
exec >> /tmp/myskills-hook.log 2>&1
echo "=== Pre-commit Hook $(date) ==="

# 로그 확인
tail -f /tmp/myskills-hook.log
```

---

## 워크플로우 요약

### 일상적인 스킬 개발

```
1. 새 스킬 작성 또는 기존 스킬 수정
   ↓
2. SKILL.md 파일 저장
   ↓
3. git add myskills/my-skill/SKILL.md
   ↓
4. git commit -m "Update skill"
   ↓
5. 🤖 자동 훅 실행:
   - update-index.sh 실행
   - sync-claude.sh 실행
   - 파일 자동 스테이징
   - 커밋 완료
   ↓
6. ✅ skills_index.json & CLAUDE.md 자동 동기화 완료!
```

### 팀 협업 워크플로우

```
팀원 A: 새 스킬 추가 & 커밋 & push
   ↓
팀원 B: git pull origin main
   ↓
🤖 post-merge 훅 자동 실행:
   - 변경사항 감지
   - 인덱스 & CLAUDE.md 동기화
   - 사용자 알림
   ↓
팀원 B: 변경사항 검토 & 커밋
   ↓
✅ 모든 파일 동기화 완료!
```

---

## 참고사항

- **보안**: 훅 스크립트는 신뢰할 수 있는 저장소에서만 실행하세요
- **성능**: 대량의 스킬(100+)이 있을 경우 인덱스 생성에 시간 소요
- **호환성**: Bash 4.0 이상 필요 (거의 모든 시스템에서 지원)
- **윈도우**: WSL (Windows Subsystem for Linux) 또는 Git Bash에서 실행 권장

---

## 추가 리소스

- 📄 [CLAUDE.md](../CLAUDE.md) - 프로젝트 가이드
- 📋 [skills_index.json](../skills_index.json) - 스킬 메타데이터
- 🔧 [SKILL.md 템플릿](../../antigravity-skills/template/SKILL.md)

---

**Last Updated**: 2026-02-27
**Version**: 1.0.0
