import functools
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def handle_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SystemExit:
            raise
        except Exception as e:
            logging.error(f"{func.__name__} ▶ {e}")
            print(f"[!] {func.__name__} failed: {e}")
            sys.exit(1)

    return wrapper
