import pandas as pd

from signal_quality import (
    calculate_distance_score,
    calculate_quality_score,
    calculate_signal_quality,
    calculate_volume_confirmation
)


def test_calculate_signal_quality_returns_component_scores():

    df = pd.DataFrame({
        "high": [10, 11, 12, 20, 13, 12, 11],
        "low": [9, 8, 7, 6, 7, 8, 9]
    })
    divergence = {
        "price_start": {"index": 3, "time": 3, "price": 20},
        "price_end": {"index": 25, "time": 25, "price": 30},
        "rsi_start": {"index": 3, "time": 3, "price": 30},
        "rsi_end": {"index": 25, "time": 25, "price": 45},
        "type": "bearish",
        "quality": None,
        "strength": 0
    }

    quality = calculate_signal_quality(df, divergence, "high")

    assert set(quality) == {"pivot", "rsi", "distance", "volume"}
    assert quality["pivot"] >= 0
    assert quality["rsi"] == 75.0
    assert quality["distance"] == 100
    assert quality["volume"] == 50


def test_calculate_volume_confirmation_uses_average_pivot_windows():

    df = pd.DataFrame({
        "volume": [10, 10, 10, 10, 10, 20, 20, 20, 20, 20],
    })
    divergence = {
        "price_start": {"index": 2, "time": 2, "price": 100},
        "price_end": {"index": 7, "time": 7, "price": 90},
        "rsi_start": {"index": 2, "time": 2, "price": 30},
        "rsi_end": {"index": 7, "time": 7, "price": 40},
        "type": "bullish"
    }

    assert calculate_volume_confirmation(df, divergence) == 100


def test_calculate_quality_score_uses_weighted_volume_model():

    quality = {
        "pivot": 80,
        "rsi": 90,
        "distance": 70,
        "volume": 50
    }

    assert calculate_quality_score(quality) == 75


def test_calculate_distance_score_uses_timeframe_profiles():

    profiles = {
        "1": (12, 24),
        "3": (11, 23),
        "5": (10, 22),
        "15": (8, 18),
        "30": (7, 16),
        "60": (6, 14),
        "240": (5, 12),
        "D": (4, 10)
    }

    for timeframe, (ideal_min, ideal_max) in profiles.items():
        assert _distance_score_for_distance(ideal_min, timeframe) == 100
        assert _distance_score_for_distance(ideal_max, timeframe) == 100
        assert 0 < _distance_score_for_distance(ideal_min - 1, timeframe) < 100
        assert 0 < _distance_score_for_distance(ideal_max + 1, timeframe) < 100


def test_calculate_distance_score_uses_fallback_profile_for_unknown_timeframe():

    assert _distance_score_for_distance(20, "UNKNOWN") == 100
    assert _distance_score_for_distance(45, "UNKNOWN") == 100
    assert 0 < _distance_score_for_distance(19, "UNKNOWN") < 100
    assert 0 < _distance_score_for_distance(46, "UNKNOWN") < 100


def _distance_score_for_distance(distance, timeframe):

    return calculate_distance_score(
        {"index": 0},
        {"index": distance},
        timeframe=timeframe
    )
