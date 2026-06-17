# ============================================================
# Voice Sample - 서버 시작 스크립트 (PowerShell)
# ============================================================
# 용도: Python STT 서버 + Go 웹 서버 동시 시작 (포트 정리 포함)
# 포트: Python(9002) + Go(8090)
# 기능: PID 확인 → 강제 종료 → 대기 → 재시작
# ============================================================
# 실행 방법:
#   powershell -ExecutionPolicy Bypass -File start-servers.ps1
# ============================================================

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Voice Sample Server Launcher (포트 정리 기능 포함)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 현재 디렉터리로 이동
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath
Write-Host "[현재 경로] $(Get-Location)"
Write-Host ""

# ==================== 1단계: 포트 정리 ====================
Write-Host "[1단계] 포트 정리 중..." -ForegroundColor Yellow
Write-Host ""

# 포트별 정리
$ports = @(
    @{Port=9002; Name="Python STT"},
    @{Port=8090; Name="Go 서버"}
)

foreach ($portInfo in $ports) {
    $port = $portInfo.Port
    $name = $portInfo.Name

    Write-Host "  [$name] 포트 $port 확인 중..." -ForegroundColor Cyan

    try {
        $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue

        if ($connections) {
            foreach ($conn in $connections) {
                $pid = $conn.OwningProcess
                $process = Get-Process -Id $pid -ErrorAction SilentlyContinue

                if ($process) {
                    Write-Host "    ✓ 발견된 프로세스:" -ForegroundColor Green
                    Write-Host "      - PID: $pid"
                    Write-Host "      - 프로세스명: $($process.ProcessName)"
                    Write-Host "    강제 종료 중..." -ForegroundColor Yellow

                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue

                    if ($?) {
                        Write-Host "    ✓ 강제 종료 완료"
                    } else {
                        Write-Host "    ⚠ 강제 종료 실패 (권한 문제?)"
                    }
                }
            }
        } else {
            Write-Host "    ℹ 사용 중인 프로세스 없음"
        }
    } catch {
        Write-Host "    ⚠ 포트 확인 중 오류: $_" -ForegroundColor Yellow
    }

    Write-Host ""
}

# Python 프로세스 전체 정리 (안전장치)
Write-Host "  [Python] 전체 Python 프로세스 정리 중..." -ForegroundColor Cyan
$pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    foreach ($proc in $pythonProcesses) {
        Write-Host "    강제 종료: PID $($proc.Id)" -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "    ✓ Python 전체 프로세스 종료 완료"
} else {
    Write-Host "    ℹ Python 프로세스 없음"
}

Write-Host ""
Write-Host "  포트 정리 대기 중... (3초)"
Start-Sleep -Seconds 3
Write-Host ""

# ==================== 2단계: Python STT 서버 시작 ====================
Write-Host "[2단계] Python STT 서버 시작 (포트 9002)..." -ForegroundColor Yellow

$pythonScript = @"
`$startTime = Get-Date
Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "Python STT Server (포트 9002)" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""
Write-Host "[시작] `$startTime"
Write-Host ""
python stt_server.py 9002
`$endTime = Get-Date
Write-Host ""
Write-Host "[중지] `$endTime"
Write-Host ""
Read-Host "프로세스 종료됨. 엔터를 눌러서 창 닫기"
"@

$pythonProcess = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoExit -Command `"$pythonScript`"" `
    -PassThru -WindowStyle Normal

Write-Host "  ✓ Python STT 서버 시작됨 (PID: $($pythonProcess.Id))"
Write-Host "  프로세스 ID 저장됨: $($pythonProcess.Id)"
Start-Sleep -Seconds 4
Write-Host ""

# ==================== 3단계: Go 웹 서버 시작 ====================
Write-Host "[3단계] Go 웹 서버 시작 (포트 8090)..." -ForegroundColor Yellow

$goScript = @"
`$startTime = Get-Date
Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Go Web Server (포트 8090)" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[시작] `$startTime"
Write-Host ""
`$env:STT_HOSTS = "ws://localhost:9002"
go run server.go
`$endTime = Get-Date
Write-Host ""
Write-Host "[중지] `$endTime"
Write-Host ""
Read-Host "프로세스 종료됨. 엔터를 눌러서 창 닫기"
"@

$goProcess = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoExit -Command `"$goScript`"" `
    -PassThru -WindowStyle Normal

Write-Host "  ✓ Go 웹 서버 시작됨 (PID: $($goProcess.Id))"
Write-Host "  프로세스 ID 저장됨: $($goProcess.Id)"
Write-Host ""

# ==================== 4단계: 완료 메시지 ====================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "[완료] 두 서버가 성공적으로 시작되었습니다!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

Write-Host "웹 접속:" -ForegroundColor Cyan
Write-Host "  http://localhost:8090/test-viz.html" -ForegroundColor Green
Write-Host ""

Write-Host "포트 정보:" -ForegroundColor Yellow
Write-Host "  [1] Go 웹 서버:       포트 8090  (PID: $($goProcess.Id))"
Write-Host "  [2] Python STT:      포트 9002  (PID: $($pythonProcess.Id))"
Write-Host ""

Write-Host "프로세스 상태:" -ForegroundColor Yellow
Write-Host "  시작 시간: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "  Python 상태: $($pythonProcess.ProcessName) (ID: $($pythonProcess.Id))"
Write-Host "  Go 상태: $($goProcess.ProcessName) (ID: $($goProcess.Id))"
Write-Host ""

Write-Host "서버 중지 방법:" -ForegroundColor Yellow
Write-Host "  방법 1: 각 터미널에서 Ctrl+C 입력"
Write-Host "  방법 2: 아래 PowerShell 명령 실행"
Write-Host ""
Write-Host "    Stop-Process -Id $($pythonProcess.Id) -Force  # Python STT 중지"
Write-Host "    Stop-Process -Id $($goProcess.Id) -Force      # Go 서버 중지"
Write-Host ""

Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

# 프로세스 모니터링 (선택사항)
Write-Host "서버 실행 중... (Ctrl+C 로 메인 스크립트 중지 가능)" -ForegroundColor Gray
Write-Host ""

# 프로세스 상태 확인
while ($true) {
    $pythonRunning = Get-Process -Id $pythonProcess.Id -ErrorAction SilentlyContinue
    $goRunning = Get-Process -Id $goProcess.Id -ErrorAction SilentlyContinue

    if (-not $pythonRunning -and -not $goRunning) {
        Write-Host ""
        Write-Host "[종료] 모든 서버가 중지되었습니다." -ForegroundColor Yellow
        break
    }

    Start-Sleep -Seconds 5
}
