from cryptography.fernet import Fernet

from app.config import get_settings


def get_fernet() -> Fernet:
    """Get a Fernet instance using the configured encryption key."""
    settings = get_settings()
    key = settings.encryption_key
    if not key:
        raise ValueError("ENCRYPTION_KEY not set in environment")
    return Fernet(key.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value and return the ciphertext as a string."""
    f = get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string and return the plaintext."""
    f = get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def generate_key() -> str:
    """Generate a new Fernet encryption key. Use this once during initial setup."""
    return Fernet.generate_key().decode()
