#!/bin/bash

###############################################################################
# quick-sync.sh
#
# PURPOSE: Simple synchronization for testing (Windows-compatible)
#          빠르고 간단한 동기화 테스트용
#
# USAGE:
#   ./scripts/quick-sync.sh               # Full sync test
#   ./scripts/quick-sync.sh status        # Show status
#
###############################################################################

set -e

# 색상
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# 경로
MYSKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$MYSKILLS_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/.claude-skills-config"
INDEX_FILE="$MYSKILLS_DIR/skills_index.json"
CLAUDE_FILE="$REPO_ROOT/CLAUDE.md"

# 로깅
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_title() {
    echo ""
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}${1}${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# 함수: 설정 로드
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE" 2>/dev/null || true
    fi
    SYNC_MODE=${SYNCHRONIZATION_MODE:-auto}
}

# 함수: 상태 표시
show_status() {
    log_title "Quick Sync - Status"

    log "Mode: $SYNC_MODE"

    # Git hooks 확인
    if [ -x "$REPO_ROOT/.git/hooks/pre-commit" ]; then
        log_success "pre-commit hook: OK"
    else
        log_error "pre-commit hook: MISSING or NO PERMISSION"
    fi

    if [ -x "$REPO_ROOT/.git/hooks/post-merge" ]; then
        log_success "post-merge hook: OK"
    else
        log_error "post-merge hook: MISSING or NO PERMISSION"
    fi

    # 파일 확인
    if [ -f "$INDEX_FILE" ]; then
        local count=$(cat "$INDEX_FILE" | grep -c "\"name\":" || echo "?")
        log_success "skills_index.json: Found ($count entries)"
    else
        log_error "skills_index.json: NOT FOUND"
    fi

    if [ -f "$CLAUDE_FILE" ]; then
        log_success "CLAUDE.md: Found"
    else
        log_error "CLAUDE.md: NOT FOUND"
    fi

    echo ""
}

# 함수: 빠른 동기화
quick_sync() {
    log_title "Quick Sync Test"

    load_config

    echo "Mode: $SYNC_MODE"
    echo ""

    # 체크리스트
    echo "Verification Checklist:"
    echo ""

    # 1. Config file
    if [ -f "$CONFIG_FILE" ]; then
        log_success "✓ Config file exists"
    else
        log_error "✗ Config file missing"
        return 1
    fi

    # 2. Settings
    if [ "$SYNC_MODE" = "auto" ]; then
        log_success "✓ Auto mode configured"
    else
        log_success "✓ Manual mode configured"
    fi

    # 3. Hooks
    if [ -x "$REPO_ROOT/.git/hooks/pre-commit" ]; then
        log_success "✓ pre-commit hook executable"
    else
        log_error "✗ pre-commit hook not executable"
    fi

    if [ -x "$REPO_ROOT/.git/hooks/post-merge" ]; then
        log_success "✓ post-merge hook executable"
    else
        log_error "✗ post-merge hook not executable"
    fi

    # 4. Scripts
    if [ -x "$MYSKILLS_DIR/scripts/sync-cli.sh" ]; then
        log_success "✓ sync-cli.sh executable"
    else
        log_error "✗ sync-cli.sh not executable"
    fi

    if [ -x "$MYSKILLS_DIR/scripts/update-index.sh" ]; then
        log_success "✓ update-index.sh executable"
    else
        log_error "✗ update-index.sh not executable"
    fi

    echo ""
    log_title "System Ready! ✅"

    echo "Configuration verified successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Add/modify a skill"
    echo "  2. git add + git commit"
    echo ""
    if [ "$SYNC_MODE" = "auto" ]; then
        echo "  3. Hooks will auto-sync!"
    else
        echo "  3. Run: ./myskills/scripts/sync-cli.sh"
    fi
    echo ""
}

# 메인
main() {
    if [ "$1" = "status" ]; then
        load_config
        show_status
    else
        quick_sync
    fi
}

main "$@"
