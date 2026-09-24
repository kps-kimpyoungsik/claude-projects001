#!/usr/bin/env bash
# .env 를 환경변수로 올린 뒤 postgres 프로파일로 기동 (비밀번호를 명령행에 노출하지 않는다)
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo ".env 가 없습니다. .env.example 을 복사해 채우세요."; exit 1; }
set -a; . ./.env; set +a
exec ./mvnw -q -B spring-boot:run -Dspring-boot.run.profiles=postgres
