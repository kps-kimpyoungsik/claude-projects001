"""분류 코드 SSOT — 00_PROJECT_CONSTITUTION.md §2(문서유형)·§5(영역/분야) 그대로 반영.

이 모듈이 유일한 코드 정의처(CRZ)다. `requirements.py`(REQ ID 검증)와
`orchestrator/task_manager.py`(Task.domain_code 검증)가 여기서 import해서 쓴다 —
같은 코드 목록을 두 곳에 따로 하드코딩하지 않는다.

코드 추가/변경 시 이 파일과 00_PROJECT_CONSTITUTION.md §2/§5를 함께 갱신한다.
"""

# §5 영역/분야 코드 — 확정(2026-07-17, 사용자 승인). **코드 키 자체는 값 변경 금지.**
# [2026-07-25 §8-2 보강] 순수 set → {코드: {"label":쉬운라벨, "desc":설명}} 딕셔너리로 승격.
# DOC_TYPE_CODES/LAYER_CODES는 이미 설명을 갖고 있었으나 이 목록만 없었다(실측 근본원인 —
# plans/_plan/04_PHASE0_PROJECT_REGISTRATION.md §8-1). 하위호환: dict의 `in`/`sorted`/순회는
# set과 동일하게 키 기준으로 동작하므로 `x in DOMAIN_CODES`류 기존 코드는 전부 그대로 동작
# (실측 확인 — requirements_api.py/project_config_store.py/task.py/classifier.py/
# id_format.py/conflict_detection.py 전체 grep, 회귀 없음).
DOMAIN_CODES = {
    "WEB": {"label": "웹 프론트엔드", "desc": "사용자가 브라우저로 직접 보는 화면(웹사이트·웹앱) 관련 요구사항"},
    "WAS": {"label": "애플리케이션 서버(WAS)", "desc": "화면 뒤에서 실제 로직을 처리하는 서버(백엔드) 관련 요구사항"},
    "DB": {"label": "데이터베이스", "desc": "데이터를 저장·조회하는 저장소(DB) 구성·성능 관련 요구사항"},
    "SEC": {"label": "보안", "desc": "암호화·인증·접근제어 등 보안 관련 요구사항"},
    "GRID": {"label": "데이터 그리드(표 화면)", "desc": "대량 데이터를 표(그리드) 형태로 보여주고 편집하는 화면 컴포넌트"},
    "A11Y": {"label": "웹 접근성", "desc": "장애인·고령자 등 누구나 이용 가능하게 하는 웹 표준 준수 요구사항"},
    "VULN": {"label": "취약점 점검", "desc": "보안 취약점 진단·모의해킹·코드 점검 관련 요구사항"},
    "GW": {"label": "게이트웨이/연계", "desc": "외부 시스템과 데이터를 주고받는 연계·중계 서버 관련 요구사항"},
    "LLM": {"label": "AI(생성형 AI/LLM)", "desc": "ChatGPT류 AI 모델을 활용하는 기능(요약·분류·챗봇 등) 관련 요구사항"},
    "RPT": {"label": "보고서/리포트", "desc": "데이터를 문서·PDF·엑셀 등으로 출력하는 보고서 기능 관련 요구사항"},
}

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
# [2026-07-25 §8-2 보강] label 필드 추가(dict-of-string → dict-of-dict) — 기존 desc는
# 문자열 그대로 두되 프론트 표시용 짧은 label을 함께 제공. `x in LAYER_CODES`/`sorted()`는
# dict 키 기준이라 이 구조변경으로도 회귀 없음(실측: requirements_api.py·
# project_config_store.py·classifier.py 전체 grep 확인).
LAYER_CODES = {
    "SYS": {"label": "시스템/인프라 계층", "desc": "시스템영역 (인프라·서버·OS·배치)"},
    "SECU": {"label": "보안 계층", "desc": "보안영역 (아키텍처 계층 관점 — area_code=SEC와는 다른 축)"},
    "UXENV": {"label": "사용자 환경 계층", "desc": "사용자환경영역 (클라이언트 UX·접근성·디바이스 환경)"},
    "TPI": {"label": "외부 연동(서드파티) 계층", "desc": "서드파티 인터페이스 영역 (외부 API·PG·인증 연동)"},
    "INTG": {"label": "내부 연계 계층", "desc": "연계영역 (내부 시스템 간 연계·배치 연동·ESB)"},
}

# [2026-07-25 §8-9 인프라 존] 네트워크 존 "프리셋" — DOMAIN_CODES/LAYER_CODES와 달리 고정 enum이
# 아니다(사용자 명시 요청: "동적으로 내가 필요한 구성을 더 연결해서 추가할 수 있도록 해줘" —
# 2026-07-25 AskUserQuestion 답변). 여기 4개는 project_config_store.py가 인프라 구성을 처음
# 켤 때 시드(seed)하는 기본값일 뿐이고, 사용자는 이 목록에 없는 커스텀 존을 자유롭게 추가할 수
# 있다(예: "외부 연계 API 제공 영역"). `exposed`는 "이 존이 외부에 노출되어 침해 가능성이 상대적
# 으로 높은가"를 나타내는 유일한 강제 검증축 — role=DB 서버가 이 축을 넘어 exposed 존에 놓이는
# 것만 하드 검증한다(그 외 정책은 자유 확장 가능해야 하므로 이름 자체를 검증하지 않음).
NETWORK_ZONE_PRESETS = {
    "external": {"label": "외부망(Internet)", "desc": "인터넷 등 신뢰할 수 없는 외부 구간", "exposed": True},
    "dmz_outer": {"label": "외부 DMZ(SSL 종단)", "desc": "리버스프록시/로드밸런서가 SSL을 종단하는 완충 구간", "exposed": True},
    "dmz_inner": {"label": "내부 DMZ(중계서버)", "desc": "외부→내부 API 호출을 대신 받아 내부로 전달하는 중계/게이트웨이 구간", "exposed": True},
    "internal": {"label": "내부망", "desc": "WAS·DB 등 실제 업무 시스템이 위치하는 신뢰 구간", "exposed": False},
}

# §5-C 요구사항 유형 — plans/_plan/01_PHASE1_DATA_MODEL.md §2-2에서 확정(IEEE 830 계열).
REQUIREMENT_TYPES = {
    "FUNC": "기능 요구사항",
    "NFUNC": "비기능 요구사항",
}

# §2-5/§2-6 디자인 시안 선행 게이트 값 — plans/_plan/01_PHASE1_DATA_MODEL.md §2-5에서 확정
# (2026-07-19). REQ 번호에는 포함하지 않고 메타데이터 필드(design_draft_gate)로만 존재.
DESIGN_GATE_VALUES = {"MANDATORY", "NOT_MANDATORY", "STRATEGIC_MANDATORY"}
