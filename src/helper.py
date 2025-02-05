import logging

logging.basicConfig(level=logging.INFO)


def get_logger(name):
    return logging.getLogger(name)


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
