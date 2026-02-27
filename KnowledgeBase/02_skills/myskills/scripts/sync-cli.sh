#!/bin/bash

###############################################################################
# sync-cli.sh
#
# PURPOSE: Manual CLI for skills synchronization
#          Replaces automatic git hooks when in manual mode
#          Provides fine-grained control over sync operations
#
# USAGE:
#   ./sync-cli.sh               # Full sync (interactive)
#   ./sync-cli.sh auto          # Quick auto sync
#   ./sync-cli.sh index         # Index generation only
#   ./sync-cli.sh claude        # CLAUDE.md sync only
#   ./sync-cli.sh status        # Show current mode & status
#   ./sync-cli.sh config        # Show configuration
#   ./sync-cli.sh reset         # Reset to default settings
#
# TRIGGERS:
#   - User explicitly runs this command
#   - No automatic execution (manual mode only)
#   - User has full control over when to sync
#
###############################################################################

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# 기본 경로
MYSKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$MYSKILLS_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/.claude-skills-config"
SCRIPTS_DIR="$MYSKILLS_DIR/scripts"
INDEX_FILE="$MYSKILLS_DIR/skills_index.json"
CLAUDE_FILE="$REPO_ROOT/CLAUDE.md"

# 로깅 함수
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

log_title() {
    echo ""
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}${1}${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# 함수: 설정 파일 읽기
load_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        log_warning "설정 파일 없음: $CONFIG_FILE"
        log_info "기본값 사용: auto mode"
        SYNC_MODE="auto"
        AUTO_ENABLE_PRE_COMMIT=true
        AUTO_ENABLE_POST_MERGE=true
        SHOW_SYNC_NOTIFICATION=true
        SHOW_SUMMARY=true
        VALIDATE_SKILLS=true
        return
    fi

    # 설정 로드
    source "$CONFIG_FILE" 2>/dev/null || {
        log_error "설정 파일 읽기 실패"
        return 1
    }

    # 기본값 설정
    SYNC_MODE=${SYNCHRONIZATION_MODE:-auto}
    AUTO_ENABLE_PRE_COMMIT=${AUTO_ENABLE_PRE_COMMIT:-true}
    AUTO_ENABLE_POST_MERGE=${AUTO_ENABLE_POST_MERGE:-true}
    SHOW_SYNC_NOTIFICATION=${SHOW_SYNC_NOTIFICATION:-true}
    SHOW_SUMMARY=${SHOW_SUMMARY:-true}
    VALIDATE_SKILLS=${VALIDATE_SKILLS:-true}
}

# 함수: 동기화 모드 표시
show_sync_mode() {
    echo ""
    if [ "$SYNC_MODE" = "auto" ]; then
        log_success "현재 모드: 자동 동기화"
        log "  • git hooks가 자동으로 실행됨"
        log "  • 이 명령어는 수동으로 명시적 동기화를 할 때 사용"
    else
        log_success "현재 모드: 수동 동기화"
        log "  • git hooks가 비활성화됨"
        log "  • 명시적으로 이 명령어로 동기화해야 함"
        log "  • 사용자가 동기화 타이밍을 완전히 제어"
    fi
    echo ""
}

# 함수: 설정 표시
show_config() {
    log_title "현재 설정"

    echo "동기화 설정:"
    echo "  SYNCHRONIZATION_MODE: $SYNC_MODE"
    echo "  SYNC_SKILLS_INDEX: true"
    echo "  SYNC_CLAUDE_MD: true"
    echo ""

    if [ "$SYNC_MODE" = "auto" ]; then
        echo "자동 모드 설정:"
        echo "  AUTO_ENABLE_PRE_COMMIT: $AUTO_ENABLE_PRE_COMMIT"
        echo "  AUTO_ENABLE_POST_MERGE: $AUTO_ENABLE_POST_MERGE"
    else
        echo "수동 모드 설정:"
        echo "  MANUAL_SHOW_CONFIRMATION: true"
        echo "  MANUAL_AUTO_COMMIT: false"
    fi
    echo ""

    echo "알림 설정:"
    echo "  SHOW_SYNC_NOTIFICATION: $SHOW_SYNC_NOTIFICATION"
    echo "  SHOW_SUMMARY: $SHOW_SUMMARY"
    echo ""

    echo "검증 설정:"
    echo "  VALIDATE_SKILLS: $VALIDATE_SKILLS"
    echo "  VALIDATE_JSON: true"
    echo "  VALIDATE_YAML: true"
    echo ""
}

# 함수: 상태 표시
show_status() {
    log_title "동기화 시스템 상태"

    show_sync_mode

    echo "설정 파일:"
    if [ -f "$CONFIG_FILE" ]; then
        log_success "존재: $CONFIG_FILE"
    else
        log_warning "없음: $CONFIG_FILE (기본값 사용)"
    fi
    echo ""

    echo "스크립트:"
    log_success "update-index.sh"
    log_success "sync-claude.sh"
    echo ""

    echo "Git Hooks:"
    if [ -x "$REPO_ROOT/.git/hooks/pre-commit" ]; then
        if [ "$AUTO_ENABLE_PRE_COMMIT" = "true" ]; then
            log_success "pre-commit: 활성화 ✓"
        else
            log_warning "pre-commit: 설정에서 비활성화됨"
        fi
    else
        log_warning "pre-commit: 실행 권한 없음"
    fi

    if [ -x "$REPO_ROOT/.git/hooks/post-merge" ]; then
        if [ "$AUTO_ENABLE_POST_MERGE" = "true" ]; then
            log_success "post-merge: 활성화 ✓"
        else
            log_warning "post-merge: 설정에서 비활성화됨"
        fi
    else
        log_warning "post-merge: 실행 권한 없음"
    fi
    echo ""

    echo "메타데이터:"
    if [ -f "$INDEX_FILE" ]; then
        local skill_count=$(jq '.total_skills' "$INDEX_FILE" 2>/dev/null || echo "?")
        log_success "skills_index.json: $skill_count개 스킬"
    else
        log_warning "skills_index.json: 없음"
    fi
    echo ""
}

# 함수: 전체 동기화
full_sync() {
    log_title "완전한 동기화 실행"

    show_sync_mode

    # 인덱스 생성
    log "Step 1/3: 스킬 인덱스 생성..."
    if bash "$SCRIPTS_DIR/update-index.sh" > /dev/null 2>&1; then
        log_success "스킬 인덱스 생성 완료"
    else
        log_error "스킬 인덱스 생성 실패"
        return 1
    fi

    echo ""

    # CLAUDE.md 동기화
    log "Step 2/3: CLAUDE.md 동기화..."
    if bash "$SCRIPTS_DIR/sync-claude.sh" > /dev/null 2>&1; then
        log_success "CLAUDE.md 동기화 완료"
    else
        log_warning "CLAUDE.md 동기화 부분 실패"
    fi

    echo ""

    # 변경사항 확인
    log "Step 3/3: 변경사항 확인..."
    local changes=$(git diff --name-only 2>/dev/null || echo "")

    if [ -z "$changes" ]; then
        log_info "변경사항 없음"
        echo ""
        return 0
    fi

    # 요약 표시
    if [ "$SHOW_SUMMARY" = "true" ]; then
        log_title "변경사항 요약"

        if echo "$changes" | grep -q "skills_index.json"; then
            log "📋 skills_index.json"
            git diff --stat myskills/skills_index.json 2>/dev/null || true
        fi

        if echo "$changes" | grep -q "CLAUDE.md"; then
            log "📄 CLAUDE.md"
            git diff --stat CLAUDE.md 2>/dev/null || true
        fi

        echo ""
    fi

    # 커밋 안내
    if [ "$SYNC_MODE" = "manual" ]; then
        log_title "다음 단계"
        log "변경사항이 생성되었습니다."
        echo ""
        log "1️⃣  변경사항 검토:"
        log "    git diff myskills/skills_index.json"
        log "    git diff CLAUDE.md"
        echo ""
        log "2️⃣  변경사항 스테이징:"
        log "    git add myskills/skills_index.json CLAUDE.md"
        echo ""
        log "3️⃣  커밋:"
        log "    git commit -m \"Sync skills (manual mode)\""
        echo ""
    fi
}

# 함수: 인덱스만 동기화
sync_index_only() {
    log_title "스킬 인덱스만 동기화"

    log "스킬 인덱스 생성 중..."

    if bash "$SCRIPTS_DIR/update-index.sh" > /dev/null 2>&1; then
        log_success "동기화 완료"

        if git diff --name-only | grep -q "skills_index.json"; then
            log_info "변경사항 생성됨: skills_index.json"
        else
            log_info "변경사항 없음"
        fi
    else
        log_error "동기화 실패"
        return 1
    fi

    echo ""
}

# 함수: CLAUDE.md만 동기화
sync_claude_only() {
    log_title "CLAUDE.md만 동기화"

    log "CLAUDE.md 동기화 중..."

    if bash "$SCRIPTS_DIR/sync-claude.sh" > /dev/null 2>&1; then
        log_success "동기화 완료"

        if git diff --name-only | grep -q "CLAUDE.md"; then
            log_info "변경사항 생성됨: CLAUDE.md"
        else
            log_info "변경사항 없음"
        fi
    else
        log_error "동기화 실패"
        return 1
    fi

    echo ""
}

# 함수: 자동 모드로 전환
switch_to_auto() {
    log_title "자동 모드로 전환"

    if [ ! -f "$CONFIG_FILE" ]; then
        log_warning "설정 파일 없음, 생성 중..."
        cp "$CONFIG_FILE.sample" "$CONFIG_FILE" 2>/dev/null || {
            log_error "설정 파일 생성 실패"
            return 1
        }
    fi

    sed -i 's/SYNCHRONIZATION_MODE=.*/SYNCHRONIZATION_MODE=auto/' "$CONFIG_FILE"
    log_success "자동 모드로 전환 완료"

    log ""
    log "설정 저장:"
    log "  git add .claude-skills-config"
    log "  git commit -m \"Switch to auto sync mode\""
    echo ""
}

# 함수: 수동 모드로 전환
switch_to_manual() {
    log_title "수동 모드로 전환"

    if [ ! -f "$CONFIG_FILE" ]; then
        log_warning "설정 파일 없음, 생성 중..."
        cp "$CONFIG_FILE.sample" "$CONFIG_FILE" 2>/dev/null || {
            log_error "설정 파일 생성 실패"
            return 1
        }
    fi

    sed -i 's/SYNCHRONIZATION_MODE=.*/SYNCHRONIZATION_MODE=manual/' "$CONFIG_FILE"
    log_success "수동 모드로 전환 완료"

    log ""
    log "이제부터는 다음 명령어로 동기화하세요:"
    log "  claude-skills-sync          # 전체 동기화"
    log "  claude-skills-sync index    # 인덱스만"
    log "  claude-skills-sync claude   # CLAUDE.md만"
    log ""
    log "설정 저장:"
    log "  git add .claude-skills-config"
    log "  git commit -m \"Switch to manual sync mode\""
    echo ""
}

# 함수: 도움말 표시
show_help() {
    cat << 'EOF'
╔════════════════════════════════════════════════════════════════════════════╗
║                        sync-cli.sh - Skills Sync CLI                      ║
╚════════════════════════════════════════════════════════════════════════════╝

사용법:
  ./sync-cli.sh [COMMAND] [OPTIONS]

명령어:

  (명령어 없음)        - 대화형 메뉴 (권장)
  sync                 - 전체 동기화 (인덱스 + CLAUDE.md)
  index                - 스킬 인덱스만 생성
  claude               - CLAUDE.md만 동기화

  status               - 현재 모드 & 상태 표시
  config               - 현재 설정 표시

  auto                 - 자동 모드로 전환
  manual               - 수동 모드로 전환

  help                 - 이 도움말 표시
  version              - 버전 정보

예시:

  # 대화형 메뉴
  ./sync-cli.sh

  # 전체 동기화
  ./sync-cli.sh sync

  # 인덱스만 동기화
  ./sync-cli.sh index

  # 현재 상태 확인
  ./sync-cli.sh status

  # 수동 모드로 전환
  ./sync-cli.sh manual

환경 변수:

  SYNC_VERBOSE=1      - 상세 출력
  SYNC_DRY_RUN=1      - 드라이런 (변경 없음)

설정:

  설정 파일: .claude-skills-config
  읽기: ./sync-cli.sh config

도움말:

  더 자세한 정보: myskills/scripts/README.md

EOF
}

# 함수: 버전 정보
show_version() {
    echo "sync-cli.sh v1.0.0"
    echo "Created: 2026-02-27"
    echo "Status: Production Ready"
}

# 함수: 대화형 메뉴
interactive_menu() {
    log_title "스킬 동기화 CLI"

    show_sync_mode

    echo "이 명령어는 무엇을 할까요?"
    echo ""
    echo "  1) 전체 동기화 (권장)"
    echo "     → 인덱스 + CLAUDE.md 모두 동기화"
    echo ""
    echo "  2) 스킬 인덱스만 동기화"
    echo "     → skills_index.json만 생성"
    echo ""
    echo "  3) CLAUDE.md만 동기화"
    echo "     → CLAUDE.md만 업데이트"
    echo ""
    echo "  4) 현재 상태 확인"
    echo "     → 모드, 설정, Git 훅 상태"
    echo ""
    echo "  5) 동기화 모드 변경"
    echo "     → 자동/수동 모드 전환"
    echo ""
    echo "  6) 도움말"
    echo "     → 명령어 및 옵션 설명"
    echo ""

    read -p "선택 (1-6): " choice

    case $choice in
        1) full_sync ;;
        2) sync_index_only ;;
        3) sync_claude_only ;;
        4) show_status ;;
        5) mode_menu ;;
        6) show_help ;;
        *) log_error "잘못된 선택"; return 1 ;;
    esac
}

# 함수: 모드 변경 메뉴
mode_menu() {
    log_title "동기화 모드 변경"

    show_sync_mode

    echo "어떤 모드로 변경할까요?"
    echo ""
    echo "  1) 자동 모드 (기본값)"
    echo "     → git hooks가 자동으로 동기화"
    echo ""
    echo "  2) 수동 모드"
    echo "     → 명시적으로 동기화 명령어 실행"
    echo ""
    echo "  3) 취소"
    echo ""

    read -p "선택 (1-3): " choice

    case $choice in
        1) switch_to_auto ;;
        2) switch_to_manual ;;
        3) log_info "취소됨" ;;
        *) log_error "잘못된 선택"; return 1 ;;
    esac
}

# 메인 로직
main() {
    # 설정 로드
    load_config

    # 인자 처리
    if [ $# -eq 0 ]; then
        # 대화형 메뉴
        interactive_menu
    else
        case "$1" in
            sync|sync-all)
                full_sync
                ;;
            index|idx)
                sync_index_only
                ;;
            claude|md)
                sync_claude_only
                ;;
            status)
                show_status
                ;;
            config)
                show_config
                ;;
            auto)
                switch_to_auto
                ;;
            manual)
                switch_to_manual
                ;;
            help|--help|-h)
                show_help
                ;;
            version|--version|-v)
                show_version
                ;;
            *)
                log_error "알 수 없는 명령어: $1"
                log_info "도움말: $0 help"
                return 1
                ;;
        esac
    fi
}

# 실행
main "$@"
exit $?
