"""6축 분류기 회귀 테스트 — 이번 세션 내내 임시 스크립트로 반복 확인하던 것을
고정 pytest로 옮긴다(/autolp Cycle 1 — "고정 pytest 없음"이 여러 턴에서 반복 지적된
한계였음, T103 AQG 정체방지 원칙: 같은 지적이 반복되면 실제로 고쳐야 한다).
"""

from backend.domain.requirements.classifier import classify_chunk


def test_security_chunk_classifies_qa_sec_secu():
    # 헤딩을 포함한다 — 실제 파이프라인(HeadingBoundarySplitter)이 만드는 청크는 항상
    # "# 보안 요건" 같은 헤딩이 본문 앞에 붙는다(순수 본문만 넣으면 ENV/QA가 동점(tie)이
    # 되어 needs_review=True로 빠진다 — 이것도 정상 동작, 아래 test_ambiguous 참조).
    text = "# 보안 요건\n암호화 솔루션과 SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다. 보안 계층 인증 체계를 강화한다."
    result = classify_chunk(text)
    assert result.doc_type_code == "QA"
    assert result.area_code == "SEC"
    assert result.layer_code == "SECU"


def test_ambiguous_chunk_without_heading_ties_and_needs_review():
    """헤딩 없이 본문만 주면 ENV("SSL")와 QA("취약성 점검")가 동점(1:1)이 되어
    needs_review=True로 빠진다 — "확신 없으면 확정하지 않는다" 설계가 실제로 동작함을
    확인하는 테스트(과신 방지, T98 AIP 정직성 원칙의 코드 레벨 구현)."""
    text = "암호화 솔루션과 SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다."
    result = classify_chunk(text)
    assert result.needs_review is True


def test_frontend_chunk_classifies_tech_web_uxenv():
    text = "반응형 UI로 프론트엔드 화면을 구성한다. 사용자 환경 접근성을 고려한다."
    result = classify_chunk(text)
    assert result.doc_type_code == "TECH"
    assert result.area_code == "WEB"
    assert result.layer_code == "UXENV"


def test_no_keyword_match_returns_none_and_needs_review():
    result = classify_chunk("특별한 키워드가 없는 애매한 잡담성 문장입니다.")
    assert result.doc_type_code is None
    assert result.area_code is None
    assert result.needs_review is True


def test_confidence_bounds_are_normalized_0_to_1():
    result = classify_chunk("암호화 보안 SSL 인증서 취약성")
    assert 0.0 <= result.doc_type_confidence <= 1.0
    assert 0.0 <= result.area_confidence <= 1.0


def test_design_gate_mandatory_when_only_ui_keywords_match():
    """plans/_plan/01_PHASE1_DATA_MODEL.md §2-6 규칙 1) — MANDATORY만 매칭, NOT_MANDATORY 없음."""
    text = "이 화면은 사용자 인터페이스 레이아웃과 디자인 테마를 확정해야 한다."
    result = classify_chunk(text)
    assert result.design_draft_gate == "MANDATORY"
    assert result.design_draft_gate_confidence > 0.0


def test_design_gate_not_mandatory_when_only_backend_keywords_match():
    """§2-6 규칙 2) — NOT_MANDATORY만 매칭, MANDATORY 없음."""
    text = "이 배치 작업은 스케줄러가 내부 로직으로 데이터 처리를 수행하는 백그라운드 작업이다."
    result = classify_chunk(text)
    assert result.design_draft_gate == "NOT_MANDATORY"
    assert result.design_draft_gate_confidence > 0.0


def test_design_gate_strategic_mandatory_on_simultaneous_match():
    """§2-6 규칙 3) — MANDATORY와 NOT_MANDATORY가 동시에 매칭되면 STRATEGIC_MANDATORY."""
    text = "이 배치 작업 화면은 아직 정의되지 않았다."
    result = classify_chunk(text)
    assert result.design_draft_gate == "STRATEGIC_MANDATORY"


def test_design_gate_strategic_mandatory_on_direct_keyword_match():
    """[커버리지 보완] STRATEGIC_MANDATORY 전용 키워드(예: "API 응답")가 직접 매칭되면
    MANDATORY/NOT_MANDATORY 동시매칭 규칙을 거치지 않고도 STRATEGIC_MANDATORY로 즉시
    판정된다."""
    text = "이 기능의 API 응답 구조를 먼저 정의해야 한다."
    result = classify_chunk(text)
    assert result.design_draft_gate == "STRATEGIC_MANDATORY"


def test_design_gate_needs_review_when_no_keyword_matches():
    """§2-6 규칙 5) — 아무 것도 안 걸리면 None + (전체 결과) needs_review=True."""
    result = classify_chunk("특별한 키워드가 없는 애매한 잡담성 문장입니다.")
    assert result.design_draft_gate is None
    assert result.design_draft_gate_confidence == 0.0
    assert result.needs_review is True
