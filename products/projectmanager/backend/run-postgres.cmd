@echo off
REM Load .env, then start with the postgres profile. Keep this file ASCII-only (see start.cmd).
cd /d "%~dp0"
if not exist .env ( echo .env not found. Copy .env.example to .env and fill it in. & exit /b 1 )
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
call mvnw.cmd -q -B spring-boot:run -Dspring-boot.run.profiles=postgres
