"""OllamaSemanticJudge(2026-07-22) 테스트.

단위테스트는 urllib 호출을 monkeypatch로 대체(네트워크 의존 없이 빠르게, CI 안정성).
실제 로컬 Ollama 연동 e2e는 test_build_faster_whisper_stt_engine_transcribes_real_audio()와
동일한 정신으로 마지막 테스트에서 수행 — Ollama 미기동 환경이면 스킵(정직 표기, 강제 실패 아님).
"""

import json

import pytest

from backend.adapters.llm.ollama_semantic_judge import OllamaSemanticJudge, OllamaUnavailableError

SECTIONS = [
    {"content": "## 보안 요건\nSSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다.",
     "char_start": 0, "char_end": 55, "heading_path": ["보안 요건"]},
    {"content": "## 보안 요건 상세\n앞서 언급한 SSL 인증서는 매년 갱신이 필요하다.",
     "char_start": 55, "char_end": 100, "heading_path": ["보안 요건 상세"]},
]


def _mock_ollama(monkeypatch, response_text):
    judge = OllamaSemanticJudge()
    monkeypatch.setattr(judge, "_call_ollama", lambda prompt: response_text)
    return judge


def test_single_section_skips_llm_call(monkeypatch):
    judge = OllamaSemanticJudge()
    called = []
    monkeypatch.setattr(judge, "_call_ollama", lambda p: called.append(p) or "{}")
    result = judge.judge(SECTIONS[:1])
    assert called == []  # 섹션 1개면 관계 개념이 없어 LLM 호출 자체를 안 함
    assert result.relationships == []


def test_valid_evidence_is_accepted(monkeypatch):
    response = json.dumps({
        "relationships": [{
            "from": 0, "to": 1, "type": "elaborates",
            "evidence": "SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다.",
            "confidence": 0.9,
        }]
    })
    judge = _mock_ollama(monkeypatch, response)
    result = judge.judge(SECTIONS)
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert rel.relation_type == "elaborates"
    assert rel.evidence_char_start == SECTIONS[0]["content"].find(rel.evidence)


def test_hallucinated_evidence_is_rejected(monkeypatch):
    """원문에 존재하지 않는 evidence는 출처 확실성 원칙에 따라 반려되어야 한다."""
    response = json.dumps({
        "relationships": [{
            "from": 0, "to": 1, "type": "elaborates",
            "evidence": "이 문장은 원문 어디에도 없는 완전히 지어낸 문구입니다",
            "confidence": 0.9,
        }]
    })
    judge = _mock_ollama(monkeypatch, response)
    result = judge.judge(SECTIONS)
    assert result.relationships == []


def test_evidence_found_in_to_section_is_self_corrected(monkeypatch):
    """실측된 모델 오류(from/to 뒤바뀜) 대응 — to 섹션에서 발견되면 그쪽으로 정정 채택."""
    response = json.dumps({
        "relationships": [{
            "from": 0, "to": 1, "type": "references",
            "evidence": "앞서 언급한 SSL 인증서는 매년 갱신이 필요하다.",  # 실제로는 SECTIONS[1]의 문구
            "confidence": 0.8,
        }]
    })
    judge = _mock_ollama(monkeypatch, response)
    result = judge.judge(SECTIONS)
    assert len(result.relationships) == 1


def test_invalid_type_normalized_to_unclassified(monkeypatch):
    response = json.dumps({
        "relationships": [{
            "from": 0, "to": 1, "type": "continues|references|elaborates",
            "evidence": "SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다.",
            "confidence": 0.5,
        }]
    })
    judge = _mock_ollama(monkeypatch, response)
    result = judge.judge(SECTIONS)
    assert result.relationships[0].relation_type == "unclassified"


def test_malformed_json_returns_empty_relationships(monkeypatch):
    judge = _mock_ollama(monkeypatch, "이것은 JSON이 아닙니다")
    result = judge.judge(SECTIONS)
    assert result.relationships == []


def test_ollama_real_connection_e2e():
    """실제 로컬 Ollama(127.0.0.1:11434) 연동 확인 — 미기동이면 스킵(강제실패 아님, 정직 표기).

    2026-07-22 실제 실행 검증 완료: qwen2.5:1.5b 모델로 위 SECTIONS에 대해 관계 판단 호출 성공.
    """
    import urllib.request

    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3)
    except Exception:
        pytest.skip("로컬 Ollama(127.0.0.1:11434) 미기동 — e2e 스킵(정직 표기)")

    judge = OllamaSemanticJudge(timeout=60)
    result = judge.judge(SECTIONS)
    assert result.model_name == "qwen2.5:1.5b"
    # 관계가 발견되든 안되든(소형모델 특성상 비결정적) 구조 자체는 항상 유효해야 함
    for rel in result.relationships:
        assert rel.evidence  # 출처 없는 관계는 애초에 여기 도달 못 함(judge 내부에서 반려)
