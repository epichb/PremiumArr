import logging
import os
from tenacity import RetryError
from datetime import datetime, UTC, timedelta

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


class UTCDateTime:
    """Always handles the datetime in UTC and applies the same formatting to all dt objects"""

    _time_fmt = "%Y-%m-%d %H:%M:%S"

    def __init__(self, datetime=datetime.now(UTC), offset=timedelta(hours=0), from_str=None):
        if from_str:
            self.datetime = datetime.strptime(from_str, self._time_fmt)
        else:
            self.datetime = datetime
        self.datetime += offset

    def __str__(self):
        return self.datetime.strftime(self._time_fmt)

    def str(self):
        return self.__str__()

    def parse_from_str(self, dt_str):
        self.datetime = datetime.strptime(dt_str, self._time_fmt)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.datetime == other.datetime

    def __lt__(self, other):
        return self.datetime < other.datetime


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

    def on_state_fail(self, retry_state):
        self.logger.error(
            f"FAILED! DEGRADE STATE, GOT EXCEPTION: {retry_state.outcome.exception()}\n"
            f"  in {retry_state.fn.__name__} with {retry_state.args}\n"
            f"  RETRIES EXHAUSTED, NOT RETRYING"
        )
        raise StateRetryError(retry_state.outcome.exception())
