#!/bin/bash

###############################################################################
# install-sync-mode.sh
#
# PURPOSE: 동기화 모드 설정 및 명령어 alias 설치
#
# USAGE:
#   ./scripts/install-sync-mode.sh               # 대화형 설치
#   ./scripts/install-sync-mode.sh auto          # 자동 모드로 설치
#   ./scripts/install-sync-mode.sh manual        # 수동 모드로 설치
#   ./scripts/install-sync-mode.sh --help        # 도움말
#
###############################################################################

set -e

# 색상
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# 경로
MYSKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$MYSKILLS_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/.claude-skills-config"
SCRIPTS_DIR="$MYSKILLS_DIR/scripts"
SYNC_CLI="$SCRIPTS_DIR/sync-cli.sh"

# 로깅
log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
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

log_title() {
    echo ""
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}${1}${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# 함수: 설정 파일 생성
create_config_file() {
    local mode=$1

    log_title "설정 파일 생성 중"

    if [ -f "$CONFIG_FILE" ]; then
        log_warning "기존 설정 파일이 있습니다: $CONFIG_FILE"
        read -p "덮어쓸까요? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "설정 파일 생성 취소"
            return 1
        fi
    fi

    # 기본 설정 파일 생성
    cat > "$CONFIG_FILE" << EOF
# Claude Skills Synchronization Configuration
# Created: $(date '+%Y-%m-%d %H:%M:%S')

SYNCHRONIZATION_MODE=$mode

AUTO_ENABLE_PRE_COMMIT=true
AUTO_ENABLE_POST_MERGE=true

SHOW_SYNC_NOTIFICATION=true
SHOW_SUMMARY=true
VALIDATE_SKILLS=true

EOF

    if [ -f "$CONFIG_FILE" ]; then
        log_success "설정 파일 생성 완료"
        log "위치: $CONFIG_FILE"
        return 0
    else
        log_error "설정 파일 생성 실패"
        return 1
    fi
}

# 함수: 설정 파일 검증
validate_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        log_warning "설정 파일 없음"
        return 1
    fi

    if ! source "$CONFIG_FILE" 2>/dev/null; then
        log_error "설정 파일 읽기 실패"
        return 1
    fi

    log_success "설정 파일 검증 완료"
    return 0
}

# 함수: CLI 권한 확인
check_cli_permissions() {
    log "CLI 권한 확인 중"

    if [ ! -f "$SYNC_CLI" ]; then
        log_error "sync-cli.sh 없음: $SYNC_CLI"
        return 1
    fi

    if [ ! -x "$SYNC_CLI" ]; then
        log_warning "실행 권한 없음, 설정 중..."
        chmod +x "$SYNC_CLI"
        log_success "실행 권한 설정"
    else
        log_success "실행 권한 확인"
    fi

    return 0
}

# 함수: Hook 검증
check_hooks() {
    log_title "Git Hooks 검증"

    local pre_commit="$REPO_ROOT/.git/hooks/pre-commit"
    local post_merge="$REPO_ROOT/.git/hooks/post-merge"

    if [ ! -x "$pre_commit" ]; then
        log_warning "pre-commit 훅: 권한 없음"
        chmod +x "$pre_commit"
        log_success "pre-commit 권한 설정"
    else
        log_success "pre-commit 훅 OK"
    fi

    if [ ! -x "$post_merge" ]; then
        log_warning "post-merge 훅: 권한 없음"
        chmod +x "$post_merge"
        log_success "post-merge 권한 설정"
    else
        log_success "post-merge 훅 OK"
    fi

    echo ""
}

# 함수: 명령어 alias 제안
show_alias_suggestions() {
    log_title "명령어 Alias 설정 (선택사항)"

    echo "편하게 사용하기 위해 다음 명령어를 .bashrc 또는 .zshrc에 추가하세요:"
    echo ""
    echo -e "${CYAN}# Add to ~/.bashrc or ~/.zshrc${NC}"
    echo "alias claude-skills-sync='$SYNC_CLI'"
    echo "alias css='$SYNC_CLI'"  # 단축 alias
    echo ""
    echo "그러면 다음과 같이 사용 가능합니다:"
    echo "  claude-skills-sync          # 대화형 메뉴"
    echo "  claude-skills-sync sync     # 전체 동기화"
    echo "  css index                   # 인덱스만"
    echo ""
}

# 함수: 설치 후 안내
show_final_instructions() {
    local mode=$1

    log_title "설치 완료! 🎉"

    if [ "$mode" = "auto" ]; then
        echo "✅ 자동 동기화 모드가 설정되었습니다."
        echo ""
        echo "이제부터:"
        echo "  1. 스킬을 추가/수정하고 커밋"
        echo "  2. Git hooks가 자동으로 동기화"
        echo "  3. 모든 파일이 자동으로 업데이트됨"
        echo ""
        echo "언제든지 수동으로도 동기화 가능:"
        echo "  ./myskills/scripts/sync-cli.sh"
    else
        echo "✅ 수동 동기화 모드가 설정되었습니다."
        echo ""
        echo "이제부터:"
        echo "  1. 스킬을 추가/수정하고 커밋"
        echo "  2. 수동으로 동기화 명령어 실행:"
        echo "     ./myskills/scripts/sync-cli.sh"
        echo "  3. 변경사항 검토 후 커밋"
        echo ""
        echo "동기화 모드 변경:"
        echo "  ./myskills/scripts/sync-cli.sh auto"
    fi

    echo ""
    echo "설정 저장:"
    echo "  git add .claude-skills-config"
    echo "  git commit -m \"Configure skills sync mode: $mode\""
    echo ""
}

# 함수: 테스트
test_installation() {
    log_title "설치 테스트 중"

    if ! bash "$SYNC_CLI" status > /dev/null 2>&1; then
        log_warning "테스트 실패했지만 계속 진행합니다"
        return 0
    fi

    log_success "설치 테스트 완료"
    return 0
}

# 함수: 대화형 설치
interactive_install() {
    log_title "동기화 모드 설치"

    echo "동기화 모드를 선택하세요:"
    echo ""
    echo "1) 자동 모드 (권장)"
    echo "   → git hooks가 자동으로 동기화"
    echo "   → 스킬 추가/수정할 때마다 자동 반영"
    echo ""
    echo "2) 수동 모드"
    echo "   → 명시적으로 sync 명령어 실행"
    echo "   → 동기화 타이밍을 완전히 제어"
    echo ""
    echo "3) 나중에 결정"
    echo ""

    read -p "선택 (1-3): " choice

    case $choice in
        1)
            install_auto_mode
            ;;
        2)
            install_manual_mode
            ;;
        3)
            log "설치를 취소했습니다."
            log "나중에 다시 실행할 수 있습니다:"
            log "  ./myskills/scripts/install-sync-mode.sh"
            return 0
            ;;
        *)
            log_error "잘못된 선택"
            return 1
            ;;
    esac
}

# 함수: 자동 모드 설치
install_auto_mode() {
    log_title "자동 모드 설치 중"

    create_config_file "auto" || return 1
    check_cli_permissions || return 1
    check_hooks
    test_installation

    # Alias 제안
    show_alias_suggestions

    # 최종 안내
    show_final_instructions "auto"

    log_success "자동 모드 설치 완료!"
}

# 함수: 수동 모드 설치
install_manual_mode() {
    log_title "수동 모드 설치 중"

    create_config_file "manual" || return 1
    check_cli_permissions || return 1
    check_hooks
    test_installation

    # Alias 제안
    show_alias_suggestions

    # 최종 안내
    show_final_instructions "manual"

    log_success "수동 모드 설치 완료!"
}

# 함수: 도움말
show_help() {
    cat << 'EOF'
install-sync-mode.sh - 동기화 모드 설치 스크립트

사용법:
  ./scripts/install-sync-mode.sh               # 대화형 설치 (권장)
  ./scripts/install-sync-mode.sh auto          # 자동 모드 설치
  ./scripts/install-sync-mode.sh manual        # 수동 모드 설치
  ./scripts/install-sync-mode.sh --help        # 이 도움말

자동 모드:
  • Git hooks가 자동으로 실행
  • 스킬 변경할 때마다 자동 동기화
  • 스킬 추가 후 커밋하면 자동 완료
  • 권장되는 모드

수동 모드:
  • 사용자가 명시적으로 명령어 실행
  • 동기화 타이밍 완전 제어
  • sync-cli.sh 명령어로 동기화
  • 팀 협업에서 더 정교한 제어 가능

예시:
  # 대화형 설치 (권장)
  ./scripts/install-sync-mode.sh

  # 자동 모드로 직접 설치
  ./scripts/install-sync-mode.sh auto

  # 수동 모드로 직접 설치
  ./scripts/install-sync-mode.sh manual

설치 후:
  • 자동 모드: git commit하면 자동 동기화
  • 수동 모드: ./myskills/scripts/sync-cli.sh로 동기화

모드 변경:
  ./myskills/scripts/sync-cli.sh auto      # → 자동 모드로
  ./myskills/scripts/sync-cli.sh manual    # → 수동 모드로

EOF
}

# 메인
main() {
    if [ $# -eq 0 ]; then
        # 대화형 설치
        interactive_install
    else
        case "$1" in
            auto)
                install_auto_mode
                ;;
            manual)
                install_manual_mode
                ;;
            --help|-h|help)
                show_help
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                log_info "도움말: $0 --help"
                return 1
                ;;
        esac
    fi
}

main "$@"
