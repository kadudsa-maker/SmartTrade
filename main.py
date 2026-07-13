from app_paths import (
    configure_https_certificates,
    configure_runtime_logging,
    ensure_runtime_environment,
    log_startup_exception
)


def main():

    ensure_runtime_environment()
    configure_https_certificates()
    configure_runtime_logging()

    try:
        from ui import SmartTradeUI

        app = SmartTradeUI()
        app.run()
    except Exception as error:
        log_startup_exception(error)
        raise


if __name__ == "__main__":
    main()
