from config import PIVOT_LEFT, PIVOT_RIGHT


def find_pivots(df, left=PIVOT_LEFT, right=PIVOT_RIGHT):

    pivot_highs = []
    pivot_lows = []

    highs = df["high"].astype(float).reset_index(drop=True)
    lows = df["low"].astype(float).reset_index(drop=True)
    times = df["time"].reset_index(drop=True)

    # A pivot needs confirmed candles on both sides, so the first `left`
    # candles and the last `right` candles cannot become pivots yet.
    for index in range(left, len(df) - right):

        high = highs.iloc[index]
        low = lows.iloc[index]

        left_highs = highs.iloc[index - left:index]
        right_highs = highs.iloc[index + 1:index + right + 1]
        left_lows = lows.iloc[index - left:index]
        right_lows = lows.iloc[index + 1:index + right + 1]

        # Pivot High: current high must be strictly higher than every
        # compared candle high on the left and on the right.
        if high > left_highs.max() and high > right_highs.max():
            pivot_highs.append({
                "index": index,
                "time": times.iloc[index],
                "price": high
            })

        # Pivot Low: current low must be strictly lower than every
        # compared candle low on the left and on the right.
        if low < left_lows.min() and low < right_lows.min():
            pivot_lows.append({
                "index": index,
                "time": times.iloc[index],
                "price": low
            })

    return pivot_highs, pivot_lows


def find_rsi_pivots(rsi, times, left=PIVOT_LEFT, right=PIVOT_RIGHT):

    rsi_df = _build_rsi_pivot_frame(rsi, times)

    if rsi_df.empty:
        return [], []

    pivot_highs, pivot_lows = find_pivots(rsi_df, left=left, right=right)

    return (
        _restore_original_pivot_indexes(pivot_highs, rsi_df),
        _restore_original_pivot_indexes(pivot_lows, rsi_df)
    )


def _build_rsi_pivot_frame(rsi, times):

    rsi_df = rsi.to_frame(name="rsi")
    rsi_df["time"] = times
    rsi_df["high"] = rsi_df["rsi"]
    rsi_df["low"] = rsi_df["rsi"]

    return rsi_df.dropna().reset_index()


def _restore_original_pivot_indexes(pivots, rsi_df):

    restored_pivots = []

    for pivot in pivots:
        original_index = int(rsi_df.loc[pivot["index"], "index"])

        restored_pivots.append({
            "index": original_index,
            "time": pivot["time"],
            "price": pivot["price"]
        })

    return restored_pivots
