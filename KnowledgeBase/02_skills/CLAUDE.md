# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a curated **AI Agent Skills** repository containing ~57 reusable skills and tools for extending the capabilities of AI coding assistants. Skills follow the universal `SKILL.md` specification and are compatible across multiple agent platforms (Claude Code, GitHub Copilot, Cursor, Gemini CLI, etc.).

### Key Directories

- **`antigravity-skills/`** - Main skills library (~57 skills)
  - `skills/` - Individual skill directories (each with at least `SKILL.md`)
  - `spec/Specification.md` - Official format specification
  - `template/SKILL.md` - Template for new skills
  - `scripts/sync_skills.sh` - Sync script for upstream sources
  - `skills_sources.json` - Upstream repository configuration
  - `skills_index.json` - Metadata index of all skills

- **`myskills/`** - Custom user skills and guides (4 skills + 1 guide collection)
  - `skills_index.json` - Metadata index of all custom skills
  - `ai-team-works/` - AI team composition, orchestration & workflow design (v2.0.0)
  - `skill-creator/` - Automated skill creation tool
  - `skill-creator-ext/` - Extended skill creator with FMSC & Prompt Engineering
  - `info-collector-analyst/` - Project scale assessment & architecture analysis
  - `prd_rule__guide_prompts/` - PRD development rules with security guidelines (5 phases, 210 items)

## Core Concepts

### SKILL.md Format

Every skill is a directory containing a `SKILL.md` file with:

1. **YAML Frontmatter** (required)
   ```yaml
   ---
   name: skill-name
   description: What this skill does and when to use it.
   ---
   ```

2. **Markdown Body** - Step-by-step instructions for the agent

3. **Optional Directories**
   - `scripts/` - Executable code (Python, Bash, JavaScript)
   - `references/` - Additional documentation files
   - `assets/` - Templates, images, data files
   - `examples/` - Usage examples

### Naming Conventions

- Skill names: lowercase, hyphens only (`skill-name`, not `skillName`)
- Must match parent directory name
- Max 64 characters
- Cannot start/end with hyphens or use consecutive hyphens

## Common Commands

### Sync Skills from Upstream Sources

```bash
# Sync ALL configured upstream sources
./antigravity-skills/scripts/sync_skills.sh

# Sync a specific source (e.g., Anthropic's skills)
./antigravity-skills/scripts/sync_skills.sh anthropics-skills

# Sync a specific source (e.g., Vercel's React best practices)
./antigravity-skills/scripts/sync_skills.sh vercel-labs/agent-skills
```

**Requirements**: `jq`, `git`, `rsync`

**Config File**: `antigravity-skills/skills_sources.json` defines all upstream repositories and sync rules.

### List All Available Skills

```bash
# View all custom skill metadata (myskills)
cat myskills/skills_index.json | jq .

# View upstream skill metadata
cat antigravity-skills/skills_index.json | jq .

# List all skill directories
ls antigravity-skills/skills/
ls myskills/
```

### Create a New Custom Skill

1. Use the automated skill creator (if invoking Claude)
2. Or manually:
   ```bash
   # Copy template
   mkdir myskills/my-skill
   cp antigravity-skills/template/SKILL.md myskills/my-skill/SKILL.md
   ```

3. Edit the SKILL.md file:
   - Update frontmatter (name, description)
   - Add step-by-step instructions in Markdown
   - Optionally add `scripts/`, `references/`, or `assets/` directories

### Validate a Skill

Check that a skill follows the specification:

```bash
# Using skills-ref (if installed)
skills-ref validate myskills/my-skill

# Or manually verify:
# - SKILL.md exists in skill directory
# - name field matches directory name
# - description is 1-1024 characters
# - Only lowercase letters, numbers, hyphens in name
# - No consecutive hyphens or leading/trailing hyphens
```

### Manage Custom Skills Index

The `myskills/skills_index.json` maintains metadata for all custom skills:

```bash
# View custom skill index
cat myskills/skills_index.json | jq .

# View specific skill metadata
cat myskills/skills_index.json | jq '.skills[] | select(.name == "ai-team-works")'

# List all custom skills with versions
cat myskills/skills_index.json | jq '.skills[] | {name, version, category}'
```

**Index includes**:
- Skill name, version, author, creation/update dates
- Category, platforms, and tags
- Links to SKILL.md, CHANGELOG.md, examples, and references
- Statistics (total lines, security items, etc.)

## Architecture & Structure

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

---

### Skill Organization

Skills are organized by category in `antigravity-skills/`:

1. **Creative & Design** (`canvas-design`, `frontend-design`, `ui-ux-pro-max`, etc.)
2. **Development & Engineering** (`composition-patterns`, `react-best-practices`, `test-driven-development`, etc.)
3. **Documentation & Office** (`obsidian-markdown`, `pdf`, `xlsx`, `pptx`, `docx`, etc.)
4. **Planning & Workflow** (`brainstorming`, `writing-plans`, `executing-plans`, etc.)
5. **Core Cognition & Architecture** (`memory-systems`, `context-compression`, `bdi-mental-states`, etc.)
6. **System Design & Evaluation** (`tool-design`, `evaluation`, `project-development`, etc.)
7. **System Extension** (`mcp-builder`, `skill-creator`, `multi-agent-patterns`, etc.)

### Upstream Sources

Skills sync from these open-source repositories (see `skills_sources.json`):

- **anthropics-skills** - Official Anthropic API usage paradigms
- **ui-ux-pro-max** - Top-tier UI/UX design intelligence
- **superpowers** - LLM "superpowers" toolkit
- **planning-with-files** - File-based task planning (Manus-style)
- **notebooklm** - Google NotebookLM integration
- **context-engineering** - Context compression, optimization, degradation
- **obsidian-skills** - Obsidian integration
- **remotion-skills** - Video creation in React
- **vercel-labs/agent-skills** - React best practices, composition patterns
- **supabase/agent-skills** - Postgres performance optimization

### Directory Structure Decision

**Why `antigravity-skills/` vs `myskills/`?**

- **`antigravity-skills/`** - Contains synced upstream skills (managed by `sync_skills.sh`). Don't manually edit; re-run sync to get latest versions.
- **`myskills/`** - Contains custom skills specific to this project. Edit freely.

## Development Workflow

### When Adding a New Custom Skill

1. **Create the directory** in `myskills/`
2. **Write `SKILL.md`** following the specification
3. **Add supporting files** (optional): scripts, references, assets
4. **Document the skill** with clear instructions and examples
5. **Test the skill** in Claude Code or your agent platform

### When Updating Existing Upstream Skills

1. **Never edit files in `antigravity-skills/`** directly
2. Instead, **update the upstream source** (the GitHub repo the skill came from)
3. Then run `./antigravity-skills/scripts/sync_skills.sh SOURCE_NAME` to pull changes

### Sync Configuration Best Practices

The `skills_sources.json` file uses copy rules with `include`/`exclude` filters. Example:

```json
{
  "name": "anthropics-skills",
  "repo_url": "https://github.com/anthropics/skills.git",
  "branch": "main",
  "copy_rules": [
    {
      "source": "skills",
      "dest": "skills",
      "exclude": []
    }
  ]
}
```

- Adjust `exclude` to skip unwanted files
- Use `include` to copy only specific files
- The `sync_skills.sh` script handles the rest

## Key Files & References

- **Specification**: `antigravity-skills/spec/Specification.md` - Complete format details
- **Contributing Guide**: `antigravity-skills/CONTRIBUTING.md` - How to contribute to upstream
- **Documentation**: `antigravity-skills/docs/Antigravity_Skills_Manual.en.md` - Full user manual
- **Changelog**: `antigravity-skills/CHANGELOG.md` - Version history and feature additions

## Platform Compatibility

Skills work with these agent platforms:

| Platform | Project Path | Global Path |
|----------|---------|------------|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Gemini CLI | `.gemini/skills/` | `~/.gemini/skills/` |
| Codex | `.codex/skills/` | `~/.codex/skills/` |
| General | `.agent/skills/` | `~/.agent/skills/` |

## Security & Development Guidelines

### PRD Rule & Guide Prompts

The `prd_rule__guide_prompts/` collection provides comprehensive security guidance across 5 development phases:

- **Phase 1 (Analysis)**: 40 items - OWASP Top 10 analysis, WCAG 2.1 accessibility audit, tech stack security
- **Phase 2 (Design)**: 35 items - Authentication/authorization design, data security architecture, HTTPS/TLS design
- **Phase 3 (Development)**: 45 items - Secure coding fundamentals, RBAC implementation, file upload security
- **Phase 4 (Testing)**: 50 items - Functional security tests, vulnerability testing, security header verification
- **Phase 5 (Review)**: 40 items - Code review checklist, input/output validation, dependency security

**Total**: 210 security checklist items with code examples and tool integration (axe DevTools, Lighthouse, npm audit).

Reference: `myskills/prd_rule__guide_prompts/SECURITY-GUIDE-INDEX.md`

---

## Automation & Git Hooks

### Auto-Sync System

When a skill changes, `skills_index.json` and `CLAUDE.md` are automatically synchronized via git hooks:

**Pre-commit Hook** (`.git/hooks/pre-commit`):
- Triggers when `myskills/*/SKILL.md` changes
- Automatically runs `update-index.sh` → regenerates `skills_index.json`
- Automatically runs `sync-claude.sh` → updates `CLAUDE.md`
- Auto-stages the modified files and continues commit

**Post-merge Hook** (`.git/hooks/post-merge`):
- Triggers after `git merge` or `git pull`
- Detects myskills changes from remote
- Regenerates indexes and syncs documentation
- Notifies user of changes

### Available Scripts

Located in `myskills/scripts/`:

1. **update-index.sh** - Scans all SKILL.md files and generates `skills_index.json`
   ```bash
   ./myskills/scripts/update-index.sh           # Full regeneration
   ./myskills/scripts/update-index.sh --dry-run # Preview only
   ./myskills/scripts/update-index.sh --watch   # Continuous monitoring
   ```

2. **sync-claude.sh** - Updates CLAUDE.md based on `skills_index.json`
   ```bash
   ./myskills/scripts/sync-claude.sh            # Sync all sections
   ./myskills/scripts/sync-claude.sh --section key-dirs     # Key Directories only
   ./myskills/scripts/sync-claude.sh --section architecture # Architecture only
   ```

3. **README.md** - Complete automation guide
   ```bash
   cat myskills/scripts/README.md  # Read full documentation
   ```

### Setup Instructions

```bash
# Ensure hooks are executable
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/post-merge
chmod +x myskills/scripts/*.sh

# Install jq (required)
# Linux: sudo apt-get install jq
# macOS: brew install jq
```

### Common Workflows

**Add a new skill:**
```bash
mkdir myskills/new-skill
# Write SKILL.md ...
git add myskills/new-skill/SKILL.md
git commit -m "Add new skill"  # Hooks auto-run
```

**Update skill version:**
```bash
# Edit SKILL.md version field
git add myskills/my-skill/SKILL.md
git commit -m "Update skill version"  # Hooks auto-run
```

**Pull remote changes:**
```bash
git pull origin main  # Post-merge hook auto-runs
# Review suggested changes:
git diff myskills/skills_index.json
git diff CLAUDE.md
```

---

## Notes

- This repository uses **symbolic links** for skill installation, so changes in the git repo automatically sync to agent platforms
- Skills are **progressive disclosure** - metadata loads first, full SKILL.md loads only when invoked
- Keep individual `SKILL.md` files under 500 lines; move detailed content to separate `references/` files
- The `skill-creator` skill in `myskills/` automates the entire workflow for building new skills
- Custom skills are indexed in `myskills/skills_index.json` for easy discovery and management
- **Skills auto-sync** - when you modify SKILL.md files, `skills_index.json` and `CLAUDE.md` update automatically via git hooks
- The `ai-team-works` skill provides production-ready AI team orchestration patterns with case studies showing 14-19% schedule reduction
- Security guides in `prd_rule__guide_prompts/` are application-agnostic and work across all tech stacks
- For detailed automation documentation, see `myskills/scripts/README.md`
