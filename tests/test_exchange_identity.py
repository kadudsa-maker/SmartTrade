import threading
from pathlib import Path
from queue import Queue

import pytest

import ui as ui_module
from alerts import build_signal_id
from exchange_providers import ExchangeSymbol
from ui import DEFAULT_EXCHANGE_ID, EXCHANGE_OPTIONS, SmartTradeUI


def test_private_okx_credentials_surface_is_completely_removed():
    source = Path(ui_module.__file__).read_text(encoding="utf-8")
    assert not hasattr(SmartTradeUI, "open_okx_api_settings")
    assert "API Key" not in source
    assert "Secret Key" not in source
    assert "Passphrase" not in source
    assert "account/instruments" not in source
    assert not (Path(ui_module.__file__).parent / "okx_credentials.py").exists()


def sample_divergence():
    return {
        "type": "bullish",
        "price_end": {"index": 42, "time": 123456},
        "confirmed_index": 42,
        "confirmed_time": 123456,
    }


def test_default_exchange_is_bybit():
    assert DEFAULT_EXCHANGE_ID == "bybit"
    assert EXCHANGE_OPTIONS == {
        "Bybit Futures": "bybit",
        "OKX Perpetual": "okx",
        "OKX Spot": "okx_spot",
    }


@pytest.mark.parametrize(
    ("exchange_id", "badge"),
    [("bybit", "BYBIT"), ("okx", "OKX PERP"), ("okx_spot", "SPOT")],
)
def test_cards_show_independent_market_badges(exchange_id, badge):
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.active_exchange_id = exchange_id
    assert ui.market_badge() == badge


def test_alert_signal_identity_separates_exchanges():
    divergence = sample_divergence()
    assert build_signal_id("BTCUSDT", "60", divergence, "bybit") != build_signal_id(
        "BTC-USDT-SWAP", "60", divergence, "okx"
    )
    assert build_signal_id("BTC-USDT", "60", divergence, "okx_spot") != build_signal_id(
        "BTC-USDT-SWAP", "60", divergence, "okx"
    )


def test_spot_and_xperp_keep_distinct_exchange_identity():
    spot = ExchangeSymbol(
        "okx_spot", "UNI-USDT", "UNIUSDT", "UNI", "USDT", "spot", "live"
    )
    perpetual = ExchangeSymbol(
        "okx", "UNI-USD_UM_XPERP-310404", "UNIUSD", "UNI", "USD", "futures", "live"
    )
    assert spot.base_currency == perpetual.base_currency
    assert spot.exchange_symbol != perpetual.exchange_symbol
    assert spot.exchange_id != perpetual.exchange_id


def test_scan_record_preserves_exchange_and_presentation_identity():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    instrument = ExchangeSymbol(
        "okx", "UNI-USD_UM_XPERP-310404", "UNIUSD", "UNI", "USD", "futures", "live",
        {"instrument_scope": "public_eea", "ruleType": "xperp"},
        platform_market_name="UNIUSD UM",
        asset_class="crypto",
    )
    ui.active_exchange_id = "okx"
    ui.instrument_by_symbol = {instrument.exchange_symbol: instrument}
    result = ui.create_scan_result_record(2, instrument.exchange_symbol, 0, "pending")
    assert result["exchange_id"] == "okx"
    assert result["exchange_symbol"] == "UNI-USD_UM_XPERP-310404"
    assert result["display_symbol"] == "UNIUSD"
    assert result["platform_market_name"] == "UNIUSD UM"
    assert result["asset_class"] == "crypto"
    assert result["market_label"] == "OKX Perpetual"


def test_active_watchlist_filter_uses_final_market_identity():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    perpetual = FakeProvider(exchange_id="okx").get_instruments()[0]
    ui.active_exchange_id = "okx"
    ui.instrument_by_symbol = {perpetual.exchange_symbol: perpetual}
    assert ui.filter_provider_symbols(["BTC-USDT", "BTC-USD_UM_XPERP-310404"]) == [
        "BTC-USD_UM_XPERP-310404"
    ]
    assert ui.platform_market_name("BTC-USD_UM_XPERP-310404") == "BTCUSD UM"
    assert ui.market_badge("BTC-USD_UM_XPERP-310404") == "OKX PERP · CRYPTO"


class FakeLabel:
    def __init__(self):
        self.options = {"text": "", "text_color": ""}

    def cget(self, key):
        return self.options.get(key)

    def configure(self, **options):
        self.options.update(options)


def test_open_chart_status_includes_xperp_asset_class():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    instrument = FakeProvider(exchange_id="okx").get_instruments()[0]
    ui.active_exchange_id = "okx"
    ui.selected_symbol = instrument.exchange_symbol
    ui.instrument_by_symbol = {instrument.exchange_symbol: instrument}
    ui.open_chart_label = FakeLabel()
    ui.update_open_chart_status(None)
    assert ui.open_chart_label.cget("text") == (
        "Open: BTCUSD UM · OKX Perpetual · CRYPTO"
    )


def test_scan_result_from_wrong_exchange_is_rejected():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    ui.active_exchange_id = "okx"
    ui.current_scan_id = 8
    ui.active_scan_job_id = None
    ui.scan_worker_busy = False
    ui.schedule_scan_loop = lambda *_args: None
    result = ui.create_scan_result_record(
        8, "BTCUSDT", 0, "no_signal", exchange_id="bybit"
    )
    assert ui.apply_scan_result(result) is False


class FakeProvider:
    def __init__(self, error=None, exchange_id="okx"):
        self.error = error
        self.exchange_id = exchange_id
        self.display_name = "OKX Spot" if exchange_id == "okx_spot" else "OKX Perpetual"

    def get_instruments(self, force=False):
        if self.error:
            raise self.error
        is_spot = self.exchange_id == "okx_spot"
        return [ExchangeSymbol(
            self.exchange_id,
            "BTC-USDT" if is_spot else "BTC-USD_UM_XPERP-310404",
            "BTCUSDT" if is_spot else "BTCUSD", "BTC", "USDT" if is_spot else "USD",
            "spot" if is_spot else "futures", "live",
            {"instrument_scope": "public" if is_spot else "public_eea",
             "ruleType": "normal" if is_spot else "xperp"},
            platform_market_name="BTCUSDT" if is_spot else "BTCUSD UM",
            asset_class="crypto",
        )]

    def get_top_symbols(self, limit):
        return self.get_instruments()


class FakeMenu:
    def __init__(self):
        self.value = None
        self.state = "normal"

    def set(self, value):
        self.value = value

    def configure(self, **options):
        self.state = options.get("state", self.state)


def build_switch_ui():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.active_exchange_id = "bybit"
    ui.instrument_by_symbol = {}
    ui.scan_mode = "top100"
    ui.top_bybit_limit = 100
    ui.selected_interval = "60"
    ui.rsi_sort_mode = "rsi"
    ui.selected_symbol = "BTCUSDT"
    ui.exchange_menu = FakeMenu()
    ui.scan_generation = 4
    ui.current_scan_id = 4
    ui.scan_result_queue = Queue()
    ui.active_scan_job_id = None
    ui.scan_worker_busy = False
    ui.scan_worker_thread = object()
    ui.coins = [{"symbol": "BTCUSDT"}]
    ui.buttons = [object()]
    ui.cancel_scan_loop = lambda: None
    ui.reset_scan_state_for_new_run = lambda: None
    ui.clear_watchlist_cards = lambda: ui.buttons.clear()
    ui.build_watchlist_cards = lambda: None
    ui.update_scan_mode_buttons = lambda: None
    ui.update_open_chart_status = lambda *_args: None
    ui.update_scan_status = lambda *_args: None
    ui.update_scan_progress = lambda *_args: None
    ui.schedule_scan_loop = lambda *_args: None
    return ui


def test_successful_exchange_switch_increments_scan_id_and_keeps_one_worker(monkeypatch):
    ui = build_switch_ui()
    worker = ui.scan_worker_thread
    monkeypatch.setattr(ui_module, "get_exchange_provider", lambda _exchange: FakeProvider())

    assert ui.select_exchange("OKX Perpetual") is True
    assert ui.active_exchange_id == "okx"
    assert ui.current_scan_id == 5
    assert ui.current_scan_symbols == ["BTC-USD_UM_XPERP-310404"]
    assert ui.buttons == []
    assert ui.scan_worker_thread is worker
    assert ui.selected_interval == "60"
    assert ui.rsi_sort_mode == "rsi"


def test_failed_exchange_switch_keeps_previous_exchange_cards_and_scan(monkeypatch):
    ui = build_switch_ui()
    errors = []
    monkeypatch.setattr(
        ui_module, "get_exchange_provider",
        lambda _exchange: FakeProvider(RuntimeError("SSL failed"))
    )
    monkeypatch.setattr(
        ui_module.messagebox, "showerror", lambda _title, message: errors.append(message)
    )

    assert ui.select_exchange("OKX Perpetual") is False
    assert ui.active_exchange_id == "bybit"
    assert ui.current_scan_id == 4
    assert ui.coins == [{"symbol": "BTCUSDT"}]
    assert len(ui.buttons) == 1
    assert "SSL failed" in errors[0]


def test_spot_to_perpetual_switch_removes_old_symbol_mappings(monkeypatch):
    ui = build_switch_ui()
    old_spot = FakeProvider(exchange_id="okx_spot").get_instruments()[0]
    ui.active_exchange_id = "okx_spot"
    ui.instrument_by_symbol = {old_spot.exchange_symbol: old_spot}
    ui.current_scan_results = {old_spot.exchange_symbol: {"status": "old"}}
    monkeypatch.setattr(
        ui_module, "get_exchange_provider", lambda target: FakeProvider(exchange_id=target)
    )
    assert ui.select_exchange("OKX Perpetual") is True
    assert "BTC-USDT" not in ui.instrument_by_symbol
    assert set(ui.instrument_by_symbol) == {"BTC-USD_UM_XPERP-310404"}
    assert ui.current_scan_results == {}


def test_late_spot_result_is_rejected_after_switch_to_perpetual():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    perpetual = FakeProvider(exchange_id="okx").get_instruments()[0]
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    ui.active_exchange_id = "okx"
    ui.current_scan_id = 10
    ui.current_scan_symbols = [perpetual.exchange_symbol]
    ui.instrument_by_symbol = {perpetual.exchange_symbol: perpetual}
    ui.active_scan_job_id = None
    ui.scan_worker_busy = False
    ui.schedule_scan_loop = lambda *_args: None
    stale = ui.create_scan_result_record(
        10, "BTC-USDT", 0, "no_signal", exchange_id="okx_spot",
        display_symbol="BTCUSDT", market_label="OKX SPOT"
    )
    assert ui.apply_scan_result(stale) is False


@pytest.mark.parametrize(
    ("option", "exchange_id", "symbol"),
    [
        ("OKX Perpetual", "okx", "BTC-USD_UM_XPERP-310404"),
        ("OKX Spot", "okx_spot", "BTC-USDT"),
    ],
)
def test_worker_context_switches_independently_to_each_okx_provider(
    monkeypatch, option, exchange_id, symbol
):
    ui = build_switch_ui()
    monkeypatch.setattr(
        ui_module, "get_exchange_provider", lambda target: FakeProvider(exchange_id=target)
    )
    assert ui.select_exchange(option) is True
    assert ui.active_exchange_id == exchange_id
    assert ui.current_scan_symbols == [symbol]
    result = ui.create_scan_result_record(
        ui.current_scan_id, symbol, 0, "no_signal", exchange_id=exchange_id
    )
    assert result["exchange_id"] == exchange_id


def test_chart_fetch_uses_active_card_provider(monkeypatch):
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.active_exchange_id = "okx_spot"
    calls = []
    monkeypatch.setattr(
        ui_module,
        "get_klines",
        lambda symbol, interval, exchange_id: calls.append((symbol, interval, exchange_id)) or object(),
    )
    ui.fetch_klines("BTC-USDT", "60")
    assert calls == [("BTC-USDT", "60", "okx_spot")]
