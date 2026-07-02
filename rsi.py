import pandas as pd


def calculate_rma_series(values, period=14):
    """Calculate Wilder's RMA seeded with the first period SMA."""

    series = pd.Series(values, dtype=float)
    rma = pd.Series(float("nan"), index=series.index, dtype=float)

    if period <= 0 or len(series) < period:
        return rma

    first_index = period - 1
    previous_rma = series.iloc[:period].mean()
    rma.iloc[first_index] = previous_rma

    for index in range(period, len(series)):
        current_value = series.iloc[index]
        previous_rma = ((previous_rma * (period - 1)) + current_value) / period
        rma.iloc[index] = previous_rma

    return rma


def calculate_rsi_series(close, period=14):
    """Calculate RSI using close prices and Wilder/RMA smoothing."""

    close_series = pd.Series(close, dtype=float)
    rsi = pd.Series(float("nan"), index=close_series.index, dtype=float)

    if period <= 0 or len(close_series) <= period:
        return rsi

    delta = close_series.diff()
    gain = delta.clip(lower=0).iloc[1:]
    loss = (-delta.clip(upper=0)).iloc[1:]

    average_gain = calculate_rma_series(gain, period)
    average_loss = calculate_rma_series(loss, period)

    for index in average_gain.index:
        avg_gain = average_gain.loc[index]
        avg_loss = average_loss.loc[index]

        if pd.isna(avg_gain) or pd.isna(avg_loss):
            continue

        output_index = index

        if avg_loss == 0:
            rsi.loc[output_index] = 100 if avg_gain > 0 else 50
            continue

        rs = avg_gain / avg_loss
        rsi.loc[output_index] = 100 - (100 / (1 + rs))

    return rsi


def calculate_latest_rsi(close, period=14):

    rsi = calculate_rsi_series(close, period=period).dropna()

    if rsi.empty:
        return None

    return round(float(rsi.iloc[-1]), 2)
