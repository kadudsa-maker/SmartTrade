import threading

from ui import SmartTradeUI


class FakeLabel:

    def __init__(self, text=""):
        self.options = {"text": text, "text_color": ""}

    def cget(self, option):
        return self.options.get(option)

    def configure(self, **options):
        self.options.update(options)


class FakeFrame:

    def __init__(self, mapped=True):
        self.manager = "pack" if mapped else ""
        self.pack_calls = 0
        self.pack_configure_calls = []
        self.pack_forget_calls = 0
        self.destroyed = False
        self.bindings = {}

    def winfo_manager(self):
        return self.manager

    def winfo_exists(self):
        return not self.destroyed

    def pack(self, **_options):
        self.manager = "pack"
        self.pack_calls += 1

    def pack_configure(self, **options):
        self.pack_configure_calls.append(options)

    def pack_forget(self):
        self.manager = ""
        self.pack_forget_calls += 1

    def destroy(self):
        self.manager = ""
        self.destroyed = True

    def bind(self, event_name, callback):
        self.bindings[event_name] = callback

    def winfo_children(self):
        return []


def make_card(symbol, mapped=True):
    return {
        "frame": FakeFrame(mapped),
        "position": FakeLabel(),
        "symbol": FakeLabel(symbol),
        "market": FakeLabel(),
        "status": FakeLabel(),
        "setup": FakeLabel(),
        "quality": FakeLabel(),
        "time": FakeLabel(),
        "age": FakeLabel(),
        "rsi": FakeLabel(),
        "symbol_value": symbol,
        "index": 0,
    }


def make_ui(*, top_mode=True, symbols=None):
    symbols = list(symbols or ["BTCUSDT"])
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    ui.active_exchange_id = "bybit"
    ui.current_scan_id = 7
    ui.current_scan_symbols = symbols
    ui.current_scan_results = {}
    ui.current_scan_rendered = 0
    ui.instrument_by_symbol = {}
    ui.active_scan_job_id = None
    ui.scan_worker_busy = False
    ui.refresh_index = 0
    ui.scan_batch_position = 0
    ui.last_scan_batch_time = None
    ui.scan_cycle_started_at = 1
    ui.scan_mode = "top200" if top_mode else "watchlist"
    ui.top_bybit_limit = 200
    ui.top50_symbols = symbols
    ui.top50_results = {}
    ui.buttons = []
    ui.cards_by_symbol = {}
    ui.top_card_pool = {}
    ui.last_card_texts = {}
    ui.watchlist_scroll = object()
    ui.is_top_bybit_mode = lambda: top_mode
    ui.get_scan_batch_size = lambda: 1
    ui.schedule_scan_loop = lambda *_args: None
    ui.sort_top50_cards_if_needed = lambda: None
    ui.mark_scan_cycle_completed = lambda *_args: None
    ui.process_alert_candidate = lambda *_args, **_kwargs: False
    ui.perf_log = lambda *_args, **_kwargs: None
    ui.create_watchlist_card = (
        lambda _parent, symbol, index, editable=False: {
            **make_card(symbol, mapped=False),
            "index": index,
        }
    )
    ui.update_watchlist_card = lambda *_args, **_kwargs: True
    return ui


def result(ui, symbol, index, status, *, scan_id=None, exchange_id="bybit"):
    record = ui.create_scan_result_record(
        ui.current_scan_id if scan_id is None else scan_id,
        symbol,
        index,
        status,
        exchange_id=exchange_id,
    )
    record.update({"rsi": 50, "candle_count": 100})
    if status == "error":
        record["error"] = "RuntimeError: scan failed"
    return record


def test_symbol_error_removes_existing_top_card_without_empty_space():
    ui = make_ui()
    card = make_card("BTCUSDT")
    ui.buttons = [card]
    ui.cards_by_symbol = {"BTCUSDT": card}
    ui.top50_results = {"BTCUSDT": {"symbol": "BTCUSDT"}}

    assert ui.apply_scan_result(result(ui, "BTCUSDT", 0, "error")) is True
    assert card["frame"].destroyed is True
    assert ui.buttons == []
    assert ui.cards_by_symbol == {}


def test_missing_candles_error_does_not_create_top_card():
    ui = make_ui()
    missing = result(ui, "BTCUSDT", 0, "error")
    missing["error"] = "ValueError: no candles"

    ui.apply_scan_result(missing)

    assert ui.buttons == []
    assert ui.cards_by_symbol == {}


def test_no_divergence_creates_filled_visible_card():
    ui = make_ui()

    ui.apply_scan_result(result(ui, "BTCUSDT", 0, "no_signal"))

    card = ui.cards_by_symbol["BTCUSDT"]
    assert card["frame"].winfo_manager() == "pack"
    assert card["frame"].destroyed is False


def test_filtered_signal_keeps_whole_card_visible():
    ui = make_ui()
    filtered = result(ui, "BTCUSDT", 0, "signal_found")
    filtered["divergence"] = {"type": "bullish", "quality": {"score": 10}}

    ui.apply_scan_result(filtered)

    assert ui.cards_by_symbol["BTCUSDT"]["frame"].winfo_manager() == "pack"


def test_stale_scan_result_does_not_create_card():
    ui = make_ui()

    assert ui.apply_scan_result(result(ui, "BTCUSDT", 0, "no_signal", scan_id=6)) is False
    assert ui.buttons == []
    assert ui.cards_by_symbol == {}


def test_foreign_exchange_result_does_not_create_card():
    ui = make_ui()

    foreign = result(ui, "BTCUSDT", 0, "no_signal", exchange_id="okx")
    assert ui.apply_scan_result(foreign) is False
    assert ui.buttons == []
    assert ui.cards_by_symbol == {}


def test_hiding_card_removes_entire_main_frame_from_pack_layout():
    ui = make_ui(top_mode=False)
    card = make_card("BTCUSDT")
    ui.buttons = [card]

    ui.hide_watchlist_card(card)

    assert card["frame"].pack_forget_calls == 1
    assert card["frame"].winfo_manager() == ""


def test_unchanged_card_visibility_does_not_refresh_all_positions():
    ui = make_ui(top_mode=False)
    visible = make_card("VISIBLE", mapped=True)
    hidden = make_card("HIDDEN", mapped=False)
    refresh_calls = []
    ui.refresh_card_positions = lambda: refresh_calls.append(True)

    assert ui.show_watchlist_card(visible) is False
    assert ui.hide_watchlist_card(hidden) is False

    assert refresh_calls == []
    assert visible["frame"].pack_calls == 0
    assert hidden["frame"].pack_forget_calls == 0


def test_numbering_has_no_gap_after_hidden_card():
    ui = make_ui(top_mode=False, symbols=["A", "B", "C"])
    first, hidden, third = make_card("A"), make_card("B"), make_card("C")
    ui.buttons = [first, hidden, third]

    ui.hide_watchlist_card(hidden)

    assert first["position"].cget("text") == "1"
    assert hidden["position"].cget("text") == ""
    assert third["position"].cget("text") == "2"


def test_top_sort_ignores_pending_and_removed_cards():
    ui = make_ui(symbols=["GOOD", "PENDING", "REMOVED"])
    good = make_card("GOOD")
    ui.buttons = [good]
    ui.cards_by_symbol = {"GOOD": good}
    ui.top50_results = {
        "GOOD": {"symbol": "GOOD", "rsi": 50, "divergence": None, "candle_count": 10}
    }
    ui.last_top50_sort_at = 0
    ui.last_top50_order = []

    ui.sort_top50_cards()

    assert ui.last_top50_order == ["GOOD"]
    assert [card["symbol_value"] for card in ui.buttons] == ["GOOD"]


def test_top_reorder_moves_only_displaced_cards_without_unmapping_or_rerendering():
    ui = make_ui(symbols=["A", "B", "C"])
    cards = [make_card(symbol) for symbol in ("A", "B", "C")]
    ui.buttons = cards
    ui.cards_by_symbol = {card["symbol_value"]: card for card in cards}
    ui.refresh_card_positions = lambda: None
    ui.update_watchlist_card = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("sorting must not render card contents again")
    )
    ui.apply_card_filters = lambda: (_ for _ in ()).throw(
        AssertionError("sorting must not reapply unchanged filters")
    )
    sorted_results = [{"symbol": symbol} for symbol in ("C", "A", "B")]

    ui.reorder_top50_cards(sorted_results)

    assert [card["symbol_value"] for card in ui.buttons] == ["C", "A", "B"]
    assert [card["index"] for card in ui.buttons] == [0, 1, 2]
    assert cards[2]["frame"].pack_configure_calls == [
        {"before": cards[0]["frame"]}
    ]
    assert sum(card["frame"].pack_forget_calls for card in cards) == 0
    assert sum(card["frame"].pack_calls for card in cards) == 0


def test_top_reorder_keeps_filtered_cards_unmapped():
    ui = make_ui(symbols=["A", "B", "C"])
    first = make_card("A")
    hidden = make_card("B", mapped=False)
    third = make_card("C")
    ui.buttons = [first, hidden, third]
    ui.cards_by_symbol = {
        card["symbol_value"]: card
        for card in ui.buttons
    }
    ui.refresh_card_positions = lambda: None

    ui.reorder_top50_cards([
        {"symbol": "B"},
        {"symbol": "C"},
        {"symbol": "A"},
    ])

    assert [card["symbol_value"] for card in ui.buttons] == ["B", "C", "A"]
    assert hidden["frame"].winfo_manager() == ""
    assert hidden["frame"].pack_calls == 0
    assert hidden["frame"].pack_configure_calls == []


def test_top200_with_errors_contains_only_successful_result_cards():
    ui = make_ui(symbols=["GOOD1", "BAD1", "GOOD2", "BAD2"])
    statuses = ["no_signal", "error", "signal_found", "error"]

    for index, (symbol, status) in enumerate(zip(ui.current_scan_symbols, statuses)):
        ui.apply_scan_result(result(ui, symbol, index, status))

    assert set(ui.cards_by_symbol) == {"GOOD1", "GOOD2"}
    assert all(card["frame"].winfo_manager() == "pack" for card in ui.buttons)


def test_scan_restart_rebuild_has_no_old_or_pending_top_cards():
    ui = make_ui(symbols=["NEW1", "NEW2"])
    old = make_card("OLD")
    ui.buttons = [old]
    ui.cards_by_symbol = {"OLD": old}
    ui.coins = [{"symbol": "NEW1"}, {"symbol": "NEW2"}]

    ui.clear_watchlist_cards()
    ui.build_watchlist_cards()

    assert old["frame"].destroyed is True
    assert ui.buttons == []
    assert ui.cards_by_symbol == {}


def test_top_rescan_stashes_cards_without_destroying_widgets():
    ui = make_ui(symbols=["A", "B"])
    cards = [make_card("A"), make_card("B")]
    ui.buttons = cards
    ui.cards_by_symbol = {card["symbol_value"]: card for card in cards}
    ui.last_card_texts = {"A": {"status": "old"}}

    ui.stash_top_result_cards()

    assert ui.buttons == []
    assert ui.cards_by_symbol == {}
    assert ui.top_card_pool == {"A": cards[0], "B": cards[1]}
    assert ui.last_card_texts == {}
    assert all(card["frame"].destroyed is False for card in cards)
    assert all(card["frame"].winfo_manager() == "" for card in cards)


def test_top_rescan_forgets_real_tk_frames_in_one_batch():
    ui = make_ui(symbols=["A", "B", "C"])

    class FakeTk:
        def __init__(self):
            self.calls = []

        def call(self, *args):
            self.calls.append(args)

    class TkFrame(FakeFrame):
        def __init__(self, tk, name):
            super().__init__()
            self.tk = tk
            self._w = name

        def pack_forget(self):
            raise AssertionError("batch-capable frames must use one Tcl call")

    tk_app = FakeTk()
    cards = [make_card(symbol) for symbol in ("A", "B", "C")]
    for index, card in enumerate(cards):
        card["frame"] = TkFrame(tk_app, f".card{index}")
    ui.buttons = cards
    ui.cards_by_symbol = {card["symbol_value"]: card for card in cards}

    ui.stash_top_result_cards()

    assert tk_app.calls == [
        ("pack", "forget", ".card0", ".card1", ".card2")
    ]
    assert ui.top_card_pool == {"A": cards[0], "B": cards[1], "C": cards[2]}


def test_first_new_result_reuses_stashed_top_card():
    ui = make_ui(symbols=["BTCUSDT"])
    card = make_card("BTCUSDT", mapped=False)
    ui.top_card_pool = {"BTCUSDT": card}
    ui.create_watchlist_card = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("a pooled card must be reused")
    )

    ui.apply_scan_result(result(ui, "BTCUSDT", 0, "no_signal"))

    assert ui.cards_by_symbol["BTCUSDT"] is card
    assert ui.buttons == [card]
    assert ui.top_card_pool == {}
    assert card["frame"].destroyed is False
    assert card["frame"].winfo_manager() == "pack"


def test_clear_watchlist_cards_destroys_active_and_pooled_cards_once():
    ui = make_ui(symbols=["ACTIVE", "POOLED"])
    active = make_card("ACTIVE")
    pooled = make_card("POOLED", mapped=False)
    ui.buttons = [active]
    ui.cards_by_symbol = {"ACTIVE": active}
    ui.top_card_pool = {"POOLED": pooled}

    ui.clear_watchlist_cards()

    assert active["frame"].destroyed is True
    assert pooled["frame"].destroyed is True
    assert ui.buttons == []
    assert ui.cards_by_symbol == {}
    assert ui.top_card_pool == {}


def test_timeframe_change_stashes_top_cards_instead_of_rebuilding_them():
    ui = make_ui(symbols=["A", "B"])
    cards = [make_card("A"), make_card("B")]
    ui.buttons = cards
    ui.cards_by_symbol = {card["symbol_value"]: card for card in cards}
    ui.selected_interval = "60"
    ui.cancel_scan_loop = lambda: None
    ui.clear_fvg_card_sections = lambda: None
    ui.clear_chart_fvg = lambda: None
    ui.reset_scan_cycle_state = lambda: None
    ui.update_timeframe_buttons = lambda: None
    ui.refresh_selected = lambda: None
    ui.begin_scan_generation = lambda: None
    ui.schedule_scan_loop = lambda *_args: None
    ui.build_watchlist_cards = lambda: (_ for _ in ()).throw(
        AssertionError("timeframe change must not rebuild top cards")
    )

    ui.select_timeframe("15")

    assert ui.selected_interval == "15"
    assert ui.buttons == []
    assert ui.cards_by_symbol == {}
    assert ui.top_card_pool == {"A": cards[0], "B": cards[1]}
    assert all(card["frame"].destroyed is False for card in cards)


def test_exchange_change_clears_previous_provider_cards_before_results():
    ui = make_ui(symbols=["BTC-USDT"])
    old = make_card("BTCUSDT")
    ui.buttons = [old]
    ui.cards_by_symbol = {"BTCUSDT": old}
    ui.coins = [{"symbol": "BTC-USDT"}]
    ui.active_exchange_id = "okx_spot"

    ui.clear_watchlist_cards()
    ui.build_watchlist_cards()

    assert old["frame"].destroyed is True
    assert ui.buttons == []
    assert ui.cards_by_symbol == {}
