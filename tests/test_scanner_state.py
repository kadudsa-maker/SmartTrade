from scanner_state import next_scan_index, run_scan_batch


def test_next_scan_index_wraps_to_zero_at_end():

    next_index, completed_cycle = next_scan_index(2, 3)

    assert next_index == 0
    assert completed_cycle is True


def test_run_scan_batch_continues_after_symbol_exception():

    scanned_symbols = []

    def scan_symbol(symbol, _index):
        scanned_symbols.append(symbol)

        if symbol == "BADUSDT":
            raise RuntimeError("boom")

    result = run_scan_batch(
        ["BTCUSDT", "BADUSDT", "ETHUSDT"],
        start_index=0,
        batch_size=3,
        scan_symbol=scan_symbol
    )

    assert scanned_symbols == ["BTCUSDT", "BADUSDT", "ETHUSDT"]
    assert result["next_index"] == 0
    assert result["completed_cycle"] is True
    assert result["scanned_count"] == 3
    assert len(result["errors"]) == 1
