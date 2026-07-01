def find_pivots(df, left=3, right=3):

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
