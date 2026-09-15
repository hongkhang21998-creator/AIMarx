"""Fixed limits for the 8 GB local deployment; callers cannot enlarge context."""

DEFAULT_LOCAL_MODEL = "qwen2.5:3b-instruct-q3_K_M"
MAX_LOCAL_CONTEXT = 2048


def checked_context(value: int) -> int:
    if type(value) is not int or not 1 <= value <= MAX_LOCAL_CONTEXT:
        raise ValueError("Context local phải từ 1 đến tối đa 2048 token")
    return value
