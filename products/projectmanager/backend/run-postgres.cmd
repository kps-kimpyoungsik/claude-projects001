@echo off
REM .env 를 환경변수로 올린 뒤 postgres 프로파일로 기동
cd /d "%~dp0"
if not exist .env ( echo .env 가 없습니다. .env.example 을 복사해 채우세요. & exit /b 1 )
for /f "usebackq tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
call mvnw.cmd -q -B spring-boot:run -Dspring-boot.run.profiles=postgres
