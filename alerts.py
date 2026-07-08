import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from signal_quality import calculate_quality_score


ALERT_SETTINGS_PATH = Path("data") / "alert_settings.json"
ALERT_LOG_PATH = Path("logs") / "alerts.log"
ALERT_OLD_LOG_PATH = Path("logs") / "alerts_old.log"
ALERT_LOG_MAX_BYTES = 5 * 1024 * 1024
SECOND_ALERT_DELAY_SECONDS = 180
MAX_ALERTS_PER_SIGNAL = 2


@dataclass
class AlertSettings:
    alerts_enabled: bool = False
    minimum_quality: int = 80
    scan_range: str = "watchlist"
    bullish: bool = True
    bearish: bool = True
    active: bool = True
    aging: bool = False
    expired: bool = False
    sound_enabled: bool = True
    windows_notification_enabled: bool = True


class AlertLogWriter:

    def __init__(
        self,
        log_path=ALERT_LOG_PATH,
        old_log_path=ALERT_OLD_LOG_PATH,
        max_bytes=ALERT_LOG_MAX_BYTES
    ):

        self.log_path = Path(log_path)
        self.old_log_path = Path(old_log_path)
        self.max_bytes = max_bytes

    def write_block(self, lines):

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.rotate_if_needed()

        content = "\n".join([
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]",
            "",
            *lines,
            "",
            "----------------------------------------",
            ""
        ])

        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(content)

    def rotate_if_needed(self):

        if not self.log_path.exists():
            return

        if self.log_path.stat().st_size <= self.max_bytes:
            return

        if self.old_log_path.exists():
            self.old_log_path.unlink()

        self.log_path.replace(self.old_log_path)


class WindowsAlertNotifier:

    def __init__(self):

        self.notification_backend = None
        self.notification_unavailable_reason = None
        self.notification_backends = self._load_notification_backends()
        self.last_notification_status = False
        self.last_notification_reason = self.notification_unavailable_reason
        self.last_sound_status = False
        self.last_sound_reason = None

    def notifications_available(self):

        return bool(self.notification_backends)

    def diagnostic_status(self):

        return {
            "notification_ok": self.last_notification_status,
            "notification_reason": self.last_notification_reason,
            "sound_ok": self.last_sound_status,
            "sound_reason": self.last_sound_reason,
            "backend": self.notification_backend_name()
        }

    def notification_backend_name(self):

        notification_backend = getattr(self, "notification_backend", None)
        notification_backends = getattr(self, "notification_backends", [])

        if notification_backend is not None:
            return notification_backend[0]

        if notification_backends:
            return notification_backends[0][0]

        return "none"

    def notify(
        self,
        title,
        message,
        sound_enabled=True,
        notification_enabled=True,
        allow_sound_only=False
    ):

        notification_sent = False
        notification_reason = None
        sound_sent = False
        sound_reason = None
        notification_backend = self.notification_backend_name()

        if sound_enabled:
            sound_sent, sound_reason = self.play_sound()
            self.last_sound_status = sound_sent
            self.last_sound_reason = sound_reason

        if notification_enabled:
            notification_sent, notification_reason, notification_backend = self.show_notification(title, message)
            self.last_notification_status = notification_sent
            self.last_notification_reason = notification_reason
        else:
            self.last_notification_status = False
            self.last_notification_reason = "notification disabled"

        return {
            "notification_sent": notification_sent,
            "notification_reason": notification_reason,
            "sound_sent": sound_sent,
            "sound_reason": sound_reason,
            "backend": notification_backend
        }

    def play_sound(self):

        try:
            import winsound

            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                winsound.MessageBeep()
            return True, None
        except Exception as error:
            return False, str(error)

    def show_notification(self, title, message):

        if not self.notification_backends:
            return False, self.notification_unavailable_reason or "no notification backend available", "none"

        failures = []

        for backend, notifier in self.notification_backends:
            try:
                if backend == "plyer":
                    notifier.notify(title=title, message=message, app_name="SmartTrade", timeout=8)
                else:
                    notifier.show_toast(title, message, duration=8, threaded=True)

                self.notification_backend = backend, notifier
                return True, None, backend
            except Exception as error:
                failures.append(f"{backend}: {error}")

        return False, "; ".join(failures) or "notification backend failed", self.notification_backend_name()

    def _load_notification_backends(self):

        backends = []
        failures = []

        try:
            from plyer import notification

            backends.append(("plyer", notification))
        except Exception as error:
            failures.append(f"plyer: {error}")

        try:
            from win10toast import ToastNotifier

            backends.append(("win10toast", ToastNotifier()))
        except Exception as error:
            failures.append(f"win10toast: {error}")

        if not backends:
            self.notification_unavailable_reason = "; ".join(failures)

        return backends


class AlertManager:

    def __init__(
        self,
        settings_path=ALERT_SETTINGS_PATH,
        notifier=None,
        log_writer=None,
        default_timeframe="15",
        default_scan_range="watchlist"
    ):

        self.settings_path = Path(settings_path)
        self.notifier = notifier or WindowsAlertNotifier()
        self.log_writer = log_writer or AlertLogWriter()
        self.has_saved_settings = self.settings_path.exists()
        self.settings = self.load_settings(default_timeframe, default_scan_range)
        self.alert_records = {}

    def load_settings(self, default_timeframe="15", default_scan_range="watchlist"):

        settings = AlertSettings(
            scan_range=default_scan_range
        )

        if not self.settings_path.exists():
            return settings

        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            return settings

        for key, value in data.items():
            if key == "alerts_enabled":
                continue

            if hasattr(settings, key):
                setattr(settings, key, value)

        return settings

    def save_settings(self):

        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(asdict(self.settings), indent=2),
            encoding="utf-8"
        )
        self.has_saved_settings = True

    def update_settings(self, **changes):

        for key, value in changes.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)

        self.save_settings()

    def process_signal(
        self,
        symbol,
        timeframe,
        scan_range,
        divergence,
        status,
        age_text,
        quality_score=None,
        now=None
    ):

        if divergence is None:
            return False

        now = self.current_time(now)
        signal_id = build_signal_id(symbol, timeframe, divergence)
        record = self.alert_records.get(signal_id)

        if record is None:
            record = {
                "sent_count": 0,
                "opened": False,
                "second_due_at": None,
                "event": None
            }
            self.alert_records[signal_id] = record

        event = self.build_event(
            symbol,
            timeframe,
            scan_range,
            divergence,
            status,
            age_text,
            quality_score
        )
        record["event"] = event

        if record["sent_count"] > 0:
            return False

        passed_filters, _reason = self.evaluate_alert(event)

        if not passed_filters:
            return False

        self.send_alert(event)
        record["sent_count"] = 1
        record["second_due_at"] = now + SECOND_ALERT_DELAY_SECONDS
        return True

    def process_due_alerts(self, now=None):

        now = self.current_time(now)
        sent_count = 0

        for record in self.alert_records.values():
            if record["sent_count"] != 1:
                continue

            if record["opened"] or record["second_due_at"] is None:
                continue

            if now < record["second_due_at"]:
                continue

            event = record["event"]

            if event is not None and self.should_alert(event):
                self.send_alert(event)
                sent_count += 1

            record["sent_count"] = MAX_ALERTS_PER_SIGNAL
            record["second_due_at"] = None

        return sent_count

    def mark_opened_for_symbol(self, symbol):

        for record in self.alert_records.values():
            event = record.get("event")

            if event is not None and event["symbol"] == symbol:
                record["opened"] = True

    def should_alert(self, event):

        passed_filters, _reason = self.evaluate_alert(event)
        return passed_filters

    def evaluate_alert(self, event):

        settings = self.settings

        if not settings.alerts_enabled:
            return False, "alerts_disabled"

        if event["quality_score"] < settings.minimum_quality:
            return False, "quality_below_minimum"

        if event["scan_range"] != settings.scan_range:
            return False, "scan_range_mismatch"

        if event["type"] == "bullish" and not settings.bullish:
            return False, "bullish_disabled"

        if event["type"] == "bearish" and not settings.bearish:
            return False, "bearish_disabled"

        status_flags = {
            "ACTIVE": settings.active,
            "AGING": settings.aging,
            "EXPIRED": settings.expired
        }

        if not status_flags.get(event["status"], False):
            return False, "status_disabled"

        return True, None

    def build_event(
        self,
        symbol,
        timeframe,
        scan_range,
        divergence,
        status,
        age_text,
        quality_score=None
    ):

        score = quality_score

        if score is None:
            score = calculate_quality_score(divergence.get("quality"))

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "scan_range": scan_range,
            "type": divergence["type"],
            "status": status,
            "age_text": age_text,
            "quality_score": score
        }

    def send_alert(self, event):

        title = "SmartTrade Alert"
        message = "\n".join([
            event["symbol"],
            f"{event['type'].title()} Divergence",
            f"Q: {event['quality_score']}",
            f"TF: {timeframe_label(event['timeframe'])}",
            event["status"],
            event["age_text"]
        ])

        result = self.notifier.notify(
            title,
            message,
            sound_enabled=self.settings.sound_enabled,
            notification_enabled=self.settings.windows_notification_enabled,
            allow_sound_only=True
        )
        self.log_real_alert(event, result)
        return result

    def send_test_alert(self):

        return self.notifier.notify(
            "SmartTrade Test Alert",
            "\n".join([
                "BTCUSDT",
                "Bullish Divergence",
                "Q: 99",
                "TF: 15m",
                "ACTIVE"
            ]),
            sound_enabled=True,
            notification_enabled=True,
            allow_sound_only=True
        )

    def send_force_test_alert(self, timeframe):

        result = self.notifier.notify(
            "SmartTrade Test Alert",
            "\n".join([
                "BTCUSDT",
                "Bullish Divergence",
                "Quality: 99",
                f"TF: {timeframe_label(timeframe)}",
                "ACTIVE"
            ]),
            sound_enabled=True,
            notification_enabled=True,
            allow_sound_only=True
        )
        self.log_force_test(result)
        return result

    def log_force_test(self, result):

        reason = (
            result.get("notification_reason")
            or result.get("sound_reason")
            or ""
        )
        self.log_writer.write_block([
            "FORCE TEST",
            "",
            f"Sound: {'OK' if result.get('sound_sent') else 'FAILED'}",
            "",
            f"Notification: {'OK' if result.get('notification_sent') else 'FAILED'}",
            "",
            f"Backend: {result.get('backend') or 'none'}",
            "",
            f"Reason: {reason}"
        ])

    def log_real_alert(self, event, result):

        self.log_writer.write_block([
            "ALERT",
            "",
            event["symbol"],
            "",
            event["type"].title(),
            "",
            f"Quality: {event['quality_score']}",
            "",
            f"TF: {timeframe_label(event['timeframe'])}",
            "",
            f"Status: {event['status']}",
            "",
            f"Notification: {'OK' if result.get('notification_sent') else 'FAILED'}"
        ])

    def current_time(self, now=None):

        if now is not None:
            return now

        return time.monotonic()


def build_signal_id(symbol, timeframe, divergence):

    confirmed_index = divergence.get(
        "confirmed_index",
        divergence["price_end"]["index"]
    )
    confirmed_time = divergence.get(
        "confirmed_time",
        divergence["price_end"]["time"]
    )

    return "|".join([
        symbol,
        timeframe,
        divergence["type"],
        str(confirmed_index),
        str(confirmed_time)
    ])


def timeframe_label(timeframe):

    labels = {
        "1": "1m",
        "5": "5m",
        "15": "15m",
        "30": "30m",
        "60": "1H",
        "240": "4H",
        "D": "1D"
    }

    return labels.get(timeframe, timeframe)
