"""[Phase 2 x Phase 3 연결] 청크 → 문서유형코드/영역코드 자동 분류기.

00_PROJECT_CONSTITUTION.md §1의 핵심 목표("청킹·구조화 → 영역/분야별 요구사항
분류·번호관리")에서 지금까지 비어있던 조각 — 청크(ingestion/chunking.py 산출물)를
보고 어느 문서유형(§5-A)·영역(§5)에 속하는지 사람이 매번 지정하지 않고 자동 판정한다.

**결정론적 키워드 매칭**만 사용한다 — LLM 의미판단이 아니다(과장 금지, T98 AIP).
그래서 애매한 청크는 자신 있게 찍지 않고 needs_review=True로 표시해 사람이 확인하도록
한다("관리 포인트") — 오분류를 자신만만하게 채번해버리는 것보다 안전하다.
"""

from dataclasses import dataclass, field

from backend.domain.requirements.codes import (
    DESIGN_GATE_VALUES,
    DOC_TYPE_CODES,
    DOMAIN_CODES,
    LAYER_CODES,
    REQUIREMENT_TYPES,
)

# 00_PROJECT_CONSTITUTION.md §5-A / §2 그대로 반영한 키워드 사전.
# 새 키워드가 필요하면 여기에만 추가한다(SSOT는 codes.py의 코드 목록, 키워드는 이 파일).
DOC_TYPE_KEYWORDS: dict[str, list[str]] = {
    "BIZ": ["제안서", "사업계획서", "수행계획서", "착수보고서", "사업 목표", "계약 기간", "예산"],
    "ITV": ["인터뷰", "이해관계자", "회의록", "구두 요청", "의견 청취"],
    "ENV": ["서버 구성", "이중화", "그리드", "SSL", "웹접근성", "네트워크 구성", "구축 환경"],
    "QA": ["취약성 점검", "보안 감사", "소스코드 점검", "침투테스트", "보안 요건"],
    "TECH": ["프론트엔드", "백엔드", "중계서버", "LLM 연계", "기술 스택", "프레임워크", "개발 언어"],
    "OUT": ["보고서 양식", "산출물 제출", "주간보고", "월간보고", "제출 서식"],
}

AREA_KEYWORDS: dict[str, list[str]] = {
    "WEB": ["프론트엔드", "화면", "UI", "반응형", "웹 브라우저"],
    "WAS": ["애플리케이션 서버", "백엔드", "비즈니스 로직", "API 서버"],
    "DB": ["데이터베이스", "DB", "테이블", "쿼리", "저장소"],
    "SEC": ["암호화", "보안", "SSL", "인증서", "취약성"],
    "GRID": ["그리드", "부하분산", "이중화", "로드밸런싱", "failover"],
    "A11Y": ["웹접근성", "스크린리더", "접근성 인증", "WCAG"],
    "VULN": ["소스코드 취약성", "정적분석", "취약점 진단", "코드 점검"],
    "GW": ["중계서버", "Gateway", "게이트웨이", "프록시"],
    "LLM": ["LLM", "GPT", "생성형 AI", "자연어 처리", "프롬프트"],
    "RPT": ["보고서", "산출물 제출", "주간보고", "월간보고"],
}

# §5-B 계층코드 키워드 — plans/_plan/01_PHASE1_DATA_MODEL.md §2-1 정의 그대로.
LAYER_KEYWORDS: dict[str, list[str]] = {
    "SYS": ["서버 인프라", "배치 작업", "운영체제", "인프라 계층", "시스템 자원"],
    "SECU": ["보안 계층", "인증 체계", "권한 관리", "접근 통제"],
    "UXENV": ["사용자 환경", "클라이언트 환경", "디바이스 환경", "사용자 접근성"],
    "TPI": ["외부 API", "PG 연동", "타사 시스템 연동", "제3자 인증", "외부 인터페이스"],
    "INTG": ["시스템 연계", "배치 연동", "ESB", "내부 시스템 간", "연계 인터페이스"],
}

# §5-C 요구사항 유형 키워드 — IEEE 830 계열 표준 문구.
REQUIREMENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "FUNC": ["기능 요구사항", "처리한다", "제공한다", "기능을 수행", "입력받아"],
    "NFUNC": ["성능 요구사항", "가용성", "응답 시간", "동시 접속", "비기능 요구사항"],
}

# §2-6 디자인 시안 선행 게이트 키워드 — plans/_plan/01_PHASE1_DATA_MODEL.md §2-6 정의 그대로.
# MANDATORY/NOT_MANDATORY는 이진 대립 축이 아니라(둘 다 동시에 매칭될 수 있음 —
# classify_design_gate()의 규칙 3), STRATEGIC_MANDATORY는 "혼재 신호"를 잡는 3번째 사전.
DESIGN_GATE_KEYWORDS: dict[str, list[str]] = {
    "MANDATORY": [
        "화면", "UI", "UX", "레이아웃", "디자인", "테마", "사용자 인터페이스",
        "화면 구성", "와이어프레임", "시안", "배치(화면)", "색상", "폰트", "반응형 화면",
    ],
    "NOT_MANDATORY": [
        "배치 작업", "스케줄러", "내부 로직", "데이터 처리", "API 전용", "백그라운드",
        "연산 처리", "동기화 작업", "무중단 배포", "인프라 설정", "화면 없음",
    ],
    "STRATEGIC_MANDATORY": [
        "API 응답", "응답 구조", "데이터 스키마", "목록 조회", "화면에 표시할",
        "추후 화면", "프론트 연동 예정", "인터페이스 정의",
    ],
}

# 이 이하 매칭이면 "찍었다"고 자신하지 않고 사람 확인으로 넘긴다.
MIN_CONFIDENCE_FOR_AUTO = 0.34


@dataclass
class ClassificationResult:
    doc_type_code: str | None
    doc_type_confidence: float
    area_code: str | None
    area_confidence: float
    layer_code: str | None = None
    layer_confidence: float = 0.0
    requirement_type: str | None = None
    requirement_type_confidence: float = 0.0
    design_draft_gate: str | None = None
    design_draft_gate_confidence: float = 0.0
    matched_keywords: dict[str, list[str]] = field(default_factory=dict)
    needs_review: bool = True


def _score_keywords(text: str, keyword_map: dict[str, list[str]]) -> dict[str, list[str]]:
    """카테고리별로 실제 매칭된 키워드 목록을 반환한다(투명성 — 왜 이렇게 찍었는지 근거 보존)."""
    hits: dict[str, list[str]] = {}
    for code, keywords in keyword_map.items():
        found = [kw for kw in keywords if kw in text]
        if found:
            hits[code] = found
    return hits


def _pick_best(hits: dict[str, list[str]]) -> tuple[str | None, float, bool]:
    """최다 매칭 카테고리를 고르고, 신뢰도(비중)와 동점 여부(needs_review 트리거)를 계산한다."""
    if not hits:
        return None, 0.0, True
    scored = {code: len(kws) for code, kws in hits.items()}
    total = sum(scored.values())
    best_code = max(scored, key=scored.get)
    best_score = scored[best_code]
    confidence = best_score / total if total else 0.0
    tie = sum(1 for v in scored.values() if v == best_score) > 1
    return best_code, confidence, tie


def classify_design_gate(text: str) -> tuple[str | None, float, bool]:
    """§2-6 판정 규칙(plans/_plan/01_PHASE1_DATA_MODEL.md §2-6 그대로):

    1) MANDATORY 키워드만 매칭 + NOT_MANDATORY 매칭 없음 → MANDATORY
    2) NOT_MANDATORY 키워드만 매칭 + MANDATORY 매칭 없음 → NOT_MANDATORY
    3) MANDATORY와 NOT_MANDATORY가 동시에 매칭(백엔드+프론트 혼재) → STRATEGIC_MANDATORY
    4) STRATEGIC_MANDATORY 전용 키워드가 매칭 → STRATEGIC_MANDATORY (1)·2) 조건을 만족해도
       이 신호가 있으면 전략적 판정으로 상향)
    5) 아무 것도 안 걸리면 None + needs_review=True(3번째 반환값)

    이진 대립(경쟁) 축이 아니라 "동시 매칭"이 그 자체로 하나의 판정 신호이므로
    `_score_keywords`/`_pick_best`의 "최다매칭 1개만 채택" 패턴을 그대로 쓰지 않고,
    `_score_keywords`가 만든 hits만 재사용해 이 규칙 전용 판정을 별도로 둔다.
    """
    hits = _score_keywords(text, DESIGN_GATE_KEYWORDS)
    mandatory = hits.get("MANDATORY", [])
    not_mandatory = hits.get("NOT_MANDATORY", [])
    strategic = hits.get("STRATEGIC_MANDATORY", [])

    if strategic:
        value, matched, total = "STRATEGIC_MANDATORY", strategic, len(mandatory) + len(not_mandatory) + len(strategic)
    elif mandatory and not_mandatory:
        value, matched, total = "STRATEGIC_MANDATORY", mandatory + not_mandatory, len(mandatory) + len(not_mandatory)
    elif mandatory:
        value, matched, total = "MANDATORY", mandatory, len(mandatory)
    elif not_mandatory:
        value, matched, total = "NOT_MANDATORY", not_mandatory, len(not_mandatory)
    else:
        return None, 0.0, True

    confidence = round(len(matched) / total, 2) if total else 0.0
    return value, confidence, False


def classify_chunk(text: str) -> ClassificationResult:
    """청크 본문을 보고 문서유형코드(§5-A)·영역코드(§5)를 결정론적으로 추정한다.

    "확신 없는 추정을 확정처럼 내놓지 않는다"(00_PROJECT_CONSTITUTION.md 전반의
    "추정 요구사항 생성 금지" 원칙의 연장) — 매칭이 없거나 애매하면 needs_review=True.
    """
    doc_hits = _score_keywords(text, DOC_TYPE_KEYWORDS)
    area_hits = _score_keywords(text, AREA_KEYWORDS)
    layer_hits = _score_keywords(text, LAYER_KEYWORDS)
    reqtype_hits = _score_keywords(text, REQUIREMENT_TYPE_KEYWORDS)

    doc_code, doc_conf, doc_tie = _pick_best(doc_hits)
    area_code, area_conf, area_tie = _pick_best(area_hits)
    layer_code, layer_conf, layer_tie = _pick_best(layer_hits)
    reqtype_code, reqtype_conf, reqtype_tie = _pick_best(reqtype_hits)
    design_gate_code, design_gate_conf, design_gate_needs_review = classify_design_gate(text)
    design_gate_hits = _score_keywords(text, DESIGN_GATE_KEYWORDS)

    # REQ ID 채번의 근거축(문서유형·영역)은 반드시 확신 있어야 하고, 계층·유형(메타데이터
    # 축)은 있으면 좋지만 없다고 채번을 막지는 않는다(add_from_classification이 doc/area만
    # 필수로 검사 — requirement_store.py 참조). 다만 needs_review 판정에는 6축 전부 반영해
    # "관리 포인트"(사람 확인 대상)로 넉넉히 잡는다.
    needs_review = (
        doc_code is None
        or area_code is None
        or doc_tie
        or area_tie
        or doc_conf < MIN_CONFIDENCE_FOR_AUTO
        or area_conf < MIN_CONFIDENCE_FOR_AUTO
        or layer_code is None
        or reqtype_code is None
        or layer_tie
        or reqtype_tie
        or layer_conf < MIN_CONFIDENCE_FOR_AUTO
        or reqtype_conf < MIN_CONFIDENCE_FOR_AUTO
        or design_gate_needs_review
    )

    assert doc_code is None or doc_code in DOC_TYPE_CODES
    assert area_code is None or area_code in DOMAIN_CODES
    assert layer_code is None or layer_code in LAYER_CODES
    assert reqtype_code is None or reqtype_code in REQUIREMENT_TYPES
    assert design_gate_code is None or design_gate_code in DESIGN_GATE_VALUES

    return ClassificationResult(
        doc_type_code=doc_code,
        doc_type_confidence=round(doc_conf, 2),
        area_code=area_code,
        area_confidence=round(area_conf, 2),
        layer_code=layer_code,
        layer_confidence=round(layer_conf, 2),
        requirement_type=reqtype_code,
        requirement_type_confidence=round(reqtype_conf, 2),
        design_draft_gate=design_gate_code,
        design_draft_gate_confidence=design_gate_conf,
        matched_keywords={
            **{f"doc:{k}": v for k, v in doc_hits.items()},
            **{f"area:{k}": v for k, v in area_hits.items()},
            **{f"layer:{k}": v for k, v in layer_hits.items()},
            **{f"reqtype:{k}": v for k, v in reqtype_hits.items()},
            **{f"design_gate:{k}": v for k, v in design_gate_hits.items()},
        },
        needs_review=needs_review,
    )
