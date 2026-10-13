from app_paths import (
    close_runtime_logging,
    configure_https_certificates,
    configure_runtime_logging,
    configure_windows_app_identity,
    ensure_runtime_environment,
    log_startup_exception
)


def main():

    ensure_runtime_environment()
    configure_https_certificates()
    runtime_log_handler = configure_runtime_logging()

    try:
        configure_windows_app_identity()
        from ui import SmartTradeUI

        app = SmartTradeUI()
        app.run()
    except Exception as error:
        log_startup_exception(error)
        raise
    finally:
        close_runtime_logging(runtime_log_handler)


if __name__ == "__main__":
    main()
