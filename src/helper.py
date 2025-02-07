import logging
import os
from tenacity import RetryError

logging.basicConfig(level=logging.INFO)


def get_logger(name):
    level = os.getenv("LOG_LEVEL", "INFO")
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


class StateRetryError(RetryError):
    """does the exact same thing as RetryError, but is a different class, to show that the state had an error"""

    pass


class RetryHandler:
    def __init__(self, logger):
        self.logger = logger

    def on_retry(self, retry_state):
        max_tries = "inf"
        if hasattr(retry_state.retry_object.stop, "max_attempt_number"):
            max_tries = str(retry_state.retry_object.stop.max_attempt_number)

        self.logger.warning(
            f"RETRYING! GOT EXCEPTION: {retry_state.outcome.exception()}\n"
            f"  in {retry_state.fn.__name__} with {retry_state.args}\n"
            f"  Retrying in {retry_state.next_action.sleep} seconds ..."
            f"  This was attempt {retry_state.attempt_number}/{max_tries}"
        )

    def on_fail(self, retry_state):
        self.logger.error(
            f"FAILED! GOT EXCEPTION: {retry_state.outcome.exception()}\n"
            f"  in {retry_state.fn.__name__} with {retry_state.args}\n"
            f"  RETRIES EXHAUSTED, NOT RETRYING"
        )
        raise retry_state.outcome.exception()
