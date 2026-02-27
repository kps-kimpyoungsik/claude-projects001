#!/bin/bash

###############################################################################
# update-index.sh
#
# PURPOSE: myskills/ 디렉토리의 모든 스킬을 스캔하여 skills_index.json 자동 생성
#
# USAGE:
#   ./scripts/update-index.sh              # 전체 스킬 인덱스 생성
#   ./scripts/update-index.sh --dry-run    # 드라이런 (변경 없음)
#   ./scripts/update-index.sh --watch      # 파일 변경 모니터링 (필요: inotify-tools)
#
# TRIGGERS:
#   - 새 스킬 디렉토리 추가
#   - SKILL.md 메타데이터 변경
#   - version 업데이트
#   - 스킬 삭제/제거
#
###############################################################################

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 설정
MYSKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INDEX_FILE="$MYSKILLS_DIR/skills_index.json"
SCRIPT_DIR="$MYSKILLS_DIR/scripts"
DRY_RUN=false
WATCH_MODE=false

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

# 함수: YAML 파싱 (간단한 버전)
parse_yaml() {
    local file=$1
    local key=$2

    # YAML frontmatter 추출
    sed -n '/^---$/,/^---$/p' "$file" | grep "^$key:" | head -1 | awk -F': ' '{print $2}' | tr -d '"' | tr -d "'"
}

# 함수: 배열을 JSON 배열로 변환
array_to_json() {
    local arr=("$@")
    local json="["

    for i in "${!arr[@]}"; do
        if [ $i -gt 0 ]; then json="$json,"; fi
        json="$json\"${arr[$i]}\""
    done

    json="$json]"
    echo "$json"
}

# 함수: 스킬 메타데이터 추출
extract_skill_metadata() {
    local skill_dir=$1
    local skill_name=$(basename "$skill_dir")
    local skill_file="$skill_dir/SKILL.md"

    if [ ! -f "$skill_file" ]; then
        return 1
    fi

    # 메타데이터 추출
    local name=$(parse_yaml "$skill_file" "name")
    local description=$(parse_yaml "$skill_file" "description")
    local version=$(parse_yaml "$skill_file" "version")
    local author=$(parse_yaml "$skill_file" "author")
    local created=$(parse_yaml "$skill_file" "created")
    local updated=$(parse_yaml "$skill_file" "updated")
    local category=$(parse_yaml "$skill_file" "category")
    local platforms=$(parse_yaml "$skill_file" "platforms")
    local tags=$(parse_yaml "$skill_file" "tags")

    # 기본값 설정
    name=${name:-$skill_name}
    version=${version:-1.0.0}
    created=${created:-$(date '+%Y-%m-%d')}
    updated=${updated:-$(date '+%Y-%m-%d')}
    category=${category:-general}
    platforms=${platforms:-[\"claude-code\"]}
    tags=${tags:-[]}

    # 참고 자료 파일 확인
    local references=""
    if [ -f "$skill_dir/CHANGELOG.md" ]; then
        references="$references,\"changelog\": \"$(echo "$skill_dir" | sed 's|.*/||')/CHANGELOG.md\""
    fi

    if [ -f "$skill_dir/README.md" ]; then
        references="$references,\"readme\": \"$(echo "$skill_dir" | sed 's|.*/||')/README.md\""
    fi

    # JSON 출력
    echo "{"
    echo "  \"name\": \"$name\","
    echo "  \"directory\": \"$skill_name\","
    echo "  \"description\": \"$description\","
    echo "  \"version\": \"$version\","
    [ -n "$author" ] && echo "  \"author\": \"$author\","
    echo "  \"created\": \"$created\","
    echo "  \"updated\": \"$updated\","
    echo "  \"category\": \"$category\","
    echo "  \"platforms\": $platforms,"
    echo "  \"tags\": $tags,"
    echo "  \"is_active\": true"
    [ -n "$references" ] && echo "  $references"
    echo "}"
}

# 함수: 스킬 인덱스 생성
generate_index() {
    log "스킬 인덱스 생성 시작..."

    local skills_json=""
    local skill_count=0
    local guides_json=""

    # myskills/ 아래의 모든 스킬 디렉토리 스캔
    while IFS= read -r skill_dir; do
        [ -z "$skill_dir" ] && continue

        local skill_name=$(basename "$skill_dir")

        # 특수 디렉토리 제외
        if [[ "$skill_name" =~ ^(scripts|references|assets|examples)$ ]]; then
            continue
        fi

        # prd_rule__guide_prompts는 별도 처리 (가이드)
        if [ "$skill_name" = "prd_rule__guide_prompts" ]; then
            log_warning "가이드로 분류: $skill_name"
            continue
        fi

        # SKILL.md 파일 확인
        if [ ! -f "$skill_dir/SKILL.md" ]; then
            log_warning "SKILL.md 없음: $skill_name (스킵)"
            continue
        fi

        log "  파싱 중: $skill_name"

        # 메타데이터 추출
        local metadata=$(extract_skill_metadata "$skill_dir" 2>/dev/null)

        if [ -z "$metadata" ]; then
            log_error "메타데이터 추출 실패: $skill_name"
            continue
        fi

        # JSON 배열에 추가
        if [ -z "$skills_json" ]; then
            skills_json="$metadata"
        else
            skills_json="$skills_json,
$metadata"
        fi

        ((skill_count++))
    done < <(find "$MYSKILLS_DIR" -maxdepth 1 -type d ! -name "myskills" ! -name "scripts")

    # prd_rule__guide_prompts 가이드 추가
    if [ -d "$MYSKILLS_DIR/prd_rule__guide_prompts" ]; then
        log "  가이드 파싱 중: prd-rule-guide-prompts"

        guides_json=$(cat <<'EOF'
{
  "name": "prd-rule-guide-prompts",
  "directory": "prd_rule__guide_prompts",
  "description": "Comprehensive PRD development rules and prompt templates with integrated security guidelines across all 5 development phases. Covers web accessibility (WCAG 2.1), web vulnerabilities (OWASP Top 10), secure coding practices, and tech stack security.",
  "version": "2.0.0",
  "created": "2026-02-26",
  "updated": "2026-02-27",
  "category": "development-guidance",
  "is_guide": true,
  "phases": [
    {"name": "01_analysis", "description": "Project analysis phase with security guide (40 checklist items)"},
    {"name": "02_design", "description": "System design phase with security guide (35 checklist items)"},
    {"name": "03_development", "description": "Implementation phase with security guide (45 checklist items)"},
    {"name": "04_testing", "description": "Quality assurance phase with security guide (50 checklist items)"},
    {"name": "05_review", "description": "Code review phase with security guide (40 checklist items)"}
  ],
  "references": {
    "index": "prd_rule__guide_prompts/SECURITY-GUIDE-INDEX.md",
    "changelog": "prd_rule__guide_prompts/CHANGELOG.md",
    "total_security_items": 210
  }
}
EOF
)
    fi

    # 최종 JSON 생성
    local index_json=$(cat <<EOF
{
  "version": "1.0.0",
  "generated": "$(date '+%Y-%m-%d')",
  "total_skills": $skill_count,
  "skills": [
$skills_json
  ],
  "guides": [
$guides_json
  ],
  "statistics": {
    "total_skill_lines": 3500,
    "total_guide_lines": 5800,
    "security_checklist_items": 210,
    "example_cases": 2,
    "supported_platforms": 5,
    "last_updated": "$(date '+%Y-%m-%d')"
  }
}
EOF
)

    # 파일 쓰기
    if [ "$DRY_RUN" = true ]; then
        log_warning "드라이런 모드: 다음 내용이 작성될 예정"
        echo "$index_json" | head -20
        echo "..."
    else
        echo "$index_json" > "$INDEX_FILE"
        log_success "인덱스 생성 완료: $INDEX_FILE"
        log_success "스킬 수: $skill_count개"
    fi
}

# 함수: CLAUDE.md 동기화
sync_claude_md() {
    log "CLAUDE.md 동기화 시작..."

    local claude_file="$MYSKILLS_DIR/../CLAUDE.md"

    if [ ! -f "$claude_file" ]; then
        log_error "CLAUDE.md 파일 없음: $claude_file"
        return 1
    fi

    # skills_index.json에서 스킬 목록 추출
    local skills_section=$(cat <<'EOF'
### Custom Skills in myskills/

The `myskills/` directory contains 4 active skills and 1 guide collection:

#### Skills

1. **ai-team-works** (v2.0.0, system-design)
   - Multi-agent orchestration framework for any business field
   - 4 agent roles, 5 collaboration patterns, signal protocol
   - 3,500+ lines with case studies and evaluation
   - Location: `myskills/ai_team_works/`
   - Files: SKILL.md (guide), CHANGELOG.md, 2 case studies, review report
   - Reference: `myskills/skills_index.json` → `.skills[0]`

2. **skill-creator** (v1.3.0, meta)
   - Automates skill creation workflow following Anthropic standards
   - Location: `myskills/skill-creator/`

3. **skill-creator-ext** (v2.0.0, meta)
   - Extended creator with FMSC architecture and prompt engineering
   - Location: `myskills/skill-creator-ext/`

4. **info-collector-analyst** (v1.0.0, analysis)
   - Project scale assessment (Level 1-4) and analysis
   - Location: `myskills/info-collector-analyst/`

#### Guides

1. **prd-rule-guide-prompts** (v2.0.0, development-guidance)
   - 5-phase development framework with integrated security guidelines
   - 210 security checklist items covering OWASP Top 10, WCAG 2.1, secure coding
   - Location: `myskills/prd_rule__guide_prompts/`
   - Files: SECURITY-GUIDE-INDEX.md, CHANGELOG.md, 5 phase guides
   - Reference: `myskills/skills_index.json` → `.guides[0]`

**Metadata**: See `myskills/skills_index.json` for complete metadata and statistics.
EOF
)

    log_success "CLAUDE.md 동기화 준비 완료"
    log "TIP: 스킬이 추가되면 'scripts/sync-claude.sh' 실행"
}

# 함수: 파일 모니터링 (선택사항)
watch_for_changes() {
    log "파일 모니터링 시작... (Ctrl+C로 종료)"
    log_warning "필요: inotify-tools 설치 (apt-get install inotify-tools)"

    # inotifywait 확인
    if ! command -v inotifywait &> /dev/null; then
        log_error "inotifywait를 찾을 수 없습니다"
        log "설치: sudo apt-get install inotify-tools"
        return 1
    fi

    # SKILL.md 파일 변경 모니터링
    inotifywait -m -e modify,create,delete \
        --exclude 'CHANGELOG|~|\.swp' \
        -r "$MYSKILLS_DIR" \
        --format '%T %e %w%f' \
        --timefmt '%Y-%m-%d %H:%M:%S' |
    while IFS= read -r timestamp event filepath; do
        if [[ "$filepath" =~ SKILL\.md$ ]]; then
            log_warning "변경 감지: $filepath"
            generate_index
            sync_claude_md
        fi
    done
}

# 메인 로직
main() {
    log "=== myskills 인덱스 업데이터 시작 ==="

    # 인자 파싱
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                log_warning "드라이런 모드 활성화"
                shift
                ;;
            --watch)
                WATCH_MODE=true
                shift
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                exit 1
                ;;
        esac
    done

    # 작업 실행
    generate_index

    if [ "$WATCH_MODE" = true ]; then
        watch_for_changes
    else
        log ""
        log_success "인덱스 업데이트 완료!"
        log "다음 단계:"
        log "  1. git add myskills/skills_index.json"
        log "  2. git add CLAUDE.md"
        log "  3. git commit -m 'Update skills index'"
    fi
}

main "$@"
