# 공통 명령어 모음

```bash
# 전체 권한으로 Claude 실행
claude --dangerously-skip-permissions

# Git Bash 스크립트 실행
& "C:\Program Files\Git\bin\bash.exe" ./myskills/scripts/sync-cli.sh manual
```

## 포트 관리

```bash
# 1. PID 찾기
netstat -ano | findstr :8080

# 2. 강제 종료
taskkill /F /PID 4567
```

## Docker

```bash
# Postgres 활성 세션 조회
docker exec -it my-postgres psql -U myuser -d mydb -c "SELECT * FROM pg_stat_activity;"
```

## 참고 경로

- `d:/gitlab/project/monitoring/.claude/commands/wireframe-save-history.md`
