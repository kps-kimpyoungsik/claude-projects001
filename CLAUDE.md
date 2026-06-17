# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Structure

This is a multi-project workspace with subdirectories for different concerns:

- `..education/class01/` — Class/learning materials
- `admin/` — Admin agent template stubs
- `desigin-type/type01/` — UI design type templates (component/, layout/)
- `guide/` — Reference notes (token optimization, etc.)
- `web-design/` — Web design project
- `web-plan/` — Web planning project

## Claude Code Usage Notes

Token optimization practices documented in `guide/token-/토큰최적화.txt`:
- Use `/context` to check token usage
- Use `/rename "task"` + `/clear` to segment work by task, then `/resume` to return
- Use `/compact "summary"` to compress context with a summary
- Model selection: `haiku` for simple queries, `sonnet` for coding, `opus` (via `/plan`) for complex design

## Common Commands

```bash
# Run Claude with full permissions
claude --dangerously-skip-permissions

# Check port usage and kill process
netstat -ano | findstr :8080
taskkill /F /PID <PID>

# Docker Postgres query
docker exec -it my-postgres psql -U myuser -d mydb -c "SELECT * FROM pg_stat_activity;"
```
## Global Policy: MD File Korean Translation Sync

All `.md` files written in English must be translated into Korean and synced to the `backup/` folder at the same relative path.

**Rules:**
- Trigger: any `.md` file is created or updated with English content
- Action: translate to Korean → write to `D:/gitlab/projects/backup/<same-relative-path>/<filename>.md`
- Empty files: create a corresponding empty file in backup (with `<!-- 원본 파일이 비어 있습니다 -->`)
- Keep structure identical: same folder hierarchy under `backup/`
- Do not translate code blocks, file paths, command strings, or technical identifiers

# Remote Control
 Enable Remote Control for all sessions    true