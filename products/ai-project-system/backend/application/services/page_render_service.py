"""[Phase 2 §8] 좌표 기반 페이지 이미지 시각화 오버레이 — 페이지 PNG 렌더링 + 캐시 서비스.

`plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md` §8-4(W2)의 신규 컴포넌트 구현. PyMuPDF
(`pymupdf 1.28.0`, 실제 import 방식은 `import pymupdf as fitz` — 이 환경에서 실측 확인,
`fitz`라는 이름의 별도 legacy 패키지가 아니다)로 PDF의 특정 페이지를 PNG로 래스터화해
디스크에 캐시한다. §8-2 아키텍처 결정(PDF 통합 파이프라인)을 그대로 따라 신규 시스템
의존성(poppler 등) 없이 단일 라이브러리로 처리한다.

**캐시 정리 정책(2026-07-25, 사용자 명시 채택 — §8-8 "운영" 관점 후속과제를 이번 구현에
포함)**: 캐시 디렉터리가 무한 증가하지 않도록 단순 LRU(mtime 기준)로 상한을 강제한다 —
새 정리 알고리즘을 여러 곳에 두지 않고 이 모듈의 `_enforce_cache_limit()` 한 곳에서만
수행한다(CRZ).
"""

from pathlib import Path

import pymupdf as fitz

# [2026-07-25 신규] 캐시 디렉터리 1개(= 문서 1건)당 보관할 최대 페이지 이미지 수. 이
# 상한을 넘으면 가장 오래전에 접근(mtime 기준)된 파일부터 삭제해 상한 이하로 유지한다
# (단순 LRU — 신규 인프라 없이 파일시스템 mtime만으로 판단, over-engineering 회피).
MAX_CACHED_PAGES = 500


def _enforce_cache_limit(cache_dir: Path, max_cached_pages: int = MAX_CACHED_PAGES) -> None:
    """`cache_dir` 안의 PNG 파일 수가 `max_cached_pages`를 넘으면 mtime이 가장 오래된
    파일부터 삭제해 상한 이하로 맞춘다.

    파일을 다시 서빙(캐시 hit)할 때마다 OS가 mtime을 자동으로 갱신하지는 않으므로, 순수
    "가장 오래전에 접근"을 재현하려면 서빙 경로에서 `Path.touch()`로 접근 시각을 갱신해
    주는 것이 이상적이나, 이번 범위(W2)는 렌더링 직후 시점의 정리만 요구한다 — 렌더링
    (캐시 miss → 신규 생성) 시점마다 이 함수가 호출되므로, 최소한 "새로 만들어진 페이지는
    항상 최신"이라는 보장은 성립한다.
    """
    if not cache_dir.exists():
        return
    png_files = list(cache_dir.glob("*.png"))
    if len(png_files) <= max_cached_pages:
        return

    # mtime 오름차순(가장 오래된 것부터) 정렬 후 초과분만 삭제.
    png_files.sort(key=lambda p: p.stat().st_mtime)
    overflow = len(png_files) - max_cached_pages
    for stale_path in png_files[:overflow]:
        stale_path.unlink(missing_ok=True)


def render_page(pdf_path: Path, page_number: int, cache_dir: Path) -> Path:
    """PDF `pdf_path`의 `page_number`(1-based) 페이지를 PNG로 렌더링해 `cache_dir`에
    캐시하고 그 경로를 반환한다. 이미 캐시돼 있으면(캐시 hit) 재렌더링 없이 그대로
    반환한다.

    Args:
        pdf_path: 원본 PDF 파일 경로.
        page_number: 1-based 페이지 번호(사용자·API 계약과 동일하게 1부터 시작 — PyMuPDF
            내부 인덱스는 0-based라 이 함수 내부에서만 -1 변환한다).
        cache_dir: `{page_number}.png`를 저장할 디렉터리(문서 1건당 1개, 호출자가 doc_id별
            로 분리해 전달).

    Raises:
        ValueError: `page_number`가 1보다 작거나 문서의 실제 페이지 수를 초과하는 경우.
    """
    cache_path = cache_dir / f"{page_number}.png"
    if cache_path.exists():
        return cache_path  # 캐시 hit — 재렌더링 없이 그대로 재사용.

    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count
        if page_number < 1 or page_number > page_count:
            raise ValueError(
                f"page_number={page_number}는 유효 범위를 벗어났습니다 "
                f"(문서 '{pdf_path.name}'의 실제 페이지 수: {page_count}, 허용 범위: 1~{page_count})"
            )

        page = doc.load_page(page_number - 1)  # PyMuPDF는 0-based 인덱스.
        pixmap = page.get_pixmap()

        cache_dir.mkdir(parents=True, exist_ok=True)
        pixmap.save(cache_path)

    _enforce_cache_limit(cache_dir)
    return cache_path
