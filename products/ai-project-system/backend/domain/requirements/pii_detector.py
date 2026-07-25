"""[Phase 2] 요구사항 본문의 PII(개인정보) 포함 여부 결정론적 판정.

plans/_plan/04_PHASE0_PROJECT_REGISTRATION.md §3 — workbase `DATA_TYPES_DEF`의 `pii` 항목
(⚠ 아이콘 경고, "이름/연락처/주소/식별자")을 벤치마킹한 설계를 그대로 구현한다. §3이 이미
`contains_pii: bool` + `pii_scan_matched: list[str]` 필드 계약과 "정규식 기반 결정론적 스캔"
방식을 확정해뒀다 — 이 모듈이 그 스캔 함수다.

classifier.py와 동일한 스타일(결정론적 키워드/정규식 매칭, LLM 의미판단 없음, T98 AIP 과장
금지)을 그대로 따른다(CRZ — 새 판정 방식 발명 없음). 단, classifier.py의 영역/문서유형 분류는
"애매하면 사람에게 넘긴다"(needs_review)가 원칙인 반면, PII는 **오탐(false positive, PII
아닌데 걸림)보다 미탐(false negative, 실제 PII인데 안 걸림)이 훨씬 위험한 비대칭 축**이다
(개인정보 유출 vs 열람 확인 클릭 한 번 더). 그래서 이 모듈은 "애매하면 넘긴다"가 아니라
"애매하면 PII로 간주한다"(관대한 판정, over-inclusive by design) — needs_review 개념 자체가
없다.

한계(정직하게 기록 — T98 AIP 과장 금지):
- 정규식/키워드 매칭이라 문맥을 이해하지 못한다. "010-1234-5678은 예시입니다" 같은 설명문도
  전화번호 패턴에 매치되면 PII로 표시된다(오탐 허용 — 위 비대칭성 때문에 의도적 트레이드오프).
- 반대로 패턴에 없는 형식(해외 전화번호, 사번, 비정형 주소 표현 등)은 걸리지 않을 수 있다
  (미탐 가능성은 존재 — 완전한 PII 탐지는 이 모듈의 범위 밖, 사람의 최종 확인이 여전히 필요).
- 실제 유효성 검증(주민번호 체크섬 등)은 하지 않는다 — 패턴 형태만 본다(과잉탐지가 목적).
"""

import re
from dataclasses import dataclass, field

# workbase DATA_TYPES_DEF의 pii 항목("이름/연락처/주소/식별자")을 결정론적 정규식으로 대응.
# 키만 보고도 어떤 패턴인지 알 수 있게 classifier.py의 DOC_TYPE_KEYWORDS 스타일을 따른다.
PII_PATTERNS: dict[str, re.Pattern] = {
    # 주민등록번호: 6자리(생년월일) + 구분자(-, 공백 허용) + 7자리(성별코드 1~4로 시작).
    "RRN": re.compile(r"\d{6}[-\s]?[1-4]\d{6}"),
    # 휴대폰/전화번호: 010/011 등 이동전화 + 지역번호(02, 031 등) 일반 형식.
    "PHONE": re.compile(r"01[0-9][-\s]?\d{3,4}[-\s]?\d{4}|0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}"),
    # 이메일.
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    # 계좌번호: 10~14자리 숫자(구분자 - 허용) — 은행 계좌 일반 형식(오탐 넓게 허용, 위 비대칭성).
    "ACCOUNT": re.compile(r"\d{2,6}-\d{2,6}-\d{2,10}"),
    # 여권번호: 영문 1자 + 숫자 8자리.
    "PASSPORT": re.compile(r"\b[A-Z]\d{8}\b"),
}

# 정규식으로 형태를 특정하기 어려운 축(이름·주소)은 classifier.py와 동일하게 키워드 사전으로
# 보조한다 — "이 문단 근처에 개인 식별정보가 있을 가능성"을 넓게 잡는 용도(관대한 판정).
PII_CONTEXT_KEYWORDS: list[str] = [
    "주민등록번호", "주민번호", "생년월일", "연락처", "휴대폰번호", "전화번호",
    "이메일", "메일주소", "집주소", "자택주소", "거주지", "계좌번호", "카드번호",
    "여권번호", "운전면허번호", "개인정보", "성명", "실명",
]


@dataclass
class PiiScanResult:
    contains_pii: bool
    pii_scan_matched: list[str] = field(default_factory=list)


def scan_for_pii(text: str) -> PiiScanResult:
    """본문에서 PII 패턴/키워드를 스캔한다 — 결정론적, 하나라도 매치되면 contains_pii=True.

    미탐(false negative)이 오탐(false positive)보다 위험하다는 비대칭성 때문에, 관대하게
    판정한다: 정규식 패턴 매치든 문맥 키워드 매치든 하나라도 있으면 PII로 표시한다.
    """
    matched: list[str] = []

    for label, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            matched.append(f"pattern:{label}")

    for keyword in PII_CONTEXT_KEYWORDS:
        if keyword in text:
            matched.append(f"keyword:{keyword}")

    return PiiScanResult(contains_pii=bool(matched), pii_scan_matched=matched)
