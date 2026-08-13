class InvalidQueryError(ValueError):
    """Raised when the client sends input that cannot be processed (4xx)."""


BUSY_MESSAGE = "The demo is busy right now. Please try again in a moment."
GENERIC_ERROR_MESSAGE = "I couldn't complete that request right now. Please try again later."


class ProviderBusyError(RuntimeError):
    """Raised when the upstream model provider is rate-limited or unavailable."""

    def __init__(self, *, status_code: int = 503) -> None:
        self.status_code = status_code
        super().__init__(BUSY_MESSAGE)


def classify_provider_busy_error(exc: Exception) -> ProviderBusyError | None:
    """Return a public-safe busy error for known provider pressure failures."""

    chain = _walk_exception_chain(exc)
    if any(_is_psycopg_error(current) for current in chain):
        return None

    for current in chain:
        status_code = getattr(current, "status_code", None)
        if status_code is None:
            response = getattr(current, "response", None)
            status_code = getattr(response, "status_code", None)
        if status_code == 429:
            return ProviderBusyError(status_code=429)
        if status_code in {408, 503, 504}:
            return ProviderBusyError(status_code=503)

        haystack = f"{type(current).__name__} {current}".lower()
        if any(token in haystack for token in ("rate limit", "ratelimit", "too many requests", "quota", "429")):
            return ProviderBusyError(status_code=429)
        if any(token in haystack for token in ("timeout", "timed out", "time-out")):
            return ProviderBusyError(status_code=503)

    return None


def _is_psycopg_error(exc: BaseException) -> bool:
    """Return whether an exception originated in psycopg or its connection pool."""

    return type(exc).__module__.startswith(("psycopg", "psycopg_pool"))


def _walk_exception_chain(exc: Exception) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain
