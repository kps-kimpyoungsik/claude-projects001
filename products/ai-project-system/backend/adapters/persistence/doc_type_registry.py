"""[2026-07-23 고도화] 프로젝트 배경 문서유형 동적 확장 레지스트리.

사용자 지시: "프로젝트 배경에서도 제안서·사업계획서·수행계획서·인터뷰·녹음·메모·회의록 등
항목은 동적으로 추가 가능하도록 해주고" — 지금까지 `backend/domain/requirements/codes.py`의
`DOC_TYPE_CODES`(BIZ/ITV/ENV/QA/TECH/OUT/MEMO/REC 8종)는 코드 변경 없이는 확장 불가능한
고정 dict였다(실측 확인 — 파일에 "코드 추가/변경 시 이 파일과 헌법을 함께 갱신"이라고
명시돼 있었음).

이 레지스트리는 그 8종을 **대체하지 않고**(SSOT 그대로 유지, CRZ) 프로젝트별로 사용자가
런타임에 추가하는 **커스텀 문서유형**만 별도로 관리한다 — `project_registry.py`와 동일한
"단일 JSON append 목록" 패턴 재사용(신규 저장기술 발명 없음). REQ ID 채번(`id_format.
build_req_id`)이 이 커스텀 코드도 인식하도록 `extra_doc_types` 파라미터로 주입된다
(도메인 계층이 이 영속 계층을 직접 import하지 않는 헥사고날 경계 유지).
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.domain.requirements.codes import DOC_TYPE_CODES

# REQ ID의 문서유형 세그먼트(id_format.py REQ_ID_PATTERN)는 `[A-Z]+`(영문 대문자만,
# 숫자 불가)로 고정돼 있다 — 커스텀 코드도 이 제약을 그대로 따라야 REQ 채번이 성립한다
# (실측 발견 2026-07-23: 숫자 접미사로 충돌을 피하려다 "REQ-CUSTOM2-WEB-001" 같은 ID가
# id_format.parse_req_id()에서 형식 위반으로 즉시 거부되는 버그를 실제로 재현·수정).
_CODE_PATTERN = re.compile(r"^[A-Z]{2,10}$")


class DocTypeValidationError(ValueError):
    pass


@dataclass
class CustomDocType:
    code: str
    label: str
    created_by: str
    created_at: str


_COLLISION_SUFFIXES = "XYZWVUTSRQPONMLKJIHGFEDCBA"  # 숫자 대신 알파벳으로 충돌 회피(아래 이유)


def _derive_code(label: str, existing_codes: set[str]) -> str:
    """라벨에서 코드를 자동 유도한다 — 자모/영문 앞 4글자 대문자화 + 충돌 시 알파벳 접미사.

    REQ ID의 문서유형 세그먼트(id_format.REQ_ID_PATTERN)가 `[A-Z]+`(영문 대문자만,
    숫자 불가)로 고정돼 있어(실측 확인) 충돌 회피에 숫자를 쓸 수 없다 — 대신 알파벳을
    덧붙인다(CUSTOM → CUSTOMX → CUSTOMXY ...). 예: "회의록"은 라틴 알파벳이 없어 유도
    실패 → 순번 대신 "CUSTOM"류 고정 접두어로 폴백한다(실사용 문서 대부분이 한글
    라벨이라는 점을 실측 반영 — 무리하게 로마자 변환하지 않음, 정직 단순화).
    """
    ascii_letters = re.sub(r"[^A-Za-z]", "", label).upper()
    base = ascii_letters[:4] if len(ascii_letters) >= 2 else "CUSTOM"
    candidate = base
    i = 0
    while candidate in existing_codes and i < len(_COLLISION_SUFFIXES):
        candidate = base + _COLLISION_SUFFIXES[: i + 1]
        i += 1
    if candidate in existing_codes:
        raise DocTypeValidationError(f"'{label}'에서 유도 가능한 코드가 모두 이미 사용 중입니다 — code를 직접 지정하세요")
    return candidate


class DocTypeRegistry:
    def __init__(self, store_path: Path):
        self._path = store_path

    def _load_raw(self) -> list[dict]:
        if not self._path.exists():
            return []
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _save_raw(self, records: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_custom(self) -> list[CustomDocType]:
        return [CustomDocType(**r) for r in self._load_raw()]

    def list_all_codes(self) -> dict[str, str]:
        """내장(codes.py) + 커스텀을 합친 {code: label} — 프론트 선택지 UI가 그대로 쓴다."""
        merged = dict(DOC_TYPE_CODES)
        for c in self.list_custom():
            merged[c.code] = c.label
        return merged

    def create(self, label: str, actor: str, code: str | None = None) -> CustomDocType:
        label = label.strip()
        if not label:
            raise DocTypeValidationError("문서유형 이름은 비어 있을 수 없습니다")

        records = self._load_raw()
        existing_codes = set(DOC_TYPE_CODES) | {r["code"] for r in records}

        if code:
            code = code.strip().upper()
            if not _CODE_PATTERN.match(code):
                raise DocTypeValidationError(
                    f"코드 형식 위반: '{code}' (영문 대문자 2~10자만 허용 — REQ ID 형식상 숫자 불가)"
                )
            if code in existing_codes:
                raise DocTypeValidationError(f"이미 등록된 코드입니다: {code}")
        else:
            code = _derive_code(label, existing_codes)

        entry = CustomDocType(
            code=code, label=label, created_by=actor,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        records.append(entry.__dict__)
        self._save_raw(records)
        return entry
