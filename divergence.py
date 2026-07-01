MAX_PIVOT_DISTANCE = 60
MAX_PIVOT_ALIGNMENT = 3


def find_regular_divergences(
    df,
    rsi,
    price_pivot_highs,
    price_pivot_lows,
    rsi_pivot_highs,
    rsi_pivot_lows
):

    divergences = []

    divergences.extend(
        _find_regular_bullish(
            df,
            rsi,
            price_pivot_lows,
            rsi_pivot_lows
        )
    )
    divergences.extend(
        _find_regular_bearish(
            df,
            rsi,
            price_pivot_highs,
            rsi_pivot_highs
        )
    )

    return divergences


def _find_regular_bullish(df, rsi, price_lows, rsi_lows):

    divergences = []

    for price_start, price_end in _consecutive_pairs(price_lows):

        if not _can_compare_price_pivots(price_start, price_end):
            continue

        rsi_pair = _find_matching_rsi_pair(
            rsi_lows,
            price_start["index"],
            price_end["index"]
        )

        if rsi_pair is None:
            continue

        rsi_start, rsi_end = rsi_pair

        # Regular Bullish: price prints a Lower Low, while RSI prints a Higher Low.
        if price_end["price"] < price_start["price"] and rsi_end["price"] > rsi_start["price"]:
            divergence = _build_divergence(
                "bullish",
                price_start,
                price_end,
                rsi_start,
                rsi_end
            )
            divergences.append(divergence)
            _log_divergence(df, rsi, divergence)

    return divergences


def _find_regular_bearish(df, rsi, price_highs, rsi_highs):

    divergences = []

    for price_start, price_end in _consecutive_pairs(price_highs):

        if not _can_compare_price_pivots(price_start, price_end):
            continue

        rsi_pair = _find_matching_rsi_pair(
            rsi_highs,
            price_start["index"],
            price_end["index"]
        )

        if rsi_pair is None:
            continue

        rsi_start, rsi_end = rsi_pair

        # Regular Bearish: price prints a Higher High, while RSI prints a Lower High.
        if price_end["price"] > price_start["price"] and rsi_end["price"] < rsi_start["price"]:
            divergence = _build_divergence(
                "bearish",
                price_start,
                price_end,
                rsi_start,
                rsi_end
            )
            divergences.append(divergence)
            _log_divergence(df, rsi, divergence)

    return divergences


def _consecutive_pairs(pivots):

    for index in range(len(pivots) - 1):
        yield pivots[index], pivots[index + 1]


def _can_compare_price_pivots(first_pivot, second_pivot):

    distance = second_pivot["index"] - first_pivot["index"]

    return 0 < distance <= MAX_PIVOT_DISTANCE


def _find_matching_rsi_pair(rsi_pivots, first_price_index, second_price_index):

    matching_pairs = []

    for rsi_start, rsi_end in _consecutive_pairs(rsi_pivots):
        if not _is_rsi_pair_aligned(rsi_start, rsi_end, first_price_index, second_price_index):
            continue

        alignment_score = (
            abs(rsi_start["index"] - first_price_index)
            + abs(rsi_end["index"] - second_price_index)
        )
        matching_pairs.append((alignment_score, rsi_start, rsi_end))

    if not matching_pairs:
        return None

    _, rsi_start, rsi_end = min(
        matching_pairs,
        key=lambda item: item[0]
    )

    return rsi_start, rsi_end


def _is_rsi_pair_aligned(rsi_start, rsi_end, first_price_index, second_price_index):

    start_aligned = abs(rsi_start["index"] - first_price_index) <= MAX_PIVOT_ALIGNMENT
    end_aligned = abs(rsi_end["index"] - second_price_index) <= MAX_PIVOT_ALIGNMENT

    return start_aligned and end_aligned


def _build_divergence(kind, price_start, price_end, rsi_start, rsi_end):

    return {
        "type": kind,
        "price_start": price_start,
        "price_end": price_end,
        "rsi_start": rsi_start,
        "rsi_end": rsi_end,
        "quality": None,
        # Deprecated: kept temporarily for compatibility with earlier code.
        "strength": 0
    }


def _log_divergence(df, rsi, divergence):

    symbol = df.attrs.get("symbol", "UNKNOWN")
    name = _divergence_name(divergence["type"])
    price_start = divergence["price_start"]
    price_end = divergence["price_end"]
    rsi_start = divergence["rsi_start"]
    rsi_end = divergence["rsi_end"]
    distance = price_end["index"] - price_start["index"]

    print("-------------------------------------")
    print(symbol)
    print(name)
    print("Price Pivot 1:")
    print(f"index: {price_start['index']}")
    print(f"price: {price_start['price']}")
    print("Price Pivot 2:")
    print(f"index: {price_end['index']}")
    print(f"price: {price_end['price']}")
    print("RSI Pivot 1:")
    print(f"index: {rsi_start['index']}")
    print(f"value: {_rsi_value(rsi, rsi_start)}")
    print("RSI Pivot 2:")
    print(f"index: {rsi_end['index']}")
    print(f"value: {_rsi_value(rsi, rsi_end)}")
    print("Distance:")
    print(distance)
    print("-------------------------------------")


def _divergence_name(kind):

    names = {
        "bullish": "Regular Bullish",
        "bearish": "Regular Bearish"
    }

    return names.get(kind, kind)


def _rsi_value(rsi, pivot):

    if "price" in pivot:
        return pivot["price"]

    try:
        return rsi.iloc[pivot["index"]]

    except Exception:
        return pivot["price"]
