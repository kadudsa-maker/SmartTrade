import pandas as pd

from signal_quality import calculate_signal_quality


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

    assert set(quality) == {"pivot", "rsi", "distance"}
    assert quality["pivot"] >= 0
    assert quality["rsi"] == 75.0
    assert quality["distance"] == 100
