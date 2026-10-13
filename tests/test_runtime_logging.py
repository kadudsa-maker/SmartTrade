import logging
import os
import sys
from io import StringIO

from app_paths import close_runtime_logging, configure_runtime_logging
from diagnostics.stability import StabilityDiagnostics


def _close(handler):
    if handler in logging.getLogger().handlers:
        close_runtime_logging(handler)


def test_runtime_log_rotates_and_keeps_at_most_three_archives(tmp_path):
    log_path = tmp_path / "startup.log"
    handler = configure_runtime_logging(
        log_path, max_bytes=350, backup_count=3, redirect_streams=False
    )
    try:
        logger = logging.getLogger("test.rotation")
        for index in range(100):
            logger.info("record=%s payload=%s", index, "x" * 80)
        handler.flush()
    finally:
        _close(handler)

    files = sorted(tmp_path.glob("startup.log*"))
    assert log_path in files
    assert len(files) == 4
    assert {path.name for path in files} == {
        "startup.log",
        "startup.log.1",
        "startup.log.2",
        "startup.log.3",
    }


def test_oversized_existing_log_is_preserved_without_copying_or_truncating(tmp_path):
    log_path = tmp_path / "startup.log"
    old_content = b"legacy-data\n" * 100
    log_path.write_bytes(old_content)

    handler = configure_runtime_logging(
        log_path, max_bytes=100, backup_count=3, redirect_streams=False
    )
    try:
        logging.getLogger("test.preservation").warning("new runtime")
        handler.flush()
    finally:
        _close(handler)

    preserved = list(tmp_path.glob("startup.legacy-*.log"))
    assert len(preserved) == 1
    assert preserved[0].read_bytes() == old_content
    assert "new runtime" in log_path.read_text(encoding="utf-8")


def test_locked_legacy_log_uses_a_separate_process_log(tmp_path, monkeypatch):
    log_path = tmp_path / "startup.log"
    old_content = b"active-log\n" * 100
    log_path.write_bytes(old_content)
    direct_errors = StringIO()

    def reject_rename(_self, _target):
        raise PermissionError("file is active")

    monkeypatch.setattr("app_paths.Path.rename", reject_rename)
    monkeypatch.setattr(sys, "__stderr__", direct_errors)
    handler = configure_runtime_logging(
        log_path, max_bytes=100, backup_count=3, redirect_streams=False
    )
    try:
        logging.getLogger("test.locked-log").error("separate log marker")
        handler.flush()
    finally:
        _close(handler)

    fallback_path = tmp_path / f"startup.{os.getpid()}.log"
    assert log_path.read_bytes() == old_content
    assert "separate log marker" in fallback_path.read_text(encoding="utf-8")
    assert "Could not preserve active startup log" in direct_errors.getvalue()


def test_uncaught_exception_traceback_is_preserved(tmp_path):
    log_path = tmp_path / "startup.log"
    handler = configure_runtime_logging(log_path, redirect_streams=False)
    try:
        try:
            raise RuntimeError("traceback-marker")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
        handler.flush()
    finally:
        _close(handler)

    content = log_path.read_text(encoding="utf-8")
    assert "Uncaught exception" in content
    assert "RuntimeError: traceback-marker" in content
    assert "test_uncaught_exception_traceback_is_preserved" in content


def test_redirected_stderr_is_logged_and_restored(tmp_path):
    log_path = tmp_path / "startup.log"
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    handler = configure_runtime_logging(log_path, redirect_streams=True)
    try:
        print("stderr-marker", file=sys.stderr)
    finally:
        _close(handler)

    assert sys.stdout is original_stdout
    assert sys.stderr is original_stderr
    content = log_path.read_text(encoding="utf-8")
    assert "ERROR stderr: stderr-marker" in content


def test_partial_stream_writes_are_combined_into_one_record(tmp_path):
    log_path = tmp_path / "startup.log"
    handler = configure_runtime_logging(log_path, redirect_streams=True)
    try:
        sys.stdout.write("one ")
        sys.stdout.write("line\n")
    finally:
        _close(handler)

    content = log_path.read_text(encoding="utf-8")
    assert content.count("INFO stdout: one line") == 1


def test_many_consecutive_writes_remain_bounded(tmp_path):
    log_path = tmp_path / "startup.log"
    handler = configure_runtime_logging(
        log_path, max_bytes=1024, backup_count=3, redirect_streams=False
    )
    try:
        logger = logging.getLogger("test.many-writes")
        for index in range(2000):
            logger.error("write %s %s", index, "y" * 40)
        handler.flush()
    finally:
        _close(handler)

    files = list(tmp_path.glob("startup.log*"))
    assert len(files) <= 4
    assert sum(path.stat().st_size for path in files) < 5000


def test_write_failure_is_reported_without_recursive_logging(tmp_path, monkeypatch):
    log_dir = tmp_path / "removed-before-write"
    log_dir.mkdir()
    direct_errors = StringIO()
    monkeypatch.setattr(sys, "__stderr__", direct_errors)
    handler = configure_runtime_logging(
        log_dir / "startup.log", redirect_streams=False
    )
    log_dir.rmdir()
    try:
        logging.getLogger("test.write-failure").error("cannot be written")
    finally:
        _close(handler)

    error_text = direct_errors.getvalue()
    assert error_text.count("SmartTrade logging error:") == 1
    assert "FileNotFoundError" in error_text


def test_closed_handler_releases_log_file(tmp_path):
    log_path = tmp_path / "startup.log"
    handler = configure_runtime_logging(log_path, redirect_streams=False)
    logging.getLogger("test.close").error("close marker")

    close_runtime_logging(handler)

    moved_path = tmp_path / "released.log"
    log_path.rename(moved_path)
    assert moved_path.exists()
    assert handler not in logging.getLogger().handlers


def test_runtime_logging_does_not_capture_stability_diagnostics(tmp_path):
    runtime_path = tmp_path / "startup.log"
    handler = configure_runtime_logging(runtime_path, redirect_streams=False)
    diagnostics = StabilityDiagnostics(enabled=True, log_dir=tmp_path / "stability")
    try:
        logging.getLogger("test.runtime").error("runtime marker")
        diagnostics.event("stability_marker")
    finally:
        diagnostics.close()
        _close(handler)

    assert "runtime marker" in runtime_path.read_text(encoding="utf-8")
    assert "stability_marker" not in runtime_path.read_text(encoding="utf-8")
    assert "stability_marker" in (
        tmp_path / "stability" / "stability.log"
    ).read_text(encoding="utf-8")
