import json
import logging
import os
import shutil
import sys
import traceback
from pathlib import Path


APP_NAME = "SmartTrade"


DEFAULT_ALERT_SETTINGS = {
    "alerts_enabled": False,
    "minimum_quality": 80,
    "scan_range": "watchlist",
    "bullish": True,
    "bearish": True,
    "active": True,
    "aging": False,
    "expired": False,
    "sound_enabled": True,
    "windows_notification_enabled": True
}
DEFAULT_WATCHLIST = {
    "coins": []
}


def is_frozen():

    return bool(getattr(sys, "frozen", False))


def app_base_dir():

    if is_frozen():
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def resource_path(*parts):

    base = Path(getattr(sys, "_MEIPASS", app_base_dir()))
    return base.joinpath(*parts)


def user_data_dir():

    local_app_data = os.environ.get("LOCALAPPDATA")

    if local_app_data:
        return Path(local_app_data) / APP_NAME

    return Path.home() / f".{APP_NAME}"


def runtime_path(*parts):

    return user_data_dir().joinpath(*parts)


def ensure_runtime_environment():

    runtime_path("data").mkdir(parents=True, exist_ok=True)
    runtime_path("logs").mkdir(parents=True, exist_ok=True)
    _ensure_default_json("data", "alert_settings.json", DEFAULT_ALERT_SETTINGS)
    _ensure_default_json("data", "watchlist.json", DEFAULT_WATCHLIST, copy_existing=True)


def configure_https_certificates():

    try:
        import truststore

        truststore.inject_into_ssl()
        return
    except Exception:
        pass

    ca_bundle = resource_path("data", "windows_ca_bundle.pem")

    if not ca_bundle.exists():
        return

    os.environ.setdefault("REQUESTS_CA_BUNDLE", str(ca_bundle))
    os.environ.setdefault("SSL_CERT_FILE", str(ca_bundle))


def _ensure_default_json(folder, filename, default_data, copy_existing=False):

    target = runtime_path(folder, filename)

    if target.exists():
        return

    source = resource_path(folder, filename)

    if copy_existing and source.exists():
        shutil.copy2(source, target)
        return

    target.write_text(
        json.dumps(default_data, indent=2),
        encoding="utf-8"
    )


def configure_runtime_logging():

    log_path = runtime_path("logs", "startup.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    sys.excepthook = _log_uncaught_exception

    if is_frozen():
        sys.stdout = _LogStream(logging.getLogger("stdout"), logging.INFO)
        sys.stderr = _LogStream(logging.getLogger("stderr"), logging.ERROR)


def _log_uncaught_exception(exc_type, exc_value, exc_traceback):

    logging.critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )


def log_startup_exception(error):

    logging.critical("Startup failed: %s", error)
    logging.critical("%s", traceback.format_exc())


class _LogStream:

    def __init__(self, logger, level):

        self.logger = logger
        self.level = level
        self._buffer = ""

    def write(self, message):

        self._buffer += message

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                self.logger.log(self.level, line)

    def flush(self):

        if self._buffer.strip():
            self.logger.log(self.level, self._buffer.strip())

        self._buffer = ""
