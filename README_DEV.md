# SmartTrade Developer Notes

## Module Responsibilities

`market.py`
Fetches market data, watchlist symbols, kline candles, and calculates the current RSI value used by the UI watchlist.

`ui.py`
Owns the CustomTkinter interface: window layout, watchlist buttons, TimeFrame buttons, selected symbol state, and passing candle data to the chart.

`chart.py`
Draws the embedded chart, RSI panel, pivot markers, and divergence lines. It should not contain signal detection rules.

`pivots.py`
Detects Pivot High and Pivot Low points using the shared left/right candle algorithm.

`divergence.py`
Detects Regular Bullish and Regular Bearish RSI divergences from prepared price and RSI pivots.

`signal_quality.py`
Contains helper scoring functions for future signal quality and Smart Score work. It does not calculate a final Smart Score yet.

## Current Architecture Rule

Detection logic should stay outside the UI and chart layers. `ui.py` passes data, `chart.py` renders data, and engine-style modules such as `pivots.py`, `divergence.py`, and `signal_quality.py` own calculations.
