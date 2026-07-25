"""[D-0993d22f] Recency 가중치 — 지식 수명 감쇠 검증."""

from datetime import datetime, timedelta, timezone

from backend.domain.graph.recency import DEFAULT_HALF_LIFE_DAYS, compute_recency_weight


def test_missing_timestamp_returns_neutral_weight():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert compute_recency_weight(None, now) == 1.0
    assert compute_recency_weight("", now) == 1.0


def test_brand_new_node_weight_is_one():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert compute_recency_weight(now.isoformat(), now) == 1.0


def test_weight_halves_after_one_half_life():
    now = datetime(2026, 1, 31, tzinfo=timezone.utc)
    created_at = (now - timedelta(days=DEFAULT_HALF_LIFE_DAYS)).isoformat()
    weight = compute_recency_weight(created_at, now)
    assert abs(weight - 0.5) < 1e-9


def test_future_timestamp_is_clamped_to_full_weight():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    future = (now + timedelta(days=5)).isoformat()
    assert compute_recency_weight(future, now) == 1.0
