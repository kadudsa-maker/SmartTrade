import copy
import inspect
from tkinter import TclError

import ui as ui_module
from ui import SmartTradeUI


class FakeLabel:

    def __init__(self, text=""):
        self.options = {"text": text}
        self.configure_calls = []

    def cget(self, option):
        return self.options.get(option)

    def configure(self, **options):
        self.configure_calls.append(options)
        self.options.update(options)


class FakeFrame:

    def __init__(self, managed=True, exists=True):
        self.managed = managed
        self.exists = exists

    def winfo_exists(self):
        return self.exists

    def winfo_manager(self):
        if not self.exists:
            raise TclError("widget was destroyed")
        return "pack" if self.managed else ""

    def pack(self, **_options):
        self.managed = True

    def destroy(self):
        self.exists = False
        self.managed = False


def make_card(symbol, managed=True, exists=True):
    return {
        "symbol_value": symbol,
        "frame": FakeFrame(managed, exists),
        "position": FakeLabel(),
        "symbol": FakeLabel(symbol),
        "quality": FakeLabel("Q:80"),
        "rsi": FakeLabel("RSI: 60"),
    }


def make_ui(cards):
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.buttons = cards
    return ui


def test_exchange_selector_is_built_once_in_left_controls_before_scan_and_watchlist():
    source = inspect.getsource(ui_module.SmartTradeUI)
    build_ui_source = inspect.getsource(ui_module.SmartTradeUI.build_ui)
    top_bar_source = inspect.getsource(ui_module.SmartTradeUI.build_top_bar)

    assert source.count("self.exchange_menu = ctk.CTkOptionMenu(") == 1
    assert "exchange_menu" not in top_bar_source
    assert build_ui_source.index("self.build_exchange_controls(left_controls)") < (
        build_ui_source.index("self.watchlist_title_label")
    )
    assert build_ui_source.index("self.build_exchange_controls(left_controls)") < (
        build_ui_source.index("self.build_scan_mode_controls(left_controls)")
    )


def test_card_position_label_is_part_of_identity_without_replacing_market_badge():
    source = inspect.getsource(ui_module.SmartTradeUI.create_watchlist_card)

    assert "identity_font_size = 14" in source
    assert "identity, str(index + 1), identity_font_size" in source
    assert "self.platform_market_name(symbol),\n            identity_font_size" in source
    assert 'position_label.configure(width=30, anchor="e")' in source
    assert '"position": position_label' in source
    assert '"market": market_label' in source


def test_positions_show_first_and_tenth_card_in_current_order():
    cards = [make_card(f"COIN{index}") for index in range(1, 11)]
    ui = make_ui(cards)

    ui.refresh_card_positions()

    assert cards[0]["position"].cget("text") == "1"
    assert cards[9]["position"].cget("text") == "10"


def test_four_visible_cards_have_continuous_positions():
    cards = [make_card(symbol) for symbol in ("A", "B", "C", "D")]
    ui = make_ui(cards)

    ui.refresh_card_positions()

    assert [card["position"].cget("text") for card in cards] == ["1", "2", "3", "4"]


def test_position_text_is_plain_for_one_two_and_three_digit_numbers():
    cards = [make_card(f"COIN{index}") for index in range(1, 201)]
    ui = make_ui(cards)

    ui.refresh_card_positions()

    assert {
        index: cards[index - 1]["position"].cget("text")
        for index in (9, 10, 99, 100, 200)
    } == {9: "9", 10: "10", 99: "99", 100: "100", 200: "200"}


def test_positions_follow_reorder_and_exchange_or_scan_replacement():
    btc = make_card("BTCUSDT")
    eth = make_card("ETHUSDT")
    ui = make_ui([btc, eth])
    ui.refresh_card_positions()

    ui.buttons = [eth, btc]
    ui.refresh_card_positions()
    assert eth["position"].cget("text") == "1"
    assert btc["position"].cget("text") == "2"

    okx = [make_card("BTC-USDT"), make_card("ETH-USDT")]
    ui.buttons = okx
    ui.refresh_card_positions()
    assert [card["position"].cget("text") for card in okx] == ["1", "2"]


def test_scan_rebuild_starts_positions_at_one():
    ui = make_ui([make_card("OLDUSDT")])
    rebuilt_cards = [make_card("BTCUSDT"), make_card("ETHUSDT")]
    ui.active_provider = lambda: type("Provider", (), {"display_name": "Bybit"})()
    ui.update_scan_status = lambda *_args: None
    ui.prepare_scan_queue_for_restart = lambda: True
    ui.cancel_scan_loop = lambda: None
    ui.reset_scan_state_for_new_run = lambda: None
    ui.begin_scan_generation = lambda: None
    ui.clear_watchlist_cards = lambda: setattr(ui, "buttons", [])
    ui.build_watchlist_cards = lambda: (
        setattr(ui, "buttons", rebuilt_cards) or ui.refresh_card_positions()
    )
    ui.update_scan_progress = lambda *_args: None
    ui.get_scan_symbols = lambda: ["BTCUSDT", "ETHUSDT"]
    ui.schedule_scan_loop = lambda *_args: None

    ui.scan_now()

    assert rebuilt_cards[0]["position"].cget("text") == "1"
    assert rebuilt_cards[1]["position"].cget("text") == "2"


def test_new_card_gets_next_position_and_hidden_cards_leave_no_gaps():
    first = make_card("BTCUSDT")
    hidden = make_card("HIDDENUSDT", managed=False)
    third = make_card("ETHUSDT")
    ui = make_ui([first, hidden, third])

    ui.refresh_card_positions()
    assert first["position"].cget("text") == "1"
    assert hidden["position"].cget("text") == ""
    assert third["position"].cget("text") == "2"

    added = make_card("SOLUSDT")
    ui.buttons.append(added)
    ui.refresh_card_positions()
    assert added["position"].cget("text") == "3"


def test_hidden_third_card_regression_is_numbered_one_through_four():
    cards = [make_card(f"COIN{index}") for index in range(1, 6)]
    cards[2]["frame"].managed = False
    ui = make_ui(cards)

    ui.refresh_card_positions()

    assert [
        card["position"].cget("text")
        for card in cards
        if card["frame"].managed
    ] == ["1", "2", "3", "4"]
    assert cards[2]["position"].cget("text") == ""


def test_missing_and_destroyed_widgets_do_not_increment_position_counter():
    first = make_card("FIRST")
    without_frame = make_card("NOFRAME")
    without_frame["frame"] = None
    destroyed = make_card("DESTROYED", exists=False)
    last = make_card("LAST")
    ui = make_ui([first, without_frame, destroyed, last])

    ui.refresh_card_positions()

    assert first["position"].cget("text") == "1"
    assert destroyed["position"].cget("text") == ""
    assert last["position"].cget("text") == "2"


def test_removing_third_card_leaves_no_position_gap():
    cards = [make_card(symbol) for symbol in ("A", "B", "C", "D")]
    ui = make_ui(cards)
    ui.refresh_card_positions()

    ui.buttons.remove(cards[2])
    ui.refresh_card_positions()

    assert [card["position"].cget("text") for card in ui.buttons] == ["1", "2", "3"]


def test_top_build_uses_visible_card_index_after_skipped_result():
    ui = make_ui([])
    ui.watchlist_scroll = object()
    ui.coins = [{"symbol": symbol} for symbol in ("A", "B", "C", "D", "E")]
    ui.scan_mode = "top200"
    ui.cards_by_symbol = {}
    ui.last_card_texts = {}
    ui.top50_results = {
        symbol: {"symbol": symbol, "rsi": 50, "divergence": None, "candle_count": 10}
        for symbol in ("A", "B", "D", "E")
    }
    ui.is_top_bybit_mode = lambda: True
    created_indexes = []

    def create_card(_parent, symbol, index, editable=False):
        created_indexes.append(index)
        return make_card(symbol)

    ui.create_watchlist_card = create_card
    ui.update_watchlist_card = lambda *_args, **_kwargs: True
    ui.refresh_card_positions = lambda: None

    ui.build_watchlist_cards()

    assert created_indexes == [0, 1, 2, 3]


def test_position_refresh_changes_only_position_text():
    cards = [make_card("BTCUSDT"), make_card("ETHUSDT")]
    ui = make_ui(cards)
    identity_and_metrics_before = [
        copy.deepcopy({
            key: card[key].options
            for key in ("symbol", "quality", "rsi")
        })
        for card in cards
    ]
    ui.build_watchlist_cards = lambda: (_ for _ in ()).throw(
        AssertionError("cards must not be rebuilt")
    )
    ui.scan_one_coin = lambda: (_ for _ in ()).throw(
        AssertionError("data must not be fetched")
    )

    ui.refresh_card_positions()

    assert [
        {key: card[key].options for key in ("symbol", "quality", "rsi")}
        for card in cards
    ] == identity_and_metrics_before
    assert all(not card["symbol"].configure_calls for card in cards)
    assert all(not card["quality"].configure_calls for card in cards)
    assert all(not card["rsi"].configure_calls for card in cards)
