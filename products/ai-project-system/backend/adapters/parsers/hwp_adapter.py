"""[2026-07-22] HWP(.hwp) -> Markdown 어댑터 — 사용자 결정(2026-07-22): "olefile + 커스텀 파싱".

실제 구현 시 자체 HWP5 이진 레코드 파서(HWPTAG_PARA_TEXT 등)를 처음부터 새로 짜는
대신, 이미 설치 가능하고(`pip install pyhwp`, 이 환경에서 실측 설치 확인) 실제로
동작하는(`hwp5txt` CLI와 동일 변환 경로, 실측 확인) 오픈소스 파서 `pyhwp`를
재사용한다(CRZ) — 자체 이진 파싱은 실제 `.hwp` 샘플이 전무해 정확성을 검증할
방법이 없고, 미검증 자체 구현으로 "그럴듯하지만 틀린" 텍스트를 낼 위험이
`olefile`을 직접 쓰는 것보다 훨씬 크다(T98 AIP 정직성 원칙 — 검증 불가능한 자체
구현보다, 이미 검증된 구현을 재사용하는 편이 안전). pyhwp 내부도 결국 OLE2
컴파운드 스토리지 파싱에 `olefile`을 사용한다.

**정직 고지(중요, 이번 세션 검증 범위)**: `Hwp5File(path)` → `TextTransform` →
`.xsl/plaintext.xsl` 변환 경로는 pyhwp의 `hwp5txt` CLI가 실제 릴리스에서 사용하는
것과 동일한 코드 경로다(`hwp5/hwp5txt.py` 소스 직접 확인). **부정 경로(유효하지
않은 .hwp)는 실측 검증 완료**(무작위 바이트 → `InvalidHwp5FileError` 발생 확인).
**긍정 경로(실제 유효한 .hwp 파일 → 올바른 텍스트 추출)는 이 세션에서 검증하지
못했다** — 실제 `.hwp` 샘플 파일도, 이를 생성할 라이브러리도 이 환경에 없기
때문이다(pptx/pdf/xlsx 어댑터와 달리 합성 테스트 픽스처를 만들 수 없음). 실사용
전 실제 `.hwp` 파일로 1회 이상 확인을 권장한다.
"""

from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, BinaryIO

from hwp5.dataio import ParseError
from hwp5.errors import InvalidHwp5FileError
from hwp5.hwp5txt import TextTransform
from hwp5.xmlmodel import Hwp5File

from backend.application.ports.parser_port import ParserPort


class HwpParsingError(ValueError):
    """유효하지 않거나 파싱에 실패한 .hwp 파일 — 거짓 성공 응답 방지(T98 AIP)."""


class HwpParserAdapter(ParserPort):
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in (".hwp",)

    def parse_to_markdown(self, file_stream: BinaryIO, metadata: dict[str, Any]) -> str:
        data = file_stream.read()
        with NamedTemporaryFile(suffix=".hwp", delete=False) as tmp_in:
            tmp_in.write(data)
            in_path = tmp_in.name
        out_path = in_path + ".txt"
        try:
            transform = TextTransform().transform_hwp5_to_text
            try:
                with closing(Hwp5File(in_path)) as hwp5file:
                    with open(out_path, "wb") as dest:
                        transform(hwp5file, dest)
            except (ParseError, InvalidHwp5FileError) as exc:
                raise HwpParsingError(f"HWP 파싱 실패: {exc}") from exc
            text = Path(out_path).read_text(encoding="utf-8", errors="replace").strip()
        finally:
            Path(in_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)
        # hwp5txt는 문단 단위 평문만 낸다(구조적 헤딩 없음) — text_passthrough_adapter와
        # 동일하게 원문 그대로 반환한다(임의 헤딩 삽입 없음, 없는 구조를 지어내지 않음).
        # HeadingBoundarySplitter는 헤딩이 없으면 문서 전체를 1개 청크로 묶는다(기존 동작).
        return text + "\n" if text else ""
