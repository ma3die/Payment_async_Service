import hashlib
import secrets


def api_keys_match(provided: str, expected: str) -> bool:
    """Сравнивает API-ключи без утечки длины и значения по времени."""
    provided_digest = hashlib.sha256(provided.encode("utf-8")).digest()
    expected_digest = hashlib.sha256(expected.encode("utf-8")).digest()
    return secrets.compare_digest(provided_digest, expected_digest)
