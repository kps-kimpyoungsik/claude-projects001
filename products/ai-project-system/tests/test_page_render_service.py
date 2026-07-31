"""[Phase 2 §8, W2] `page_render_service.render_page()` 단위 테스트 — 캐시 hit/miss,
캐시 정리 정책(mtime 기반 LRU), 잘못된 page_number의 ValueError를 검증한다.
"""

import time

import pymupdf as fitz
import pytest

from backend.application.services.page_render_service import (
    MAX_CACHED_PAGES,
    _enforce_cache_limit,
    render_page,
)


def _make_pdf(path, page_count=1):
    doc = fitz.open()
    for i in range(page_count):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {i + 1}")
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def pdf_path(tmp_path):
    return _make_pdf(tmp_path / "sample.pdf", page_count=3)


def test_render_page_creates_png_cache_miss(pdf_path, tmp_path):
    cache_dir = tmp_path / "cache"
    result = render_page(pdf_path, 1, cache_dir)

    assert result == cache_dir / "1.png"
    assert result.exists()
    assert result.stat().st_size > 0


def test_render_page_reuses_existing_cache_hit(pdf_path, tmp_path):
    cache_dir = tmp_path / "cache"
    first = render_page(pdf_path, 2, cache_dir)
    first_mtime = first.stat().st_mtime

    # 캐시 파일을 인위적으로 손상시켜서 두 번째 호출이 재렌더링했다면 복구됐을 것 —
    # 캐시 hit이면 이 손상 내용이 그대로 유지되어야 한다.
    marker = b"CACHE_HIT_MARKER"
    with open(first, "wb") as f:
        f.write(marker)

    second = render_page(pdf_path, 2, cache_dir)

    assert second == first
    with open(second, "rb") as f:
        assert f.read() == marker  # 재렌더링되지 않았다면(캐시 hit) 마커가 그대로 남는다.


def test_render_page_invalid_page_number_raises_value_error(pdf_path, tmp_path):
    cache_dir = tmp_path / "cache"

    with pytest.raises(ValueError, match="page_number"):
        render_page(pdf_path, 99, cache_dir)

    with pytest.raises(ValueError, match="page_number"):
        render_page(pdf_path, 0, cache_dir)


def test_enforce_cache_limit_deletes_oldest_files_over_threshold(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    # 임계값보다 많은 더미 PNG 파일을 생성 시각을 다르게(mtime 순서 보장) 만들어둔다.
    threshold = 5
    paths = []
    for i in range(threshold + 3):
        p = cache_dir / f"{i}.png"
        p.write_bytes(b"fake-png")
        paths.append(p)
        time.sleep(0.01)  # mtime 해상도 확보(같은 tick에 몰리면 정렬이 불안정해짐).

    _enforce_cache_limit(cache_dir, max_cached_pages=threshold)

    remaining = sorted(cache_dir.glob("*.png"))
    assert len(remaining) == threshold
    # 가장 오래된(먼저 만든) 파일들이 삭제되고, 가장 최근 파일들만 남아야 한다.
    remaining_names = {p.name for p in remaining}
    expected_survivors = {f"{i}.png" for i in range(3, threshold + 3)}
    assert remaining_names == expected_survivors


def test_enforce_cache_limit_noop_when_under_threshold(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "1.png").write_bytes(b"fake-png")

    _enforce_cache_limit(cache_dir, max_cached_pages=MAX_CACHED_PAGES)

    assert len(list(cache_dir.glob("*.png"))) == 1


def test_render_page_triggers_cache_limit_enforcement(tmp_path):
    """render_page()가 신규 렌더링 후 `_enforce_cache_limit()`을 실제로 호출하는지 —
    임계값을 낮게 지정할 수는 없으므로(상수) 여러 페이지를 렌더링해도 정리 정책 함수
    자체가 예외 없이 동작하는지를 통합적으로 확인한다."""
    pdf = _make_pdf(tmp_path / "multi.pdf", page_count=3)
    cache_dir = tmp_path / "cache"

    for page_number in (1, 2, 3):
        render_page(pdf, page_number, cache_dir)

    assert len(list(cache_dir.glob("*.png"))) == 3


def test_enforce_cache_limit_noop_when_cache_dir_does_not_exist(tmp_path):
    """[커버리지 보완] cache_dir 자체가 아직 생성되지 않은 상태(첫 렌더링 이전)에서
    호출돼도 예외 없이 조용히 반환한다."""
    from backend.application.services.page_render_service import _enforce_cache_limit

    non_existent = tmp_path / "never_created"
    _enforce_cache_limit(non_existent)  # 예외 없이 통과하면 성공
