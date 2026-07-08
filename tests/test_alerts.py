import json

from alerts import AlertLogWriter, AlertManager, WindowsAlertNotifier, build_signal_id
from ui import clamp_alert_quality


class FakeNotifier:

    def __init__(self):

        self.sent = []

    def notifications_available(self):

        return True

    def notify(
        self,
        title,
        message,
        sound_enabled=True,
        notification_enabled=True,
        allow_sound_only=False
    ):

        self.sent.append({
            "title": title,
            "message": message,
            "sound_enabled": sound_enabled,
            "notification_enabled": notification_enabled,
            "allow_sound_only": allow_sound_only
        })
        return {
            "notification_sent": notification_enabled,
            "notification_reason": None if notification_enabled else "notification disabled",
            "sound_sent": sound_enabled,
            "sound_reason": None if sound_enabled else "sound disabled",
            "backend": "plyer" if notification_enabled else "none"
        }


class FakeLogWriter:

    def __init__(self):

        self.blocks = []

    def write_block(self, lines):

        self.blocks.append(lines)


def test_alert_fires_for_quality_at_or_above_minimum(tmp_path):

    notifier = FakeNotifier()
    manager = create_manager(tmp_path, notifier)

    fired = manager.process_signal(
        "BTCUSDT",
        "15",
        "watchlist",
        sample_divergence(),
        "ACTIVE",
        "1 świeca temu",
        quality_score=80,
        now=100
    )

    assert fired is True
    assert len(notifier.sent) == 1
    assert "Q: 80" in notifier.sent[0]["message"]
    assert "TF: 15m" in notifier.sent[0]["message"]
    assert "ACTIVE" in notifier.sent[0]["message"]
    assert "1 świeca temu" in notifier.sent[0]["message"]


def test_alert_does_not_fire_below_minimum_quality(tmp_path):

    notifier = FakeNotifier()
    manager = create_manager(tmp_path, notifier)

    fired = manager.process_signal(
        "BTCUSDT",
        "15",
        "watchlist",
        sample_divergence(),
        "ACTIVE",
        "1 świeca temu",
        quality_score=79,
        now=100
    )

    assert fired is False
    assert notifier.sent == []


def test_test_alert_ignores_filters(tmp_path):

    notifier = FakeNotifier()
    manager = AlertManager(
        settings_path=tmp_path / "alert_settings.json",
        notifier=notifier,
        log_writer=FakeLogWriter(),
        default_timeframe="15",
        default_scan_range="watchlist"
    )
    manager.settings.alerts_enabled = False
    manager.settings.minimum_quality = 100
    manager.settings.scan_range = "top200"

    manager.send_test_alert()

    assert len(notifier.sent) == 1
    assert notifier.sent[0]["title"] == "SmartTrade Test Alert"
    assert "BTCUSDT" in notifier.sent[0]["message"]
    assert "Q: 99" in notifier.sent[0]["message"]


def test_force_test_alert_ignores_filters_and_uses_current_timeframe(tmp_path):

    notifier = FakeNotifier()
    manager = AlertManager(
        settings_path=tmp_path / "alert_settings.json",
        notifier=notifier,
        log_writer=FakeLogWriter(),
        default_timeframe="15",
        default_scan_range="watchlist"
    )
    manager.settings.alerts_enabled = False
    manager.settings.minimum_quality = 100
    manager.settings.scan_range = "top200"
    manager.settings.bullish = False
    manager.settings.active = False

    manager.send_force_test_alert("60")

    assert len(notifier.sent) == 1
    assert notifier.sent[0]["title"] == "SmartTrade Test Alert"
    assert "Quality: 99" in notifier.sent[0]["message"]
    assert "TF: 1H" in notifier.sent[0]["message"]


def test_alert_with_enabled_false_does_not_pass(tmp_path):

    notifier = FakeNotifier()
    manager = create_manager(tmp_path, notifier)
    manager.settings.alerts_enabled = False

    fired = manager.process_signal(
        "BTCUSDT",
        "15",
        "watchlist",
        sample_divergence(),
        "ACTIVE",
        "1 świeca temu",
        quality_score=90,
        now=100
    )

    assert fired is False
    assert notifier.sent == []


def test_alert_with_enabled_true_and_quality_above_minimum_passes(tmp_path):

    notifier = FakeNotifier()
    manager = create_manager(tmp_path, notifier)

    fired = manager.process_signal(
        "BTCUSDT",
        "15",
        "watchlist",
        sample_divergence(),
        "ACTIVE",
        "1 świeca temu",
        quality_score=90,
        now=100
    )

    assert fired is True
    assert len(notifier.sent) == 1


def test_alert_no_longer_filters_by_timeframe(tmp_path):

    notifier = FakeNotifier()
    manager = create_manager(tmp_path, notifier)

    fired = manager.process_signal(
        "BTCUSDT",
        "60",
        "watchlist",
        sample_divergence(),
        "ACTIVE",
        "1 świeca temu",
        quality_score=90,
        now=100
    )

    assert fired is True
    assert len(notifier.sent) == 1


def test_alert_with_wrong_scan_range_does_not_pass(tmp_path):

    notifier = FakeNotifier()
    manager = create_manager(tmp_path, notifier)

    fired = manager.process_signal(
        "BTCUSDT",
        "15",
        "top100",
        sample_divergence(),
        "ACTIVE",
        "1 świeca temu",
        quality_score=90,
        now=100
    )

    assert fired is False
    assert notifier.sent == []


def test_same_signal_id_does_not_fire_more_than_twice(tmp_path):

    notifier = FakeNotifier()
    manager = create_manager(tmp_path, notifier)

    for now in (100, 110, 120):
        manager.process_signal(
            "BTCUSDT",
            "15",
            "watchlist",
            sample_divergence(),
            "ACTIVE",
            "1 świeca temu",
            quality_score=90,
            now=now
        )

    manager.process_due_alerts(now=280)
    manager.process_due_alerts(now=500)

    assert len(notifier.sent) == 2


def test_second_alert_does_not_fire_if_signal_was_opened(tmp_path):

    notifier = FakeNotifier()
    manager = create_manager(tmp_path, notifier)

    manager.process_signal(
        "BTCUSDT",
        "15",
        "watchlist",
        sample_divergence(),
        "ACTIVE",
        "1 świeca temu",
        quality_score=90,
        now=100
    )
    manager.mark_opened_for_symbol("BTCUSDT")
    manager.process_due_alerts(now=280)

    assert len(notifier.sent) == 1


def test_signal_id_is_stable():

    divergence = sample_divergence()

    first_signal_id = build_signal_id("BTCUSDT", "15", divergence)
    second_signal_id = build_signal_id("BTCUSDT", "15", dict(divergence))

    assert first_signal_id == second_signal_id
    assert first_signal_id == "BTCUSDT|15|bullish|42|123456"


def test_alert_quality_is_clamped_for_settings():

    assert clamp_alert_quality("-1") == 0
    assert clamp_alert_quality("101") == 100
    assert clamp_alert_quality("80") == 80


def test_sound_only_plays_when_windows_notification_is_sent():

    notifier = SpyWindowsNotifier(notification_sent=True)

    notifier.notify(
        "SmartTrade Alert",
        "BTCUSDT\nBullish Divergence",
        sound_enabled=True,
        notification_enabled=True
    )

    assert notifier.notification_attempts == 1
    assert notifier.sound_count == 1


def test_sound_plays_before_windows_notification():

    notifier = OrderedWindowsNotifier(notification_sent=True)

    notifier.notify(
        "SmartTrade Alert",
        "BTCUSDT\nBullish Divergence",
        sound_enabled=True,
        notification_enabled=True
    )

    assert notifier.calls == ["sound", "notification"]


def test_sound_still_plays_without_windows_notification():

    notifier = SpyWindowsNotifier(notification_sent=False)

    notifier.notify(
        "SmartTrade Alert",
        "BTCUSDT\nBullish Divergence",
        sound_enabled=True,
        notification_enabled=True
    )
    notifier.notify(
        "SmartTrade Alert",
        "BTCUSDT\nBullish Divergence",
        sound_enabled=True,
        notification_enabled=False
    )

    assert notifier.notification_attempts == 1
    assert notifier.sound_count == 2


def test_notifier_fallback_does_not_crash_without_notification_backend():

    notifier = SpyWindowsNotifier(notification_sent=False)

    result = notifier.notify(
        "SmartTrade Alert",
        "BTCUSDT\nBullish Divergence",
        sound_enabled=True,
        notification_enabled=True,
        allow_sound_only=True
    )

    assert result["notification_sent"] is False
    assert result["sound_sent"] is True


def test_notification_status_reports_ok_and_not_available():

    ok_notifier = SpyWindowsNotifier(notification_sent=True)
    ok_notifier.notify(
        "SmartTrade Alert",
        "BTCUSDT",
        sound_enabled=True,
        notification_enabled=True
    )

    failed_notifier = SpyWindowsNotifier(notification_sent=False)
    failed_notifier.notify(
        "SmartTrade Alert",
        "BTCUSDT",
        sound_enabled=True,
        notification_enabled=True
    )

    assert ok_notifier.diagnostic_status()["notification_ok"] is True
    assert failed_notifier.diagnostic_status()["notification_ok"] is False
    assert failed_notifier.diagnostic_status()["notification_reason"] == "failed"


def test_force_test_writes_alert_log_file(tmp_path):

    notifier = FakeNotifier()
    manager = AlertManager(
        settings_path=tmp_path / "alert_settings.json",
        notifier=notifier,
        log_writer=AlertLogWriter(
            log_path=tmp_path / "logs" / "alerts.log",
            old_log_path=tmp_path / "logs" / "alerts_old.log"
        ),
        default_timeframe="15",
        default_scan_range="watchlist"
    )

    manager.send_force_test_alert("15")

    log_text = (tmp_path / "logs" / "alerts.log").read_text(encoding="utf-8")
    assert "FORCE TEST" in log_text
    assert "Sound: OK" in log_text
    assert "Notification: OK" in log_text
    assert "Backend: plyer" in log_text


def test_real_alert_writes_alert_log_file(tmp_path):

    notifier = FakeNotifier()
    manager = create_manager(tmp_path, notifier)

    manager.process_signal(
        "BTCUSDT",
        "15",
        "watchlist",
        sample_divergence(),
        "ACTIVE",
        "1 świeca temu",
        quality_score=91,
        now=100
    )

    assert manager.log_writer.blocks
    log_lines = "\n".join(manager.log_writer.blocks[0])
    assert "ALERT" in log_lines
    assert "BTCUSDT" in log_lines
    assert "Bullish" in log_lines
    assert "Quality: 91" in log_lines
    assert "TF: 15m" in log_lines
    assert "Notification: OK" in log_lines


def test_alert_logging_keeps_terminal_clean(tmp_path, capsys):

    notifier = FakeNotifier()
    manager = create_manager(tmp_path, notifier)

    manager.process_signal(
        "BTCUSDT",
        "15",
        "watchlist",
        sample_divergence(),
        "ACTIVE",
        "1 świeca temu",
        quality_score=91,
        now=100
    )
    manager.send_force_test_alert("15")

    captured = capsys.readouterr()
    assert captured.out == ""


def test_alert_log_rotates_above_max_size(tmp_path):

    log_path = tmp_path / "logs" / "alerts.log"
    old_log_path = tmp_path / "logs" / "alerts_old.log"
    log_path.parent.mkdir()
    log_path.write_text("x" * 20, encoding="utf-8")
    writer = AlertLogWriter(
        log_path=log_path,
        old_log_path=old_log_path,
        max_bytes=10
    )

    writer.write_block(["FORCE TEST"])

    assert old_log_path.exists()
    assert old_log_path.read_text(encoding="utf-8") == "x" * 20
    assert "FORCE TEST" in log_path.read_text(encoding="utf-8")


def test_saved_alerts_enabled_does_not_enable_alerts_on_startup(tmp_path):

    settings_path = tmp_path / "alert_settings.json"
    settings_path.write_text(
        json.dumps({
            "alerts_enabled": True,
            "minimum_quality": 72,
            "scan_range": "top100"
        }),
        encoding="utf-8"
    )

    manager = AlertManager(
        settings_path=settings_path,
        notifier=FakeNotifier(),
        log_writer=FakeLogWriter(),
        default_timeframe="60",
        default_scan_range="top100"
    )

    assert manager.settings.alerts_enabled is False
    assert manager.settings.minimum_quality == 72
    assert manager.settings.scan_range == "top100"


def create_manager(tmp_path, notifier):

    manager = AlertManager(
        settings_path=tmp_path / "alert_settings.json",
        notifier=notifier,
        log_writer=FakeLogWriter(),
        default_timeframe="15",
        default_scan_range="watchlist"
    )
    manager.settings.alerts_enabled = True
    manager.settings.minimum_quality = 80
    manager.settings.scan_range = "watchlist"
    manager.settings.active = True
    return manager


class SpyWindowsNotifier(WindowsAlertNotifier):

    def __init__(self, notification_sent):

        self.notification_sent = notification_sent
        self.notification_attempts = 0
        self.sound_count = 0
        self.last_notification_status = False
        self.last_notification_reason = None
        self.last_sound_status = False
        self.last_sound_reason = None

    def notifications_available(self):

        return True

    def show_notification(self, title, message):

        self.notification_attempts += 1
        backend = "plyer" if self.notification_sent else "none"
        return self.notification_sent, None if self.notification_sent else "failed", backend

    def play_sound(self):

        self.sound_count += 1
        return True, None


class OrderedWindowsNotifier(SpyWindowsNotifier):

    def __init__(self, notification_sent):

        super().__init__(notification_sent)
        self.calls = []

    def show_notification(self, title, message):

        self.calls.append("notification")
        return super().show_notification(title, message)

    def play_sound(self):

        self.calls.append("sound")
        return super().play_sound()


def sample_divergence():

    return {
        "type": "bullish",
        "confirmed_index": 42,
        "confirmed_time": 123456,
        "price_end": {
            "index": 42,
            "time": 123456
        },
        "quality": {
            "pivot": 90,
            "rsi": 90,
            "distance": 90,
            "volume": 90
        }
    }
