# Skills Synchronization Modes Guide

**Version**: 2.0.0
**Created**: 2026-02-27
**Status**: ✅ Production Ready

---

## 📋 목차

1. [개요](#개요)
2. [두 가지 모드](#두-가지-모드)
3. [모드 비교](#모드-비교)
4. [설치 & 설정](#설치--설정)
5. [사용 방법](#사용-방법)
6. [모드 전환](#모드-전환)
7. [실전 예시](#실전-예시)

---

## 개요

**동기화 모드**는 `skills_index.json`과 `CLAUDE.md`가 언제 업데이트되는지 제어합니다.

- **자동 모드 (Auto)**: Git hooks가 자동으로 동기화
- **수동 모드 (Manual)**: 사용자가 명시적으로 명령어를 실행할 때만 동기화

설정 파일: `.claude-skills-config`

---

## 두 가지 모드

### 🔄 자동 모드 (Auto Mode)

**특징:**
- Git hooks가 커밋/병합 시 자동으로 동기화
- 개발자 개입 최소화
- 항상 문서가 최신 상태 유지

**언제 사용:**
- 팀 전체가 함께 작업하는 경우
- 문서를 항상 최신 상태로 유지하고 싶을 때
- 자동화를 선호하는 팀

**동작 흐름:**
```
git add SKILL.md
    ↓
git commit
    ↓
[pre-commit 훅] ⚡
├─ 변경 감지
├─ 인덱스 생성
├─ CLAUDE.md 동기화
└─ 커밋 완료
    ↓
✅ 모든 파일 자동 동기화!
```

---

### 🎮 수동 모드 (Manual Mode)

**특징:**
- 개발자가 명시적으로 동기화 명령어 실행
- 완전한 타이밍 제어
- 선택적 동기화 가능

**언제 사용:**
- 동기화 타이밍을 정교하게 제어하고 싶을 때
- 여러 스킬을 한 번에 추가한 후 동기화하고 싶을 때
- 테스트 후에만 동기화하고 싶을 때

**동작 흐름:**
```
git add SKILL.md
    ↓
git commit
    ↓
[pre-commit 훅] → 스킵 (수동 모드)
    ↓
개발자가 명시적으로 실행:
./myskills/scripts/sync-cli.sh
    ↓
[sync-cli.sh 실행]
├─ 변경 감지
├─ 인덱스 생성
├─ CLAUDE.md 동기화
└─ 변경사항 표시
    ↓
개발자가 검토 & 커밋
    ↓
✅ 수동 제어로 동기화 완료!
```

---

## 모드 비교

| 항목 | 자동 모드 | 수동 모드 |
|------|---------|---------|
| **자동 실행** | ✅ Git hooks 자동 | ❌ 수동 명령어 |
| **타이밍** | 매 커밋마다 | 사용자 선택 |
| **편의성** | 높음 | 중간 |
| **제어** | 낮음 | 높음 |
| **실행 속도** | 느림 (매번) | 빠름 (선택적) |
| **문서 최신성** | 항상 최신 | 수동 관리 |
| **팀 협업** | 추천 | 정교한 제어 |
| **학습곡선** | 쉬움 | 중간 |
| **에러 관리** | 자동 처리 | 수동 검토 |

---

## 설치 & 설정

### 빠른 설치 (권장)

**Step 1: 설치 스크립트 실행**

```bash
cd D:\gitlab\project\KnowledgeBase\02_skills
./myskills/scripts/install-sync-mode.sh
```

**Step 2: 대화형 메뉴에서 선택**

```
1) 자동 모드 (권장)
2) 수동 모드
3) 나중에 결정
```

**Step 3: 설정 저장**

```bash
git add .claude-skills-config
git commit -m "Configure skills sync mode"
```

---

### 수동 설정

**Option A: 자동 모드로 설치**

```bash
./myskills/scripts/install-sync-mode.sh auto
```

**Option B: 수동 모드로 설치**

```bash
./myskills/scripts/install-sync-mode.sh manual
```

---

## 사용 방법

### 자동 모드 사용법

```bash
# 1. 스킬 추가/수정
mkdir myskills/new-skill
cat > myskills/new-skill/SKILL.md <<'EOF'
---
name: new-skill
description: My awesome skill
version: 1.0.0
---
# Content...
EOF

# 2. 커밋 (자동으로 모든 것이 동기화됨)
git add myskills/new-skill/SKILL.md
git commit -m "Add new-skill"

# 결과: 🎉
# ✓ skills_index.json 자동 생성
# ✓ CLAUDE.md 자동 동기화
# ✓ 파일 자동 스테이징
```

**수동으로도 동기화 가능:**
```bash
# 필요시 수동 동기화
./myskills/scripts/sync-cli.sh
```

---

### 수동 모드 사용법

```bash
# 1. 스킬 추가/수정
mkdir myskills/new-skill
# SKILL.md 작성...

# 2. 커밋 (동기화는 아직 안 함)
git add myskills/new-skill/SKILL.md
git commit -m "Add new-skill"

# 3. 수동으로 동기화 명령어 실행
./myskills/scripts/sync-cli.sh

# 또는 대화형 메뉴
./myskills/scripts/sync-cli.sh      # 대화형 메뉴
./myskills/scripts/sync-cli.sh sync # 전체 동기화
./myskills/scripts/sync-cli.sh index # 인덱스만
./myskills/scripts/sync-cli.sh claude # CLAUDE.md만

# 4. 변경사항 검토
git diff myskills/skills_index.json
git diff CLAUDE.md

# 5. 커밋
git add myskills/skills_index.json CLAUDE.md
git commit -m "Sync skills (manual mode)"
```

---

## 모드 전환

### 현재 모드 확인

```bash
./myskills/scripts/sync-cli.sh status
```

**출력 예:**
```
현재 모드: 자동 동기화
  • git hooks가 자동으로 실행됨
  • 이 명령어는 수동으로 명시적 동기화를 할 때 사용
```

---

### 자동 → 수동으로 전환

```bash
./myskills/scripts/sync-cli.sh manual
```

또는:

```bash
./myskills/scripts/install-sync-mode.sh manual
```

**설정 저장:**
```bash
git add .claude-skills-config
git commit -m "Switch to manual sync mode"
```

---

### 수동 → 자동으로 전환

```bash
./myskills/scripts/sync-cli.sh auto
```

또는:

```bash
./myskills/scripts/install-sync-mode.sh auto
```

**설정 저장:**
```bash
git add .claude-skills-config
git commit -m "Switch to auto sync mode"
```

---

## 실전 예시

### 시나리오 1: 자동 모드 - 새 스킬 추가

```bash
# 1️⃣  스킬 생성
$ mkdir myskills/my-awesome-skill
$ cat > myskills/my-awesome-skill/SKILL.md <<EOF
---
name: my-awesome-skill
description: Does something awesome
version: 1.0.0
category: development
---
# My Awesome Skill
EOF

# 2️⃣  커밋
$ git add myskills/my-awesome-skill/SKILL.md
$ git commit -m "Add my-awesome-skill"

[pre-commit] === myskills 변경 감지 & 자동 업데이트 ===
[pre-commit] 스킬 인덱스 생성 중...
✓ 스킬 인덱스 생성 완료
[pre-commit] CLAUDE.md 동기화 중...
✓ CLAUDE.md 동기화 완료
✓ 2개 파일 스테이징

[main 1a2b3c4] Add my-awesome-skill
 3 files changed, 25 insertions(+)
 create mode 100644 myskills/my-awesome-skill/SKILL.md

# ✅ 완료! 모든 파일이 자동으로 동기화됨
```

---

### 시나리오 2: 수동 모드 - 버전 업데이트

```bash
# 1️⃣  버전 변경
$ vi myskills/ai-team-works/SKILL.md
# version: 2.0.0 → version: 2.1.0

# 2️⃣  커밋
$ git add myskills/ai-team-works/SKILL.md
$ git commit -m "Update ai-team-works to v2.1.0"

[main 5d6e7f8] Update ai-team-works to v2.1.0
 1 file changed, 1 insertion(+)
# (자동으로 동기화되지 않음)

# 3️⃣  수동으로 동기화
$ ./myskills/scripts/sync-cli.sh

╔════════════════════════════════════════════════════════════════════════════╗
║                   스킬 동기화 CLI                                          ║
╚════════════════════════════════════════════════════════════════════════════╝

현재 모드: 수동 동기화
  • git hooks가 비활성화됨
  • 명시적으로 이 명령어로 동기화해야 함

이 명령어는 무엇을 할까요?
  1) 전체 동기화 (권장)
  2) 스킬 인덱스만 동기화
  3) CLAUDE.md만 동기화
  4) 현재 상태 확인
  5) 동기화 모드 변경
  6) 도움말

선택 (1-6): 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 변경사항 요약

  skills_index.json updated

# 4️⃣  변경사항 검토
$ git diff myskills/skills_index.json
# 변경사항 확인

# 5️⃣  커밋
$ git add myskills/skills_index.json
$ git commit -m "Sync skills index after version update"

[main 9a0b1c2] Sync skills index after version update
 1 file changed, 1 insertion(+)

# ✅ 완료! 수동으로 제어하면서 동기화됨
```

---

### 시나리오 3: 팀 협업 - 여러 스킬 한 번에 추가

**수동 모드가 유리한 경우:**

```bash
# 👥 팀 프로젝트: 5개의 새로운 스킬 추가

# Day 1: 스킬 1, 2 추가
mkdir myskills/skill-{1,2}
# SKILL.md 작성...
git add myskills/skill-{1,2}/SKILL.md
git commit -m "Add skills 1 and 2"
# (자동 동기화 안 함, 수동 모드)

# Day 2: 스킬 3, 4 추가
mkdir myskills/skill-{3,4}
# SKILL.md 작성...
git add myskills/skill-{3,4}/SKILL.md
git commit -m "Add skills 3 and 4"
# (자동 동기화 안 함)

# Day 3: 스킬 5 추가 + 테스트
mkdir myskills/skill-5
# SKILL.md 작성...
git add myskills/skill-5/SKILL.md
git commit -m "Add skill 5"

# Day 4: 모든 스킬 테스트 완료 후 한 번에 동기화
$ ./myskills/scripts/sync-cli.sh

# 결과: 5개의 새로운 스킬이 한 번의 동기화로 반영
# ✅ 구조화된 개발 프로세스 완성!
```

---

## 고급 사용법

### 특정 섹션만 동기화 (수동 모드)

```bash
# 인덱스만 동기화
./myskills/scripts/sync-cli.sh index

# CLAUDE.md만 동기화
./myskills/scripts/sync-cli.sh claude
```

---

### 설정 파일 직접 수정

```bash
# 설정 파일 열기
vi .claude-skills-config

# 변경 가능한 설정
SYNCHRONIZATION_MODE=auto          # auto or manual
AUTO_ENABLE_PRE_COMMIT=true        # 훅 활성화
AUTO_ENABLE_POST_MERGE=true        # 병합 훅 활성화
SHOW_SYNC_NOTIFICATION=true        # 알림 표시
VALIDATE_SKILLS=true               # 검증 수행

# 저장
git add .claude-skills-config
git commit -m "Update sync configuration"
```

---

### 훅 임시 우회

자동 모드에서 훅을 한 번 스킵하고 싶을 때:

```bash
# --no-verify 플래그로 우회
git commit --no-verify -m "WIP: Skip hooks"
```

---

## 모드 선택 가이드

### 자동 모드를 선택하세요 👉 if:
- ✅ 팀 전체가 협업하는 경우
- ✅ 문서를 항상 최신으로 유지하고 싶을 때
- ✅ 개발자 개입을 최소화하고 싶을 때
- ✅ 초보자 팀

### 수동 모드를 선택하세요 👉 if:
- ✅ 동기화 타이밍을 정교하게 제어하고 싶을 때
- ✅ 여러 스킬을 한 번에 작업한 후 동기화하고 싶을 때
- ✅ 테스트 후에만 동기화하고 싶을 때
- ✅ 복잡한 멀티-팀 프로젝트
- ✅ 고급 사용자

---

## 문제 해결

### Q: 자동 모드인데 동기화가 안 됨

```bash
# 1. 설정 확인
./myskills/scripts/sync-cli.sh status

# 2. 훅 권한 확인
ls -la .git/hooks/pre-commit
# -rwxr-xr-x 확인

# 3. 권한 설정
chmod +x .git/hooks/pre-commit .git/hooks/post-merge

# 4. 다시 커밋
git commit --amend -m "message" --no-verify
git commit -m "test commit"
```

---

### Q: 수동 모드에서 동기화 명령어 안 먹힘

```bash
# 1. 스크립트 존재 확인
ls -la myskills/scripts/sync-cli.sh

# 2. 권한 확인
ls -la myskills/scripts/sync-cli.sh
# -rwxr-xr-x 확인

# 3. 권한 설정
chmod +x myskills/scripts/sync-cli.sh

# 4. 다시 실행
./myskills/scripts/sync-cli.sh
```

---

### Q: 모드를 잘못 선택했어요

```bash
# 모드 다시 선택
./myskills/scripts/install-sync-mode.sh

# 또는 직접 전환
./myskills/scripts/sync-cli.sh auto    # → 자동 모드
./myskills/scripts/sync-cli.sh manual  # → 수동 모드

# 설정 저장
git add .claude-skills-config
git commit -m "Change sync mode"
```

---

## 요약

| 상황 | 추천 모드 | 명령어 |
|------|----------|-------|
| 팀 협업 | 자동 | `install-sync-mode.sh auto` |
| 개인 프로젝트 | 수동 | `install-sync-mode.sh manual` |
| 정확한 제어 | 수동 | `sync-cli.sh` |
| 빠른 개발 | 자동 | (자동 실행) |
| 테스트 후 배포 | 수동 | `sync-cli.sh sync` |

---

## 다음 단계

1. **설치**: `./myskills/scripts/install-sync-mode.sh`
2. **확인**: `./myskills/scripts/sync-cli.sh status`
3. **사용**: 스킬을 추가하고 커밋 또는 동기화
4. **전환**: 필요시 `./myskills/scripts/sync-cli.sh auto/manual`

---

**Created**: 2026-02-27
**Version**: 2.0.0
**Status**: ✅ Production Ready
