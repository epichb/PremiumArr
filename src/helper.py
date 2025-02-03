def on_fail(retry_state):
    print(
        f'Retries exhausted for "{retry_state.fn.__name__}" with "{retry_state.args}"\n'
        f"  Exception: {retry_state.outcome.exception()}"
    )
