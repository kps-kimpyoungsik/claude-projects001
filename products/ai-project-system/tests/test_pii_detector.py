"""pii_detector.scan_for_pii() 단위 테스트 — 정규식/키워드 매치 및 관대한(over-inclusive)
비대칭 판정(미탐보다 오탐을 허용) 확인."""

from backend.domain.requirements.pii_detector import scan_for_pii


def test_no_pii_in_plain_text():
    result = scan_for_pii("암호화 솔루션과 SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다.")
    assert result.contains_pii is False
    assert result.pii_scan_matched == []


def test_phone_number_pattern_detected():
    result = scan_for_pii("담당자 연락처는 010-1234-5678 입니다.")
    assert result.contains_pii is True
    assert any(m.startswith("pattern:PHONE") for m in result.pii_scan_matched)


def test_email_pattern_detected():
    result = scan_for_pii("문의는 pm.hong@example.co.kr 로 보내주세요.")
    assert result.contains_pii is True
    assert any(m.startswith("pattern:EMAIL") for m in result.pii_scan_matched)


def test_resident_registration_number_pattern_detected():
    result = scan_for_pii("주민등록번호 901231-1234567 확인 필요.")
    assert result.contains_pii is True
    assert any(m.startswith("pattern:RRN") for m in result.pii_scan_matched)


def test_context_keyword_alone_triggers_gate():
    """형태 패턴이 없어도 '개인정보'류 문맥 키워드만으로 관대하게 PII로 표시한다
    (미탐이 오탐보다 위험하다는 비대칭 설계)."""
    result = scan_for_pii("이 문서는 이해관계자의 개인정보를 포함할 수 있다.")
    assert result.contains_pii is True
    assert any(m.startswith("keyword:") for m in result.pii_scan_matched)


def test_multiple_matches_all_recorded():
    result = scan_for_pii("이름과 연락처(010-1111-2222), 이메일(a@b.com)을 남겨주세요.")
    assert result.contains_pii is True
    assert len(result.pii_scan_matched) >= 2
