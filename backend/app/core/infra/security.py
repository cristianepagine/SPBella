import hashlib
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # argon2id com os parâmetros recomendados pela biblioteca

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache
def _dummy_hash() -> str:
    return hash_password("senha-que-nao-existe")


def burn_password_check() -> None:
    """Gasta o mesmo tempo de uma verificação real. Usado quando o e-mail não existe, para
    que o tempo de resposta não revele quais e-mails têm conta."""
    verify_password(_dummy_hash(), "x")


def password_problem(password: str, email: str) -> str | None:
    """Código do problema da senha nova, ou None se ela serve."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return "too_short"
    if len(password) > PASSWORD_MAX_LENGTH:
        return "too_long"
    if len(set(password)) < 4:
        return "too_simple"
    local = email.split("@")[0].lower()
    if len(local) >= 4 and local in password.lower():
        return "contains_email"
    return None


def generate_temporary_password() -> str:
    """Senha provisória para o primeiro acesso (o usuário troca no primeiro login)."""
    return secrets.token_urlsafe(9)


def generate_token() -> str:
    """Segredo aleatório para refresh e link de redefinição de senha (256 bits)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Guardamos só o hash: quem lê o banco não consegue usar os tokens."""
    return hashlib.sha256(token.encode()).hexdigest()
