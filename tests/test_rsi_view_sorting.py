from ui import (
    GREEN,
    RSI_SORT_MODE_QUALITY,
    RSI_SORT_MODE_RSI,
    RSI_SORT_MODE_RSI_QUALITY,
    RSI_VIEW_OFF,
    RSI_VIEW_ON,
    RSI_VIEW_QUALITY_SORT,
    RSI_VIEW_SORT,
    RED,
    SmartTradeUI,
    TEXT_COLOR
)


class Flag:

    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeAlertManager:

    def __init__(self):
        self.calls = []

    def process_signal(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class FakeCell:

    def __init__(self, mapped=True):
        self.mapped = mapped
        self.grid_calls = 0
        self.grid_remove_calls = 0

    def winfo_ismapped(self):
        return self.mapped

    def grid(self):
        self.mapped = True
        self.grid_calls += 1

    def grid_remove(self):
        self.mapped = False
        self.grid_remove_calls += 1


def _ui_with_rsi_mode(sort_mode=RSI_SORT_MODE_QUALITY, view_option=RSI_VIEW_OFF):

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.rsi_sort_mode = sort_mode
    ui.rsi_view_option = Flag(view_option)
    ui.rsi_sort_mode_label = None
    ui.last_card_texts = {}
    ui.scan_mode = "top200"
    ui.top_bybit_limit = 200

    return ui


def _quality(score):

    return {
        "pivot": score,
        "rsi": score,
        "distance": score,
        "volume": score
    }


def _divergence(quality, age_candles=0):

    return {
        "type": "bullish",
        "price_start": {"index": 1, "time": 1, "price": 1},
        "price_end": {"index": 10, "time": 10, "price": 1},
        "rsi_start": {"index": 1, "time": 1, "price": 30},
        "rsi_end": {"index": 10, "time": 10, "price": 45},
        "confirmed_index": 12,
        "confirmed_time": 12,
        "age_candles": age_candles,
        "quality": _quality(quality)
    }


def _result(rsi, quality=80, age_candles=0):

    return {
        "symbol": "BTCUSDT",
        "rsi": rsi,
        "divergence": _divergence(quality, age_candles),
        "candle_count": 100
    }


def test_rsi_extreme_score_is_distance_from_50():

    ui = _ui_with_rsi_mode()

    assert ui.rsi_extreme_score(90) == ui.rsi_extreme_score(10)
    assert ui.rsi_extreme_score(50) == 0
    assert ui.rsi_extreme_score(90) == 80
    assert ui.rsi_extreme_score(10) == 80
    assert ui.rsi_extreme_score(70) == 40
    assert ui.rsi_extreme_score(30) == 40
    assert ui.rsi_extreme_score(80) > ui.rsi_extreme_score(60)


def test_rsi_value_color_uses_extreme_thresholds():

    ui = _ui_with_rsi_mode()

    assert ui.rsi_value_color(71) == RED
    assert ui.rsi_value_color(29) == GREEN
    assert ui.rsi_value_color(30) == TEXT_COLOR
    assert ui.rsi_value_color(70) == TEXT_COLOR
    assert ui.rsi_value_color(50) == TEXT_COLOR


def test_rsi_on_shows_rsi_without_changing_sort_mode():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_QUALITY, RSI_VIEW_OFF)
    ui.is_top_bybit_mode = lambda: False
    rsi_cell = FakeCell(mapped=False)

    ui.apply_rsi_view_option(RSI_VIEW_ON)
    ui.update_rsi_card_visibility({"rsi_cell": rsi_cell})

    assert ui.rsi_sort_mode == RSI_SORT_MODE_QUALITY
    assert rsi_cell.mapped is True


def test_rsi_off_hides_rsi_and_resets_rsi_sort_to_quality():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI, RSI_VIEW_SORT)
    ui.is_top_bybit_mode = lambda: False
    rsi_cell = FakeCell(mapped=True)

    ui.apply_rsi_view_option(RSI_VIEW_OFF)
    ui.update_rsi_card_visibility({"rsi_cell": rsi_cell})

    assert ui.rsi_sort_mode == RSI_SORT_MODE_QUALITY
    assert rsi_cell.mapped is False


def test_rsi_sort_keeps_fresh_signal_above_expired_extreme_rsi():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI, RSI_VIEW_SORT)
    fresh_signal = _result(rsi=70, quality=65, age_candles=0)
    expired_extreme_signal = _result(rsi=95, quality=95, age_candles=50)

    assert ui.get_signal_sort_key(fresh_signal) > ui.get_signal_sort_key(expired_extreme_signal)


def test_rsi_sort_uses_rsi_extreme_for_similar_freshness():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI, RSI_VIEW_SORT)
    less_extreme = _result(rsi=65, quality=90, age_candles=1)
    more_extreme = _result(rsi=85, quality=70, age_candles=1)

    assert ui.get_signal_sort_key(more_extreme) > ui.get_signal_sort_key(less_extreme)


def test_rsi_sort_prefers_one_candle_ago_over_three_candles_ago():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI, RSI_VIEW_SORT)
    one_candle_ago = _result(rsi=60, quality=60, age_candles=1)
    three_candles_ago = _result(rsi=95, quality=95, age_candles=3)

    assert ui.get_signal_sort_key(one_candle_ago) > ui.get_signal_sort_key(three_candles_ago)


def test_rsi_sort_prefers_two_candles_ago_over_older_setup():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI, RSI_VIEW_SORT)
    two_candles_ago = _result(rsi=60, quality=60, age_candles=2)
    older_setup = _result(rsi=95, quality=95, age_candles=5)

    assert ui.get_signal_sort_key(two_candles_ago) > ui.get_signal_sort_key(older_setup)


def test_rsi_sort_for_old_setups_prioritizes_rsi_extreme_over_age():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI, RSI_VIEW_SORT)
    less_extreme_newer_old_setup = _result(rsi=60, quality=70, age_candles=5)
    more_extreme_older_setup = _result(rsi=95, quality=70, age_candles=6)

    assert (
        ui.get_signal_sort_key(more_extreme_older_setup)
        > ui.get_signal_sort_key(less_extreme_newer_old_setup)
    )


def test_rsi_sort_does_not_use_quality_as_criterion():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI, RSI_VIEW_SORT)
    lower_quality = _result(rsi=80, quality=70, age_candles=2)
    higher_quality = _result(rsi=80, quality=95, age_candles=2)

    assert ui.get_signal_sort_key(lower_quality) == ui.get_signal_sort_key(higher_quality)


def test_rsi_quality_sort_uses_freshness_before_quality_priority():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI_QUALITY, RSI_VIEW_QUALITY_SORT)
    fresher_lower_quality = _result(rsi=60, quality=60, age_candles=1)
    older_higher_quality = _result(rsi=95, quality=95, age_candles=2)

    assert ui.get_signal_sort_key(fresher_lower_quality) > ui.get_signal_sort_key(older_higher_quality)


def test_rsi_quality_sort_quality_above_65_prioritizes_over_rsi_extreme():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI_QUALITY, RSI_VIEW_QUALITY_SORT)
    quality_priority = _result(rsi=85, quality=66, age_candles=2)
    lower_quality_more_extreme = _result(rsi=95, quality=55, age_candles=2)

    assert (
        ui.get_signal_sort_key(quality_priority)
        > ui.get_signal_sort_key(lower_quality_more_extreme)
    )


def test_rsi_quality_sort_uses_rsi_then_quality_then_average():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI_QUALITY, RSI_VIEW_QUALITY_SORT)
    less_extreme = _result(rsi=70, quality=70, age_candles=2)
    more_extreme = _result(rsi=80, quality=70, age_candles=2)
    lower_quality = _result(rsi=80, quality=70, age_candles=2)
    higher_quality = _result(rsi=80, quality=75, age_candles=2)

    assert ui.get_signal_sort_key(more_extreme) > ui.get_signal_sort_key(less_extreme)
    assert ui.get_signal_sort_key(higher_quality) > ui.get_signal_sort_key(lower_quality)


def test_rsi_sort_does_not_change_quality_or_rsi():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI, RSI_VIEW_SORT)
    result = _result(rsi=90, quality=80, age_candles=1)
    quality_before = result["divergence"]["quality"].copy()
    rsi_before = result["rsi"]

    ui.get_signal_sort_key(result)

    assert result["divergence"]["quality"] == quality_before
    assert result["rsi"] == rsi_before


def test_rsi_on_does_not_change_sort_mode():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI, RSI_VIEW_SORT)
    ui.is_top_bybit_mode = lambda: False

    ui.apply_rsi_view_option(RSI_VIEW_ON)

    assert ui.rsi_sort_mode == RSI_SORT_MODE_RSI


def test_alerts_use_base_quality_with_rsi_sort_enabled():

    ui = _ui_with_rsi_mode(RSI_SORT_MODE_RSI_QUALITY, RSI_VIEW_QUALITY_SORT)
    ui.selected_interval = "15"
    ui.scan_mode = "top200"
    ui.alert_manager = FakeAlertManager()
    ui.update_alert_status_labels = lambda: None
    divergence = _divergence(80, age_candles=0)

    ui.process_alert_candidate("BTCUSDT", divergence, candle_count=100)

    _args, kwargs = ui.alert_manager.calls[0]
    assert kwargs["quality_score"] == 80
