from ui import SmartTradeUI


class FakeLabel:

    def __init__(self, text=""):
        self.options = {
            "text": text,
            "text_color": ""
        }

    def cget(self, option):
        return self.options.get(option)

    def configure(self, **options):
        self.options.update(options)


class FakeFrame:

    def __init__(self):
        self.bindings = {}

    def bind(self, event_name, callback):
        self.bindings[event_name] = callback

    def winfo_children(self):
        return []

    def winfo_exists(self):
        return True


class FakeAlertManager:

    def __init__(self):
        self.calls = []

    def process_signal(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return True


def build_ui_shell():

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.cards_by_symbol = {}
    ui.buttons = []
    ui.last_card_texts = {}
    ui.selected_interval = "15"
    ui.scan_mode = "top200"
    ui.top_bybit_limit = 200
    ui.current_scan_id = "top200-15-1"
    ui.current_scan_symbols = []
    ui.current_scan_results = {}
    ui.current_scan_rendered = 0
    ui.scan_cycle_alert_sent_count = 0
    ui.alert_manager = FakeAlertManager()
    ui.update_alert_status_labels = lambda: None
    return ui


def sample_divergence(score=85):

    return {
        "type": "bullish",
        "price_start": {"index": 10, "time": 1},
        "price_end": {"index": 20, "time": 2},
        "rsi_start": {"index": 10, "time": 1},
        "rsi_end": {"index": 20, "time": 2},
        "confirmed_index": 21,
        "confirmed_time": 2,
        "quality": {"score": score}
    }


def test_alert_candidate_is_skipped_without_clickable_card():

    ui = build_ui_shell()

    sent = ui.process_alert_candidate(
        "BTCUSDT",
        sample_divergence(),
        candle_count=22,
        ui_ready=False
    )

    assert sent is False
    assert ui.alert_manager.calls == []


def test_watchlist_card_update_verifies_clickable_card():

    ui = build_ui_shell()
    frame = FakeFrame()
    card = {
        "frame": frame,
        "symbol": FakeLabel("BTCUSDT"),
        "status": FakeLabel(),
        "setup": FakeLabel(),
        "time": FakeLabel(),
        "age": FakeLabel(),
        "rsi": FakeLabel(),
        "symbol_value": "BTCUSDT"
    }
    ui.buttons = [card]
    ui.cards_by_symbol = {"BTCUSDT": card}

    assert ui.update_watchlist_card(0, "BTCUSDT", 50, None, 0) is True
    assert "<Button-1>" in frame.bindings


def test_top_scan_ranking_sorts_visible_signals_by_quality():

    ui = build_ui_shell()
    ui.current_scan_symbols = ["LOWUSDT", "HIGHUSDT", "NONEUSDT"]
    ui.current_scan_results = {
        "LOWUSDT": {
            **ui.create_scan_result_record(ui.current_scan_id, "LOWUSDT", 0, "signal_found"),
            "divergence": sample_divergence(70),
            "quality": 70,
            "candle_count": 22
        },
        "HIGHUSDT": {
            **ui.create_scan_result_record(ui.current_scan_id, "HIGHUSDT", 1, "signal_found"),
            "divergence": sample_divergence(95),
            "quality": 95,
            "candle_count": 22
        },
        "NONEUSDT": ui.create_scan_result_record(
            ui.current_scan_id,
            "NONEUSDT",
            2,
            "no_signal"
        )
    }

    ranking = ui.build_top_scan_ranking()

    assert [result["symbol"] for result in ranking] == [
        "HIGHUSDT",
        "LOWUSDT",
        "NONEUSDT"
    ]


def test_top_alerts_skip_hidden_quality_signal():

    ui = build_ui_shell()
    hidden = {
        **ui.create_scan_result_record(ui.current_scan_id, "LOWUSDT", 0, "signal_found"),
        "divergence": sample_divergence(10),
        "quality": 10,
        "signal_key": "LOWUSDT|15|hidden",
        "candle_count": 22,
        "ui_visible": True
    }

    ui.process_visible_top_alerts([hidden])

    assert ui.alert_manager.calls == []
    assert ui.scan_cycle_alert_sent_count == 0
