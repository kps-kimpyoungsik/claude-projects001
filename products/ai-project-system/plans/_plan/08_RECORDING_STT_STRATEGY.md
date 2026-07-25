---
role: DESIGN_PHASE2_FOLLOWUP
scope: REC(녹음) 문서유형 STT ingestion 전략 — 02_PHASE2_ORCHESTRATION_PREVIEW.md §1-3에서
  "3차 이후 별도 착수 단위로 분리"로 미뤄뒀던 timestamp_*(오디오) 구현 착수
status: 실제 엔진 연결 완료(2026-07-20) — faster-whisper tiny, voiceAW 패턴 참고(코드 복사 아님)
updated: 2026-07-20
---

# 8번 설계 — 녹음(REC) STT ingestion 전략

> 상위: [`00_INDEX.md`](./00_INDEX.md) | 관련: [`02_PHASE2_ORCHESTRATION_PREVIEW.md`](./02_PHASE2_ORCHESTRATION_PREVIEW.md) §1-2·§1-3

> **전제**: `backend/domain/requirements/codes.py`의 `REC` 문서유형이 "STT 변환 후 처리,
> ingestion 미구현"으로 남아있던 것을 이번 착수 단위에서 메운다. 사용자 지시로 사내 sibling
> 프로젝트 `D:\projects\products\chatAW`·`D:\projects\products\chatAWV2`의 실제 STT/녹음
> 구현을 조사해 신규 발명을 최소화하는 것이 출발점이었다.

## §1. 조사 결과 (읽기 전용 조사, 두 프로젝트 어떤 파일도 수정하지 않음)

### §1-1. chatAW — 서버측 STT 엔진 없음, 브라우저 Web Speech API 얇은 래퍼

- 실제 음성인식은 **브라우저 Web Speech API**로 수행한다(`static/app.js`의 `VoiceInput`
  모듈, `docx/voice-to-text/voice-to-text-impl.md`). 인식된 **텍스트만** 채팅창에 삽입하고
  **오디오 자체는 저장하지 않는다**(`docx/voice-to-text/voice-to-text-spec.md:14`).
- Go 백엔드 `internal/bridge/voice_domain.go`는 완성된 STT 결과(WAV/전사문/리포트)를
  **외부 서비스가 밀어넣는 리시버**일 뿐이다 — `/api/voice/health`·`/api/voice/receive`·
  `/api/voice/setdomin` 엔드포인트(`local_guide/Requirements/voice/api-contract.md`)가
  이를 뒷받침한다. 즉 chatAW 자체에는 "오디오 → 전사문" 변환 로직이 없다.
- 실제 STT 엔진은 완전히 **별도 프로젝트** `D:\projects\products\voiceAW`에 있다(엔진
  옵션: whisper/browser/hybrid — `local_guide/Requirements/voice/parameters.md:50`).
- 에러 처리는 브라우저 API 레벨에서만 존재한다: `no-speech`/`onend` 시 자동 재시작,
  `not-allowed`/`service-not-allowed` 시 완전 정지. **서버측 STT 재시도 로직은 없다**
  (애초에 서버측 STT 호출 자체가 없기 때문).

### §1-2. chatAWV2 — STT/녹음 관련 코드 전무 (V1의 개선판이 아니다)

- grep 매치(`stt`, `whisper`, `transcri` 등)는 전부 **오탐**이었다: `FirstToken`이라는
  변수명, `TestTerminalStagesAreDoneOrError`라는 테스트 함수명 등 문자열 우연 매칭이다.
- "V2"라는 이름이 chatAW의 음성 기능 개선판을 암시하지만, 실측 결과 **음성 기능 자체가
  애초에 존재하지 않는다** — 우열 비교의 전제 자체가 성립하지 않는다.

### §1-3. 두 프로젝트 간 비교 — 우열 판단 불가

chatAWV2는 관련 구현이 아예 없고, chatAW는 실전사 파이프라인이 아니라 브라우저 API의
얇은 래퍼(오디오 미저장, 서버 STT 없음)다. **어느 쪽도 이 프로젝트(ai-project-system)가
필요로 하는 "서버측 오디오 파일 → 텍스트+타임스탬프" 파이프라인의 참고 사례가 되지
못한다** — 이 사실을 그대로 인정한다(추정으로 포장하지 않음, T98 AIP).

### §1-4. 실질적 노하우는 별도 프로젝트 `voiceAW`에 있다 (이번 사이클 조사 범위 밖)

chatAW의 문서가 가리키는 실제 엔진 프로젝트 `voiceAW`의 존재만 확인했다 — 그 프로젝트를
추가로 열람·조사하지는 않았다(사용자가 이번 사이클에 명시한 조사 대상은 chatAW·
chatAWV2 두 개뿐이었고, voiceAW는 범위 밖). chatAW 문서에 인용된 형태로 다음 사실만
간접 확인됐다(voiceAW 코드를 직접 읽지 않았으므로 "chatAW 문서가 언급"하는 수준의
근거로만 취급한다):

- `02_backend/python/pipeline/batch_stt.py`가 **faster-whisper**를 쓰고, `vad_filter=True`·
  `min_silence_duration_ms=300`·`speech_pad_ms=200`으로 **무음구간(VAD) 기반 세그먼트
  분할**을 한다(고정 길이 분할이 아니다).
- 세그먼트 구조는 `segments: [{start, end, text}]`(초 단위), WhisperX 강제정렬로 단어
  단위 타임스탬프까지 지원한다는 언급이 있다.

**후속 조사 필요 사항(명시적으로 범위 밖으로 남김)**: `voiceAW`가 실제로 참고 가치가
높아 보이므로(이미 운영 중인 VAD 기반 세그먼트 분할 + faster-whisper 파이프라인), 이
프로젝트가 실제 STT 엔진을 연결하는 후속 단계에 들어가기 전에 `voiceAW`를 직접 조사하는
**별도 착수 단위**를 사용자가 지시하는 것을 권장한다. 이번 문서는 그 조사를 대신하지
않는다.

### §1-5. 로컬 whisper 계열 패키지 실측

- chatAW·chatAWV2 어디에도 `requirements.txt`/`pyproject.toml`에 whisper 계열 의존성
  선언이 없다.
- **이 프로젝트(ai-project-system)의 Python 환경에는 `faster-whisper` 1.2.1이 이미
  설치돼 있음을 `pip list`로 직접 확인**했다. 신규 유료 API 의존성을 추가하지 않고
  이미 존재하는 로컬 자산을 재사용하는 것이 `00_PROJECT_CONSTITUTION.md` §1·§4의
  "범용 인프라는 도구로만, 목적이 되지 않게"·"신규 발명 최소화" 원칙과 일치한다.

## §2. 이 프로젝트에 채택하는 전략

### §2-1. 엔진: faster-whisper (로컬, 실측 근거 §1-5)

chatAW/chatAWV2 자체에는 채택할 서버측 구현이 없었으므로, 엔진 선택은 "이 프로젝트
환경에 이미 설치되어 있다"는 실측 사실을 근거로 삼는다. 실제 `WhisperModel` 인스턴스
생성·호출은 **이번 착수 범위 밖**이다 — 아래 §2-2 콜백 주입 구조가 그 자리를 비워둔다.

### §2-2. 인터페이스: 콜백 주입 패턴 (기존 코드베이스 관례 재사용, CRZ)

이 프로젝트는 이미 두 곳에서 "실제 판단/엔진 호출이 필요한 부분은 콜백으로 주입하고,
미주입 시 `NotImplementedError`로 정직하게 알린다"는 패턴을 쓴다:

- `heading_splitter.SPCEngine.__init__(recall_hook=None)` — 미주입 시 "recall 미실행"
- `heading_splitter.SemanticBoundarySplitter.split()` — 항상 `NotImplementedError`

`speech_to_text_adapter.SpeechToTextAdapter(stt_engine=None)`도 동일 원칙을 따른다 —
`stt_engine: Callable[[str], list[SpeechSegment]]`을 주입하지 않으면 즉시
`NotImplementedError`를 낸다. 실제 faster-whisper 연결은 이 콜백 하나만 구현하면 되므로,
후속 작업 범위가 명확히 한정된다.

### §2-3. 오디오 청크 분할: 이번 스캐폴딩 범위 밖 (VAD는 후속 옵션으로 기록만)

voiceAW가 VAD 기반 세그먼트 분할(§1-4)을 쓴다는 점을 참고 가치로 기록해두되, **이번
스캐폴딩은 청크 분할 알고리즘 자체를 구현하지 않는다** — `stt_engine` 콜백이 이미
분할된 `SpeechSegment` 리스트(`start_ms`/`end_ms`/`text`)를 반환한다고 가정하고, 그
세그먼트를 `Chunk` 리스트로 변환하는 부분만 구현한다. 실제 엔진을 연결하는 후속 작업에서
VAD 파라미터(`vad_filter`·`min_silence_duration_ms`·`speech_pad_ms`) 채택 여부를
`voiceAW` 추가 조사(§1-4 권고) 이후 결정하는 것이 순서상 맞다 — 지금 임의로 파라미터를
베끼면 검증되지 않은 채 하드코딩되는 위험이 있다(과잉설계 회피, T57 PVS).

### §2-4. 타임스탬프 구조: ms 단위로 통일 (기존 Chunk 필드명과 정합)

voiceAW는 초 단위 `{start, end}`를 쓰지만, 이 프로젝트의 `02_PHASE2_ORCHESTRATION_
PREVIEW.md` §1-2가 이미 `SourceLocation.timestamp_start_ms`/`timestamp_end_ms`(ms 단위)로
필드명을 확정해뒀다. 단위 변환은 **어댑터 경계(`SpeechToTextAdapter._transcribe`가
반환받는 지점)에서 한 번만** 수행하는 것으로 설계한다 — 그 이후 계층(`Chunk`, 미리보기
UI)은 항상 ms만 다뤄 단위 혼재를 방지한다. (이번 스캐폴딩의 mock/테스트는 콜백이 이미
ms를 반환한다고 가정 — 실제 엔진 연결 시 초→ms 변환 책임을 어디에 둘지는 후속 작업에서
`stt_engine` 콜백 구현부가 정한다.)

### §2-5. 에러 처리·재시도: 이번 스캐폴딩 범위 밖 (설계만 기록)

chatAW의 클라이언트측 자동재시작(`no-speech`/`onend`) 전략은 브라우저 API 특유의
것이라 서버측 배치 처리에는 그대로 적용되지 않는다. chatAW/chatAWV2 어디에도 서버측
STT 재시도 로직이 없었으므로(§1-1·§1-2), 참고할 기존 패턴이 없다. 이번 스캐폴딩은
`stt_engine` 콜백 호출을 감싸는 타임아웃/재시도 로직을 구현하지 않는다 — 실제 엔진이
연결된 뒤에야 (배치 처리 시간·모델 크기에 따른) 현실적인 타임아웃 값을 정할 수 있어,
지금 임의 값을 하드코딩하면 근거 없는 매직 넘버가 된다(과장 금지, T98 AIP). 후속 작업
체크리스트로만 남긴다.

## §3. 구현한 스캐폴딩 (이번 착수 단위)

| 파일 | 변경 내용 |
|---|---|
| `backend/domain/chunking/chunk.py` | `Chunk`에 `timestamp_start_ms`/`timestamp_end_ms` 필드 추가(§2-4), `inject_global_context`가 보존하도록 갱신 |
| `backend/adapters/parsers/router.py` | `FORMAT_STRATEGY`에 `.wav`/`.mp3`/`.m4a` → `"speech_to_text"` 매핑 추가 |
| `backend/adapters/parsers/speech_to_text_adapter.py` (신규) | `SpeechSegment` 데이터클래스, `SpeechToTextAdapter(ParserPort)` — `stt_engine` 콜백 주입(§2-2), `parse_to_markdown`(타임스탬프 표기 마크다운) + `transcribe_to_chunks`(timestamp_*_ms 채워진 `Chunk` 리스트) |
| `backend/domain/requirements/codes.py` | `REC` 설명을 "STT 어댑터 스캐폴딩 완료, 실제 엔진 연결 미구현"으로 갱신 |
| `tests/test_speech_to_text_adapter.py` (신규) | can_handle·미주입 시 NotImplementedError·source_path 누락 시 ValueError·timestamp 필드 채움·markdown 렌더링·router 매핑 검증 (mock stt_engine, 실제 STT 호출 없음) |
| `tests/test_chunking.py` | `Chunk` 신규 필드 기본값 None 회귀 테스트 + `inject_global_context` 보존 테스트 추가 |

**실제 STT 엔진 호출 코드·API 키·유료 서비스 연동은 작성하지 않았다** — `stt_engine`
콜백 인터페이스까지만 구현했다(사용자 지시 SAFETY 제약 그대로).

## §4. MPCR 7관점 품질검토

| 관점 | 검토 |
|---|---|
| 개발 | 기존 콜백 주입 관례(`SPCEngine.recall_hook`)를 재사용해 신규 패턴을 만들지 않았다. `ParserPort` 인터페이스를 그대로 구현해 향후 `router.py`의 `FORMAT_STRATEGY["speech_to_text"]` 어댑터로 주입 가능하다. |
| 설계 | 텍스트/오디오 두 좌표계(char_*/timestamp_*)가 같은 `Chunk`에 공존하되 포맷별로 선택적으로 채워지는 §1-2 원 설계를 그대로 따른다 — 신규 데이터클래스 분리 없이 기존 구조 확장(CRZ). |
| 운영 | 실제 엔진 연결 시 필요한 변경은 `stt_engine` 콜백 구현 하나로 한정된다 — `SpeechToTextAdapter` 자체는 수정 불필요. |
| 정보안정성 | `metadata["source_path"]` 누락 시 `ValueError`, 엔진 미주입 시 `NotImplementedError` — 조용한 실패(빈 결과 반환 등)를 만들지 않는다. |
| 헌법(정합) | `00_PROJECT_CONSTITUTION.md` §1(신규 발명 최소화·범용 인프라는 도구로만)·§4 드리프트 체크리스트에 부합 — REQ 구조화·태스크 관리라는 핵심 목표에 직접 기여하는 ingestion 경로 확장이다. |
| 검증 | mock `stt_engine`으로 콜백 주입 구조·타임스탬프 필드 채움·markdown 렌더링을 전수 테스트(신규 9건), 기존 101건 회귀 0(§5 확인). |
| 책임 | chatAW/chatAWV2에 실질적 참고 구현이 없었다는 사실과, voiceAW 추가 조사가 범위 밖으로 남았다는 사실을 §1-4에 정직하게 기록해 후속 작업자가 오인하지 않도록 했다. |

## §5. 테스트 결과

`python -m pytest tests/ -v` — 기존 101개 + 신규 9개(`test_speech_to_text_adapter.py` 7건 +
`test_chunking.py` 2건) = **110개 전부 pass, 회귀 0**.

## §6. 후속 작업 (범위 밖으로 명시적으로 남김)

1. ~~`voiceAW` 프로젝트 직접 조사(§1-4)~~ — **완료(2026-07-20)**, §7 참조.
2. ~~`stt_engine` 콜백의 실제 구현~~ — **완료(2026-07-20)**, §7 참조.
3. ~~오디오 청크 분할 전략(VAD 파라미터 채택 여부)~~ — **완료(2026-07-20)**: voiceAW
   VAD 파라미터(`min_silence_duration_ms=300`, `speech_pad_ms=200`) 그대로 채택(§7).
4. 타임아웃/재시도 전략 — §2-5, 실제 엔진 성능 실측 이후 결정(여전히 범위 밖).
5. `router.py`의 `speech_to_text` 전략에 `SpeechToTextAdapter` 인스턴스를 실제로 주입하는
   배선(wiring) 코드 — 현재 `DocxParserAdapter`도 아직 주입되지 않은 것과 동일한 상태
   (라우터 자체가 아직 어댑터를 주입받지 않는 스캐폴딩 단계). 여전히 범위 밖.

## §7. 실제 엔진 연결 (2026-07-20 착수 단위)

`D:\projects\products\voiceAW\02_backend\python\pipeline\batch_stt.py`를 읽기 전용으로
조사(그 프로젝트 파일은 수정하지 않음)해 아래 사실을 확인하고, **코드를 복사하지 않고
패턴·파라미터만 참고**해 `backend/adapters/parsers/faster_whisper_engine.py`를 신규
작성했다.

### §7-1. voiceAW에서 확인한 사실

- `WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)`로 인스턴스화 후
  `model.transcribe(path, **params)` → `(segments_generator, info)` 반환.
- voiceAW 설정값: `MODEL_SIZE="large-v3-turbo"`, `COMPUTE_TYPE="int8_float32"`,
  `DEVICE="cpu"`, `beam_size=5`, `best_of=5` — **상시 기동 배치 서버** 전제(정확도 우선).
- VAD: `vad_filter=True`, `vad_parameters={"min_silence_duration_ms": 300,
  "speech_pad_ms": 200}` — 무음구간 기준 세그먼트 분할.
- 세그먼트 객체 속성: `seg.start`/`seg.end`(초 단위 float)/`seg.text`.
- `requirements.txt`: `faster-whisper>=1.2.1` (이 프로젝트에 이미 설치된 1.2.1과 호환).

### §7-2. 이 프로젝트의 채택 — 모델 크기는 voiceAW와 다르게 결정

이 프로젝트는 **로컬 세션 실행**(사용자 워크스테이션에서 업로드 즉시 처리)이라
voiceAW의 "상시 배치 서버" 전제와 다르다. 과잉설계 회피(T57 PVS) 근거:

| 항목 | voiceAW | 이 프로젝트 채택 | 근거 |
|---|---|---|---|
| 모델 크기 | large-v3-turbo | **tiny**(기본값, 조정 가능) | 다운로드(~75MB) + 로딩 시간 최소화, 로컬 즉시 처리 전제 |
| beam_size | 5 | 1 | tiny 모델은 beam 확대 효과가 작고 속도 우선 |
| compute_type | int8_float32 | int8 | CPU 전용 경량 양자화, 긴 배치 오디오 아님 |
| VAD 파라미터 | min_silence=300ms, pad=200ms | **동일 채택** | 모델 크기와 독립적인 검증된 임계치(CRZ, 재발명 안 함) |

### §7-3. 신규 파일

- `backend/adapters/parsers/faster_whisper_engine.py` — `build_faster_whisper_stt_engine()`
  이 `SpeechToTextAdapter(stt_engine=...)`에 주입 가능한 콜백을 반환. `WhisperModel`은
  함수 호출 시점에 지연 로딩(모듈 import만으로 모델 다운로드 트리거 안 함). 초(float)
  → ms(int) 변환은 이 파일 경계에서 1회만 수행(§2-4 원칙 그대로).
- `tests/test_faster_whisper_engine.py` — 지연 로딩 확인·함수 시그니처 확인·
  faster-whisper 설치 확인 3건 + 실제 오디오 추론 1건(2026-07-20부로 skip 해제,
  아래 §7-5 참고).
- `tests/fixtures/sample_speech_ko.wav` — Windows SAPI(`System.Speech`, Zira 음성)로
  합성한 약 5.7초 영어 문장 오디오. 실제 음성 내용을 갖춰 VAD가 무음으로 필터링하지
  않도록 했다(순수 사인파 톤 대신 채택 — VAD 통과 보장 목적).

### §7-4. 검증 범위 (2026-05-XX 시점 — §7-5로 갱신됨)

이번 사이클에서는 실제 오디오 end-to-end 테스트를 실행하지 않고 skip으로 남겼다
(모델 다운로드 필요, 세션 범위 밖 판단). 아래 §7-5에서 후속 세션이 실제로 실행·검증했다.

### §7-5. 실제 오디오 e2e 검증 완료(2026-07-20)

`test_build_faster_whisper_stt_engine_transcribes_real_audio`의 `@pytest.mark.skip`을
제거하고 실제로 실행·통과시켰다.

- **모델**: `tiny` (`Systran/faster-whisper-tiny`), `device="cpu"`, `compute_type="int8"`.
  최초 실행 시 HuggingFace 캐시(`~/.cache/huggingface/hub/models--Systran--faster-whisper-tiny`)에
  자동 다운로드됨을 확인 — 별도 캐시 로직 구현 없이 라이브러리 기본 동작만으로 이후
  실행은 재다운로드 없이 캐시를 재사용한다.
- **오디오**: `tests/fixtures/sample_speech_ko.wav`(SAPI 합성 영어 문장, 5.7초).
- **결과**: `transcribe()` 실호출 → `SpeechSegment(text='Hello, this is a short test
  recording for the speech to text pipeline verification.', start_ms=0, end_ms=5000)`
  1건 반환 — 합성 원문과 텍스트가 정확히 일치, `start_ms`/`end_ms`가 채워진 유효한
  자료구조로 확인됨.
- **전체 회귀**: `python -m pytest tests/ -v` → **114 passed, 0 skipped**(기존 113개 +
  이번에 skip 해제된 1건), 총 소요 약 51초(모델은 이미 캐시된 상태 기준 재실행 시).
- **결론**: `build_faster_whisper_stt_engine()` 콜백이 실제 `WhisperModel`과 연결되어
  파이프라인이 에러 없이 동작함을 실측으로 확인. `test_faster_whisper_engine.py`의
  skip 마킹은 이제 없다.
