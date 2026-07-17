import pytest

from fvg import (
    Candle,
    FVGOpportunityStatus,
    FVGScanResult,
    FVGService,
)


def candle(time, low, high, close=None):
    price = (low + high) / 2 if close is None else close
    return Candle(time=time, open=price, high=high, low=low, close=price)


def bullish_history():
    return (
        candle(1, 90, 100),
        candle(2, 95, 102),
        candle(3, 101, 105),
    )


def overlapping_history():
    return (
        candle(1, 90, 105),
        candle(2, 92, 106),
        candle(3, 94, 107),
    )


def test_no_fvg_returns_empty_none_result():
    result = FVGService().analyze(
        overlapping_history(),
        candle(4, 98, 102, 100),
        candle(3, 97, 101, 99),
    )

    assert result == FVGScanResult(
        current_price=100.0,
        gaps=(),
        selected_fvg=None,
        status=FVGOpportunityStatus.NONE,
    )


def test_single_active_fvg_is_selected():
    result = FVGService().analyze(
        bullish_history(),
        candle(4, 100, 101, 100.5),
        candle(3, 99, 100, 99.5),
    )

    assert result.status is FVGOpportunityStatus.ACTIVE
    assert result.selected_fvg is result.gaps[0]


def test_single_pending_fvg_is_selected():
    result = FVGService().analyze(
        bullish_history(),
        candle(4, 99.8, 100, 99.8),
        candle(3, 99, 100, 99.0),
    )

    assert result.status is FVGOpportunityStatus.PENDING
    assert result.selected_fvg is result.gaps[0]


def test_none_only_gaps_are_preserved_without_selection():
    result = FVGService().analyze(
        bullish_history(),
        candle(4, 89, 90, 90),
        candle(3, 88, 89, 89),
    )

    assert len(result.gaps) == 1
    assert result.gaps[0].status is FVGOpportunityStatus.NONE
    assert result.selected_fvg is None
    assert result.status is FVGOpportunityStatus.NONE


def test_active_has_priority_over_pending_with_multiple_gaps():
    history = (
        candle(1, 90, 100),
        candle(2, 99.5, 100.5),
        candle(3, 101, 102),
        candle(4, 102, 102.5),
        candle(5, 103, 104),
    )

    result = FVGService().analyze(
        history,
        candle(6, 100, 101, 100.5),
        candle(5, 98.5, 99.5, 99.0),
        pending_distance_percent=20,
    )

    assert any(
        item.status is FVGOpportunityStatus.ACTIVE for item in result.gaps
    )
    assert any(
        item.status is FVGOpportunityStatus.PENDING for item in result.gaps
    )
    assert result.status is FVGOpportunityStatus.ACTIVE


def test_multiple_active_gaps_use_selector_rules():
    history = tuple(
        candle(index, index * 2, index * 2 + 1)
        for index in range(1, 6)
    )

    result = FVGService().analyze(
        history,
        candle(6, 7, 8, 7.5),
        candle(5, 6, 7, 6.5),
    )

    assert result.status is FVGOpportunityStatus.ACTIVE
    assert result.selected_fvg.gap.candle3_time == 5


def test_result_gaps_are_tuple():
    result = FVGService().analyze(
        bullish_history(),
        candle(4, 100, 101, 100.5),
        candle(3, 99, 100, 99.5),
    )
    assert isinstance(result.gaps, tuple)


def test_service_does_not_mutate_inputs():
    closed = list(bullish_history())
    snapshot = list(closed)
    current = candle(4, 100, 101, 100.5)
    previous = candle(3, 99, 100, 99.5)

    FVGService().analyze(closed, current, previous)

    assert closed == snapshot


def test_detector_validation_error_is_propagated():
    with pytest.raises(ValueError, match="at least three"):
        FVGService().analyze(
            bullish_history()[:2],
            candle(4, 100, 101, 100.5),
            candle(3, 99, 100, 99.5),
        )


def test_invalid_pending_threshold_is_propagated():
    with pytest.raises(ValueError, match="non-negative"):
        FVGService().analyze(
            bullish_history(),
            candle(4, 99.8, 100, 99.8),
            candle(3, 99, 100, 99.0),
            pending_distance_percent=-1,
        )


def test_repeated_calls_return_identical_results():
    service = FVGService()
    arguments = (
        bullish_history(),
        candle(4, 100, 101, 100.5),
        candle(3, 99, 100, 99.5),
    )

    assert service.analyze(*arguments) == service.analyze(*arguments)


def test_service_keeps_no_state_between_calls():
    service = FVGService()
    first = service.analyze(
        bullish_history(),
        candle(4, 100, 101, 100.5),
        candle(3, 99, 100, 99.5),
    )
    second = service.analyze(
        overlapping_history(),
        candle(4, 98, 102, 100),
        candle(3, 97, 101, 99),
    )

    assert first.gaps
    assert second.gaps == ()
    assert service.__dict__ == {}
