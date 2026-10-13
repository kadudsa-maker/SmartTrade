"""Opt-in stability diagnostics with a GUI heartbeat watchdog.

The module uses only the Python standard library and remains inert unless
``ST_DIAGNOSTICS=1`` is present in the environment.
"""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
import time
import traceback

from app_paths import runtime_path


_TRUE_VALUES = {"1", "true", "yes", "on"}
_REDACTED_KEYS = {"api_key", "api_secret", "authorization", "secret", "token"}


def _environment_enabled():
    return os.environ.get("ST_DIAGNOSTICS", "").strip().lower() in _TRUE_VALUES


class StabilityDiagnostics:
    """Bounded diagnostic recorder and independent GUI-hang watchdog."""

    def __init__(
        self,
        *,
        enabled=False,
        log_dir=None,
        hang_threshold_seconds=5.0,
        snapshot_cooldown_seconds=60.0,
        max_snapshots=5,
        max_snapshot_files=10,
        heartbeat_interval_ms=1000,
        watchdog_interval_seconds=1.0,
        monotonic=time.monotonic,
    ):
        self.enabled = bool(enabled)
        self.log_dir = Path(log_dir or runtime_path("logs", "stability"))
        self.hang_threshold_seconds = float(hang_threshold_seconds)
        self.snapshot_cooldown_seconds = float(snapshot_cooldown_seconds)
        self.max_snapshots = int(max_snapshots)
        self.max_snapshot_files = int(max_snapshot_files)
        self.heartbeat_interval_ms = int(heartbeat_interval_ms)
        self.watchdog_interval_seconds = float(watchdog_interval_seconds)
        self._monotonic = monotonic
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._watchdog_thread = None
        self._root = None
        self._heartbeat_after_id = None
        self._state_provider = None
        self._last_heartbeat = None
        self._heartbeat_due = None
        self._last_snapshot = None
        self._snapshot_count = 0
        self._active_operations = {}
        self._recent_started = deque(maxlen=40)
        self._recent_completed = deque(maxlen=40)
        self._logger = None
        if self.enabled:
            self._configure_logger()

    @classmethod
    def from_environment(cls):
        return cls(enabled=_environment_enabled())

    def _configure_logger(self):
        self.log_dir.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(f"smarttrade.stability.{id(self)}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = RotatingFileHandler(
            self.log_dir / "stability.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        self._logger = logger
        self.event("diagnostics_started", pid=os.getpid())

    @staticmethod
    def _safe_fields(fields):
        safe = {}
        for key, value in fields.items():
            if key.lower() in _REDACTED_KEYS:
                safe[key] = "<redacted>"
            else:
                text = repr(value)
                safe[key] = text if len(text) <= 240 else text[:237] + "..."
        return safe

    def event(self, name, **fields):
        if not self.enabled or self._logger is None:
            return
        safe = self._safe_fields(fields)
        details = " ".join(f"{key}={value}" for key, value in sorted(safe.items()))
        self._logger.info("event=%s%s", name, f" {details}" if details else "")

    @contextmanager
    def operation(self, name, **fields):
        if not self.enabled:
            yield
            return
        started = self._monotonic()
        thread_id = threading.get_ident()
        operation_id = f"{thread_id}:{name}:{started:.6f}"
        safe_fields = self._safe_fields(fields)
        entry = {"name": name, "started": started, "thread_id": thread_id, **safe_fields}
        with self._lock:
            self._active_operations[operation_id] = entry
            self._recent_started.append(dict(entry))
        self.event("operation_started", operation=name, **fields)
        try:
            yield
        except BaseException as error:
            self.event(
                "operation_failed",
                operation=name,
                duration_ms=round((self._monotonic() - started) * 1000, 3),
                error_type=type(error).__name__,
                error=str(error),
                **fields,
            )
            raise
        else:
            self.record_duration(name, started, **fields)
        finally:
            with self._lock:
                self._active_operations.pop(operation_id, None)

    def record_duration(self, name, started_at, **fields):
        if not self.enabled:
            return
        duration_ms = (self._monotonic() - started_at) * 1000
        entry = {
            "name": name,
            "duration_ms": round(duration_ms, 3),
            "completed": self._monotonic(),
            **self._safe_fields(fields),
        }
        with self._lock:
            self._recent_completed.append(entry)
        self.event("operation_completed", operation=name, duration_ms=round(duration_ms, 3), **fields)

    def record_exception(self, name, error, **fields):
        if not self.enabled:
            return
        self.event(
            "exception",
            operation=name,
            error_type=type(error).__name__,
            error=str(error),
            **fields,
        )

    def attach_gui(self, root, state_provider=None):
        if not self.enabled or self._watchdog_thread is not None:
            return
        self._root = root
        self._state_provider = state_provider
        now = self._monotonic()
        self._last_heartbeat = now
        self._heartbeat_due = now + (self.heartbeat_interval_ms / 1000)
        self._schedule_heartbeat()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="SmartTradeStabilityWatchdog",
            daemon=True,
        )
        self._watchdog_thread.start()

    def _schedule_heartbeat(self):
        if self._stop_event.is_set() or self._root is None:
            return
        self._heartbeat_after_id = self._root.after(
            self.heartbeat_interval_ms, self._heartbeat_callback
        )

    def _heartbeat_callback(self):
        if self._stop_event.is_set():
            return
        now = self._monotonic()
        due = self._heartbeat_due or now
        delay_ms = max(0.0, (now - due) * 1000)
        self.mark_heartbeat(now)
        if delay_ms >= 250:
            self.event("gui_callback_delay", delay_ms=round(delay_ms, 3))
        self._heartbeat_due = now + (self.heartbeat_interval_ms / 1000)
        self._schedule_heartbeat()

    def mark_heartbeat(self, now=None):
        if not self.enabled:
            return
        with self._lock:
            self._last_heartbeat = self._monotonic() if now is None else float(now)

    def _watchdog_loop(self):
        while not self._stop_event.wait(self.watchdog_interval_seconds):
            try:
                self.check_for_hang()
            except Exception as error:
                self.record_exception("watchdog", error)

    def check_for_hang(self, now=None):
        if not self.enabled or self._stop_event.is_set():
            return None
        now = self._monotonic() if now is None else float(now)
        with self._lock:
            heartbeat = self._last_heartbeat
            last_snapshot = self._last_snapshot
            snapshot_count = self._snapshot_count
        if heartbeat is None or now - heartbeat < self.hang_threshold_seconds:
            return None
        if snapshot_count >= self.max_snapshots:
            return None
        if last_snapshot is not None and now - last_snapshot < self.snapshot_cooldown_seconds:
            return None
        return self._capture_snapshot(now, now - heartbeat)

    def _runtime_state(self):
        if self._state_provider is None:
            return {}
        try:
            state = self._state_provider()
            return state if isinstance(state, dict) else {"state": state}
        except Exception as error:
            return {"state_provider_error": f"{type(error).__name__}: {error}"}

    def _capture_snapshot(self, now, heartbeat_age):
        with self._lock:
            if self._snapshot_count >= self.max_snapshots:
                return None
            self._snapshot_count += 1
            self._last_snapshot = now
            active = list(self._active_operations.values())
            recent_started = list(self._recent_started)
            recent_completed = list(self._recent_completed)

        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.log_dir / f"hang_snapshot_{timestamp}.txt"
        frames = sys._current_frames()
        threads = {thread.ident: thread for thread in threading.enumerate()}
        lines = [
            f"timestamp={datetime.now().astimezone().isoformat()}",
            f"heartbeat_age_seconds={heartbeat_age:.3f}",
            f"thread_count={threading.active_count()}",
            f"runtime_state={self._safe_fields(self._runtime_state())}",
            f"active_operations={active!r}",
            f"recent_started={recent_started!r}",
            f"recent_completed={recent_completed!r}",
            "",
            "THREAD STACKS",
        ]
        for thread_id, frame in frames.items():
            thread = threads.get(thread_id)
            name = thread.name if thread is not None else "unknown"
            lines.append(f"\n--- thread_id={thread_id} name={name} ---")
            lines.extend(traceback.format_stack(frame))
        path.write_text("\n".join(lines), encoding="utf-8", errors="replace")
        self._prune_snapshot_files()
        self.event(
            "gui_hang_snapshot",
            path=str(path),
            heartbeat_age_seconds=round(heartbeat_age, 3),
            thread_count=threading.active_count(),
        )
        return path

    def _prune_snapshot_files(self):
        snapshots = sorted(
            self.log_dir.glob("hang_snapshot_*.txt"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for expired in snapshots[self.max_snapshot_files:]:
            try:
                expired.unlink()
            except OSError as error:
                self.record_exception("snapshot_retention", error, path=str(expired))

    def close(self):
        if not self.enabled:
            return
        self._stop_event.set()
        root = self._root
        after_id = self._heartbeat_after_id
        self._heartbeat_after_id = None
        if root is not None and after_id is not None:
            try:
                root.after_cancel(after_id)
            except Exception:
                pass
        thread = self._watchdog_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self.event("diagnostics_stopped", snapshot_count=self._snapshot_count)
        if self._logger is not None:
            for handler in list(self._logger.handlers):
                handler.flush()
                handler.close()
                self._logger.removeHandler(handler)
        self._watchdog_thread = None


stability_diagnostics = StabilityDiagnostics.from_environment()
