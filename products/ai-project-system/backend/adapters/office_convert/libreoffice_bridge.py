"""[Phase 2 §8-4, W4] LibreOffice headless 변환 브리지 — DOCX/PPTX 등 오피스 포맷을 PDF로
변환해, PDF 전용인 `pdf_bbox_adapter.py`/`page_render_service.py` 파이프라인에 그대로
편입시킨다(CRZ — 포맷별 별도 렌더러를 만들지 않고 PDF 뼈대 하나만 재사용, §8-2 아키텍처
결정). 이 파일은 "변환"만 책임진다 — 변환된 PDF의 bbox/페이지 렌더링은 기존 W1/W2 모듈이
그대로 처리한다(신규 로직 없음).

실측(2026-07-25): 이 개발환경에 LibreOffice 미설치였으나 평식 승인 후 `winget install
TheDocumentFoundation.LibreOffice`로 설치 완료. Windows 표준 설치 경로에 바이너리가
있음(경로는 아래 `_DEFAULT_SOFFICE_PATH` 참조) — `soffice`가 시스템 PATH에 자동 등록되지
않으므로 절대경로를 기본값으로 쓰고, 환경변수로 override 가능하게 한다.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Windows 기본 설치 경로(winget/공식 인스톨러 공통) — LibreOffice는 설치 시 시스템 PATH에
# 자동 등록되지 않는다(실측: `where soffice` 설치 후에도 실패) — 절대경로를 기본값으로 사용.
_DEFAULT_SOFFICE_PATH = r"C:\Program Files\LibreOffice\program\soffice.exe"

# ENV-047 표준 타임아웃 가드 패턴(§0-5 Pre-Q) — 대용량 문서 변환이 무한 대기하지 않도록
# 상한을 둔다. hang 시 subprocess.run의 timeout이 TimeoutExpired를 던지고, Python은
# 이 예외 발생 시 자식 프로세스를 자동 종료한다(PS1과 달리 별도 taskkill 불필요).
DEFAULT_TIMEOUT_SECONDS = 120


class LibreOfficeNotFoundError(RuntimeError):
    """soffice 실행 파일을 찾을 수 없을 때(설치 안 됨/경로 상이) — 추정으로 진행 금지."""


class ConversionTimeoutError(RuntimeError):
    """변환이 DEFAULT_TIMEOUT_SECONDS 안에 끝나지 않았을 때(hang 의심, DES-027 계열 리스크)."""


class ConversionFailedError(RuntimeError):
    """soffice가 0이 아닌 종료코드를 반환했을 때 — stderr를 그대로 담아 원인 추적 가능하게."""


def _soffice_path() -> Path:
    """환경변수 `LIBREOFFICE_SOFFICE_PATH`가 있으면 그것을, 없으면 Windows 기본 설치
    경로를 쓴다. 파일이 실제로 존재하는지 여기서 확인해 호출부가 "설치 안 됨"과
    "변환 실패"를 구분할 수 있게 한다(추정 금지, T98 AIP)."""
    override = os.environ.get("LIBREOFFICE_SOFFICE_PATH")
    path = Path(override) if override else Path(_DEFAULT_SOFFICE_PATH)
    if not path.exists():
        raise LibreOfficeNotFoundError(
            f"soffice 실행파일을 찾을 수 없습니다: {path} "
            f"(LibreOffice 미설치이거나 LIBREOFFICE_SOFFICE_PATH 환경변수로 실제 경로 지정 필요)"
        )
    return path


def convert_to_pdf(input_path: Path, output_dir: Path, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Path:
    """`input_path`(DOCX/PPTX 등)를 `output_dir`에 동일 파일명의 PDF로 변환하고 그 경로를
    반환한다. 변환된 PDF는 `pdf_bbox_adapter.locate()`/`page_render_service.render_page()`가
    그대로 소비할 수 있는 표준 PDF다(§8-2 파이프라인 편입, 신규 처리 로직 없음).

    hang 방지: `timeout`초 안에 끝나지 않으면 `ConversionTimeoutError`를 던진다(§0-5 Pre-Q
    ENV-047 가드 — 대용량 문서 하나가 전체 요청을 무한정 막지 않게 한다).
    """
    soffice = _soffice_path()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                str(soffice), "--headless", "--norestore", "--convert-to", "pdf",
                "--outdir", str(output_dir), str(input_path),
            ],
            capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired as exc:
        raise ConversionTimeoutError(
            f"LibreOffice 변환이 {timeout}초 안에 끝나지 않음: {input_path.name}"
        ) from exc

    if result.returncode != 0:
        raise ConversionFailedError(
            f"LibreOffice 변환 실패(exit {result.returncode}): {input_path.name} — "
            f"{(result.stderr or '').strip()[:500]}"
        )

    converted = output_dir / f"{input_path.stem}.pdf"
    if not converted.exists():
        raise ConversionFailedError(
            f"변환 명령은 성공(exit 0)했으나 예상 출력 파일이 없음: {converted}"
        )
    return converted
