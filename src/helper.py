import logging

logging.basicConfig(level=logging.INFO)


def get_logger(name):
    return logging.getLogger(name)


def on_fail(retry_state):
    logger = get_logger(__name__)
    logger.error(
        f'Retries exhausted for "{retry_state.fn.__name__}" with "{retry_state.args}"\n'
        f"  Exception: {retry_state.outcome.exception()}"
    )
