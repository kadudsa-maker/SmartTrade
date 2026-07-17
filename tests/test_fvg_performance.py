from statistics import median
from time import perf_counter

from fvg import Candle, FVGService


def synthetic_history(candle_count=300):
    return tuple(
        Candle(
            time=index * 60,
            open=index * 2.0 + 0.5,
            high=index * 2.0 + 1.0,
            low=index * 2.0,
            close=index * 2.0 + 0.5,
        )
        for index in range(1, candle_count + 1)
    )


def test_full_fvg_recalculation_for_top200(capsys):
    closed_candles = synthetic_history()
    current_candle = closed_candles[-1]
    previous_candle = closed_candles[-2]
    service = FVGService()
    durations = []

    started_at = perf_counter()
    for _symbol_index in range(200):
        symbol_started_at = perf_counter()
        service.analyze(closed_candles, current_candle, previous_candle)
        durations.append(perf_counter() - symbol_started_at)
    total_seconds = perf_counter() - started_at

    average_ms = total_seconds / 200 * 1000
    median_ms = median(durations) * 1000
    slowest_ms = max(durations) * 1000
    print(
        "FVG Top200 benchmark: "
        f"total={total_seconds:.4f}s "
        f"average={average_ms:.3f}ms "
        f"median={median_ms:.3f}ms "
        f"slowest={slowest_ms:.3f}ms"
    )

    assert total_seconds < 5.0
    assert capsys.readouterr().out.startswith("FVG Top200 benchmark:")
