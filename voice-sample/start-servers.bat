@echo off
REM ============================================================
REM Voice Sample - 서버 시작 스크립트 (Windows)
REM ============================================================
REM 용도: Python STT 서버 + Go 웹 서버 동시 시작 (포트 정리 포함)
REM 포트: Python(9002) + Go(8090)
REM 기능: PID 확인 → 강제 종료 → 대기 → 재시작
REM ============================================================

chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   Voice Sample Server Launcher (포트 정리 기능 포함)
echo ============================================================
echo.

REM 현재 디렉터리 확인
cd /d %~dp0
echo [현재 경로] %cd%
echo.

REM ==================== 1단계: 포트 정리 ====================
echo [1단계] 포트 9002 (Python STT) 정리 중...

REM 포트 9002 확인
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :9002') do (
    if not "%%a"=="" (
        echo   발견된 PID: %%a
        taskkill /F /PID %%a 2>nul
        if !errorlevel! equ 0 (
            echo   ✓ PID %%a 강제 종료 완료
        ) else (
            echo   ⚠ PID %%a 종료 실패
        )
    )
)

echo   대기 중... (3초)
timeout /t 3 /nobreak

echo.
echo [1단계-2] 포트 8090 (Go 서버) 정리 중...

REM 포트 8090 확인
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8090') do (
    if not "%%a"=="" (
        echo   발견된 PID: %%a
        taskkill /F /PID %%a 2>nul
        if !errorlevel! equ 0 (
            echo   ✓ PID %%a 강제 종료 완료
        ) else (
            echo   ⚠ PID %%a 종료 실패
        )
    )
)

echo   대기 중... (3초)
timeout /t 3 /nobreak

REM Python 프로세스 전체 정리 (안전장치)
taskkill /F /IM python.exe 2>nul
if !errorlevel! equ 0 (
    echo.
    echo [1단계-3] Python 프로세스 전체 종료 완료
    timeout /t 2 /nobreak
)

REM ==================== 2단계: Python STT 서버 시작 ====================
echo.
echo [2단계] Python STT 서버 시작 (포트 9002)...
echo   프로세스 시작 중...

start "Python STT (9002)" cmd /k ^
  "title Python STT Server (9002) && ^
   echo. && ^
   echo ================================== && ^
   echo   Python STT Server (포트 9002) && ^
   echo ================================== && ^
   echo. && ^
   echo [시작] %time% && ^
   echo. && ^
   python stt_server.py 9002 && ^
   echo. && ^
   echo [중지] %time% && ^
   pause"

echo   ✓ Python STT 터미널 시작됨
timeout /t 4 /nobreak

REM ==================== 3단계: Go 웹 서버 시작 ====================
echo.
echo [3단계] Go 웹 서버 시작 (포트 8090)...
echo   프로세스 시작 중...

start "Go Server (8090)" cmd /k ^
  "title Go Server (8090) && ^
   echo. && ^
   echo ================================== && ^
   echo   Go Web Server (포트 8090) && ^
   echo ================================== && ^
   echo. && ^
   echo [시작] %time% && ^
   echo. && ^
   set STT_HOSTS=ws://localhost:9002 && ^
   go run server.go && ^
   echo. && ^
   echo [중지] %time% && ^
   pause"

echo   ✓ Go 서버 터미널 시작됨
timeout /t 2 /nobreak

REM ==================== 4단계: 완료 메시지 ====================
echo.
echo ============================================================
echo [완료] 두 서버가 성공적으로 시작되었습니다.
echo ============================================================
echo.
echo 접속 주소: http://localhost:8090/test-viz.html
echo.
echo 포트 정보:
echo   [1] Go 웹 서버:    포트 8090
echo   [2] Python STT:    포트 9002
echo.
echo 아래 터미널 창이 자동으로 열렸습니다:
echo   - 터미널 1: Go Server (8090)
echo   - 터미널 2: Python STT (9002)
echo.
echo 서버 중지 방법:
echo   - 각 터미널에서 Ctrl+C 입력
echo   - 또는 터미널 닫기 버튼 클릭
echo.
echo ============================================================
echo.

pause
