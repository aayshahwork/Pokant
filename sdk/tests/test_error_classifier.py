"""Tests for computeruse.error_classifier — error classification."""

from computeruse.error_classifier import (
    ClassifiedError,
    ErrorCategory,
    classify_error,
    classify_error_message,
)


# ---------------------------------------------------------------------------
# Helper: fake exception classes (avoids importing anthropic/playwright)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code=None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


def _make_anthropic_exc(message="", status_code=None, response=None):
    """Create an exception that looks like an Anthropic API error."""

    class _Exc(Exception):
        __module__ = "anthropic._exceptions"

    exc = _Exc(message)
    if status_code is not None:
        exc.status_code = status_code
    if response is not None:
        exc.response = response
    return exc


def _make_named_exc(name, module="anthropic._exceptions", message=""):
    """Create an exception with a specific __name__ and __module__."""

    class _Exc(Exception):
        pass

    _Exc.__name__ = name
    _Exc.__module__ = module
    return _Exc(message)


def _make_playwright_exc(message=""):
    class _Exc(Exception):
        __module__ = "playwright._impl._errors"

    return _Exc(message)


# ---------------------------------------------------------------------------
# classify_error — exception-object classification
# ---------------------------------------------------------------------------


class TestClassifyErrorLLM:
    def test_anthropic_529_overloaded(self):
        exc = _make_anthropic_exc("overloaded", status_code=529)
        result = classify_error(exc)
        assert result.category == ErrorCategory.TRANSIENT_LLM
        assert result.retriable is True

    def test_anthropic_502(self):
        exc = _make_anthropic_exc("bad gateway", status_code=502)
        result = classify_error(exc)
        assert result.category == ErrorCategory.TRANSIENT_LLM
        assert result.retriable is True

    def test_anthropic_503(self):
        exc = _make_anthropic_exc("service unavailable", status_code=503)
        result = classify_error(exc)
        assert result.category == ErrorCategory.TRANSIENT_LLM

    def test_anthropic_500(self):
        exc = _make_anthropic_exc("internal error", status_code=500)
        result = classify_error(exc)
        assert result.category == ErrorCategory.TRANSIENT_LLM

    def test_anthropic_429_by_status(self):
        exc = _make_anthropic_exc("rate limited", status_code=429)
        result = classify_error(exc)
        assert result.category == ErrorCategory.RATE_LIMITED
        assert result.retriable is True
        assert result.retry_after_seconds == 60  # default

    def test_rate_limit_error_by_class_name(self):
        exc = _make_named_exc("RateLimitError", message="too many requests")
        result = classify_error(exc)
        assert result.category == ErrorCategory.RATE_LIMITED

    def test_429_with_retry_after_header(self):
        resp = _FakeResponse(status_code=429, headers={"retry-after": "120"})
        exc = _make_anthropic_exc("rate limited", status_code=429, response=resp)
        result = classify_error(exc)
        assert result.category == ErrorCategory.RATE_LIMITED
        assert result.retry_after_seconds == 120

    def test_anthropic_401_permanent(self):
        exc = _make_anthropic_exc("unauthorized", status_code=401)
        result = classify_error(exc)
        assert result.category == ErrorCategory.PERMANENT_LLM
        assert result.retriable is False

    def test_anthropic_403_permanent(self):
        exc = _make_anthropic_exc("forbidden", status_code=403)
        result = classify_error(exc)
        assert result.category == ErrorCategory.PERMANENT_LLM

    def test_anthropic_400_permanent(self):
        exc = _make_anthropic_exc("bad request", status_code=400)
        result = classify_error(exc)
        assert result.category == ErrorCategory.PERMANENT_LLM

    def test_api_connection_error(self):
        exc = _make_named_exc("APIConnectionError", message="connection failed")
        result = classify_error(exc)
        assert result.category == ErrorCategory.TRANSIENT_LLM
        assert result.retriable is True

    def test_api_timeout_error(self):
        exc = _make_named_exc("APITimeoutError", message="timed out")
        result = classify_error(exc)
        assert result.category == ErrorCategory.TRANSIENT_LLM

    def test_status_code_from_response_attribute(self):
        """status_code extracted from exc.response.status_code when direct attr absent."""

        class _Exc(Exception):
            __module__ = "anthropic._exceptions"

        exc = _Exc("server error")
        exc.response = _FakeResponse(status_code=500)
        result = classify_error(exc)
        assert result.category == ErrorCategory.TRANSIENT_LLM


class TestClassifyErrorBrowser:
    def test_playwright_timeout(self):
        exc = _make_playwright_exc("Timeout 30000ms exceeded while navigating")
        result = classify_error(exc)
        assert result.category == ErrorCategory.TRANSIENT_BROWSER
        assert result.retriable is True

    def test_playwright_target_closed(self):
        exc = _make_playwright_exc("Target closed")
        result = classify_error(exc)
        assert result.category == ErrorCategory.TRANSIENT_BROWSER

    def test_playwright_permanent(self):
        exc = _make_playwright_exc("Element not found: #nonexistent")
        result = classify_error(exc)
        assert result.category == ErrorCategory.PERMANENT_BROWSER
        assert result.retriable is False

    def test_browser_class_name_with_timeout(self):
        exc = _make_named_exc(
            "BrowserError", module="some.module", message="navigation timeout"
        )
        result = classify_error(exc)
        assert result.category == ErrorCategory.TRANSIENT_BROWSER


class TestClassifyErrorNetwork:
    def test_connection_error(self):
        result = classify_error(ConnectionError("Connection refused"))
        assert result.category == ErrorCategory.TRANSIENT_NETWORK
        assert result.retriable is True

    def test_timeout_error(self):
        result = classify_error(TimeoutError("timed out"))
        assert result.category == ErrorCategory.TRANSIENT_NETWORK

    def test_os_error(self):
        result = classify_error(OSError("Network unreachable"))
        assert result.category == ErrorCategory.TRANSIENT_NETWORK


class TestClassifyErrorFallback:
    def test_unknown_exception(self):
        result = classify_error(ValueError("something unexpected"))
        assert result.category == ErrorCategory.UNKNOWN
        assert result.retriable is False


# ---------------------------------------------------------------------------
# classify_error_message — string-only classification
# ---------------------------------------------------------------------------


class TestClassifyErrorMessage:
    def test_overloaded(self):
        result = classify_error_message("Server overloaded, please try again")
        assert result.category == ErrorCategory.TRANSIENT_LLM
        assert result.retriable is True

    def test_529_in_message(self):
        result = classify_error_message("HTTP 529: overloaded")
        assert result.category == ErrorCategory.TRANSIENT_LLM

    def test_502_in_message(self):
        result = classify_error_message("502 Bad Gateway")
        assert result.category == ErrorCategory.TRANSIENT_LLM

    def test_rate_limit_message(self):
        result = classify_error_message("Rate limit exceeded")
        assert result.category == ErrorCategory.RATE_LIMITED
        assert result.retry_after_seconds == 60

    def test_429_in_message(self):
        result = classify_error_message("HTTP 429 Too Many Requests")
        assert result.category == ErrorCategory.RATE_LIMITED

    def test_invalid_api_key(self):
        result = classify_error_message("Invalid API key provided")
        assert result.category == ErrorCategory.PERMANENT_LLM
        assert result.retriable is False

    def test_401_in_message(self):
        result = classify_error_message("401 Unauthorized")
        assert result.category == ErrorCategory.PERMANENT_LLM

    def test_timeout_message(self):
        result = classify_error_message("Connection timeout after 30s")
        assert result.category == ErrorCategory.TRANSIENT_NETWORK

    def test_connection_refused(self):
        result = classify_error_message("Connection refused by remote host")
        assert result.category == ErrorCategory.TRANSIENT_NETWORK

    def test_browser_timeout_message(self):
        result = classify_error_message(
            "Playwright browser timeout waiting for selector"
        )
        assert result.category == ErrorCategory.TRANSIENT_BROWSER

    def test_browser_crash_permanent(self):
        result = classify_error_message("Browser page crash detected")
        assert result.category == ErrorCategory.PERMANENT_BROWSER

    def test_unknown_message(self):
        result = classify_error_message("Some completely unknown error")
        assert result.category == ErrorCategory.UNKNOWN
        assert result.retriable is False

    def test_empty_message(self):
        result = classify_error_message("")
        assert result.category == ErrorCategory.UNKNOWN
