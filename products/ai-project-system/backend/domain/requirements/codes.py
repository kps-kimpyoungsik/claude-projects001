"""분류 코드 SSOT — 00_PROJECT_CONSTITUTION.md §2(문서유형)·§5(영역/분야) 그대로 반영.

이 모듈이 유일한 코드 정의처(CRZ)다. `requirements.py`(REQ ID 검증)와
`orchestrator/task_manager.py`(Task.domain_code 검증)가 여기서 import해서 쓴다 —
같은 코드 목록을 두 곳에 따로 하드코딩하지 않는다.

코드 추가/변경 시 이 파일과 00_PROJECT_CONSTITUTION.md §2/§5를 함께 갱신한다.
"""

# §5 영역/분야 코드 — 확정(2026-07-17, 사용자 승인). 값 변경 금지.
DOMAIN_CODES = {"WEB", "WAS", "DB", "SEC", "GRID", "A11Y", "VULN", "GW", "LLM", "RPT"}

# §2 문서유형 코드 — 제안값(2026-07-18). 구조(REQ 번호에 포함)는 사용자 확정,
# 코드 문자열 자체는 실사용 문서를 보며 조정 가능(변경 시 이 파일 + 헌법 §2 동시 갱신).
# MEMO/REC은 2026-07-18 재설계(plans/_plan/04_PHASE0_PROJECT_REGISTRATION.md §2)에서
# 사용자 원 요청 "녹음·메모" 첨부를 다루기 위해 추가.
DOC_TYPE_CODES = {
    "BIZ": "사업 문서 (제안서/사업계획서/수행계획서/착수보고서)",
    "ITV": "정성 정보 (이해관계자 인터뷰)",
    "ENV": "구축 환경 스펙 (WEB/WAS/DB 구성, 암호화 솔루션, SSL, 그리드)",
    "QA": "품질·보안 요건 (소스코드 취약성 점검, 보안 감사)",
    "TECH": "기술 스택 요건 (Frontend/Backend/Gateway 언어, LLM 연계)",
    "OUT": "산출물 요건 (보고서 양식·주기)",
    "MEMO": "메모 (담당자 비정형 메모)",
    # 2026-07-20: faster_whisper_engine.py로 실제 엔진 연결 완료(tiny 모델, voiceAW
    # VAD 파라미터 참고 — 코드 복사 아님). 2026-07-22 재검토 정정: 이 주석이 "실제 오디오
    # 미검증"이라 stale하게 남아있었으나, tests/test_faster_whisper_engine.py의
    # test_build_faster_whisper_stt_engine_transcribes_real_audio()가 실제 오디오
    # fixture(tests/fixtures/sample_speech_ko.wav)로 이미 2026-07-20 검증 완료했음을 확인.
    "REC": "녹음 (음성 녹취 — 엔진 연결 + 실제 오디오 e2e 검증 완료 2026-07-20)",
}

# §5-B 아키텍처 계층코드 — plans/_plan/01_PHASE1_DATA_MODEL.md §2-1에서 확정(2026-07-18).
# area_code(§5, 기술영역)와 다른 독립 축 — REQ 번호에는 포함하지 않고 메타데이터로만 존재.
LAYER_CODES = {
    "SYS": "시스템영역 (인프라·서버·OS·배치)",
    "SECU": "보안영역 (아키텍처 계층 관점 — area_code=SEC와는 다른 축)",
    "UXENV": "사용자환경영역 (클라이언트 UX·접근성·디바이스 환경)",
    "TPI": "서드파티 인터페이스 영역 (외부 API·PG·인증 연동)",
    "INTG": "연계영역 (내부 시스템 간 연계·배치 연동·ESB)",
}

# §5-C 요구사항 유형 — plans/_plan/01_PHASE1_DATA_MODEL.md §2-2에서 확정(IEEE 830 계열).
REQUIREMENT_TYPES = {
    "FUNC": "기능 요구사항",
    "NFUNC": "비기능 요구사항",
}

# §2-5/§2-6 디자인 시안 선행 게이트 값 — plans/_plan/01_PHASE1_DATA_MODEL.md §2-5에서 확정
# (2026-07-19). REQ 번호에는 포함하지 않고 메타데이터 필드(design_draft_gate)로만 존재.
DESIGN_GATE_VALUES = {"MANDATORY", "NOT_MANDATORY", "STRATEGIC_MANDATORY"}
