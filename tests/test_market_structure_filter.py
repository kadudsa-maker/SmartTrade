from copy import deepcopy

from analysis_modes import FVG_ON, MARKET_STRUCTURE, RSI_VIEW_ON
from market_structure import (
    MarketStructureResult,
    MarketStructureState,
    PriceStructure,
    SemanticColor,
    Strength,
    TrendDirection,
)
from ui import MARKET_STRUCTURE_STATE_TEXT, SmartTradeUI


class ModeValue:

    def __init__(self, value):

        self.value = value

    def get(self):

        return self.value

    def set(self, value):

        self.value = value


class FakePanel:

    def __init__(self, mapped=False):

        self.mapped = mapped
        self.pack_calls = 0
        self.pack_forget_calls = 0

    def winfo_ismapped(self):

        return self.mapped

    def pack(self, **_options):

        self.mapped = True
        self.pack_calls += 1

    def pack_forget(self):

        self.mapped = False
        self.pack_forget_calls += 1


class FakeFrame:

    def __init__(self, mapped=True):

        self.manager = "pack" if mapped else ""

    def winfo_exists(self):

        return True

    def winfo_manager(self):

        return self.manager

    def pack(self, **_options):

        self.manager = "pack"

    def pack_forget(self):

        self.manager = ""


class FakeLabel:

    def __init__(self):

        self.text = ""

    def cget(self, option):

        return self.text if option == "text" else None

    def configure(self, **options):

        self.text = options.get("text", self.text)


def _result(state):

    return MarketStructureResult(
        state=state,
        previous_trend=TrendDirection.NONE,
        strength=Strength.MEDIUM,
        reason="",
        price_structure=PriceStructure.MIXED,
        divergence_direction=None,
        rsi_value=None,
        color_key=SemanticColor.NEUTRAL,
    )


def _filter_ui(states=None):

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.rsi_view_option = ModeValue(MARKET_STRUCTURE)
    ui.market_structure_filter_states = (
        set(MarketStructureState) if states is None else set(states)
    )
    ui.market_structure_filter_vars = {}
    ui.buttons = []
    ui.current_scan_results = {}
    return ui


def _card(symbol, mapped=True):

    return {
        "symbol_value": symbol,
        "frame": FakeFrame(mapped),
        "position": FakeLabel(),
    }


def _install_records(ui, records):

    ui.current_scan_results = records
    ui.current_card_scan_record = lambda symbol: records.get(symbol)


def test_all_market_structure_states_are_active_by_default():

    ui = SmartTradeUI.__new__(SmartTradeUI)

    assert ui.active_market_structure_filter_states() == set(
        MarketStructureState
    )
    assert set(MARKET_STRUCTURE_STATE_TEXT) == set(MarketStructureState)


def test_filter_panel_is_visible_only_in_market_structure_mode():

    ui = _filter_ui()
    ui.market_structure_filter_panel = FakePanel()
    ui.analysis_top_bar = object()

    ui.update_market_structure_filter_panel_visibility()
    assert ui.market_structure_filter_panel.mapped is True

    ui.rsi_view_option.set(RSI_VIEW_ON)
    ui.update_market_structure_filter_panel_visibility()
    assert ui.market_structure_filter_panel.mapped is False


def test_mode_round_trip_preserves_session_selection():

    ui = _filter_ui({MarketStructureState.UPTREND})
    ui.market_structure_filter_panel = FakePanel(mapped=True)
    ui.analysis_top_bar = object()

    ui.rsi_view_option.set(FVG_ON)
    ui.update_market_structure_filter_panel_visibility()
    ui.rsi_view_option.set(MARKET_STRUCTURE)
    ui.update_market_structure_filter_panel_visibility()

    assert ui.active_market_structure_filter_states() == {
        MarketStructureState.UPTREND
    }
    assert ui.market_structure_filter_panel.mapped is True


def test_selected_and_unselected_states_control_card_visibility():

    ui = _filter_ui({MarketStructureState.UPTREND})

    assert ui.card_matches_active_filters(
        "UP",
        {"market_structure": _result(MarketStructureState.UPTREND)},
    )
    assert not ui.card_matches_active_filters(
        "DOWN",
        {"market_structure": _result(MarketStructureState.DOWNTREND)},
    )


def test_multiple_states_and_empty_selection_are_supported():

    ui = _filter_ui({
        MarketStructureState.POTENTIAL_DISTRIBUTION,
        MarketStructureState.POTENTIAL_ACCUMULATION,
    })

    assert ui.is_market_structure_state_visible(
        MarketStructureState.POTENTIAL_DISTRIBUTION
    )
    assert ui.is_market_structure_state_visible(
        MarketStructureState.POTENTIAL_ACCUMULATION
    )
    assert not ui.is_market_structure_state_visible(
        MarketStructureState.UPTREND
    )

    ui.market_structure_filter_states.clear()
    assert all(
        not ui.is_market_structure_state_visible(state)
        for state in MarketStructureState
    )


def test_checkbox_state_change_refreshes_only_existing_card_visibility():

    ui = _filter_ui()
    refreshes = []
    ui.apply_card_filters = lambda: refreshes.append(True)

    assert ui.set_market_structure_filter_state(
        MarketStructureState.UNDEFINED,
        False,
    )
    assert MarketStructureState.UNDEFINED not in (
        ui.active_market_structure_filter_states()
    )
    assert refreshes == [True]


def test_missing_result_is_filtered_as_undefined():

    ui = _filter_ui({MarketStructureState.UNDEFINED})

    assert ui.card_matches_active_filters("OLD", {})
    ui.market_structure_filter_states.clear()
    assert not ui.card_matches_active_filters("OLD", {})


def test_filter_change_hides_and_restores_existing_cards_without_duplicates():

    ui = _filter_ui({MarketStructureState.UPTREND})
    up_card = _card("UP")
    down_card = _card("DOWN")
    ui.buttons = [up_card, down_card]
    _install_records(
        ui,
        {
            "UP": {"market_structure": _result(MarketStructureState.UPTREND)},
            "DOWN": {
                "market_structure": _result(MarketStructureState.DOWNTREND)
            },
        },
    )
    card_ids = [id(card) for card in ui.buttons]

    ui.apply_card_filters()
    assert [card["frame"].winfo_manager() for card in ui.buttons] == [
        "pack",
        "",
    ]

    ui.market_structure_filter_states.add(MarketStructureState.DOWNTREND)
    ui.apply_card_filters()

    assert [card["frame"].winfo_manager() for card in ui.buttons] == [
        "pack",
        "pack",
    ]
    assert [id(card) for card in ui.buttons] == card_ids


def test_existing_card_state_change_is_re_evaluated():

    ui = _filter_ui({MarketStructureState.UPTREND})
    card = _card("BTC")
    ui.buttons = [card]
    records = {
        "BTC": {"market_structure": _result(MarketStructureState.UPTREND)}
    }
    _install_records(ui, records)

    ui.apply_card_filters()
    assert card["frame"].winfo_manager() == "pack"

    records["BTC"] = {
        "market_structure": _result(MarketStructureState.DOWNTREND)
    }
    ui.apply_card_filters()
    assert card["frame"].winfo_manager() == ""


def test_filter_preserves_record_data_and_card_order():

    ui = _filter_ui({MarketStructureState.DOWNTREND})
    ui.buttons = [_card("A"), _card("B"), _card("C")]
    records = {
        "A": {"market_structure": _result(MarketStructureState.UPTREND)},
        "B": {"market_structure": _result(MarketStructureState.DOWNTREND)},
        "C": {"market_structure": _result(MarketStructureState.UPTREND)},
    }
    _install_records(ui, records)
    snapshot = deepcopy(records)
    order = list(ui.buttons)

    ui.apply_card_filters()

    assert records == snapshot
    assert ui.buttons == order
    assert [card["symbol_value"] for card in ui.buttons if card["frame"].manager] == [
        "B"
    ]


def test_filter_refresh_does_not_run_market_analysis_or_requests():

    ui = _filter_ui(set())
    ui.buttons = [_card("BTC")]
    _install_records(
        ui,
        {"BTC": {"market_structure": _result(MarketStructureState.UPTREND)}},
    )
    ui.fetch_klines = lambda *_args: (_ for _ in ()).throw(
        AssertionError("filter must not fetch")
    )
    ui.find_coin_divergences_from_candles = lambda *_args: (
        _ for _ in ()
    ).throw(AssertionError("filter must not analyze pivots or RSI"))
    ui.evaluate_passive_market_structure = lambda *_args: (
        _ for _ in ()
    ).throw(AssertionError("filter must not evaluate Market Structure"))

    ui.apply_card_filters()

    assert ui.buttons[0]["frame"].winfo_manager() == ""


def test_top_n_is_not_supplemented_after_filtering():

    ui = _filter_ui({MarketStructureState.UPTREND})
    ui.scan_mode = "top100"
    ui.buttons = [_card("A"), _card("B"), _card("C")]
    _install_records(
        ui,
        {
            "A": {"market_structure": _result(MarketStructureState.UPTREND)},
            "B": {
                "market_structure": _result(MarketStructureState.DOWNTREND)
            },
            "C": {
                "market_structure": _result(MarketStructureState.DOWNTREND)
            },
        },
    )

    ui.apply_card_filters()

    assert len(ui.buttons) == 3
    assert sum(bool(card["frame"].manager) for card in ui.buttons) == 1


def test_watchlist_uses_the_same_filter_path():

    ui = _filter_ui({MarketStructureState.POTENTIAL_ACCUMULATION})
    ui.scan_mode = "watchlist"
    card = _card("ETH")
    ui.buttons = [card]
    records = {
        "ETH": {
            "market_structure": _result(
                MarketStructureState.POTENTIAL_DISTRIBUTION
            )
        }
    }
    _install_records(ui, records)

    ui.apply_card_filters()
    assert card["frame"].winfo_manager() == ""

    records["ETH"] = {
        "market_structure": _result(
            MarketStructureState.POTENTIAL_ACCUMULATION
        )
    }
    ui.apply_card_filters()
    assert card["frame"].winfo_manager() == "pack"
