IDEAL_MIN_DISTANCE = 20
IDEAL_MAX_DISTANCE = 45
MAX_DISTANCE = 60


def calculate_pivot_strength(df, pivot, pivot_type, left=3, right=3):

    if df is None or df.empty:
        return 0

    pivot_index = pivot["index"]

    if pivot_index < 0 or pivot_index >= len(df):
        return 0

    if pivot_type == "high":
        return _calculate_high_pivot_strength(df, pivot, left, right)

    if pivot_type == "low":
        return _calculate_low_pivot_strength(df, pivot, left, right)

    return 0


def calculate_rsi_strength(rsi_start, rsi_end):

    difference = abs(_pivot_value(rsi_end) - _pivot_value(rsi_start))

    return _clamp_score((difference / 20) * 100)


def calculate_distance_score(price_start, price_end):

    distance = abs(price_end["index"] - price_start["index"])

    if distance <= 0 or distance > MAX_DISTANCE:
        return 0

    if IDEAL_MIN_DISTANCE <= distance <= IDEAL_MAX_DISTANCE:
        return 100

    if distance < IDEAL_MIN_DISTANCE:
        return _clamp_score((distance / IDEAL_MIN_DISTANCE) * 100)

    return _clamp_score(((MAX_DISTANCE - distance) / (MAX_DISTANCE - IDEAL_MAX_DISTANCE)) * 100)


def calculate_signal_quality(df, divergence, price_pivot_type):

    return {
        "pivot": _calculate_divergence_pivot_strength(df, divergence, price_pivot_type),
        "rsi": calculate_rsi_strength(
            divergence["rsi_start"],
            divergence["rsi_end"]
        ),
        "distance": calculate_distance_score(
            divergence["price_start"],
            divergence["price_end"]
        )
    }


def calculate_quality_score(quality):

    if not quality:
        return 0

    pivot = quality.get("pivot", 0)
    rsi = quality.get("rsi", 0)
    distance = quality.get("distance", 0)

    return round((pivot + rsi + distance) / 3)


def _calculate_divergence_pivot_strength(df, divergence, price_pivot_type):

    first_strength = calculate_pivot_strength(
        df,
        divergence["price_start"],
        price_pivot_type
    )
    second_strength = calculate_pivot_strength(
        df,
        divergence["price_end"],
        price_pivot_type
    )

    return round((first_strength + second_strength) / 2, 2)


def _calculate_high_pivot_strength(df, pivot, left, right):

    index = pivot["index"]
    high = _pivot_value(pivot)
    window = _local_window(df, index, left, right)

    if window.empty:
        return 0

    local_highs = window["high"].astype(float).drop(index, errors="ignore")
    local_lows = window["low"].astype(float)

    if local_highs.empty:
        return 0

    breakout_height = high - local_highs.max()
    local_range = max(local_lows.max() - local_lows.min(), high * 0.001)

    return _structure_score(breakout_height, local_range, len(window), left + right + 1)


def _calculate_low_pivot_strength(df, pivot, left, right):

    index = pivot["index"]
    low = _pivot_value(pivot)
    window = _local_window(df, index, left, right)

    if window.empty:
        return 0

    local_lows = window["low"].astype(float).drop(index, errors="ignore")
    local_highs = window["high"].astype(float)

    if local_lows.empty:
        return 0

    breakout_height = local_lows.min() - low
    local_range = max(local_highs.max() - local_highs.min(), abs(low) * 0.001)

    return _structure_score(breakout_height, local_range, len(window), left + right + 1)


def _structure_score(breakout_height, local_range, candle_count, expected_count):

    height_score = _clamp_score((breakout_height / local_range) * 250)
    candle_score = _clamp_score((candle_count / expected_count) * 100)

    return round((height_score * 0.75) + (candle_score * 0.25), 2)


def _local_window(df, index, left, right):

    start = max(0, index - left)
    end = min(len(df), index + right + 1)

    return df.iloc[start:end]


def _pivot_value(pivot):

    return float(pivot["price"])


def _clamp_score(value):

    return round(max(0, min(100, value)), 2)
