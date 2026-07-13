APP_TITLE = "SmartTrade"

SCAN_LOADING_BYBIT = "SCAN: loading Bybit..."
SCAN_START = "SCAN: start"
SCAN_READY = "SCAN ready"
WATCHLIST_EMPTY = "Watchlist is empty."
BYBIT_FETCH_TOP_ERROR = "Could not fetch Top {limit} Bybit: {error}"
BYBIT_FETCH_TOP_EMPTY = "Bybit returned no Top {limit} symbols."
BYBIT_TOP_WARNING = "Could not fetch Top {limit} Bybit. Try again in a moment."

PL_TIME_LABEL = "EU Time: --:--:--"
PL_TIME = "EU Time: {time}"
OPEN_CHART_EMPTY = "Open: -"
OPEN_CHART = "Open: {symbol}"
GUIDE_BUTTON = "GUIDE"
ALERTS_BUTTON = "Alerts"
RESET_TOP20_BUTTON = "Reset to Top20 Bybit"
CHART_NO_DATA = "No chart data"

COIN_SELECTOR_TITLE = "Select coin"
COIN_SELECTOR_HEADER = "Change {symbol}"
COIN_SEARCH_LABEL = "Search"
COIN_NO_RESULTS = "No results"
COIN_LIST_ERROR = "Could not fetch the coin list from Bybit.\n\n{error}"
COIN_LIST_EMPTY = "Bybit returned no USDT Perpetual contracts."
WATCHLIST_SAVE_ERROR = "Could not save the watchlist.\n\n{error}"
WATCHLIST_RESET_CONFIRM = "Replace the watchlist with current Top20 Bybit by 24h Turnover?"
WATCHLIST_RESET_ERROR = "Could not reset the watchlist.\n\n{error}"

CANCEL_BUTTON = "Cancel"
SAVE_BUTTON = "Save"
CLOSE_BUTTON = "Close"
MINIMUM_QUALITY_ERROR = "Minimum Quality must be a number from 0 to 100."

GUIDE_TITLE = "SMARTTRADE QUICK GUIDE"
GUIDE_CONTENT = """SMARTTRADE QUICK GUIDE

SmartTrade is designed to quickly identify high-probability trading opportunities.

Always perform your own market analysis before entering any trade.

LONG SETUP

• Bull signal

• Quality 60 or higher (green)

• RSI below 30 (green)

SHORT SETUP

• Bear signal

• Quality 60 or higher (red)

• RSI 60 or higher (red)

STATUS

ACTIVE

Fresh setup.

Highest priority.

AGING

Setup is getting older but may still remain valid.

EXPIRED

The setup is no longer considered fresh.

FILTERED

The signal was detected but filtered by current Quality rules.

IMPORTANT

Quality measures divergence strength.

RSI measures momentum extremes.

Status is only additional confirmation.

Never use a single indicator alone.

Always evaluate the complete market structure before entering a trade.
"""
GUIDE_NOTE = (
    "SmartTrade is a market scanner, not an automated trading system.\n\n"
    "All trading decisions remain the responsibility of the trader."
)
