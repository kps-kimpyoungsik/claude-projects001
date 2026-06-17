# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 이 저장소에서 작업할 때 참고하는 안내 문서입니다.

## 저장소 구조

이 저장소는 다양한 목적별 하위 디렉토리로 구성된 멀티 프로젝트 워크스페이스입니다:

- `..education/class01/` — 수업/학습 자료
- `admin/` — 관리자 에이전트 템플릿 스텁
- `desigin-type/type01/` — UI 디자인 타입 템플릿 (component/, layout/)
- `guide/` — 참고 노트 (토큰 최적화 등)
- `web-design/` — 웹 디자인 프로젝트
- `web-plan/` — 웹 기획 프로젝트

## Claude Code 사용 메모

`guide/token-/토큰최적화.txt`에 문서화된 토큰 최적화 방법:
- `/context` — 토큰 사용량 확인
- `/rename "작업명"` + `/clear` — 작업 단위로 분리 후, `/resume`으로 복귀
- `/compact "요약"` — 요약과 함께 컨텍스트 압축
- 모델 선택: 단순 질의는 `haiku`, 코딩은 `sonnet`, 복잡한 설계는 `opus` (`/plan` 경유)

## 공통 명령어

```bash
# 전체 권한으로 Claude 실행
claude --dangerously-skip-permissions

# 포트 사용 확인 및 프로세스 종료
netstat -ano | findstr :8080
taskkill /F /PID <PID>

# Docker Postgres 쿼리
docker exec -it my-postgres psql -U myuser -d mydb -c "SELECT * FROM pg_stat_activity;"
```

## 전역 정책: MD 파일 한국어 번역 싱크

영어로 작성된 모든 `.md` 파일은 한국어로 번역하여 `backup/` 폴더의 동일 경로에 싱크를 유지해야 합니다.

**규칙:**
- 트리거: 영어 내용이 포함된 `.md` 파일이 생성되거나 수정될 때
- 동작: 한국어로 번역 → `D:/gitlab/projects/backup/<동일-상대경로>/<파일명>.md` 에 저장
- 빈 파일: backup에도 동일하게 빈 파일 생성 (`<!-- 원본 파일이 비어 있습니다 -->`)
- 폴더 구조는 `backup/` 아래에 동일하게 유지
- 코드 블록, 파일 경로, 명령어 문자열, 기술 식별자는 번역하지 않음

## 원격 제어
모든 세션에서 원격 제어 활성화: true
