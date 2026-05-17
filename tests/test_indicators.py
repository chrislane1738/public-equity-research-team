"""Pure technical-indicator functions — deterministic, list in / list out."""
import math

import pytest

from tools.indicators import (
    sma, ema, rsi, atr, macd, bollinger, adx,
    rolling_vwap, anchored_vwap, volume_by_price,
    realized_volatility, range_position, drawdown_from_high, cross_events,
)


def test_sma_basic():
    assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_sma_rejects_nonpositive_window():
    with pytest.raises(ValueError):
        sma([1, 2, 3], 0)


def test_ema_seeds_with_sma_then_smooths():
    # seed = mean(1,2,3) = 2 at idx 2; k = 0.5 → idx3 = 3, idx4 = 4
    assert ema([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_rsi_is_100_for_monotonic_rise_and_0_for_fall():
    rising = rsi(list(range(1, 30)), period=14)
    assert math.isclose(rising[14], 100.0)
    falling = rsi(list(range(30, 1, -1)), period=14)
    assert math.isclose(falling[14], 0.0)


def test_rsi_stays_in_bounds():
    closes = [10, 11, 10.5, 12, 11.5, 13, 12, 14, 13, 15, 14, 16, 15, 17, 16, 18]
    for v in rsi(closes, period=14):
        if v is not None:
            assert 0.0 <= v <= 100.0


def test_atr_constant_range_equals_range():
    highs = [10.0] * 20
    lows = [8.0] * 20
    closes = [9.0] * 20
    # every TR = max(2, |10-9|, |8-9|) = 2
    assert math.isclose(atr(highs, lows, closes, period=14)[14], 2.0)


def test_macd_keys_align_and_histogram_is_difference():
    closes = [float(x) for x in range(1, 60)]
    out = macd(closes)
    assert set(out) == {"macd", "signal", "histogram"}
    assert len(out["macd"]) == len(closes)
    for m, s, h in zip(out["macd"], out["signal"], out["histogram"]):
        if m is not None and s is not None:
            assert math.isclose(h, m - s)


def test_bollinger_mid_is_sma_and_bands_bracket_it():
    closes = [10, 12, 11, 13, 12, 14, 13, 15, 14, 16,
              15, 17, 16, 18, 17, 19, 18, 20, 19, 21, 20]
    b = bollinger(closes, window=20, n_std=2.0)
    assert b["mid"][-1] == sma(closes, 20)[-1]
    assert b["lower"][-1] < b["mid"][-1] < b["upper"][-1]


def test_bollinger_flat_series_collapses_bands_to_mid():
    b = bollinger([5.0] * 25, window=20)
    assert math.isclose(b["upper"][-1], 5.0)
    assert math.isclose(b["lower"][-1], 5.0)


def test_adx_flags_a_strong_uptrend():
    highs = [10.0 + i for i in range(40)]
    lows = [8.0 + i for i in range(40)]
    closes = [9.0 + i for i in range(40)]
    out = adx(highs, lows, closes, period=14)
    assert out["plus_di"][-1] > out["minus_di"][-1]      # rising → +DI dominates
    assert out["adx"][-1] is not None and out["adx"][-1] > 50  # strong trend
    assert 0.0 <= out["adx"][-1] <= 100.0


def test_rolling_vwap_constant_bars_equals_typical_price():
    n = 10
    vwap = rolling_vwap([10.0] * n, [8.0] * n, [9.0] * n, [100.0] * n, window=5)
    assert math.isclose(vwap[-1], 9.0)  # typical price (10+8+9)/3 = 9


def test_anchored_vwap_starts_at_anchor_and_is_none_before():
    highs = [12, 11, 13, 14, 15]
    lows = [8, 9, 10, 11, 12]
    closes = [10, 10, 12, 13, 14]
    vols = [100, 100, 100, 100, 100]
    av = anchored_vwap(highs, lows, closes, vols, anchor_index=2)
    assert av[0] is None and av[1] is None
    assert math.isclose(av[2], (13 + 10 + 12) / 3)  # first anchored bar = its TP


def test_volume_by_price_buckets_sum_to_total_volume():
    highs = [10, 12, 14, 11, 13, 15, 9, 16]
    lows = [8, 9, 11, 9, 10, 12, 7, 13]
    closes = [9, 11, 13, 10, 12, 14, 8, 15]
    vols = [100, 200, 150, 120, 180, 90, 110, 130]
    buckets = volume_by_price(highs, lows, closes, vols, n_buckets=8)
    assert math.isclose(sum(b["volume"] for b in buckets), sum(vols))
    assert all(b["low"] <= b["mid"] <= b["high"] for b in buckets)


def test_realized_volatility_is_positive_for_a_moving_series():
    closes = [100, 102, 99, 103, 101, 105, 102, 107, 104, 108]
    rv = realized_volatility(closes)
    assert rv is not None and rv > 0


def test_range_position_locates_last_value_in_window():
    assert math.isclose(range_position([10, 20, 30, 15]), 0.25)
    assert math.isclose(range_position([10, 20, 30]), 1.0)   # last == high
    assert math.isclose(range_position([30, 20, 10]), 0.0)   # last == low


def test_drawdown_from_high_is_zero_at_peak_and_negative_below():
    assert math.isclose(drawdown_from_high([100, 120, 90]), 90 / 120 - 1)
    assert math.isclose(drawdown_from_high([100, 120]), 0.0)  # last == peak


def test_cross_events_detects_golden_and_death():
    golden = cross_events([1, 1, 3], [2, 2, 2])
    assert golden == [{"index": 2, "type": "golden"}]
    death = cross_events([3, 3, 1], [2, 2, 2])
    assert death == [{"index": 2, "type": "death"}]


def test_cross_events_skips_none_positions():
    assert cross_events([None, 1, 3], [None, 2, 2]) == [{"index": 2, "type": "golden"}]
