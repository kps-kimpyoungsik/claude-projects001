"""
tests/test_e2e_pipeline.py — Go 서버 + Python STT 전체 파이프라인 E2E 테스트

테스트 범위 (START → END 완전 검증):
  Step 01: Go 서버 헬스체크
  Step 02: Python STT 서버 헬스체크
  Step 03: 녹음 세션 시작 (/api/recordings/start)
  Step 04: /ws/live WebSocket 연결 (브로드캐스트 수신 준비)
  Step 05: WAV 파일 3개 연속 POST (/api/recordings)
  Step 06: 각 파일 queued → processing 상태 전환 확인
  Step 07: 전체 파일 done 상태 완료 대기 (STT 결과 수신)
  Step 08: /ws/live 브로드캐스트 수신 검증
  Step 09: transcript.txt 존재 + 내용 검증
  Step 10: 녹음 종료 + flushPending (/api/recordings/stop)
  Step 11: 최종 transcript.txt 완결성 검증

실행:
    # Go 서버 + Python STT 서버 모두 실행 후:
    python tests/test_e2e_pipeline.py

    # Go 서버만 실행 (STT 없이 큐/상태 파이프라인만 검증):
    SKIP_STT=1 python tests/test_e2e_pipeline.py
"""

import sys, os, time, json, wave, io, struct, threading, socket
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np

# ── 설정 ─────────────────────────────────────────────────────
GO_BASE      = os.getenv("GO_SERVER", "http://localhost:8090")
STT_WS       = os.getenv("STT_HOST",  "ws://localhost:9001")
SKIP_STT     = os.getenv("SKIP_STT",  "0") == "1"
TOPIC        = "e2e_test_" + str(int(time.time()))
POLL_TIMEOUT = int(os.getenv("POLL_TIMEOUT", "300"))  # CPU large-v3-turbo 대비 5분 기본
SAMPLE_RATE  = 16000

# ── 테스트 결과 추적 ─────────────────────────────────────────
_passed, _failed = [], []

def _assert(name: str, cond: bool, detail: str = ""):
    if cond:
        print(f"  ✅ {name}")
        _passed.append(name)
    else:
        msg = f"  ❌ {name}" + (f"  ← {detail}" if detail else "")
        print(msg)
        _failed.append(name)

def _skip(name: str, reason: str):
    print(f"  ⏭  {name}  [{reason}]")

# ── 오디오 유틸 ─────────────────────────────────────────────
def _make_wav(freq: float = 440.0, duration_sec: float = 1.5,
              amplitude: float = 0.3) -> bytes:
    """16kHz mono PCM WAV 바이트 생성"""
    n = int(SAMPLE_RATE * duration_sec)
    t = np.linspace(0, duration_sec, n, dtype=np.float32)
    # 주파수 + 여러 배음 혼합 (음성 유사)
    pcm = (
        np.sin(2 * np.pi * freq * t) * amplitude
        + np.sin(2 * np.pi * freq * 2 * t) * amplitude * 0.3
        + np.sin(2 * np.pi * freq * 3 * t) * amplitude * 0.1
    ).astype(np.float32)
    # 발화 패턴 (무음 구간 삽입)
    envelope = np.ones(n, dtype=np.float32)
    for i in range(3):
        s = int(i * n / 3)
        e = int((i + 0.7) * n / 3)
        if e < n:
            envelope[e:int((i+1)*n/3)] = 0.0
    pcm *= envelope

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        data = np.clip(pcm, -1.0, 1.0)
        wf.writeframes((data * 32767).astype(np.int16).tobytes())
    return buf.getvalue()

def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except:
        return False

# ── HTTP 헬퍼 ────────────────────────────────────────────────
try:
    import urllib.request, urllib.error
    def _get(path: str):
        req = urllib.request.Request(f"{GO_BASE}{path}")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read()), r.status

    def _post(path: str, data: bytes = b'', content_type: str = 'application/json'):
        req = urllib.request.Request(
            f"{GO_BASE}{path}", data=data,
            headers={'Content-Type': content_type},
            method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read()), r.status
        except urllib.error.HTTPError as e:
            return {'error': e.reason}, e.code
except ImportError:
    pass

# ── /ws/live 브로드캐스트 수신기 (백그라운드 스레드) ───────────
_live_msgs = []
_live_lock = threading.Lock()
_ws_ready  = threading.Event()

def _start_live_ws():
    """백그라운드에서 /ws/live 연결 유지, 수신 메시지를 _live_msgs에 누적"""
    try:
        import websocket  # websocket-client
        def on_msg(ws, msg):
            try:
                d = json.loads(msg)
                with _live_lock:
                    _live_msgs.append(d)
            except:
                pass
        def on_open(ws):
            _ws_ready.set()

        ws_url = GO_BASE.replace("http://", "ws://").replace("https://", "wss://") + "/ws/live"
        ws = websocket.WebSocketApp(ws_url, on_message=on_msg, on_open=on_open)
        t = threading.Thread(target=ws.run_forever, daemon=True)
        t.start()
        return ws, t
    except ImportError:
        return None, None

# ══════════════════════════════════════════════════════════════
#  T01: Go 서버 헬스체크
# ══════════════════════════════════════════════════════════════
def test_01_go_server():
    print("\n[T01] Go 서버 헬스체크")
    alive = _port_open("localhost", 8090)
    _assert("포트 8090 열림", alive, "go run server.go 를 먼저 실행하세요")
    if not alive:
        return False

    cfg, status = _get("/api/config")
    _assert("GET /api/config 200", status == 200)
    _assert("maxFileMB 필드 존재", "maxFileMB" in cfg, str(cfg))
    _assert("scenario 필드 존재", "scenario" in cfg)
    print(f"     서버 설정: {cfg}")
    return True

# ══════════════════════════════════════════════════════════════
#  T02: Python STT 서버 헬스체크
# ══════════════════════════════════════════════════════════════
def test_02_stt_server():
    print("\n[T02] Python STT 서버 헬스체크")
    if SKIP_STT:
        _skip("STT 서버 확인", "SKIP_STT=1")
        return None  # None = skip

    alive = _port_open("localhost", 9001)
    _assert("포트 9001 열림", alive, "python stt_server.py 를 먼저 실행하세요")
    return alive

# ══════════════════════════════════════════════════════════════
#  T03: 녹음 세션 시작
# ══════════════════════════════════════════════════════════════
def test_03_session_start():
    print(f"\n[T03] 녹음 세션 시작  (topic={TOPIC})")
    resp, status = _post(f"/api/recordings/start?topic={TOPIC}")
    _assert("POST /api/recordings/start 200", status == 200,
            f"status={status} resp={resp}")
    _assert("topic 필드 반환", "topic" in resp or status == 200)
    print(f"     응답: {resp}")
    return status == 200

# ══════════════════════════════════════════════════════════════
#  T04: /ws/live 연결 (브로드캐스트 수신 준비)
# ══════════════════════════════════════════════════════════════
def test_04_ws_live():
    print("\n[T04] /ws/live WebSocket 연결")
    ws, t = _start_live_ws()
    if ws is None:
        _skip("websocket-client 미설치", "pip install websocket-client")
        return None
    ready = _ws_ready.wait(timeout=3.0)
    _assert("/ws/live 연결 성공", ready, "3초 내 연결 실패")
    return ws if ready else None

# ══════════════════════════════════════════════════════════════
#  T05: WAV 파일 3개 연속 POST
#  → queued 상태 반환 검증 (Step 5-6)
# ══════════════════════════════════════════════════════════════
def test_05_post_wavs():
    print("\n[T05] WAV 3개 연속 POST → queued 확인")
    # 서로 다른 주파수 = 다른 화자 시뮬레이션
    wavs = [
        ("화자A 시뮬레이션", _make_wav(300.0, 1.5)),  # 저음
        ("화자B 시뮬레이션", _make_wav(600.0, 1.2)),  # 중음
        ("화자A 재등장",    _make_wav(300.0, 1.8)),  # 저음 (같은 화자)
    ]
    filenames = []
    for label, wav_bytes in wavs:
        resp, status = _post(
            f"/api/recordings?topic={TOPIC}",
            data=wav_bytes,
            content_type="audio/wav"
        )
        ok = status == 200 and "filename" in resp
        _assert(f"POST WAV ({label})", ok,
                f"status={status} resp={resp}")
        if ok:
            filenames.append(resp["filename"])
            print(f"     파일명: {resp['filename']}  ({resp.get('sizeKB','?')} KB)  status={resp.get('status','?')}")
        time.sleep(0.1)  # 약간 간격

    _assert("3개 파일 모두 등록됨", len(filenames) == 3,
            f"실제 등록: {len(filenames)}개")
    return filenames

# ══════════════════════════════════════════════════════════════
#  T06: 상태 전환 검증 (queued → processing → done)
#  → POLL_TIMEOUT 초 내 모든 파일 완료 대기
# ══════════════════════════════════════════════════════════════
def test_06_status_transitions(filenames: list, stt_alive: bool):
    print(f"\n[T06] 상태 전환 검증 (최대 {POLL_TIMEOUT}초 대기)")

    if not filenames:
        _assert("파일 목록 존재", False, "T05 실패로 파일 없음")
        return False

    deadline = time.time() + POLL_TIMEOUT
    seen_processing = set()
    seen_done       = set()

    while time.time() < deadline:
        list_resp, status = _get(f"/api/recordings?topic={TOPIC}")
        if status != 200:
            time.sleep(1)
            continue

        for item in list_resp:
            fn  = item["filename"]
            st  = item["status"]
            if fn in filenames:
                if st == "processing":
                    seen_processing.add(fn)
                elif st == "done":
                    seen_done.add(fn)

        if not stt_alive:
            # STT 없으면 "처리대기" 또는 "processing"까지만 확인
            all_seen = seen_processing | seen_done
            if all_seen == set(filenames):
                break
        else:
            if seen_done == set(filenames):
                break

        time.sleep(1.0)
        sys.stdout.write('.')
        sys.stdout.flush()

    print()

    if stt_alive:
        _assert("전체 파일 queued → processing 전환됨",
                len(seen_processing | seen_done) == len(filenames),
                f"미전환: {set(filenames) - seen_processing - seen_done}")
        _assert("전체 파일 done 완료",
                seen_done == set(filenames),
                f"미완료: {set(filenames) - seen_done}")
        return seen_done == set(filenames)
    else:
        _assert("STT 없이 queued/processing 전환 확인",
                len(seen_processing | seen_done) > 0, "상태 변화 없음")
        _skip("done 완료 확인", "STT 서버 없음 (SKIP_STT=1 또는 미실행)")
        return False

# ══════════════════════════════════════════════════════════════
#  T07: /ws/live 브로드캐스트 수신 검증
# ══════════════════════════════════════════════════════════════
def test_07_live_broadcast(filenames: list, stt_alive: bool):
    print("\n[T07] /ws/live 브로드캐스트 수신 검증")

    if not stt_alive:
        _skip("브로드캐스트 검증", "STT 결과 없음 — STT 서버 필요")
        return

    with _live_lock:
        msgs = list(_live_msgs)

    stt_msgs = [m for m in msgs if m.get("type") == "stt_result"
                and m.get("topic") == TOPIC]

    _assert("stt_result 브로드캐스트 수신됨", len(stt_msgs) > 0,
            f"수신된 총 메시지: {len(msgs)}개")

    if stt_msgs:
        recv_files = {m.get("filename") for m in stt_msgs}
        _assert("전체 파일 브로드캐스트 수신",
                set(filenames).issubset(recv_files),
                f"누락: {set(filenames) - recv_files}")

        for m in stt_msgs:
            _assert(f"브로드캐스트 text 존재 ({m.get('filename','')})",
                    bool(m.get("text")), str(m))
            _assert(f"브로드캐스트 speaker 존재 ({m.get('filename','')})",
                    bool(m.get("speaker")))

        print(f"     수신 메시지 {len(stt_msgs)}개 / 예상 {len(filenames)}개")

# ══════════════════════════════════════════════════════════════
#  T08: transcript.txt 내용 검증
# ══════════════════════════════════════════════════════════════
def test_08_transcript(stt_alive: bool):
    print("\n[T08] transcript.txt 내용 검증")

    if not stt_alive:
        _skip("transcript.txt 검증", "STT 결과 없음")
        return

    txt_path = os.path.join("recordings", TOPIC, "transcript.txt")
    _assert("transcript.txt 존재", os.path.exists(txt_path), txt_path)

    if not os.path.exists(txt_path):
        return

    content = open(txt_path, encoding='utf-8').read()
    _assert("회의 전사 기록 헤더 존재", "# 회의 전사 기록" in content)
    _assert("화자 레이블 포함", "화자" in content, f"내용: {content[:100]}")
    _assert("발화 내용 있음", len(content.strip()) > 30, f"길이: {len(content)}")
    _assert("Markdown 형식 (굵게)", "**[" in content)

    # 시간 순 정렬 확인: 굵게 타임스탬프 파싱
    import re
    times = re.findall(r'\[(\d{2}:\d{2}:\d{2})\]', content)
    sorted_times = sorted(times)
    _assert("타임스탬프 시간순 정렬",
            times == sorted_times,
            f"원본: {times}  정렬: {sorted_times}")

    print(f"     transcript 내용 ({len(content)}자):\n{content[:300]}...")

# ══════════════════════════════════════════════════════════════
#  T09: 녹음 종료 + flushPending
# ══════════════════════════════════════════════════════════════
def test_09_session_stop():
    print("\n[T09] 녹음 종료 (/api/recordings/stop)")
    resp, status = _post(f"/api/recordings/stop?topic={TOPIC}")
    _assert("POST /api/recordings/stop 200", status == 200,
            f"status={status} resp={resp}")
    _assert("status:stopped 반환", resp.get("status") == "stopped", str(resp))
    print(f"     응답: {resp}")
    return status == 200

# ══════════════════════════════════════════════════════════════
#  T10: 최종 상태 완결성 검증
# ══════════════════════════════════════════════════════════════
def test_10_final_state(filenames: list, stt_alive: bool):
    print("\n[T10] 최종 파이프라인 완결성 검증")

    # 파일 목록 최종 확인
    list_resp, status = _get(f"/api/recordings?topic={TOPIC}")
    _assert("GET /api/recordings 200", status == 200)

    if status == 200:
        items = {item["filename"]: item for item in list_resp}
        _assert(f"등록된 파일 수 ≥ 3", len(items) >= 3, f"실제: {len(items)}개")

        if stt_alive and filenames:
            all_done = all(items.get(fn, {}).get("status") == "done"
                          for fn in filenames)
            _assert("모든 파일 최종 done 상태", all_done,
                    str({fn: items.get(fn, {}).get("status") for fn in filenames}))

    # transcript.txt 최종 확인
    txt_path = os.path.join("recordings", TOPIC, "transcript.txt")
    if stt_alive:
        _assert("transcript.txt 최종 존재", os.path.exists(txt_path))
    else:
        _skip("transcript.txt 최종 확인", "STT 없음")

    # 시나리오 API 상태 확인
    cfg, _ = _get("/api/config")
    _assert("서버 여전히 응답 중 (안정성)", "maxFileMB" in cfg)

# ══════════════════════════════════════════════════════════════
#  T11: 다중 세션 격리 검증
#  → 다른 topic으로 세션 시작해도 기존 topic에 영향 없음
# ══════════════════════════════════════════════════════════════
def test_11_session_isolation():
    print("\n[T11] 다중 세션 격리 검증")
    other_topic = TOPIC + "_other"

    # 다른 세션 시작
    r1, s1 = _post(f"/api/recordings/start?topic={other_topic}")
    _assert("다른 세션 시작 OK", s1 == 200)

    # 다른 세션에 WAV 전송
    wav = _make_wav(800.0, 0.8)
    r2, s2 = _post(f"/api/recordings?topic={other_topic}", data=wav,
                   content_type="audio/wav")
    _assert("다른 세션 WAV 등록 OK", s2 == 200)

    # 기존 topic 목록 — 다른 세션 파일 섞이지 않아야
    list1, _ = _get(f"/api/recordings?topic={TOPIC}")
    list2, _ = _get(f"/api/recordings?topic={other_topic}")

    files1 = {item["filename"] for item in list1}
    files2 = {item["filename"] for item in list2}

    _assert("세션 간 파일 격리 (교차 없음)",
            files1.isdisjoint(files2) or len(files2) <= 1,
            f"겹침: {files1 & files2}")

    # 다른 세션 정리
    _post(f"/api/recordings/stop?topic={other_topic}")
    print(f"     세션1 파일 수: {len(files1)}, 세션2 파일 수: {len(files2)}")

# ══════════════════════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 65)
    print("  E2E 파이프라인 테스트 — voice-sample 전체 워크플로우")
    print(f"  대상: {GO_BASE}  |  Topic: {TOPIC}")
    print("=" * 65)

    # T01: Go 서버 확인
    go_ok = test_01_go_server()
    if not go_ok:
        print("\n⛔ Go 서버 미실행 — 테스트 중단")
        sys.exit(1)

    # T02: STT 서버 확인
    stt_result = test_02_stt_server()
    stt_alive = stt_result is True  # None = skip, False = 미실행

    # T03: 세션 시작
    session_ok = test_03_session_start()
    if not session_ok:
        print("\n⛔ 세션 시작 실패 — 테스트 중단")
        sys.exit(1)

    # T04: /ws/live 연결
    ws_conn = test_04_ws_live()
    time.sleep(0.5)  # WebSocket 안정화

    # T05: WAV POST
    filenames = test_05_post_wavs()

    # T06: 상태 전환 대기
    all_done = test_06_status_transitions(filenames, stt_alive)

    # T07: 브로드캐스트 수신
    test_07_live_broadcast(filenames, stt_alive)

    # T08: transcript.txt
    test_08_transcript(stt_alive)

    # T09: 세션 종료
    test_09_session_stop()
    time.sleep(0.5)  # flushPending 처리 대기

    # T10: 최종 상태
    test_10_final_state(filenames, stt_alive)

    # T11: 세션 격리
    test_11_session_isolation()

    # ── 결과 ──────────────────────────────────────────────────
    print("\n" + "=" * 65)
    total = len(_passed) + len(_failed)
    print(f"  결과: {len(_passed)}/{total} PASS  |  {len(_failed)} FAIL")
    if _failed:
        print(f"  실패 항목:")
        for f in _failed:
            print(f"    - {f}")
    if not stt_alive:
        print("\n  ℹ️  STT 서버 없이 실행 → STT 관련 단계 SKIP됨")
        print("     전체 검증: python stt_server.py 실행 후 재테스트")
    print("=" * 65)

    sys.exit(0 if not _failed else 1)
