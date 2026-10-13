import json
import logging
import os
import shutil
import sys
import threading
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


APP_NAME = "SmartTrade"
WINDOWS_APP_USER_MODEL_ID = "SmartTrade.SmartTrade"
STARTUP_LOG_MAX_BYTES = 5 * 1024 * 1024
STARTUP_LOG_BACKUP_COUNT = 3


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


def configure_windows_app_identity():

    if sys.platform != "win32":
        return

    import ctypes

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    set_app_id = shell32.SetCurrentProcessExplicitAppUserModelID
    set_app_id.argtypes = [ctypes.c_wchar_p]
    set_app_id.restype = ctypes.c_long

    result = set_app_id(WINDOWS_APP_USER_MODEL_ID)
    if result != 0:
        raise OSError(f"SetCurrentProcessExplicitAppUserModelID failed: 0x{result & 0xFFFFFFFF:08X}")


def configure_windows_window_icon(window):

    if sys.platform != "win32":
        return

    import ctypes

    icon_path = str(resource_path("SmartTrade.ico"))
    window.iconbitmap(default=icon_path)

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    load_image = user32.LoadImageW
    load_image.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_uint,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint
    ]
    load_image.restype = ctypes.c_void_p

    send_message = user32.SendMessageW
    send_message.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    send_message.restype = ctypes.c_void_p

    destroy_icon = user32.DestroyIcon
    destroy_icon.argtypes = [ctypes.c_void_p]
    destroy_icon.restype = ctypes.c_bool

    get_ancestor = user32.GetAncestor
    get_ancestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    get_ancestor.restype = ctypes.c_void_p

    big_icon = load_image(None, icon_path, 1, 32, 32, 0x0010)
    small_icon = load_image(None, icon_path, 1, 16, 16, 0x0010)
    if not big_icon or not small_icon:
        if big_icon:
            destroy_icon(big_icon)
        if small_icon:
            destroy_icon(small_icon)
        raise ctypes.WinError(ctypes.get_last_error())

    window_handle = get_ancestor(window.winfo_id(), 2)
    if not window_handle:
        window_handle = window.winfo_id()
    send_message(window_handle, 0x0080, 1, big_icon)
    send_message(window_handle, 0x0080, 0, small_icon)

    previous_icons = getattr(window, "_smarttrade_icon_handles", ())
    window._smarttrade_icon_handles = (big_icon, small_icon)
    for previous_icon in previous_icons:
        destroy_icon(previous_icon)


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


def configure_runtime_logging(
    log_path=None,
    *,
    max_bytes=STARTUP_LOG_MAX_BYTES,
    backup_count=STARTUP_LOG_BACKUP_COUNT,
    redirect_streams=None,
):

    log_path = Path(log_path) if log_path is not None else runtime_path("logs", "startup.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path, preserved_path = _prepare_startup_log(log_path, max_bytes)

    handler = _SafeRotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handler._smarttrade_runtime_handler = True

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    handler._smarttrade_previous_excepthook = sys.excepthook
    sys.excepthook = _log_uncaught_exception

    if redirect_streams is None:
        redirect_streams = is_frozen()
    if redirect_streams:
        stdout_stream = _LogStream(
            logging.getLogger("stdout"), logging.INFO, original_stream=sys.stdout
        )
        stderr_stream = _LogStream(
            logging.getLogger("stderr"), logging.ERROR, original_stream=sys.stderr
        )
        handler._smarttrade_redirected_streams = (stdout_stream, stderr_stream)
        sys.stdout = stdout_stream
        sys.stderr = stderr_stream

    if preserved_path is not None:
        logging.getLogger(__name__).info(
            "Preserved oversized startup log as %s", preserved_path
        )

    return handler


def close_runtime_logging(handler):

    redirected_streams = getattr(handler, "_smarttrade_redirected_streams", ())
    for stream in redirected_streams:
        stream.flush()

    if len(redirected_streams) == 2:
        stdout_stream, stderr_stream = redirected_streams
        if sys.stdout is stdout_stream:
            sys.stdout = stdout_stream.original_stream
        if sys.stderr is stderr_stream:
            sys.stderr = stderr_stream.original_stream

    if sys.excepthook is _log_uncaught_exception:
        sys.excepthook = getattr(
            handler, "_smarttrade_previous_excepthook", sys.__excepthook__
        )

    root_logger = logging.getLogger()
    root_logger.removeHandler(handler)
    handler.flush()
    handler.close()


def _prepare_startup_log(log_path, max_bytes):

    try:
        if not log_path.exists() or log_path.stat().st_size <= max_bytes:
            return log_path, None

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        candidate = log_path.with_name(
            f"{log_path.stem}.legacy-{timestamp}{log_path.suffix}"
        )
        counter = 1
        while candidate.exists():
            candidate = log_path.with_name(
                f"{log_path.stem}.legacy-{timestamp}-{counter}{log_path.suffix}"
            )
            counter += 1

        log_path.rename(candidate)
        return log_path, candidate
    except OSError as error:
        fallback = log_path.with_name(
            f"{log_path.stem}.{os.getpid()}{log_path.suffix}"
        )
        _write_logging_failure(
            f"Could not preserve active startup log {log_path}; "
            f"using {fallback}: {type(error).__name__}: {error}"
        )
        return fallback, None


def _log_uncaught_exception(exc_type, exc_value, exc_traceback):

    logging.critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )


def log_startup_exception(error):

    logging.critical("Startup failed: %s", error)
    logging.critical("%s", traceback.format_exc())


class _LogStream:

    def __init__(self, logger, level, original_stream=None):

        self.logger = logger
        self.level = level
        self.original_stream = original_stream
        self._buffer = ""
        self._lock = threading.RLock()

    def write(self, message):

        if not isinstance(message, str):
            message = str(message)

        with self._lock:
            self._buffer += message

            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line.strip():
                    self.logger.log(self.level, line)

        return len(message)

    def flush(self):

        with self._lock:
            if self._buffer.strip():
                self.logger.log(self.level, self._buffer.strip())

            self._buffer = ""

    def isatty(self):

        return False

    @property
    def encoding(self):

        return getattr(self.original_stream, "encoding", "utf-8")


class _SafeRotatingFileHandler(RotatingFileHandler):

    def handleError(self, record):

        _write_logging_failure(
            f"Could not write SmartTrade log record from {record.name}",
            include_exception=True,
        )


def _write_logging_failure(message, include_exception=False):

    stream = getattr(sys, "__stderr__", None)
    if stream is None:
        return

    try:
        stream.write(f"SmartTrade logging error: {message}\n")
        if include_exception:
            traceback.print_exception(*sys.exc_info(), file=stream)
        stream.flush()
    except Exception:
        pass
