from psycopg_pool import PoolTimeout

from src.core.errors import (
    PROVIDER_BUSY_ERROR_CODE,
    ProviderBusyError,
    classify_provider_busy_error,
)


def test_pool_timeout_is_not_reclassified_as_provider_busy() -> None:
    assert classify_provider_busy_error(PoolTimeout("pool timeout")) is None


def test_psycopg_cause_prevents_timeout_reclassification() -> None:
    error = TimeoutError("request timed out")
    error.__cause__ = PoolTimeout("pool timeout")

    assert classify_provider_busy_error(error) is None


def test_provider_429_remains_provider_busy() -> None:
    class ProviderRateLimitError(Exception):
        status_code = 429

    error = classify_provider_busy_error(ProviderRateLimitError("rate limit"))

    assert isinstance(error, ProviderBusyError)
    assert error.status_code == 429
    assert error.code == PROVIDER_BUSY_ERROR_CODE
    assert error.retryable is True
