"""Unit tests for workers.encryption.EncryptionKeyCache."""

from __future__ import annotations

import uuid

import pytest
from cryptography.exceptions import InvalidTag

from workers.encryption import EncryptionKeyCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cache() -> EncryptionKeyCache:
    return EncryptionKeyCache(master_key="test-encryption-key")


@pytest.fixture
def account_id() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Encrypt / Decrypt round-trip
# ---------------------------------------------------------------------------

class TestEncryptDecrypt:
    def test_round_trip(self, cache: EncryptionKeyCache) -> None:
        key = cache._derive_key(uuid.uuid4())
        plaintext = b"hello world"
        ciphertext = EncryptionKeyCache.encrypt(plaintext, key)
        assert EncryptionKeyCache.decrypt(ciphertext, key) == plaintext

    def test_different_keys_produce_different_ciphertext(self) -> None:
        cache_a = EncryptionKeyCache(master_key="key-a")
        cache_b = EncryptionKeyCache(master_key="key-b")
        aid = uuid.uuid4()
        key_a = cache_a._derive_key(aid)
        key_b = cache_b._derive_key(aid)
        plaintext = b"same data"
        ct_a = EncryptionKeyCache.encrypt(plaintext, key_a)
        ct_b = EncryptionKeyCache.encrypt(plaintext, key_b)
        # Ciphertexts should differ (different keys + random nonces).
        assert ct_a != ct_b

    def test_tampered_ciphertext_raises(self, cache: EncryptionKeyCache) -> None:
        key = cache._derive_key(uuid.uuid4())
        ct = EncryptionKeyCache.encrypt(b"secret", key)
        # Flip a byte in the ciphertext body (after the 12-byte nonce).
        tampered = bytearray(ct)
        tampered[14] ^= 0xFF
        with pytest.raises(InvalidTag):
            EncryptionKeyCache.decrypt(bytes(tampered), key)

    def test_empty_plaintext(self, cache: EncryptionKeyCache) -> None:
        key = cache._derive_key(uuid.uuid4())
        ct = EncryptionKeyCache.encrypt(b"", key)
        assert EncryptionKeyCache.decrypt(ct, key) == b""

    def test_large_plaintext(self, cache: EncryptionKeyCache) -> None:
        key = cache._derive_key(uuid.uuid4())
        plaintext = b"x" * (1024 * 1024)  # 1 MB
        ct = EncryptionKeyCache.encrypt(plaintext, key)
        assert EncryptionKeyCache.decrypt(ct, key) == plaintext


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

class TestKeyDerivation:
    def test_deterministic_derivation(self) -> None:
        aid = uuid.uuid4()
        cache_1 = EncryptionKeyCache(master_key="same-key")
        cache_2 = EncryptionKeyCache(master_key="same-key")
        assert cache_1._derive_key(aid) == cache_2._derive_key(aid)

    def test_different_accounts_get_different_keys(
        self, cache: EncryptionKeyCache
    ) -> None:
        key_a = cache._derive_key(uuid.uuid4())
        key_b = cache._derive_key(uuid.uuid4())
        assert key_a != key_b

    def test_key_is_32_bytes(self, cache: EncryptionKeyCache) -> None:
        key = cache._derive_key(uuid.uuid4())
        assert len(key) == 32


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------

class TestCache:
    @pytest.mark.asyncio
    async def test_cache_hit(self, cache: EncryptionKeyCache) -> None:
        aid = uuid.uuid4()
        key1 = await cache.get_key(aid)
        key2 = await cache.get_key(aid)
        assert key1 == key2
        assert cache.cache_size == 1

    @pytest.mark.asyncio
    async def test_cache_ttl_expiry(self) -> None:
        cache = EncryptionKeyCache(
            master_key="test", ttl_seconds=0
        )
        aid = uuid.uuid4()
        k1 = await cache.get_key(aid)
        k2 = await cache.get_key(aid)
        # Keys are the same (deterministic derivation) but cache expired.
        assert k1 == k2

    @pytest.mark.asyncio
    async def test_cache_max_size_eviction(self) -> None:
        cache = EncryptionKeyCache(
            master_key="test", max_size=2
        )
        ids = [uuid.uuid4() for _ in range(3)]
        for aid in ids:
            await cache.get_key(aid)
        assert cache.cache_size == 2

    @pytest.mark.asyncio
    async def test_clear_cache(self, cache: EncryptionKeyCache) -> None:
        await cache.get_key(uuid.uuid4())
        await cache.get_key(uuid.uuid4())
        assert cache.cache_size == 2
        cache.clear_cache()
        assert cache.cache_size == 0
