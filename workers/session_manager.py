"""
workers/session_manager.py — Database-backed encrypted session manager.

Manages browser session cookies in PostgreSQL with AES-256-GCM encryption.
Uses advisory locks for concurrent access safety and Redis for
auth-in-progress signaling.
"""

from __future__ import annotations

import asyncio
import json
import uuid
import zlib
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from workers.encryption import EncryptionKeyCache

# Maximum number of cookies to persist per session.
_MAX_COOKIES = 500

# Size limit (bytes) for the serialised cookie blob before encryption.
_MAX_PAYLOAD_BYTES = 1_048_576  # 1 MB


class SessionManager:
    """Encrypted, DB-backed browser session persistence.

    Each ``(account_id, origin_domain)`` pair maps to at most one session
    row.  Cookies are AES-256-GCM encrypted with a per-account key
    derived from the platform master key.
    """

    def __init__(
        self,
        db_session: Any,
        encryption_cache: EncryptionKeyCache,
        redis_client: Any,
    ) -> None:
        self._db = db_session
        self._encryption = encryption_cache
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def load_session(
        self, account_id: uuid.UUID, domain: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Load and decrypt cookies for *account_id* on *domain*.

        Returns the deserialized cookie list, or ``None`` if no active
        session exists.
        """
        result = await self._db.execute(
            text(
                "SELECT id, cookies_encrypted "
                "FROM sessions "
                "WHERE account_id = :account_id "
                "  AND origin_domain = :domain "
                "  AND auth_state = 'active'"
            ),
            {"account_id": account_id, "domain": domain},
        )
        row = result.first()
        if row is None:
            return None

        key = await self._encryption.get_key(account_id)
        plaintext = EncryptionKeyCache.decrypt(row.cookies_encrypted, key)
        cookies: List[Dict[str, Any]] = json.loads(plaintext)

        # Touch last_used_at so the session doesn't expire prematurely.
        await self._db.execute(
            text(
                "UPDATE sessions SET last_used_at = now() "
                "WHERE id = :session_id"
            ),
            {"session_id": row.id},
        )

        return cookies

    async def save_session(
        self,
        account_id: uuid.UUID,
        domain: str,
        cookies: List[Dict[str, Any]],
    ) -> None:
        """Encrypt and persist *cookies* for *account_id* on *domain*.

        Acquires a PostgreSQL advisory lock to prevent concurrent writes
        for the same ``(account_id, domain)`` pair.  Sets a Redis flag
        ``auth_in_progress:{account_id}:{domain}`` with a 300 s TTL.
        """
        # Truncate to _MAX_COOKIES if the list is too large.
        if len(cookies) > _MAX_COOKIES:
            cookies = cookies[-_MAX_COOKIES:]

        plaintext = json.dumps(cookies).encode("utf-8")

        # If serialised payload still exceeds 1 MB after truncation,
        # trim again (shouldn't normally happen with 500 cookies).
        if len(plaintext) > _MAX_PAYLOAD_BYTES:
            cookies = cookies[-_MAX_COOKIES:]
            plaintext = json.dumps(cookies).encode("utf-8")

        key = await self._encryption.get_key(account_id)
        encrypted = EncryptionKeyCache.encrypt(plaintext, key)

        # Advisory lock scoped to the transaction — released on commit.
        lock_id = zlib.crc32(
            (str(account_id) + domain).encode()
        ) & 0x7FFFFFFF
        await self._db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": lock_id},
        )

        await self._db.execute(
            text(
                "INSERT INTO sessions "
                "  (account_id, origin_domain, cookies_encrypted, "
                "   auth_state, last_used_at) "
                "VALUES "
                "  (:account_id, :domain, :encrypted, 'active', now()) "
                "ON CONFLICT (account_id, origin_domain) "
                "DO UPDATE SET "
                "  cookies_encrypted = :encrypted, "
                "  auth_state = 'active', "
                "  last_used_at = now()"
            ),
            {
                "account_id": account_id,
                "domain": domain,
                "encrypted": encrypted,
            },
        )

        # Signal other workers that authentication is in progress.
        redis_key = f"auth_in_progress:{account_id}:{domain}"
        self._redis.setex(redis_key, 300, "1")

        await self._db.commit()

    async def wait_for_auth(
        self,
        account_id: uuid.UUID,
        domain: str,
        timeout: int = 30,
    ) -> bool:
        """Poll Redis for an auth-in-progress flag.

        Returns ``True`` if the flag is detected within *timeout*
        seconds, ``False`` otherwise.  Useful for avoiding duplicate
        authentication flows across concurrent workers.
        """
        redis_key = f"auth_in_progress:{account_id}:{domain}"
        elapsed = 0
        while elapsed < timeout:
            if self._redis.get(redis_key):
                return True
            await asyncio.sleep(1)
            elapsed += 1
        return False
