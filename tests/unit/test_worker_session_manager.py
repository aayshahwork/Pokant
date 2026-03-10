"""Unit tests for workers.session_manager.SessionManager."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workers.encryption import EncryptionKeyCache
from workers.session_manager import SessionManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def encryption_cache() -> EncryptionKeyCache:
    return EncryptionKeyCache(master_key="test-encryption-key")


@pytest.fixture
def mock_redis() -> MagicMock:
    r = MagicMock()
    r.setex = MagicMock()
    r.get = MagicMock(return_value=None)
    return r


@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def account_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def manager(
    mock_db: AsyncMock,
    encryption_cache: EncryptionKeyCache,
    mock_redis: MagicMock,
) -> SessionManager:
    return SessionManager(mock_db, encryption_cache, mock_redis)


def _encrypt_cookies(
    cookies: list, cache: EncryptionKeyCache, account_id: uuid.UUID
) -> bytes:
    """Helper to produce an encrypted cookie blob for test fixtures."""
    import asyncio
    key = asyncio.get_event_loop().run_until_complete(cache.get_key(account_id))
    plaintext = json.dumps(cookies).encode("utf-8")
    return EncryptionKeyCache.encrypt(plaintext, key)


# ---------------------------------------------------------------------------
# load_session
# ---------------------------------------------------------------------------

class TestLoadSession:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_row(
        self, manager: SessionManager, mock_db: AsyncMock, account_id: uuid.UUID
    ) -> None:
        result_mock = MagicMock()
        result_mock.first.return_value = None
        mock_db.execute.return_value = result_mock

        result = await manager.load_session(account_id, "example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_decrypted_cookies(
        self,
        manager: SessionManager,
        mock_db: AsyncMock,
        encryption_cache: EncryptionKeyCache,
        account_id: uuid.UUID,
    ) -> None:
        cookies = [{"name": "session", "value": "abc123"}]
        key = await encryption_cache.get_key(account_id)
        encrypted = EncryptionKeyCache.encrypt(
            json.dumps(cookies).encode("utf-8"), key
        )

        row = MagicMock()
        row.id = uuid.uuid4()
        row.cookies_encrypted = encrypted

        result_mock = MagicMock()
        result_mock.first.return_value = row
        mock_db.execute.return_value = result_mock

        result = await manager.load_session(account_id, "example.com")
        assert result == cookies

    @pytest.mark.asyncio
    async def test_updates_last_used_at(
        self,
        manager: SessionManager,
        mock_db: AsyncMock,
        encryption_cache: EncryptionKeyCache,
        account_id: uuid.UUID,
    ) -> None:
        key = await encryption_cache.get_key(account_id)
        encrypted = EncryptionKeyCache.encrypt(
            json.dumps([]).encode("utf-8"), key
        )

        row = MagicMock()
        row.id = uuid.uuid4()
        row.cookies_encrypted = encrypted

        result_mock = MagicMock()
        result_mock.first.return_value = row
        mock_db.execute.return_value = result_mock

        await manager.load_session(account_id, "example.com")

        # Should have been called twice: SELECT + UPDATE last_used_at.
        assert mock_db.execute.await_count == 2
        update_call = mock_db.execute.call_args_list[1]
        sql_text = str(update_call.args[0])
        assert "last_used_at" in sql_text


# ---------------------------------------------------------------------------
# save_session
# ---------------------------------------------------------------------------

class TestSaveSession:
    @pytest.mark.asyncio
    async def test_encrypts_and_upserts(
        self,
        manager: SessionManager,
        mock_db: AsyncMock,
        account_id: uuid.UUID,
    ) -> None:
        cookies = [{"name": "token", "value": "xyz"}]
        await manager.save_session(account_id, "example.com", cookies)

        # Calls: advisory lock, UPSERT.
        assert mock_db.execute.await_count >= 2
        # The UPSERT call should contain encrypted data.
        upsert_call = mock_db.execute.call_args_list[1]
        sql_text = str(upsert_call.args[0])
        assert "INSERT INTO sessions" in sql_text

    @pytest.mark.asyncio
    async def test_sets_redis_flag(
        self,
        manager: SessionManager,
        mock_db: AsyncMock,
        mock_redis: MagicMock,
        account_id: uuid.UUID,
    ) -> None:
        await manager.save_session(account_id, "example.com", [])

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        redis_key = call_args.args[0] if call_args.args else call_args[0][0]
        assert redis_key == f"auth_in_progress:{account_id}:example.com"
        ttl = call_args.args[1] if call_args.args else call_args[0][1]
        assert ttl == 300

    @pytest.mark.asyncio
    async def test_acquires_advisory_lock(
        self,
        manager: SessionManager,
        mock_db: AsyncMock,
        account_id: uuid.UUID,
    ) -> None:
        await manager.save_session(account_id, "example.com", [])

        lock_call = mock_db.execute.call_args_list[0]
        sql_text = str(lock_call.args[0])
        assert "pg_advisory_xact_lock" in sql_text

    @pytest.mark.asyncio
    async def test_truncates_large_cookie_list(
        self,
        manager: SessionManager,
        mock_db: AsyncMock,
        encryption_cache: EncryptionKeyCache,
        account_id: uuid.UUID,
    ) -> None:
        cookies = [{"name": f"c{i}", "value": "v"} for i in range(600)]
        await manager.save_session(account_id, "example.com", cookies)

        # Verify by decrypting what was passed to the UPSERT.
        upsert_call = mock_db.execute.call_args_list[1]
        params = upsert_call.args[1]
        encrypted = params["encrypted"]
        key = await encryption_cache.get_key(account_id)
        plaintext = EncryptionKeyCache.decrypt(encrypted, key)
        saved_cookies = json.loads(plaintext)
        assert len(saved_cookies) == 500

    @pytest.mark.asyncio
    async def test_commits_transaction(
        self,
        manager: SessionManager,
        mock_db: AsyncMock,
        account_id: uuid.UUID,
    ) -> None:
        await manager.save_session(account_id, "example.com", [])
        mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# wait_for_auth
# ---------------------------------------------------------------------------

class TestWaitForAuth:
    @pytest.mark.asyncio
    async def test_returns_true_when_flag_exists(
        self,
        manager: SessionManager,
        mock_redis: MagicMock,
        account_id: uuid.UUID,
    ) -> None:
        mock_redis.get.return_value = b"1"
        result = await manager.wait_for_auth(account_id, "example.com", timeout=2)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(
        self,
        manager: SessionManager,
        mock_redis: MagicMock,
        account_id: uuid.UUID,
    ) -> None:
        mock_redis.get.return_value = None
        with patch("workers.session_manager.asyncio.sleep", new_callable=AsyncMock):
            result = await manager.wait_for_auth(
                account_id, "example.com", timeout=2
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_polls_with_correct_key(
        self,
        manager: SessionManager,
        mock_redis: MagicMock,
        account_id: uuid.UUID,
    ) -> None:
        mock_redis.get.return_value = b"1"
        await manager.wait_for_auth(account_id, "example.com")

        expected_key = f"auth_in_progress:{account_id}:example.com"
        mock_redis.get.assert_called_with(expected_key)
