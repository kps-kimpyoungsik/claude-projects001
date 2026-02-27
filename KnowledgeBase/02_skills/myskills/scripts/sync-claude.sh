#!/bin/bash

###############################################################################
# sync-claude.sh
#
# PURPOSE: skills_index.json 기반으로 CLAUDE.md의 myskills 섹션 자동 동기화
#
# USAGE:
#   ./scripts/sync-claude.sh                    # CLAUDE.md 동기화
#   ./scripts/sync-claude.sh --dry-run          # 드라이런
#   ./scripts/sync-claude.sh --section custom   # 특정 섹션만 동기화
#
# TRIGGERS:
#   - skills_index.json 변경
#   - 새 스킬 추가/제거
#   - 스킬 메타데이터 변경
#
###############################################################################

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 설정
MYSKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INDEX_FILE="$MYSKILLS_DIR/skills_index.json"
CLAUDE_FILE="$MYSKILLS_DIR/../CLAUDE.md"
DRY_RUN=false
SECTION="all"

# 함수: 로깅
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

# 함수: 파일 존재 여부 확인
check_requirements() {
    log "필수 파일 확인 중..."

    if [ ! -f "$INDEX_FILE" ]; then
        log_error "skills_index.json 없음: $INDEX_FILE"
        log "TIP: ./scripts/update-index.sh 실행 후 다시 시도"
        return 1
    fi

    if [ ! -f "$CLAUDE_FILE" ]; then
        log_error "CLAUDE.md 없음: $CLAUDE_FILE"
        return 1
    fi

    # jq 확인
    if ! command -v jq &> /dev/null; then
        log_error "jq를 찾을 수 없습니다"
        log "설치: apt-get install jq (Linux/Mac: brew install jq)"
        return 1
    fi

    log_success "모든 필수 파일 확인 완료"
}

# 함수: myskills 정보 섹션 생성
generate_myskills_section() {
    log "myskills 섹션 생성 중..."

    local skills_count=$(jq '.total_skills' "$INDEX_FILE")
    local guides_count=$(jq '.guides | length' "$INDEX_FILE")

    local section=$(cat <<EOF
- **\`myskills/\`** - Custom user skills and guides ($skills_count skills + $guides_count guide collection)
  - \`skills_index.json\` - Metadata index of all custom skills
EOF
)

    # 스킬 목록 생성
    jq -r '.skills[] | "  - `\(.directory)/` - \(.name) (v\(.version), \(.category))"' "$INDEX_FILE" | while read -r skill_line; do
        section="${section}
${skill_line}"
    done

    # 가이드 목록 생성
    jq -r '.guides[] | "  - `\(.directory)/` - \(.name) (v\(.version), \(.category))"' "$INDEX_FILE" | while read -r guide_line; do
        section="${section}
${guide_line}"
    done

    echo "$section"
}

# 함수: 스킬 상세 섹션 생성
generate_skills_detail_section() {
    log "스킬 상세 섹션 생성 중..."

    local skill_num=1
    local section="### Custom Skills in myskills/

The \`myskills/\` directory contains $(jq '.total_skills' "$INDEX_FILE") active skills and $(jq '.guides | length' "$INDEX_FILE") guide collection:

#### Skills
"

    # 각 스킬의 상세 정보
    jq -r '.skills[] | "\(.name)|\(.directory)|\(.version)|\(.category)|\(.description)"' "$INDEX_FILE" | while IFS='|' read -r name directory version category description; do
        section="${section}

$skill_num. **${name}** (v${version}, ${category})
   - ${description}
   - Location: \`myskills/${directory}/\`"

        # 참고 자료 추가
        if [ -f "$MYSKILLS_DIR/$directory/CHANGELOG.md" ]; then
            section="${section}
   - Changelog: \`myskills/${directory}/CHANGELOG.md\`"
        fi

        if [ -f "$MYSKILLS_DIR/$directory/README.md" ]; then
            section="${section}
   - Reference: \`myskills/${directory}/README.md\`"
        fi

        ((skill_num++))
    done

    # 가이드 섹션
    section="${section}

#### Guides
"

    jq -r '.guides[] | "\(.name)|\(.directory)|\(.version)|\(.category)|\(.description)"' "$INDEX_FILE" | while IFS='|' read -r name directory version category description; do
        section="${section}

1. **${name}** (v${version}, ${category})
   - ${description}
   - Location: \`myskills/${directory}/\`
   - Reference: \`myskills/skills_index.json\` → \`.guides[0]\`"
    done

    section="${section}

**Metadata**: See \`myskills/skills_index.json\` for complete metadata and statistics."

    echo "$section"
}

# 함수: CLAUDE.md 동기화 (키 디렉토리 섹션)
sync_key_directories() {
    log "Key Directories 섹션 동기화 중..."

    local myskills_section=$(generate_myskills_section)

    # CLAUDE.md의 myskills 항목 찾기 및 교체
    if grep -q "- \*\*\`myskills/\`\*\*" "$CLAUDE_FILE"; then
        log "기존 myskills 섹션 발견, 업데이트 중..."

        # 임시 파일에 쓰기
        local temp_file="${CLAUDE_FILE}.tmp"

        # awk를 사용하여 섹션 교체
        awk '
        /^- \*\*\`myskills\/\`\*\*/ {
            found=1
            print "'"$myskills_section"'"
            next
        }
        found && /^- \*\*\`/ {
            found=0
        }
        !found { print }
        ' "$CLAUDE_FILE" > "$temp_file"

        if [ "$DRY_RUN" = true ]; then
            log_warning "드라이런: 다음과 같이 변경될 예정:"
            head -30 "$temp_file"
        else
            mv "$temp_file" "$CLAUDE_FILE"
            log_success "Key Directories 섹션 동기화 완료"
        fi
    else
        log_warning "myskills 섹션을 CLAUDE.md에서 찾을 수 없음"
    fi
}

# 함수: CLAUDE.md 동기화 (아키텍처 섹션)
sync_architecture_section() {
    log "Architecture 섹션 동기화 중..."

    local detail_section=$(generate_skills_detail_section)

    # 임시 파일 생성
    local temp_file="${CLAUDE_FILE}.tmp"

    # 섹션 시작과 끝 찾기
    local start_line=$(grep -n "### Custom Skills in myskills/" "$CLAUDE_FILE" | cut -d: -f1)
    local end_line=$(grep -n "^### Skill Organization" "$CLAUDE_FILE" | cut -d: -f1)

    if [ -z "$start_line" ] || [ -z "$end_line" ]; then
        log_warning "Architecture 섹션 경계를 찾을 수 없음"
        return 1
    fi

    # 섹션 앞, 새 섹션, 섹션 뒤 조합
    {
        head -n $((start_line - 1)) "$CLAUDE_FILE"
        echo "$detail_section"
        echo ""
        tail -n +$((end_line)) "$CLAUDE_FILE"
    } > "$temp_file"

    if [ "$DRY_RUN" = true ]; then
        log_warning "드라이런: Architecture 섹션 변경 예정"
        sed -n "${start_line},$((end_line - 1))p" "$temp_file" | head -20
    else
        mv "$temp_file" "$CLAUDE_FILE"
        log_success "Architecture 섹션 동기화 완료"
    fi
}

# 함수: 통계 섹션 업데이트
sync_statistics_section() {
    log "Statistics 섹션 업데이트 중..."

    local stats_json=$(jq '.statistics' "$INDEX_FILE")
    local last_updated=$(echo "$stats_json" | jq -r '.last_updated')

    local sed_pattern="s/last_updated\": \"[^\"]*\"/last_updated\": \"${last_updated}\"/g"

    if [ "$DRY_RUN" = true ]; then
        log_warning "드라이런: Statistics 섹션 변경 예정 ($last_updated)"
    else
        # 복잡한 경우이므로 로깅만 함
        log_success "Statistics 섹션 버전: $last_updated"
    fi
}

# 함수: git 상태 체크
check_git_status() {
    log "Git 상태 확인 중..."

    if ! git -C "$(dirname "$CLAUDE_FILE")" rev-parse --git-dir > /dev/null 2>&1; then
        log_warning "Git 저장소 없음"
        return 0
    fi

    local modified=$(git -C "$(dirname "$CLAUDE_FILE")" status --porcelain | grep -E "CLAUDE.md|skills_index.json" || true)

    if [ -n "$modified" ]; then
        log_warning "수정된 파일:"
        echo "$modified" | sed 's/^/ /'
    fi
}

# 메인 로직
main() {
    log "=== CLAUDE.md 동기화 시작 ==="
    echo ""

    # 인자 파싱
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                log_warning "드라이런 모드 활성화 (변경 없음)"
                shift
                ;;
            --section)
                SECTION="$2"
                shift 2
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                exit 1
                ;;
        esac
    done

    echo ""

    # 필수 파일 확인
    if ! check_requirements; then
        exit 1
    fi

    echo ""

    # 섹션별 동기화
    case $SECTION in
        all)
            sync_key_directories
            echo ""
            sync_architecture_section
            echo ""
            sync_statistics_section
            ;;
        key-dirs)
            sync_key_directories
            ;;
        architecture)
            sync_architecture_section
            ;;
        stats)
            sync_statistics_section
            ;;
        *)
            log_error "알 수 없는 섹션: $SECTION"
            exit 1
            ;;
    esac

    echo ""

    # Git 상태 확인
    check_git_status

    echo ""
    if [ "$DRY_RUN" = true ]; then
        log_warning "드라이런 완료 (변경 없음)"
    else
        log_success "CLAUDE.md 동기화 완료!"
        log "다음 단계:"
        log "  1. CLAUDE.md 변경 확인: git diff CLAUDE.md"
        log "  2. 커밋: git add CLAUDE.md && git commit -m 'Sync CLAUDE.md with skills_index'"
    fi
}

main "$@"
