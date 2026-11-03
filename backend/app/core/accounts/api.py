"""Login, sessão e senha.

Sessão = access token (na memória do app) + refresh token (cookie httpOnly restrito a
/t/{slug}/auth, que o JavaScript não consegue ler). A cada refresh, o cookie é trocado.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.core.accounts.auth import UserPendingPasswordChange, create_access_token
from app.core.accounts.models import PasswordResetToken, RefreshToken, User
from app.core.accounts.permissions import Permission, permissions_for
from app.core.accounts.sessions import revoke_all_sessions
from app.core.infra.config import Settings
from app.core.infra.errors import ApiError, FieldError, error_response, error_responses
from app.core.infra.i18n import translate
from app.core.infra.logging import log
from app.core.infra.mailer import Email
from app.core.infra.ratelimit import client_ip
from app.core.infra.security import (
    burn_password_check,
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    password_problem,
    verify_password,
)
from app.core.infra.tenancy import DbSession, TenantContext, TenantDep

router = APIRouter(prefix="/t/{slug}/auth", tags=["Login"])

REFRESH_COOKIE = "spbella_refresh"
MINUTE = 60

RefreshCookie = Annotated[
    str | None,
    Cookie(
        alias=REFRESH_COOKIE,
        description="Enviado automaticamente pelo navegador (cookie httpOnly do login).",
    ),
]


# --- Esquemas ----------------------------------------------------------------------------


class LoginIn(BaseModel):
    email: str = Field(max_length=254, examples=["dono@studio-bella.demo"])
    password: str = Field(max_length=128, examples=["demo-spbella"])
    turnstile_token: str | None = Field(
        default=None, description="Token do widget Cloudflare Turnstile."
    )


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: Literal["owner", "reception", "professional"]
    must_change_password: bool = Field(
        description="Se `true`, a pessoa só pode usar `/me`, `/change-password` e `/logout` "
        "até trocar a senha provisória. As demais rotas respondem 403 `password_change_required`."
    )
    permissions: list[Permission] = Field(
        description="O que o perfil pode fazer. O app usa esta lista para montar o menu; "
        "o servidor confere a permissão em cada rota (ver tabela no guia da API).",
        examples=[["agenda.view_own"]],
    )

    @classmethod
    def of(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            must_change_password=user.must_change_password,
            permissions=sorted(permissions_for(user.role)),
        )


class SessionOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - tipo do token, não é senha
    expires_in: int = Field(description="Segundos até o access token expirar.", examples=[900])
    user: UserOut


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)


class ForgotPasswordIn(BaseModel):
    email: str = Field(max_length=254)
    turnstile_token: str | None = None


class ResetPasswordIn(BaseModel):
    token: str = Field(max_length=128, description="Token que veio no link do e-mail.")
    new_password: str = Field(max_length=128)
    turnstile_token: str | None = None


# --- Utilitários -------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _limit(request: Request, key: str, limit: int, window_seconds: int) -> None:
    request.app.state.rate_limiter.hit(key, limit, window_seconds)


def _ip(request: Request) -> str:
    return client_ip(request, _settings(request))


def _check_turnstile(request: Request, token: str | None) -> None:
    if not request.app.state.turnstile.verify(token, _ip(request)):
        raise ApiError(400, "turnstile_failed", "Verificação anti-robô falhou")


def _check_origin(request: Request) -> None:
    """Rotas que mexem no cookie só aceitam pedidos vindos do nosso app (defesa contra CSRF,
    somada ao SameSite=Strict do cookie)."""
    origin = request.headers.get("origin")
    if origin and origin not in _settings(request).cors_origins:
        raise ApiError(403, "forbidden_origin", "Origem não permitida")


def _cookie_path(tenant: TenantContext) -> str:
    return f"/t/{tenant.slug}/auth"


def _set_refresh_cookie(request: Request, response: Response, tenant: TenantContext, token: str):
    settings = _settings(request)
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_days * 24 * 3600,
        path=_cookie_path(tenant),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def _clear_refresh_cookie(request: Request, response: Response, tenant: TenantContext) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=_cookie_path(tenant),
        httponly=True,
        secure=_settings(request).cookie_secure,
        samesite="strict",
    )


def _start_session(
    request: Request,
    response: Response,
    db: DbSession,
    tenant: TenantContext,
    user: User,
    family_id: uuid.UUID | None = None,
) -> tuple[SessionOut, RefreshToken]:
    """Cria o refresh (no banco e no cookie) e o access token."""
    settings = _settings(request)
    raw = generate_token()
    refresh_token = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        family_id=family_id or uuid.uuid4(),
        token_hash=hash_token(raw),
        expires_at=_now() + timedelta(days=settings.refresh_token_days),
    )
    db.add(refresh_token)
    _set_refresh_cookie(request, response, tenant, raw)
    access_token, expires_in = create_access_token(settings, tenant, user)
    session = SessionOut(
        access_token=access_token,
        expires_in=expires_in,
        user=UserOut.of(user),
    )
    return session, refresh_token


def _revoke_family(db: DbSession, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def _check_new_password(password: str, user: User) -> None:
    problem = password_problem(password, user.email)
    if problem:
        raise ApiError(
            422,
            "weak_password",
            "Senha fraca",
            fields=[FieldError(field="new_password", code=problem)],
        )


def _find_user(db: DbSession, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


# --- Rotas -------------------------------------------------------------------------------


@router.post(
    "/login",
    summary="Entrar",
    description=(
        "Confere e-mail e senha. Se estiverem certos, devolve o access token e grava o cookie "
        "httpOnly de refresh (restrito a `/t/{slug}/auth`).\n\n"
        "- E-mail não diferencia maiúsculas.\n"
        "- E-mail inexistente, senha errada e conta desativada recebem a **mesma** resposta "
        "(`401 invalid_credentials`), para não revelar quem tem conta.\n"
        "- Exige `turnstile_token` (`400 turnstile_failed`).\n"
        "- Limites: 10 tentativas por conta a cada 15 min e 20 por IP por minuto (`429`, com "
        "`Retry-After`).\n"
        "- Se `user.must_change_password` vier `true`, o app deve levar à troca de senha."
    ),
    response_model=SessionOut,
    responses=error_responses(400, 401, 403, 404, 429),
)
def login(
    payload: LoginIn, request: Request, response: Response, tenant: TenantDep, db: DbSession
) -> SessionOut:
    _check_origin(request)
    email = payload.email.strip().lower()
    _limit(request, f"login:ip:{_ip(request)}", 20, MINUTE)
    _limit(request, f"login:account:{tenant.id}:{hash_token(email)}", 10, 15 * MINUTE)
    _check_turnstile(request, payload.turnstile_token)

    user = _find_user(db, email)
    if user is None:
        burn_password_check()
    if (
        user is None
        or not verify_password(user.password_hash, payload.password)
        or not user.is_active
    ):
        log.info("login_failed", tenant_id=str(tenant.id))
        raise ApiError(401, "invalid_credentials", "E-mail ou senha incorretos")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    user.last_login_at = _now()
    log.info("login_succeeded", tenant_id=str(tenant.id), user_id=str(user.id))
    return _start_session(request, response, db, tenant, user)[0]


@router.post(
    "/refresh",
    summary="Renovar a sessão",
    description=(
        "Usa o cookie de refresh para emitir um novo access token. O cookie é **trocado** a "
        "cada chamada (rotação).\n\n"
        "- Sem cookie, cookie inválido, expirado ou de conta desativada: `401 refresh_invalid` "
        "(o cookie é apagado; o app deve voltar ao login).\n"
        "- Reapresentar um cookie que já foi trocado é sinal de roubo: **todas** as sessões "
        "daquela família são encerradas. Exceção: até 30 s depois da troca, tratamos como "
        "duas abas renovando ao mesmo tempo: respondemos `401 refresh_superseded`, sem "
        "encerrar nada e sem apagar o cookie; o app deve tentar de novo uma vez.\n"
        "- O pedido precisa vir do app (`Origin` permitido) ou não ter `Origin` "
        "(`403 forbidden_origin`)."
    ),
    response_model=SessionOut,
    responses=error_responses(401, 403, 404),
)
def refresh(
    request: Request,
    response: Response,
    tenant: TenantDep,
    db: DbSession,
    refresh_cookie: RefreshCookie = None,
) -> SessionOut | JSONResponse:
    _check_origin(request)
    now = _now()

    def invalid() -> JSONResponse:
        # Devolvemos (em vez de lançar) para que revogações feitas aqui sejam gravadas.
        failure = error_response(request, 401, "refresh_invalid", "Sessão inválida")
        _clear_refresh_cookie(request, failure, tenant)
        return failure

    if not refresh_cookie:
        return invalid()
    token = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(refresh_cookie))
        .with_for_update()
    )
    if token is None:
        return invalid()

    if token.revoked_at is not None:
        grace = timedelta(seconds=_settings(request).refresh_reuse_grace_seconds)
        if token.replaced_by is not None and now - token.revoked_at <= grace:
            log.info("refresh_race", tenant_id=str(tenant.id), user_id=str(token.user_id))
            # Outra aba acabou de renovar; o navegador já tem (ou está recebendo) o cookie novo.
            return error_response(request, 401, "refresh_superseded", "Sessão já renovada")
        log.warning("refresh_reuse_detected", tenant_id=str(tenant.id), user_id=str(token.user_id))
        _revoke_family(db, token.family_id)
        return invalid()

    user = db.get(User, token.user_id)
    if token.expires_at <= now or user is None or not user.is_active:
        token.revoked_at = now
        return invalid()

    session, new_token = _start_session(request, response, db, tenant, user, token.family_id)
    token.revoked_at = now
    token.replaced_by = new_token.id
    return session


@router.post(
    "/logout",
    summary="Sair",
    description=(
        "Encerra a sessão deste aparelho (a família do refresh) e apaga o cookie. Funciona "
        "mesmo com o access token vencido. Sempre responde 204."
    ),
    status_code=204,
    responses=error_responses(403, 404),
)
def logout(
    request: Request, tenant: TenantDep, db: DbSession, refresh_cookie: RefreshCookie = None
) -> Response:
    _check_origin(request)
    if refresh_cookie:
        token = db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_cookie))
        )
        if token is not None:
            _revoke_family(db, token.family_id)
    response = Response(status_code=204)
    _clear_refresh_cookie(request, response, tenant)
    return response


@router.get(
    "/me",
    summary="Quem sou eu",
    description=(
        "Dados da pessoa logada. Funciona também enquanto a senha provisória não foi trocada. "
        "Exige `Authorization: Bearer`."
    ),
    response_model=UserOut,
    responses=error_responses(401, 404),
)
def me(user: UserPendingPasswordChange) -> UserOut:
    return UserOut.of(user)


@router.post(
    "/change-password",
    summary="Trocar a senha",
    description=(
        "Troca a senha de quem está logado (inclusive a provisória do primeiro acesso).\n\n"
        "- `400 wrong_current_password`: senha atual errada.\n"
        "- `422 weak_password`: senha nova fraca. `fields[0].code` diz o motivo: `too_short` "
        "(menos de 8), `too_long` (mais de 128), `too_simple` (menos de 4 caracteres "
        "diferentes), `contains_email` (contém o e-mail) ou `same_as_current`.\n"
        "- Encerra **todas** as outras sessões e devolve uma sessão nova (novo access token e "
        "novo cookie).\n"
        "- Limite: 10 tentativas a cada 15 min."
    ),
    response_model=SessionOut,
    responses=error_responses(400, 401, 403, 404, 422, 429),
)
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    response: Response,
    tenant: TenantDep,
    db: DbSession,
    user: UserPendingPasswordChange,
) -> SessionOut:
    _check_origin(request)
    _limit(request, f"change-password:{tenant.id}:{user.id}", 10, 15 * MINUTE)
    if not verify_password(user.password_hash, payload.current_password):
        raise ApiError(400, "wrong_current_password", "Senha atual incorreta")
    if payload.new_password == payload.current_password:
        raise ApiError(
            422,
            "weak_password",
            "Senha igual à atual",
            fields=[FieldError(field="new_password", code="same_as_current")],
        )
    _check_new_password(payload.new_password, user)

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    revoke_all_sessions(db, user.id)
    log.info("password_changed", tenant_id=str(tenant.id), user_id=str(user.id))
    return _start_session(request, response, db, tenant, user)[0]


@router.post(
    "/forgot-password",
    summary="Esqueci a senha",
    description=(
        "Se existir uma conta ativa com o e-mail, envia um link para criar uma senha nova, "
        "válido por 30 minutos e de uso único, no idioma do salão. **Sempre** responde 202, "
        "exista a conta ou não.\n\n"
        "O link tem o formato `<app>/{slug}/reset-password#token=<token>`. O token vai depois "
        "do `#` para não ir parar em logs de servidor nem no cabeçalho Referer.\n\n"
        "Exige `turnstile_token`. Limites: 5 pedidos por IP e 3 por e-mail a cada 15 min."
    ),
    status_code=202,
    responses=error_responses(400, 404, 429),
)
def forgot_password(
    payload: ForgotPasswordIn, request: Request, tenant: TenantDep, db: DbSession
) -> Response:
    email = payload.email.strip().lower()
    _limit(request, f"forgot:ip:{_ip(request)}", 5, 15 * MINUTE)
    _limit(request, f"forgot:account:{tenant.id}:{hash_token(email)}", 3, 15 * MINUTE)
    _check_turnstile(request, payload.turnstile_token)

    user = _find_user(db, email)
    if user is not None and user.is_active:
        settings = _settings(request)
        raw = generate_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=_now() + timedelta(minutes=settings.password_reset_minutes),
            )
        )
        link = f"{settings.app_public_url}/{tenant.slug}/reset-password#token={raw}"
        values = {
            "name": user.name,
            "salon": tenant.name,
            "minutes": settings.password_reset_minutes,
            "link": link,
        }
        request.app.state.mailer.send(
            Email(
                to=user.email,
                subject=translate(tenant.locale, "email.password_reset.subject", **values),
                body=translate(tenant.locale, "email.password_reset.body", **values),
            )
        )
        log.info("password_reset_requested", tenant_id=str(tenant.id), user_id=str(user.id))
    return Response(status_code=202)


@router.post(
    "/reset-password",
    summary="Criar senha nova pelo link do e-mail",
    description=(
        'Usa o token do link de "esqueci a senha" para definir uma senha nova.\n\n'
        "- `400 invalid_reset_token`: token inexistente, vencido, já usado ou de outro salão.\n"
        "- `422 weak_password`: mesmas regras de `/change-password`.\n"
        "- Encerra **todas** as sessões da pessoa, que entra de novo com a senha nova.\n\n"
        "Exige `turnstile_token`. Limite: 10 tentativas por IP a cada 15 min."
    ),
    status_code=204,
    responses=error_responses(400, 404, 422, 429),
)
def reset_password(
    payload: ResetPasswordIn, request: Request, tenant: TenantDep, db: DbSession
) -> Response:
    _limit(request, f"reset:ip:{_ip(request)}", 10, 15 * MINUTE)
    _check_turnstile(request, payload.turnstile_token)
    now = _now()

    reset = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_token(payload.token))
        .with_for_update()
    )
    user = db.get(User, reset.user_id) if reset else None
    if reset is None or reset.used_at or reset.expires_at <= now or not user or not user.is_active:
        raise ApiError(400, "invalid_reset_token", "Link inválido ou vencido")
    _check_new_password(payload.new_password, user)

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    revoke_all_sessions(db, user.id)
    log.info("password_reset_completed", tenant_id=str(tenant.id), user_id=str(user.id))
    return Response(status_code=204)
