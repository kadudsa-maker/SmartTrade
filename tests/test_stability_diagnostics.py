import logging
import threading

from diagnostics.stability import StabilityDiagnostics


class FakeRoot:
    def __init__(self):
        self.callbacks = {}
        self.cancelled = []
        self.sequence = 0

    def after(self, _delay, callback):
        self.sequence += 1
        after_id = f"after-{self.sequence}"
        self.callbacks[after_id] = callback
        return after_id

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)
        self.callbacks.pop(after_id, None)


def test_disabled_diagnostics_are_inert(tmp_path):
    diagnostics = StabilityDiagnostics(enabled=False, log_dir=tmp_path)
    with diagnostics.operation("scan"):
        pass
    diagnostics.attach_gui(FakeRoot())
    assert not list(tmp_path.iterdir())
    assert diagnostics.check_for_hang(now=100) is None


def test_environment_flag_enables_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setenv("ST_DIAGNOSTICS", "1")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    diagnostics = StabilityDiagnostics.from_environment()
    assert diagnostics.enabled is True
    diagnostics.close()


def test_enabled_diagnostics_record_operation_and_heartbeat(tmp_path):
    clock = iter([10.0, 10.0, 10.25, 10.25, 10.25])
    diagnostics = StabilityDiagnostics(
        enabled=True, log_dir=tmp_path, monotonic=lambda: next(clock)
    )
    with diagnostics.operation("fetch", symbol="BTCUSDT"):
        pass
    diagnostics.mark_heartbeat(12.0)
    diagnostics.close()
    log = (tmp_path / "stability.log").read_text(encoding="utf-8")
    assert "operation='fetch'" in log
    assert "symbol='BTCUSDT'" in log


def test_simulated_gui_hang_writes_bounded_snapshots(tmp_path):
    diagnostics = StabilityDiagnostics(
        enabled=True,
        log_dir=tmp_path,
        hang_threshold_seconds=5,
        snapshot_cooldown_seconds=10,
        max_snapshots=2,
        monotonic=lambda: 0.0,
    )
    diagnostics.mark_heartbeat(0)
    first = diagnostics.check_for_hang(now=6)
    assert first is not None and first.exists()
    assert "THREAD STACKS" in first.read_text(encoding="utf-8")
    assert diagnostics.check_for_hang(now=7) is None
    second = diagnostics.check_for_hang(now=17)
    assert second is not None and second.exists()
    assert diagnostics.check_for_hang(now=40) is None
    assert len(list(tmp_path.glob("hang_snapshot_*.txt"))) == 2
    diagnostics.close()


def test_snapshot_files_are_retained_with_a_fixed_limit(tmp_path):
    diagnostics = StabilityDiagnostics(
        enabled=True,
        log_dir=tmp_path,
        hang_threshold_seconds=1,
        snapshot_cooldown_seconds=0,
        max_snapshots=4,
        max_snapshot_files=2,
        monotonic=lambda: 0.0,
    )
    diagnostics.mark_heartbeat(0)
    for now in (2, 3, 4, 5):
        assert diagnostics.check_for_hang(now=now) is not None
    assert len(list(tmp_path.glob("hang_snapshot_*.txt"))) == 2
    diagnostics.close()


def test_watchdog_stops_and_cancels_heartbeat(tmp_path):
    root = FakeRoot()
    diagnostics = StabilityDiagnostics(
        enabled=True,
        log_dir=tmp_path,
        watchdog_interval_seconds=60,
    )
    diagnostics.attach_gui(root, lambda: {"scan_active": False})
    watchdog = diagnostics._watchdog_thread
    assert watchdog is not None and watchdog.is_alive()
    heartbeat_id = diagnostics._heartbeat_after_id
    diagnostics.close()
    assert heartbeat_id in root.cancelled
    assert not watchdog.is_alive()
    assert not any(
        thread.name == "SmartTradeStabilityWatchdog" and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_sensitive_fields_are_redacted(tmp_path):
    diagnostics = StabilityDiagnostics(enabled=True, log_dir=tmp_path)
    diagnostics.event("request", api_key="do-not-log", symbol="BTCUSDT")
    diagnostics.close()
    log = (tmp_path / "stability.log").read_text(encoding="utf-8")
    assert "do-not-log" not in log
    assert "<redacted>" in log


def test_log_is_rotating_and_bounded(tmp_path):
    diagnostics = StabilityDiagnostics(enabled=True, log_dir=tmp_path)
    handlers = diagnostics._logger.handlers
    assert len(handlers) == 1
    assert handlers[0].maxBytes == 1_000_000
    assert handlers[0].backupCount == 3
    diagnostics.close()
    assert not logging.getLogger(f"smarttrade.stability.{id(diagnostics)}").handlers
