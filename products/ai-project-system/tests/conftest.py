"""pytest 공통 설정 — CI(GitHub Actions 등, 로컬 Ollama 서비스가 없는 환경) 대응.

로컬 개발 환경(이 세션)은 Ollama가 pm2로 상시 기동돼 있어 vision/semantic-judge e2e
테스트가 실제 모델을 호출해 검증한다. CI 러너에는 Ollama가 없으므로, Ollama가 필요한
테스트만 골라 건강하지 않으면 자동 스킵한다(전체 스위트 실패로 CI를 막지 않음) — 신규
헬스체크 로직 발명 없음, `document_upload_service._build_chunking_splitter()`가 이미
쓰는 것과 동일한 "짧은 타임아웃 GET /api/tags" 패턴을 테스트 쪽에서 재사용한다(CRZ).
"""

import urllib.error
import urllib.request

OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"


def ollama_is_reachable(timeout: float = 1.5) -> bool:
    try:
        urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=timeout)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
