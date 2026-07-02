from config import DISTANCE_PROFILE


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


def calculate_distance_score(price_start, price_end, timeframe=None):

    distance = abs(price_end["index"] - price_start["index"])
    ideal_min, ideal_max, max_distance = _distance_profile_for_timeframe(timeframe)

    if distance <= 0:
        return 0

    if ideal_min <= distance <= ideal_max:
        return 100

    if distance < ideal_min:
        return _clamp_score((distance / ideal_min) * 100)

    return _clamp_score(((max_distance - distance) / (max_distance - ideal_max)) * 100)


def calculate_volume_confirmation(df, divergence):

    if df is None or df.empty or "volume" not in df.columns:
        return 50

    first_average = _average_pivot_volume(df, divergence["price_start"])
    second_average = _average_pivot_volume(df, divergence["price_end"])

    if first_average <= 0 or second_average < 0:
        return 50

    ratio = second_average / first_average

    if divergence["type"] == "bearish":
        return _bearish_volume_score(ratio)

    return _bullish_volume_score(ratio)


def calculate_signal_quality(df, divergence, price_pivot_type):

    return {
        "pivot": _calculate_divergence_pivot_strength(df, divergence, price_pivot_type),
        "rsi": calculate_rsi_strength(
            divergence["rsi_start"],
            divergence["rsi_end"]
        ),
        "distance": calculate_distance_score(
            divergence["price_start"],
            divergence["price_end"],
            _timeframe_from_df(df)
        ),
        "volume": calculate_volume_confirmation(df, divergence)
    }


def calculate_quality_score(quality):

    if not quality:
        return 0

    pivot = quality.get("pivot", 0)
    rsi = quality.get("rsi", 0)
    distance = quality.get("distance", 0)
    volume = quality.get("volume", 50)

    return round(
        (pivot * 0.30)
        + (rsi * 0.30)
        + (distance * 0.20)
        + (volume * 0.20)
    )


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


def _timeframe_from_df(df):

    if df is None:
        return None

    return df.attrs.get("timeframe")


def _distance_profile_for_timeframe(timeframe):

    profile = DISTANCE_PROFILE.get(timeframe)

    if profile is None:
        return IDEAL_MIN_DISTANCE, IDEAL_MAX_DISTANCE, MAX_DISTANCE

    ideal_min, ideal_max = profile
    max_distance = ideal_max + (ideal_max - ideal_min)

    return ideal_min, ideal_max, max_distance


def _average_pivot_volume(df, pivot, window=2):

    index = pivot["index"]

    if index < 0 or index >= len(df):
        return 0

    local_window = _local_window(df, index, window, window)

    if local_window.empty:
        return 0

    volume = local_window["volume"].astype(float)
    volume = volume[volume >= 0]

    if volume.empty:
        return 0

    return float(volume.mean())


def _bullish_volume_score(ratio):

    if ratio >= 1:
        return _clamp_score(50 + ((ratio - 1) / 0.5) * 50)

    return _clamp_score(50 - ((1 - ratio) / 0.5) * 50)


def _bearish_volume_score(ratio):

    if ratio >= 1:
        return _clamp_score(50 + ((ratio - 1) / 0.5) * 50)

    return _clamp_score(50 - ((1 - ratio) / 0.5) * 25)


def _pivot_value(pivot):

    return float(pivot["price"])


def _clamp_score(value):

    return round(max(0, min(100, value)), 2)
