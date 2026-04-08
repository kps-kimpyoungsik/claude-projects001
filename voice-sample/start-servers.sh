#!/bin/bash
# ============================================================
# Voice Sample - 서버 시작 스크립트 (macOS/Linux)
# ============================================================
# 용도: Python STT 서버 + Go 웹 서버 동시 시작 (포트 정리 포함)
# 포트: Python(9002) + Go(8090)
# 기능: PID 확인 → 강제 종료 → 대기 → 재시작
# ============================================================

set +e  # 에러 발생해도 계속 진행

echo ""
echo "============================================================"
echo "  Voice Sample Server Launcher (포트 정리 기능 포함)"
echo "============================================================"
echo ""

# 현재 디렉터리로 이동
cd "$(dirname "$0")"
echo "[현재 경로] $(pwd)"
echo ""

# ==================== 1단계: 포트 정리 ====================
echo "[1단계] 포트 정리 중..."
echo ""

# 포트 9002 (Python STT)
echo "  [Python STT] 포트 9002 확인 중..."
PIDS=$(lsof -ti:9002)
if [ ! -z "$PIDS" ]; then
    echo "    ✓ 발견된 PID: $PIDS"
    for PID in $PIDS; do
        PS_NAME=$(ps -p $PID -o comm=)
        echo "      프로세스: $PS_NAME"
        echo "    강제 종료 중..."
        kill -9 $PID 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "    ✓ PID $PID 강제 종료 완료"
        else
            echo "    ⚠ PID $PID 종료 실패"
        fi
    done
else
    echo "    ℹ 사용 중인 프로세스 없음"
fi

echo ""

# 포트 8090 (Go 서버)
echo "  [Go Server] 포트 8090 확인 중..."
PIDS=$(lsof -ti:8090)
if [ ! -z "$PIDS" ]; then
    echo "    ✓ 발견된 PID: $PIDS"
    for PID in $PIDS; do
        PS_NAME=$(ps -p $PID -o comm=)
        echo "      프로세스: $PS_NAME"
        echo "    강제 종료 중..."
        kill -9 $PID 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "    ✓ PID $PID 강제 종료 완료"
        else
            echo "    ⚠ PID $PID 종료 실패"
        fi
    done
else
    echo "    ℹ 사용 중인 프로세스 없음"
fi

echo ""

# Python 프로세스 전체 정리 (안전장치)
echo "  [Python] 전체 Python 프로세스 정리 중..."
PYTHON_PIDS=$(pgrep -f "python.*stt_server")
if [ ! -z "$PYTHON_PIDS" ]; then
    echo "    발견된 Python 프로세스: $PYTHON_PIDS"
    kill -9 $PYTHON_PIDS 2>/dev/null
    echo "    ✓ Python 프로세스 전체 종료 완료"
else
    echo "    ℹ Python 프로세스 없음"
fi

echo ""
echo "  포트 정리 대기 중... (3초)"
sleep 3
echo ""

# ==================== 2단계: Python STT 서버 시작 ====================
echo "[2단계] Python STT 서버 시작 (포트 9002)..."
echo "  프로세스 시작 중..."
echo ""

python stt_server.py 9002 &
PYTHON_PID=$!

if ps -p $PYTHON_PID > /dev/null 2>&1; then
    echo "  ✓ Python STT 서버 시작됨"
    echo "    PID: $PYTHON_PID"
else
    echo "  ⚠ Python STT 서버 시작 실패!"
    exit 1
fi

sleep 4
echo ""

# ==================== 3단계: Go 웹 서버 시작 ====================
echo "[3단계] Go 웹 서버 시작 (포트 8090)..."
echo "  프로세스 시작 중..."
echo ""

export STT_HOSTS="ws://localhost:9002"
go run server.go &
GO_PID=$!

if ps -p $GO_PID > /dev/null 2>&1; then
    echo "  ✓ Go 웹 서버 시작됨"
    echo "    PID: $GO_PID"
else
    echo "  ⚠ Go 웹 서버 시작 실패!"
    kill -9 $PYTHON_PID 2>/dev/null
    exit 1
fi

echo ""

# ==================== 4단계: 완료 메시지 ====================
echo "============================================================"
echo "[완료] 두 서버가 성공적으로 시작되었습니다!"
echo "============================================================"
echo ""

echo "웹 접속:"
echo "  http://localhost:8090/test-viz.html"
echo ""

echo "포트 정보:"
echo "  [1] Go 웹 서버:       포트 8090  (PID: $GO_PID)"
echo "  [2] Python STT:      포트 9002  (PID: $PYTHON_PID)"
echo ""

echo "프로세스 상태:"
CURRENT_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "  시작 시간: $CURRENT_TIME"
echo ""

echo "서버 중지 방법:"
echo "  방법 1: Ctrl+C 입력"
echo "  방법 2: 아래 명령 실행"
echo ""
echo "    kill $PYTHON_PID  # Python STT 중지"
echo "    kill $GO_PID      # Go 서버 중지"
echo ""

echo "또는:"
echo "    pkill -f 'python stt_server'  # Python 프로세스 중지"
echo "    pkill -f 'go run'              # Go 프로세스 중지"
echo ""

echo "============================================================"
echo ""

# 프로세스 모니터링
echo "서버 실행 중... (Ctrl+C 로 중지 가능)"
echo ""

# 부모 프로세스가 종료될 때까지 대기
trap "echo ''; echo '[종료] 서버를 중지합니다...'; kill $PYTHON_PID $GO_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait $PYTHON_PID $GO_PID 2>/dev/null

echo ""
echo "[종료] 모든 서버가 중지되었습니다."
echo ""
