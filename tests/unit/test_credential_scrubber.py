"""Tests for api/middleware/credential_scrubber.py."""

from __future__ import annotations

from api.middleware.credential_scrubber import CredentialScrubber


class TestCredentialScrubber:
    def setup_method(self):
        self.scrubber = CredentialScrubber()

    def _call(self, event_dict: dict) -> dict:
        return self.scrubber(None, "info", event_dict)

    # -- Top-level key scrubbing --

    def test_scrubs_credentials_key(self):
        result = self._call({"event": "task_started", "credentials": {"user": "a", "pass": "b"}})
        assert result["credentials"] == "[REDACTED]"
        assert result["event"] == "task_started"

    def test_scrubs_password_key(self):
        result = self._call({"event": "login", "password": "hunter2"})
        assert result["password"] == "[REDACTED]"

    def test_scrubs_api_key_key(self):
        result = self._call({"event": "call", "api_key": "sk-12345"})
        assert result["api_key"] == "[REDACTED]"

    def test_scrubs_secret_key(self):
        result = self._call({"event": "config", "secret": "s3cr3t"})
        assert result["secret"] == "[REDACTED]"

    def test_scrubs_cookies_encrypted_key(self):
        result = self._call({"event": "session", "cookies_encrypted": b"\x00\x01"})
        assert result["cookies_encrypted"] == "[REDACTED]"

    def test_scrubs_token_key(self):
        result = self._call({"event": "auth", "token": "jwt.xyz"})
        assert result["token"] == "[REDACTED]"

    def test_scrubs_authorization_key(self):
        result = self._call({"event": "req", "authorization": "Bearer xyz"})
        assert result["authorization"] == "[REDACTED]"

    # -- Case insensitivity --

    def test_case_insensitive_uppercase(self):
        result = self._call({"event": "x", "PASSWORD": "hunter2"})
        assert result["PASSWORD"] == "[REDACTED]"

    def test_case_insensitive_mixed(self):
        result = self._call({"event": "x", "Api_Key": "sk-12345"})
        assert result["Api_Key"] == "[REDACTED]"

    # -- Non-sensitive keys preserved --

    def test_preserves_non_sensitive_keys(self):
        result = self._call({"event": "task_queued", "task_id": "abc", "account_id": "123"})
        assert result["event"] == "task_queued"
        assert result["task_id"] == "abc"
        assert result["account_id"] == "123"

    def test_preserves_event_key(self):
        result = self._call({"event": "something_happened"})
        assert result["event"] == "something_happened"

    # -- Nested dicts --

    def test_scrubs_nested_dicts(self):
        result = self._call({
            "event": "webhook",
            "body": {
                "credentials": {"user": "a"},
                "safe_key": "visible",
            },
        })
        assert result["body"]["credentials"] == "[REDACTED]"
        assert result["body"]["safe_key"] == "visible"

    def test_deeply_nested_scrubbing(self):
        result = self._call({
            "event": "x",
            "outer": {"inner": {"password": "deep_secret", "data": "ok"}},
        })
        assert result["outer"]["inner"]["password"] == "[REDACTED]"
        assert result["outer"]["inner"]["data"] == "ok"

    # -- Lists --

    def test_scrubs_inside_lists(self):
        result = self._call({
            "event": "batch",
            "items": [{"password": "x", "name": "a"}, {"password": "y", "name": "b"}],
        })
        assert result["items"][0]["password"] == "[REDACTED]"
        assert result["items"][0]["name"] == "a"
        assert result["items"][1]["password"] == "[REDACTED]"

    def test_preserves_tuple_type(self):
        result = self._call({
            "event": "x",
            "data": ({"password": "x"}, {"name": "a"}),
        })
        assert isinstance(result["data"], tuple)
        assert result["data"][0]["password"] == "[REDACTED]"

    # -- structlog protocol conformance --

    def test_returns_dict(self):
        result = self._call({"event": "test"})
        assert isinstance(result, dict)

    def test_callable_accepts_three_args(self):
        """Structlog processors receive (logger, method_name, event_dict)."""
        result = self.scrubber("some_logger", "warning", {"event": "test", "api_key": "k"})
        assert result["api_key"] == "[REDACTED]"

    def test_replaces_with_redacted_string(self):
        result = self._call({"event": "x", "secret": "value"})
        assert result["secret"] == "[REDACTED]"
        assert isinstance(result["secret"], str)
