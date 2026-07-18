import pytest

import ui as ui_module
from analysis_modes import ANALYSIS_MODE_OPTIONS, FVG_ON, FVG_ONLY, FVG_RSI
from fvg import (
    EvaluatedFVG,
    FairValueGap,
    FVGDirection,
    FVGOpportunityStatus,
)
from fvg.filtering import normalize_fvg_status, record_has_qualifying_fvg
from ui import GREEN, RED, SmartTradeUI


class ModeValue:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def selected(status, distance=0.0):
    return EvaluatedFVG(
        FairValueGap(FVGDirection.BULLISH, 1, 2, 100, 101),
        status,
        distance,
    )


def record(status="ACTIVE", *, rsi=50, distance=0.0, quality=0, position=0):
    item = selected(FVGOpportunityStatus(status), distance)
    return {
        "fvg_status": status,
        "fvg_result": object(),
        "selected_fvg": item,
        "rsi": rsi,
        "quality": quality,
        "position": position,
        "status": "no_signal",
    }


def mode_ui(mode):
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.rsi_view_option = ModeValue(mode)
    return ui


@pytest.mark.parametrize(
    "value, expected",
    [
        ("ACTIVE", "ACTIVE"),
        (" pending ", "PENDING"),
        (FVGOpportunityStatus.ACTIVE, "ACTIVE"),
        (None, ""),
        (123, ""),
    ],
)
def test_status_normalization(value, expected):
    assert normalize_fvg_status(value) == expected


@pytest.mark.parametrize("status", ["ACTIVE", "PENDING"])
def test_qualifying_fvg_matches(status):
    assert record_has_qualifying_fvg(record(status))


@pytest.mark.parametrize(
    "changes",
    [
        {"fvg_status": ""},
        {"fvg_status": "NONE"},
        {"fvg_result": None},
        {"selected_fvg": None},
    ],
)
def test_missing_or_nonqualifying_fvg_does_not_match(changes):
    value = record()
    value.update(changes)
    assert not record_has_qualifying_fvg(value)


def test_three_fvg_modes_are_in_existing_menu_and_no_buttons(monkeypatch):
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
    ui.rsi_view_option = ModeValue(FVG_ON)
    ui.build_top_bar()
    assert set((FVG_ON, FVG_ONLY, FVG_RSI)).issubset(ANALYSIS_MODE_OPTIONS)
    assert ui.rsi_view_menu.options["values"] == list(ANALYSIS_MODE_OPTIONS)
    assert not hasattr(ui, "fvg_enabled_button")
    assert not hasattr(ui, "fvg_only_button")


@pytest.mark.parametrize(
    "mode,value,expected",
    [
        (FVG_ON, {"fvg_status": "", "fvg_result": None, "selected_fvg": None}, True),
        (FVG_ONLY, record("ACTIVE"), True),
        (FVG_ONLY, record("PENDING", distance=0.2), True),
        (FVG_ONLY, {"fvg_status": "", "fvg_result": None, "selected_fvg": None}, False),
        (FVG_RSI, record("ACTIVE", rsi=30), True),
        (FVG_RSI, record("PENDING", rsi=60), True),
        (FVG_RSI, record("ACTIVE", rsi=45), True),
        (FVG_RSI, {"rsi": 30}, True),
    ],
)
def test_mode_visibility_contract(mode, value, expected):
    ui = mode_ui(mode)
    assert ui.card_matches_active_filters("BTCUSDT", value) is expected


def test_good_rsi_reuses_existing_color_logic():
    ui = mode_ui(FVG_RSI)
    assert ui.has_good_rsi({"rsi": 30})
    assert ui.rsi_value_color(30) == GREEN
    assert ui.has_good_rsi({"rsi": 60})
    assert ui.rsi_value_color(60) == RED
    assert not ui.has_good_rsi({"rsi": 45})


def test_fvg_rsi_keeps_neutral_rsi_and_missing_fvg_visible():
    ui = mode_ui(FVG_RSI)
    assert ui.card_matches_active_filters("ACTIVE", record("ACTIVE", rsi=45))
    assert ui.card_matches_active_filters("PENDING", record("PENDING", rsi=45))
    assert ui.card_matches_active_filters("OTHER", {"rsi": 45, "status": "no_signal"})


def test_fvg_only_remains_the_fvg_filter_exception():
    missing_fvg = {"rsi": 30, "status": "no_signal"}
    assert not mode_ui(FVG_ONLY).card_matches_active_filters("OTHER", missing_fvg)
    assert mode_ui(FVG_RSI).card_matches_active_filters("OTHER", missing_fvg)


def sorted_symbols(ui, records):
    for position, item in enumerate(records):
        item["position"] = position
    return [
        item["symbol"]
        for item in sorted(
            records,
            key=lambda item: (ui.analysis_mode_sort_key(item), -item["position"]),
            reverse=True,
        )
    ]


def named(symbol, item):
    item["symbol"] = symbol
    return item


def test_fvg_on_sorts_fvg_then_rsi_then_quality_stably():
    ui = mode_ui(FVG_ON)
    values = [
        named("NONE", {"fvg_status": "", "rsi": 30, "quality": 100}),
        named("PENDING", record("PENDING", rsi=45, quality=100)),
        named("ACTIVE_NEUTRAL", record("ACTIVE", rsi=45, quality=100)),
        named("ACTIVE_GOOD_LOW_Q", record("ACTIVE", rsi=30, quality=20)),
        named("ACTIVE_GOOD_HIGH_Q", record("ACTIVE", rsi=60, quality=90)),
        named("ACTIVE_GOOD_HIGH_Q_2", record("ACTIVE", rsi=60, quality=90)),
    ]
    assert sorted_symbols(ui, values) == [
        "ACTIVE_GOOD_HIGH_Q",
        "ACTIVE_GOOD_HIGH_Q_2",
        "ACTIVE_GOOD_LOW_Q",
        "ACTIVE_NEUTRAL",
        "PENDING",
        "NONE",
    ]


def test_fvg_only_sorts_active_before_pending_and_pending_by_distance():
    ui = mode_ui(FVG_ONLY)
    values = [
        named("PENDING_FAR", record("PENDING", distance=0.25, rsi=30, quality=100)),
        named("ACTIVE", record("ACTIVE", distance=0, rsi=45, quality=0)),
        named("PENDING_NEAR", record("PENDING", distance=0.05, rsi=60, quality=0)),
    ]
    assert sorted_symbols(ui, values) == ["ACTIVE", "PENDING_NEAR", "PENDING_FAR"]


def test_fvg_only_ignores_rsi_and_quality_for_order():
    ui = mode_ui(FVG_ONLY)
    values = [
        named("FIRST", record("ACTIVE", rsi=45, quality=0)),
        named("SECOND", record("ACTIVE", rsi=30, quality=100)),
    ]
    assert sorted_symbols(ui, values) == ["FIRST", "SECOND"]


def test_fvg_rsi_uses_combined_priority_without_filtering_weaker_coins():
    ui = mode_ui(FVG_RSI)
    values = [
        named("OTHER", {"fvg_status": "", "rsi": 30, "quality": 100}),
        named("PENDING_NEUTRAL", record("PENDING", rsi=45, distance=0.05)),
        named("PENDING_GOOD", record("PENDING", rsi=60, distance=0.2)),
        named("ACTIVE_NEUTRAL", record("ACTIVE", rsi=45)),
        named("ACTIVE_GOOD", record("ACTIVE", rsi=30)),
    ]
    assert sorted_symbols(ui, values) == [
        "ACTIVE_GOOD",
        "ACTIVE_NEUTRAL",
        "PENDING_GOOD",
        "PENDING_NEUTRAL",
        "OTHER",
    ]


class FakeCell:
    def __init__(self, mapped=True):
        self.mapped = mapped

    def winfo_ismapped(self):
        return self.mapped

    def grid(self):
        self.mapped = True

    def grid_remove(self):
        self.mapped = False


class FakeCardFrame(FakeCell):
    def __init__(self, mapped=True):
        super().__init__(mapped)
        self.manager = "pack" if mapped else ""
        self.columns = {}

    def winfo_manager(self):
        return self.manager

    def pack(self, **_options):
        self.manager = "pack"

    def pack_forget(self):
        self.manager = ""

    def grid_columnconfigure(self, column, **options):
        self.columns[column] = options


class FakeLabel:
    def __init__(self):
        self.text = ""

    def cget(self, key):
        return self.text if key == "text" else None

    def configure(self, **options):
        self.text = options.get("text", self.text)


def lifecycle_ui(mode, symbols=("A", "B", "C")):
    ui = mode_ui(mode)
    ui.current_scan_id = 9
    ui.active_exchange_id = "bybit"
    ui.selected_interval = "15"
    ui.market_label = lambda exchange_id=None: "Bybit Futures"
    ui.get_active_exchange_id = lambda: "bybit"
    ui.buttons = [
        {
            "symbol_value": symbol,
            "frame": FakeCardFrame(),
            "position": FakeLabel(),
        }
        for symbol in symbols
    ]
    ui.cards_by_symbol = {card["symbol_value"]: card for card in ui.buttons}
    ui.current_scan_results = {}
    return ui


def contextual_record(ui, symbol, **changes):
    value = record("ACTIVE", rsi=30)
    value.update(
        {
            "scan_id": ui.current_scan_id,
            "exchange_id": "bybit",
            "exchange_symbol": symbol,
            "symbol": symbol,
            "interval": ui.selected_interval,
            "market_label": "Bybit Futures",
            "analysis_mode": ui.current_analysis_mode(),
        }
    )
    value.update(changes)
    return value


def test_fvg_only_hides_nonmatches_without_gaps_and_numbers_continuously():
    ui = lifecycle_ui(FVG_ONLY)
    ui.current_scan_results = {
        "A": contextual_record(ui, "A"),
        "B": contextual_record(ui, "B", fvg_status="", selected_fvg=None),
        "C": contextual_record(
            ui,
            "C",
            fvg_status="PENDING",
            selected_fvg=selected(FVGOpportunityStatus.PENDING, 0.1),
        ),
    }
    ui.apply_card_filters()
    assert [card["frame"].winfo_manager() for card in ui.buttons] == ["pack", "", "pack"]
    assert [card["position"].cget("text") for card in ui.buttons] == ["1", "", "2"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("scan_id", 8),
        ("exchange_id", "okx"),
        ("market_label", "OKX Perpetual"),
        ("interval", "60"),
        ("analysis_mode", FVG_RSI),
    ],
)
def test_previous_context_record_cannot_restore_card(field, value):
    ui = lifecycle_ui(FVG_ONLY, ("A",))
    ui.current_scan_results["A"] = contextual_record(ui, "A", **{field: value})
    ui.apply_card_filters()
    assert ui.buttons[0]["frame"].winfo_manager() == ""


@pytest.mark.parametrize("scan_mode", ["watchlist", "top50", "top100", "top200"])
def test_mode_filter_path_is_shared_by_every_scan_range(scan_mode):
    ui = lifecycle_ui(FVG_RSI, ("A", "B"))
    ui.scan_mode = scan_mode
    ui.current_scan_results = {
        "A": contextual_record(ui, "A", rsi=30),
        "B": contextual_record(ui, "B", rsi=45),
    }
    ui.apply_card_filters()
    assert [card["frame"].winfo_manager() for card in ui.buttons] == ["pack", "pack"]


@pytest.mark.parametrize(
    "mode, expected_standard, expected_rsi, expected_rsi_width",
    [
        (FVG_ON, True, True, 48),
        (FVG_ONLY, False, False, 0),
        (FVG_RSI, False, True, 48),
    ],
)
def test_disabled_analysis_sections_are_removed_from_card_grid(
    mode, expected_standard, expected_rsi, expected_rsi_width
):
    ui = mode_ui(mode)
    frame = FakeCardFrame()
    card = {
        "frame": frame,
        "rsi_cell": FakeCell(),
        "analysis_cells": {
            name: FakeCell() for name in ("setup", "quality", "age", "status")
        },
    }
    ui.update_card_analysis_visibility(card)
    assert all(
        cell.winfo_ismapped() is expected_standard
        for cell in card["analysis_cells"].values()
    )
    assert card["rsi_cell"].winfo_ismapped() is expected_rsi
    assert frame.columns[3]["minsize"] == expected_rsi_width
