from copy import deepcopy

import pytest

import ui as ui_module
from fvg import FVGOpportunityStatus
from fvg.filtering import (
    FVG_ONLY_DEFAULT,
    normalize_fvg_status,
    record_matches_fvg_filter,
)
from ui import SmartTradeUI


class FakeFrame:
    def __init__(self, mapped=True):
        self.manager = "pack" if mapped else ""
        self.pack_calls = 0
        self.forget_calls = 0

    def winfo_manager(self):
        return self.manager

    def winfo_exists(self):
        return True

    def pack(self, **_options):
        self.manager = "pack"
        self.pack_calls += 1

    def pack_forget(self):
        self.manager = ""
        self.forget_calls += 1


class FakeLabel:
    def __init__(self):
        self.options = {"text": ""}

    def cget(self, key):
        return self.options.get(key)

    def configure(self, **options):
        self.options.update(options)


class FakeButton:
    def __init__(self):
        self.options = {}

    def configure(self, **options):
        self.options.update(options)


def card(symbol, mapped=True):
    return {
        "symbol_value": symbol,
        "frame": FakeFrame(mapped),
        "position": FakeLabel(),
    }


def scan_record(ui, symbol, fvg_status="ACTIVE", *, selected=object(), fvg_result=object(), **changes):
    value = {
        "scan_id": ui.current_scan_id,
        "exchange_id": ui.active_exchange_id,
        "exchange_symbol": symbol,
        "symbol": symbol,
        "interval": ui.selected_interval,
        "market_label": ui.market_label(),
        "status": "no_signal",
        "fvg_status": fvg_status,
        "fvg_result": fvg_result,
        "selected_fvg": selected,
        "quality": 88,
        "signal_status": "ACTIVE",
    }
    value.update(changes)
    return value


def make_ui(symbols=("A", "B", "C"), enabled=True):
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.fvg_enabled = True
    ui.fvg_only_enabled = enabled
    ui.fvg_enabled_button = FakeButton()
    ui.fvg_only_button = FakeButton()
    ui.current_scan_id = 9
    ui.active_exchange_id = "bybit"
    ui.selected_interval = "15"
    ui.current_scan_results = {}
    ui.buttons = [card(symbol) for symbol in symbols]
    ui.cards_by_symbol = {item["symbol_value"]: item for item in ui.buttons}
    ui.market_label = lambda exchange_id=None: "Bybit Futures"
    ui.get_active_exchange_id = lambda: ui.active_exchange_id
    return ui


def test_filter_is_disabled_by_default():
    assert FVG_ONLY_DEFAULT is False


@pytest.mark.parametrize(
    "value, expected",
    [
        ("ACTIVE", "ACTIVE"), (" active ", "ACTIVE"),
        ("PENDING", "PENDING"), ("pending", "PENDING"),
        ("", ""), ("NONE", "NONE"), (None, ""), (123, ""),
        (FVGOpportunityStatus.ACTIVE, "ACTIVE"),
        (FVGOpportunityStatus.PENDING, "PENDING"),
    ],
)
def test_status_normalization(value, expected):
    assert normalize_fvg_status(value) == expected


@pytest.mark.parametrize(
    "enabled,status,result_value,selected,expected",
    [
        (False, "", None, None, True),
        (False, "NONE", None, None, True),
        (True, "ACTIVE", object(), object(), True),
        (True, "PENDING", object(), object(), True),
        (True, FVGOpportunityStatus.ACTIVE, object(), object(), True),
        (True, FVGOpportunityStatus.PENDING, object(), object(), True),
        (True, "NONE", object(), object(), False),
        (True, "", object(), object(), False),
        (True, "UNKNOWN", object(), object(), False),
        (True, "ACTIVE", None, object(), False),
        (True, "ACTIVE", object(), None, False),
        (True, "PENDING", None, None, False),
        (True, None, object(), object(), False),
        (True, object(), object(), object(), False),
        (True, "AGING", object(), object(), False),
    ],
)
def test_record_match_contract(enabled, status, result_value, selected, expected):
    record = {"fvg_status": status, "fvg_result": result_value, "selected_fvg": selected}
    assert record_matches_fvg_filter(record, enabled) is expected


def test_filter_control_exists_beside_rsi_controls(monkeypatch):
    widgets = []

    class Widget:
        def __init__(self, _parent=None, **options):
            self.options = options
            widgets.append(self)

        def pack(self, **options):
            self.pack_options = options

        def pack_propagate(self, _value):
            pass

        def configure(self, **options):
            self.options.update(options)

    monkeypatch.setattr(ui_module.ctk, "CTkFrame", Widget)
    monkeypatch.setattr(ui_module.ctk, "CTkLabel", Widget)
    monkeypatch.setattr(ui_module.ctk, "CTkButton", Widget)
    monkeypatch.setattr(ui_module.ctk, "CTkOptionMenu", Widget)
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.center = object()
    ui.rsi_view_option = object()
    ui.fvg_enabled = False
    ui.fvg_only_enabled = False
    ui.build_top_bar()
    assert ui.fvg_enabled_button.options["text"] == "FVG ON"
    assert ui.fvg_enabled_button.options["command"] == ui.toggle_fvg_enabled
    assert ui.fvg_only_button.options["text"] == "FVG ONLY"
    assert ui.fvg_only_button.options["command"] == ui.toggle_fvg_only
    assert ui.rsi_view_menu in widgets


def test_first_and_second_only_click_toggle_state_and_visuals():
    ui = make_ui(())
    ui.fvg_only_enabled = False
    ui.toggle_fvg_only()
    assert ui.fvg_only_enabled is True
    assert ui.fvg_only_button.options["fg_color"] == ui_module.BLUE
    ui.toggle_fvg_only()
    assert ui.fvg_only_enabled is False
    assert ui.fvg_only_button.options["fg_color"] == ui_module.PANEL_COLOR


def test_click_uses_existing_records_without_recalculation():
    ui = make_ui(("A",), enabled=False)
    ui.current_scan_results["A"] = scan_record(ui, "A")
    before = deepcopy({key: value for key, value in ui.current_scan_results["A"].items() if key not in ("fvg_result", "selected_fvg")})
    ui.scan_now = lambda: (_ for _ in ()).throw(AssertionError("scan"))
    ui.fetch_klines = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("request"))
    ui.find_coin_divergences_from_candles = lambda *_a: (_ for _ in ()).throw(AssertionError("divergence"))
    ui.toggle_fvg_only()
    after = {key: value for key, value in ui.current_scan_results["A"].items() if key not in ("fvg_result", "selected_fvg")}
    assert after == before


def test_filter_preserves_quality_signal_status_and_order():
    ui = make_ui(("A", "B"))
    ui.current_scan_results = {
        "A": scan_record(ui, "A", "PENDING"),
        "B": scan_record(ui, "B", "ACTIVE"),
    }
    original_order = list(ui.buttons)
    original_fields = [(item["quality"], item["signal_status"]) for item in ui.current_scan_results.values()]
    ui.apply_card_filters()
    assert ui.buttons == original_order
    assert [(item["quality"], item["signal_status"]) for item in ui.current_scan_results.values()] == original_fields


def test_filter_hides_nonmatches_without_layout_gaps_and_numbers_continuously():
    ui = make_ui(("A", "B", "C"))
    ui.current_scan_results = {
        "A": scan_record(ui, "A", "ACTIVE"),
        "B": scan_record(ui, "B", ""),
        "C": scan_record(ui, "C", "PENDING"),
    }
    ui.apply_card_filters()
    assert [item["frame"].winfo_manager() for item in ui.buttons] == ["pack", "", "pack"]
    assert [item["position"].cget("text") for item in ui.buttons] == ["1", "", "2"]


def test_disabling_filter_restores_layout_order_and_numbering():
    ui = make_ui(("A", "B", "C"))
    ui.current_scan_results = {
        "A": scan_record(ui, "A", "ACTIVE"),
        "B": scan_record(ui, "B", ""),
        "C": scan_record(ui, "C", "PENDING"),
    }
    ui.apply_card_filters()
    ui.toggle_fvg_only()
    assert [item["frame"].winfo_manager() for item in ui.buttons] == ["pack"] * 3
    assert [item["position"].cget("text") for item in ui.buttons] == ["1", "2", "3"]


@pytest.mark.parametrize(
    "old_status,new_status,old_visible,new_visible",
    [
        ("", "PENDING", False, True),
        ("", "ACTIVE", False, True),
        ("PENDING", "ACTIVE", True, True),
        ("ACTIVE", "PENDING", True, True),
        ("ACTIVE", "", True, False),
        ("PENDING", "NONE", True, False),
        ("ACTIVE", "UNKNOWN", True, False),
        ("PENDING", "", True, False),
    ],
)
def test_status_transition_updates_card_visibility(old_status, new_status, old_visible, new_visible):
    ui = make_ui(("A",))
    old = scan_record(ui, "A", old_status)
    ui.current_scan_results["A"] = old
    assert ui.apply_card_filter_to_card(ui.buttons[0], old) is old_visible
    new = scan_record(ui, "A", new_status)
    ui.current_scan_results["A"] = new
    assert ui.apply_card_filter_to_card(ui.buttons[0], new) is new_visible


def test_fvg_analysis_error_hides_card_without_deleting_other_data():
    ui = make_ui(("A",))
    failed = scan_record(ui, "A", "", fvg_result=None, selected=None)
    assert ui.apply_card_filter_to_card(ui.buttons[0], failed) is False
    assert failed["quality"] == 88
    assert failed["signal_status"] == "ACTIVE"


def test_old_scan_id_cannot_restore_visibility():
    ui = make_ui(("A",))
    stale = scan_record(ui, "A", "ACTIVE", scan_id=8)
    ui.current_scan_results["A"] = stale
    ui.apply_card_filters()
    assert ui.buttons[0]["frame"].winfo_manager() == ""


@pytest.mark.parametrize(
    "changed_field,value",
    [
        ("interval", "60"),
        ("exchange_id", "okx"),
        ("market_label", "OKX Perpetual"),
        ("scan_id", 8),
    ],
)
def test_previous_context_record_does_not_match(changed_field, value):
    ui = make_ui(("A",))
    ui.current_scan_results["A"] = scan_record(ui, "A", **{changed_field: value})
    ui.apply_card_filters()
    assert ui.buttons[0]["frame"].winfo_manager() == ""


@pytest.mark.parametrize("mode", ["watchlist", "top50", "top100", "top200"])
def test_shared_filter_path_works_in_every_scan_mode(mode):
    ui = make_ui(("A", "B"))
    ui.scan_mode = mode
    ui.current_scan_results = {
        "A": scan_record(ui, "A", "ACTIVE"),
        "B": scan_record(ui, "B", "NONE"),
    }
    ui.apply_card_filters()
    assert [item["frame"].winfo_manager() for item in ui.buttons] == ["pack", ""]
