"""Quem está chamando a API, e o que pode fazer.

- Access token: JWT curto (15 min), enviado em `Authorization: Bearer`. Leva o ID do salão
  (`tid`); um token do salão A é recusado em /t/B/...
- O perfil (dono, recepção, profissional) e se a conta está ativa são lidos do BANCO a cada
  pedido, nunca confiados ao token: desativar alguém vale na hora.
- Permissões são sempre verificadas aqui, no back-end. O front só esconde botões.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.tenancy import DbSession, TenantContext, TenantDep
from app.models.tenant import User

ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - tipo do token, não é senha

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Access token recebido no login ou no refresh (`access_token`).",
)


def create_access_token(settings: Settings, tenant: TenantContext, user: User) -> tuple[str, int]:
    """Devolve (token, segundos até expirar)."""
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user.id),
        "tid": str(tenant.id),
        "role": user.role,  # só informativo para o front; o back-end lê o perfil do banco
        "typ": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + lifetime,
    }
    token = jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_access_token(settings: Settings, token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],  # fixo: impede "alg: none" e troca de algoritmo
            options={"require": ["sub", "tid", "typ", "iat", "exp"]},
        )
    except jwt.PyJWTError:
        return None
    return payload if payload.get("typ") == ACCESS_TOKEN_TYPE else None


def _authenticate(
    request: Request,
    tenant: TenantContext,
    db: DbSession,
    credentials: HTTPAuthorizationCredentials | None,
    *,
    allow_password_change_pending: bool,
) -> User:
    not_authenticated = ApiError(401, "not_authenticated", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise not_authenticated
    payload = decode_access_token(request.app.state.settings, credentials.credentials)
    if payload is None or payload["tid"] != str(tenant.id):
        raise not_authenticated
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise not_authenticated from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise not_authenticated
    if user.must_change_password and not allow_password_change_pending:
        raise ApiError(403, "password_change_required", "Troque a senha provisória")

    request.state.user_id = str(user.id)  # aparece no log de acesso
    return user


Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def get_current_user(
    request: Request, tenant: TenantDep, db: DbSession, credentials: Credentials
) -> User:
    return _authenticate(request, tenant, db, credentials, allow_password_change_pending=False)


def get_user_even_with_pending_password_change(
    request: Request, tenant: TenantDep, db: DbSession, credentials: Credentials
) -> User:
    """Só para as rotas que a pessoa precisa usar ANTES de trocar a senha provisória."""
    return _authenticate(request, tenant, db, credentials, allow_password_change_pending=True)


CurrentUser = Annotated[User, Depends(get_current_user)]
UserPendingPasswordChange = Annotated[User, Depends(get_user_even_with_pending_password_change)]


def require_roles(*roles: str):
    """Uso: `user: Annotated[User, require_roles("owner", "reception")]`."""

    def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ApiError(403, "forbidden", "Seu perfil não tem permissão")
        return user

    return Depends(dependency)


OwnerUser = Annotated[User, require_roles("owner")]
StaffUser = Annotated[User, require_roles("owner", "reception")]
