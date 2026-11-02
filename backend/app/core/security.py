import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # argon2id com os parâmetros recomendados pela biblioteca


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def generate_temporary_password() -> str:
    """Senha provisória para o primeiro acesso (o usuário troca no primeiro login)."""
    return secrets.token_urlsafe(9)
