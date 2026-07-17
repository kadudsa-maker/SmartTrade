import inspect
import threading

import ui as ui_module
from fvg import (
    EvaluatedFVG,
    FairValueGap,
    FVGDirection,
    FVGOpportunityStatus,
    FVGScanResult,
)
from ui import GREEN, RED, RSI_SORT_MODE_QUALITY, SmartTradeUI


class FakeLabel:

    def __init__(self, text="", text_color=""):
        self.options = {"text": text, "text_color": text_color}

    def cget(self, option):
        return self.options.get(option)

    def configure(self, **options):
        self.options.update(options)


class FakeCell:

    def __init__(self, mapped=False, exists=True):
        self.mapped = mapped
        self.exists = exists
        self.grid_calls = 0
        self.grid_remove_calls = 0

    def winfo_exists(self):
        return self.exists

    def winfo_ismapped(self):
        return self.mapped

    def grid(self):
        self.mapped = True
        self.grid_calls += 1

    def grid_remove(self):
        self.mapped = False
        self.grid_remove_calls += 1


class FakeFrame:

    def __init__(self):
        self.bindings = {}
        self.destroyed = False

    def bind(self, event_name, callback):
        self.bindings[event_name] = callback

    def winfo_children(self):
        return []

    def winfo_exists(self):
        return not self.destroyed

    def destroy(self):
        self.destroyed = True


def selected_fvg(
    status=FVGOpportunityStatus.ACTIVE,
    direction=FVGDirection.BULLISH,
    lower=65200,
    upper=65450,
    distance=0.18,
):
    return EvaluatedFVG(
        gap=FairValueGap(
            direction=direction,
            candle1_time=1,
            candle3_time=3,
            lower_price=lower,
            upper_price=upper,
        ),
        status=status,
        distance_percent=distance,
    )


def scan_result(selected):
    status = selected.status if selected is not None else FVGOpportunityStatus.NONE
    gaps = () if selected is None else (selected,)
    return FVGScanResult(100, gaps, selected, status)


def fvg_card(mapped=False, exists=True):
    return {
        "fvg_cell": FakeCell(mapped=mapped, exists=exists),
        "fvg_header": FakeLabel(),
        "fvg_detail": FakeLabel(),
    }


def ui_shell():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.buttons = []
    return ui


def show(ui, card, selected, status=None):
    result = scan_result(selected)
    return ui.update_fvg_card_section(
        card,
        fvg_result=result,
        fvg_status=(status or result.status).value,
        selected_fvg=selected,
    )


def full_card(symbol="BTCUSDT"):
    card = fvg_card()
    card.update({
        "frame": FakeFrame(),
        "symbol": FakeLabel(symbol),
        "market": FakeLabel(),
        "status": FakeLabel(),
        "setup": FakeLabel(),
        "quality": FakeLabel(),
        "time": None,
        "age": FakeLabel(),
        "rsi": FakeLabel(),
        "rsi_cell": FakeCell(mapped=True),
        "position": FakeLabel("1"),
        "symbol_value": symbol,
    })
    return card


def full_ui(card=None):
    ui = ui_shell()
    card = card or full_card()
    ui.buttons = [card]
    ui.cards_by_symbol = {card["symbol_value"]: card}
    ui.last_card_texts = {}
    ui.instrument_by_symbol = {}
    ui.active_exchange_id = "bybit"
    ui.rsi_sort_mode = RSI_SORT_MODE_QUALITY
    return ui


def divergence():
    return {
        "type": "bullish",
        "price_start": {"index": 10, "time": 1},
        "price_end": {"index": 20, "time": 2},
        "rsi_start": {"index": 10, "time": 1},
        "rsi_end": {"index": 20, "time": 2},
        "confirmed_index": 21,
        "confirmed_time": 2,
        "quality": {"score": 85},
    }


def test_active_bullish_shows_status():
    ui, card = ui_shell(), fvg_card()
    show(ui, card, selected_fvg())
    assert card["fvg_header"].cget("text") == "FVG ACTIVE · Bullish"


def test_active_bearish_shows_status():
    ui, card = ui_shell(), fvg_card()
    show(ui, card, selected_fvg(direction=FVGDirection.BEARISH))
    assert card["fvg_header"].cget("text") == "FVG ACTIVE · Bearish"


def test_active_shows_zone_boundaries():
    ui, card = ui_shell(), fvg_card()
    show(ui, card, selected_fvg(lower=65200, upper=65450))
    assert card["fvg_detail"].cget("text") == "65 200 – 65 450"


def test_pending_bullish_shows_status():
    ui, card = ui_shell(), fvg_card()
    show(ui, card, selected_fvg(status=FVGOpportunityStatus.PENDING))
    assert card["fvg_header"].cget("text") == "FVG PENDING · Bullish"


def test_pending_bearish_shows_status():
    ui, card = ui_shell(), fvg_card()
    pending = selected_fvg(
        status=FVGOpportunityStatus.PENDING,
        direction=FVGDirection.BEARISH,
    )
    show(ui, card, pending)
    assert card["fvg_header"].cget("text") == "FVG PENDING · Bearish"


def test_pending_shows_distance_percent():
    ui, card = ui_shell(), fvg_card()
    show(ui, card, selected_fvg(status=FVGOpportunityStatus.PENDING, distance=0.18))
    assert card["fvg_detail"].cget("text") == "Distance: 0.18%"


def test_none_hides_fvg_section():
    ui, card = ui_shell(), fvg_card(mapped=True)
    ui.update_fvg_card_section(card, scan_result(None), "", None)
    assert card["fvg_cell"].mapped is False


def test_missing_fvg_result_hides_section():
    ui, card = ui_shell(), fvg_card(mapped=True)
    ui.update_fvg_card_section(card, None, "ACTIVE", selected_fvg())
    assert card["fvg_cell"].mapped is False


def test_missing_selected_fvg_hides_section():
    ui, card = ui_shell(), fvg_card(mapped=True)
    ui.update_fvg_card_section(card, scan_result(None), "ACTIVE", None)
    assert card["fvg_cell"].mapped is False


def test_active_to_none_clears_old_text():
    ui, card = ui_shell(), fvg_card()
    show(ui, card, selected_fvg())
    ui.update_fvg_card_section(card)
    assert card["fvg_header"].cget("text") == ""
    assert card["fvg_cell"].mapped is False


def test_pending_to_none_clears_old_text():
    ui, card = ui_shell(), fvg_card()
    show(ui, card, selected_fvg(status=FVGOpportunityStatus.PENDING))
    ui.update_fvg_card_section(card)
    assert card["fvg_detail"].cget("text") == ""
    assert card["fvg_cell"].mapped is False


def test_none_to_active_shows_section():
    ui, card = ui_shell(), fvg_card()
    ui.update_fvg_card_section(card)
    show(ui, card, selected_fvg())
    assert card["fvg_cell"].mapped is True


def test_pending_to_active_updates_same_section():
    ui, card = ui_shell(), fvg_card()
    show(ui, card, selected_fvg(status=FVGOpportunityStatus.PENDING))
    cell_id = id(card["fvg_cell"])
    show(ui, card, selected_fvg())
    assert id(card["fvg_cell"]) == cell_id
    assert card["fvg_header"].cget("text").startswith("FVG ACTIVE")


def test_bullish_to_bearish_updates_direction_and_style():
    ui, card = ui_shell(), fvg_card()
    show(ui, card, selected_fvg())
    assert card["fvg_header"].cget("text_color") == GREEN
    show(ui, card, selected_fvg(direction=FVGDirection.BEARISH))
    assert "Bearish" in card["fvg_header"].cget("text")
    assert card["fvg_header"].cget("text_color") == RED


def test_very_low_price_uses_adaptive_precision():
    assert SmartTradeUI.format_fvg_price(0.00001234) == "0.00001234"


def test_high_price_uses_grouping_without_forced_decimals():
    assert SmartTradeUI.format_fvg_price(65450) == "65 450"


def test_distance_is_rounded_readably():
    ui, card = ui_shell(), fvg_card()
    show(ui, card, selected_fvg(status=FVGOpportunityStatus.PENDING, distance=0.1849))
    assert card["fvg_detail"].cget("text") == "Distance: 0.18%"


def test_pending_without_distance_keeps_safe_header():
    ui, card = ui_shell(), fvg_card()
    assert show(
        ui,
        card,
        selected_fvg(status=FVGOpportunityStatus.PENDING, distance=None),
    ) is True
    assert card["fvg_header"].cget("text") == "FVG PENDING · Bullish"
    assert card["fvg_detail"].cget("text") == ""


def test_fvg_does_not_change_divergence_status_label():
    card = full_card()
    ui = full_ui(card)
    div = divergence()
    ui.update_watchlist_card(0, "BTCUSDT", 45, div, 22)
    original = card["status"].cget("text")
    chosen = selected_fvg()
    ui.update_watchlist_card(
        0, "BTCUSDT", 45, div, 22,
        fvg_result=scan_result(chosen), fvg_status="ACTIVE", selected_fvg=chosen,
    )
    assert card["status"].cget("text") == original


def test_fvg_does_not_change_quality_label():
    card = full_card()
    ui = full_ui(card)
    div = divergence()
    ui.update_watchlist_card(0, "BTCUSDT", 45, div, 22)
    original = card["quality"].cget("text")
    chosen = selected_fvg()
    ui.update_watchlist_card(
        0, "BTCUSDT", 45, div, 22,
        fvg_result=scan_result(chosen), fvg_status="ACTIVE", selected_fvg=chosen,
    )
    assert card["quality"].cget("text") == original


def test_fvg_does_not_change_signal_status_calculation():
    ui = full_ui()
    div = divergence()
    before = ui.signal_status(div, 22)
    show(ui, ui.buttons[0], selected_fvg())
    assert ui.signal_status(div, 22) == before


def test_fvg_does_not_change_ui_visible_record_field():
    ui, card = ui_shell(), fvg_card()
    record = {"ui_visible": False}
    show(ui, card, selected_fvg())
    assert record["ui_visible"] is False


def test_fvg_does_not_change_signal_sort_key():
    ui = full_ui()
    record = {"divergence": divergence(), "rsi": 45, "candle_count": 22}
    before = ui.get_signal_sort_key(record)
    chosen = selected_fvg()
    record.update(
        fvg_result=scan_result(chosen),
        fvg_status="ACTIVE",
        selected_fvg=chosen,
    )
    assert ui.get_signal_sort_key(record) == before


def test_fvg_update_does_not_change_card_order():
    ui = ui_shell()
    first, second = fvg_card(), fvg_card()
    ui.buttons = [first, second]
    show(ui, second, selected_fvg())
    assert ui.buttons == [first, second]


def test_fvg_update_does_not_change_card_numbering():
    ui, card = ui_shell(), fvg_card()
    card["position"] = FakeLabel("7")
    show(ui, card, selected_fvg())
    assert card["position"].cget("text") == "7"


def test_fvg_update_does_not_change_card_count():
    ui = ui_shell()
    ui.buttons = [fvg_card(), fvg_card(), fvg_card()]
    show(ui, ui.buttons[1], selected_fvg())
    assert len(ui.buttons) == 3


def test_hidden_section_leaves_no_reserved_grid_width():
    ui, card = ui_shell(), fvg_card(mapped=True)
    ui.update_fvg_card_section(card)
    source = inspect.getsource(SmartTradeUI.create_watchlist_card)
    assert card["fvg_cell"].mapped is False
    assert "grid_columnconfigure(6, weight=0)" in source
    assert "grid_columnconfigure(6, weight=0, minsize=" not in source


def test_repeated_updates_do_not_create_duplicate_widgets():
    ui, card = ui_shell(), fvg_card()
    widget_ids = tuple(id(card[key]) for key in ("fvg_cell", "fvg_header", "fvg_detail"))
    chosen = selected_fvg()
    show(ui, card, chosen)
    show(ui, card, chosen)
    assert tuple(id(card[key]) for key in ("fvg_cell", "fvg_header", "fvg_detail")) == widget_ids
    assert card["fvg_cell"].grid_calls == 1


def test_destroyed_or_missing_widget_does_not_stop_other_cards():
    ui = ui_shell()
    destroyed = fvg_card(exists=False)
    healthy = fvg_card(mapped=True)
    healthy["fvg_header"].configure(text="old")
    ui.buttons = [destroyed, {}, healthy]
    ui.clear_fvg_card_sections()
    assert healthy["fvg_header"].cget("text") == ""
    assert healthy["fvg_cell"].mapped is False


def test_stale_scan_id_does_not_update_visible_fvg():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    ui.current_scan_id = 2
    ui.active_exchange_id = "bybit"
    ui.current_scan_symbols = ["BTCUSDT"]
    ui.instrument_by_symbol = {}
    ui.current_scan_results = {}
    ui.current_scan_rendered = 0
    ui.active_scan_job_id = None
    ui.scan_worker_busy = False
    ui.refresh_index = 0
    ui.scan_batch_position = 0
    ui.scan_cycle_started_at = 1
    ui.scan_mode = "watchlist"
    ui.top_bybit_limit = 100
    ui.buttons = []
    ui.cards_by_symbol = {}
    ui.schedule_scan_loop = lambda *_args: None
    calls = []
    ui.update_watchlist_card = lambda *_args, **_kwargs: calls.append(True)
    stale = ui.create_scan_result_record(1, "BTCUSDT", 0, "no_signal")
    stale["fvg_status"] = "ACTIVE"
    assert ui.apply_scan_result(stale) is False
    assert calls == []


def test_timeframe_and_exchange_changes_remove_old_fvg_state():
    ui = ui_shell()
    old = fvg_card()
    show(ui, old, selected_fvg())
    ui.buttons = [old]
    ui.cancel_scan_loop = lambda: None
    ui.refresh_index = 0
    ui.top50_results = {}
    ui.reset_scan_cycle_state = lambda: None
    ui.is_top_bybit_mode = lambda: False
    ui.update_timeframe_buttons = lambda: None
    ui.refresh_selected = lambda: None
    ui.begin_scan_generation = lambda *_args: None
    ui.schedule_scan_loop = lambda *_args: None
    ui.select_timeframe("15")
    assert old["fvg_cell"].mapped is False

    old_frame = FakeFrame()
    ui.buttons = [{"frame": old_frame, "symbol_value": "BTCUSDT"}]
    ui.cards_by_symbol = {"BTCUSDT": ui.buttons[0]}
    ui.scan_mode = "watchlist"
    ui.reset_scan_state_for_new_run = lambda: None
    ui.clear_watchlist_cards = SmartTradeUI.clear_watchlist_cards.__get__(ui)
    ui.build_watchlist_cards = lambda: None
    ui.update_scan_mode_buttons = lambda: None
    ui.update_open_chart_status = lambda *_args: None
    ui.update_scan_status = lambda *_args: None
    ui.update_scan_progress = lambda *_args: None
    ui.exchange_menu = None
    provider = type("Provider", (), {"display_name": "OKX"})()
    ui.apply_exchange_switch("okx", provider, {}, ["BTC-USDT"])
    assert old_frame.destroyed is True
    assert ui.buttons == []


def test_card_update_does_not_run_fvg_analysis(monkeypatch):
    class ForbiddenService:
        def __init__(self):
            raise AssertionError("FVGService must not run in card UI")

    monkeypatch.setattr(ui_module, "FVGService", ForbiddenService)
    ui = full_ui()
    chosen = selected_fvg()
    assert ui.update_watchlist_card(
        0, "BTCUSDT", 50, None, 0,
        fvg_result=scan_result(chosen), fvg_status="ACTIVE", selected_fvg=chosen,
    ) is True


def test_card_update_does_not_make_api_request(monkeypatch):
    monkeypatch.setattr(
        ui_module,
        "get_klines",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("card UI must not request OHLC")
        ),
    )
    ui = full_ui()
    chosen = selected_fvg()
    assert ui.update_watchlist_card(
        0, "BTCUSDT", 50, None, 0,
        fvg_result=scan_result(chosen), fvg_status="ACTIVE", selected_fvg=chosen,
    ) is True
