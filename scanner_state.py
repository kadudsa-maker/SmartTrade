def next_scan_index(current_index, total_symbols):

    if total_symbols <= 0:
        return 0, False

    next_index = current_index + 1

    if next_index >= total_symbols:
        return 0, True

    return next_index, False


def scan_mode_label(mode, top_bybit_limit=None):

    if top_bybit_limit and mode != "watchlist":
        return f"Top{top_bybit_limit}"

    return "Watchlist"


def run_scan_batch(symbols, start_index, batch_size, scan_symbol):
    """Run one scanner batch and keep going when a single symbol fails."""

    if not symbols or batch_size <= 0:
        return {
            "next_index": 0,
            "scanned_count": 0,
            "completed_cycle": False,
            "errors": []
        }

    current_index = start_index
    scanned_count = 0
    completed_cycle = False
    errors = []

    while scanned_count < batch_size:
        if current_index >= len(symbols):
            current_index = 0

        symbol = symbols[current_index]

        try:
            scan_symbol(symbol, current_index)
        except Exception as error:
            errors.append((symbol, error))

        current_index, wrapped = next_scan_index(current_index, len(symbols))
        scanned_count += 1

        if wrapped:
            completed_cycle = True
            break

    return {
        "next_index": current_index,
        "scanned_count": scanned_count,
        "completed_cycle": completed_cycle,
        "errors": errors
    }
