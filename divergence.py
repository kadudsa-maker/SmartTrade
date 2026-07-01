def find_regular_divergences(
    price_highs,
    price_lows,
    rsi_highs,
    rsi_lows,
    max_distance=60,
    max_alignment=3
):

    bullish = _find_bullish_divergences(
        price_lows,
        rsi_lows,
        max_distance,
        max_alignment
    )
    bearish = _find_bearish_divergences(
        price_highs,
        rsi_highs,
        max_distance,
        max_alignment
    )

    return bullish, bearish


def _find_bullish_divergences(price_lows, rsi_lows, max_distance, max_alignment):

    divergences = []

    for first_price, second_price in _consecutive_pairs(price_lows):

        if not _is_valid_distance(first_price, second_price, max_distance):
            continue

        rsi_pair = _find_aligned_consecutive_pair(
            rsi_lows,
            first_price["index"],
            second_price["index"],
            max_alignment
        )

        if rsi_pair is None:
            continue

        first_rsi, second_rsi = rsi_pair

        # Regular Bullish Divergence:
        # price makes a Lower Low while RSI makes a Higher Low.
        if second_price["price"] < first_price["price"] and second_rsi["price"] > first_rsi["price"]:
            divergences.append(_build_divergence("bullish", first_price, second_price, first_rsi, second_rsi))

    return divergences


def _find_bearish_divergences(price_highs, rsi_highs, max_distance, max_alignment):

    divergences = []

    for first_price, second_price in _consecutive_pairs(price_highs):

        if not _is_valid_distance(first_price, second_price, max_distance):
            continue

        rsi_pair = _find_aligned_consecutive_pair(
            rsi_highs,
            first_price["index"],
            second_price["index"],
            max_alignment
        )

        if rsi_pair is None:
            continue

        first_rsi, second_rsi = rsi_pair

        # Regular Bearish Divergence:
        # price makes a Higher High while RSI makes a Lower High.
        if second_price["price"] > first_price["price"] and second_rsi["price"] < first_rsi["price"]:
            divergences.append(_build_divergence("bearish", first_price, second_price, first_rsi, second_rsi))

    return divergences


def _consecutive_pairs(pivots):

    for index in range(len(pivots) - 1):
        yield pivots[index], pivots[index + 1]


def _is_valid_distance(first_pivot, second_pivot, max_distance):

    return 0 < second_pivot["index"] - first_pivot["index"] <= max_distance


def _find_aligned_consecutive_pair(pivots, first_index, second_index, max_alignment):

    aligned_pairs = []

    for first_pivot, second_pivot in _consecutive_pairs(pivots):
        first_distance = abs(first_pivot["index"] - first_index)
        second_distance = abs(second_pivot["index"] - second_index)

        if first_distance <= max_alignment and second_distance <= max_alignment:
            aligned_pairs.append((first_distance + second_distance, first_pivot, second_pivot))

    if not aligned_pairs:
        return None

    _, first_pivot, second_pivot = min(
        aligned_pairs,
        key=lambda item: item[0]
    )

    return first_pivot, second_pivot


def _build_divergence(kind, first_price, second_price, first_rsi, second_rsi):

    return {
        "type": kind,
        "price_line": {
            "start": first_price,
            "end": second_price
        },
        "rsi_line": {
            "start": first_rsi,
            "end": second_rsi
        }
    }
