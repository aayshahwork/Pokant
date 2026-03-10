"""
workers/encryption.py — Per-account encryption key cache and AES-256-GCM primitives.

Uses HKDF to derive per-account data encryption keys from a master key.
Provides encrypt/decrypt using AES-256-GCM with random nonces.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Dict, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


class EncryptionKeyCache:
    """LRU cache for per-account AES-256 data encryption keys.

    Keys are derived from a master key using HKDF-SHA256 with the
    account UUID as the info parameter.  The cache evicts the oldest
    entry when full and expires entries after ``ttl_seconds``.
    """

    def __init__(
        self,
        master_key: str,
        max_size: int = 1000,
        ttl_seconds: int = 300,
    ) -> None:
        self._master_key = (
            master_key.encode("utf-8") if isinstance(master_key, str) else master_key
        )
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        # {account_id: (derived_key_bytes, monotonic_timestamp)}
        self._cache: Dict[uuid.UUID, Tuple[bytes, float]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_key(self, account_id: uuid.UUID) -> bytes:
        """Return the 32-byte AES-256 key for *account_id*.

        Checks the in-memory cache first.  On a miss (or TTL expiry)
        the key is derived via HKDF and cached.  Made async to
        future-proof for real KMS network calls.
        """
        entry = self._cache.get(account_id)
        now = time.monotonic()

        if entry is not None:
            key_bytes, ts = entry
            if now - ts < self._ttl_seconds:
                return key_bytes
            # Expired — remove and re-derive.
            del self._cache[account_id]

        key_bytes = self._derive_key(account_id)

        # Evict oldest entry if at capacity.
        if len(self._cache) >= self._max_size:
            oldest_id = next(iter(self._cache))
            del self._cache[oldest_id]

        self._cache[account_id] = (key_bytes, now)
        return key_bytes

    @staticmethod
    def encrypt(data: bytes, key: bytes) -> bytes:
        """AES-256-GCM encrypt *data* with *key*.

        Returns ``nonce (12 B) || ciphertext || tag (16 B)``.
        """
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext_with_tag = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext_with_tag

    @staticmethod
    def decrypt(data: bytes, key: bytes) -> bytes:
        """AES-256-GCM decrypt *data* with *key*.

        Expects the format produced by :meth:`encrypt`:
        ``nonce (12 B) || ciphertext || tag (16 B)``.
        Raises ``cryptography.exceptions.InvalidTag`` on tampered data.
        """
        nonce = data[:12]
        ciphertext_with_tag = data[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext_with_tag, None)

    def clear_cache(self) -> None:
        """Drop all cached keys."""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Number of entries currently in the cache."""
        return len(self._cache)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _derive_key(self, account_id: uuid.UUID) -> bytes:
        """Derive a 32-byte AES-256 key for *account_id* via HKDF-SHA256."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=account_id.bytes,
        )
        return hkdf.derive(self._master_key)
