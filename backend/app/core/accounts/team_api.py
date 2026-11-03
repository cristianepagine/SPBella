"""Equipe do estabelecimento: o dono cadastra recepção e profissionais.

Ainda não há envio de e-mail (SAL-14): a senha provisória volta na resposta, uma única vez, e o
dono a repassa à pessoa. No primeiro login, ela é obrigada a trocá-la.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc
from app.core.accounts.sessions import revoke_all_sessions
from app.core.infra.errors import ApiError, FieldError, error_responses
from app.core.infra.logging import log
from app.core.infra.security import (
    generate_temporary_password,
    hash_password,
    is_valid_email,
    normalize_email,
)
from app.core.infra.tenancy import DbSession, TenantDep

router = APIRouter(prefix="/t/{slug}/team", tags=["Equipe"])

TeamManager = Annotated[User, require_permission(Permission.TEAM_MANAGE)]
Role = Literal["owner", "reception", "professional"]
ROLE_DESCRIPTION = "`owner` (dono), `reception` (recepção) ou `professional` (profissional)."


class TeamMember(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: Role
    is_active: bool
    must_change_password: bool = Field(description="Ainda não trocou a senha provisória.")
    last_login_at: datetime | None
    created_at: datetime


class NewMember(BaseModel):
    name: str = Field(min_length=1, max_length=120, examples=["Carla Souza"])
    email: str = Field(max_length=254, examples=["carla@studio-bella.com"])
    role: Role = Field(description=ROLE_DESCRIPTION)


class MemberChanges(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = Field(default=None, description=ROLE_DESCRIPTION)
    is_active: bool | None = Field(
        default=None, description="`false` desativa a conta e encerra as sessões na hora."
    )


class MemberWithPassword(BaseModel):
    member: TeamMember
    temporary_password: str = Field(
        description="Senha provisória. Aparece SÓ nesta resposta; a pessoa troca no 1º login."
    )


def _member(user: User) -> TeamMember:
    return TeamMember.model_validate(user, from_attributes=True)


def _get(db: DbSession, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "not_found", "Pessoa não encontrada")
    return user


def _active_owners(db: DbSession) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(User.role == "owner", User.is_active)
    )


@router.get(
    "",
    summary="Listar a equipe",
    description="Todas as pessoas com acesso ao sistema, inclusive as desativadas.",
    response_model=list[TeamMember],
    responses=error_responses(401, 403, 404),
    openapi_extra=permission_doc(Permission.TEAM_MANAGE),
)
def list_team(db: DbSession, _user: TeamManager) -> list[TeamMember]:
    users = db.scalars(select(User).order_by(User.is_active.desc(), User.name))
    return [_member(u) for u in users]


@router.post(
    "",
    summary="Cadastrar pessoa na equipe",
    description=(
        "Cria o acesso com uma senha provisória, devolvida **uma única vez** em "
        "`temporary_password`. No primeiro login, a pessoa é obrigada a trocá-la.\n\n"
        "- `409 email_taken`: já existe alguém com esse e-mail neste estabelecimento.\n"
        "- `422 validation_error`: e-mail inválido (`fields[0].code = invalid_email`)."
    ),
    status_code=201,
    response_model=MemberWithPassword,
    responses=error_responses(401, 403, 404, 409, 422),
    openapi_extra=permission_doc(Permission.TEAM_MANAGE),
)
def add_member(
    payload: NewMember, tenant: TenantDep, db: DbSession, user: TeamManager
) -> MemberWithPassword:
    email = normalize_email(payload.email)
    if not is_valid_email(email):
        raise ApiError(
            422,
            "validation_error",
            "E-mail inválido",
            fields=[FieldError(field="email", code="invalid_email")],
        )
    if db.scalar(select(User.id).where(User.email == email)):
        raise ApiError(409, "email_taken", "E-mail já cadastrado")

    password = generate_temporary_password()
    member = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(password),
        role=payload.role,
        must_change_password=True,
        is_active=True,
    )
    db.add(member)
    db.flush()
    db.refresh(member)
    log.info(
        "team_member_added",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        member_id=str(member.id),
        role=member.role,
    )
    return MemberWithPassword(member=_member(member), temporary_password=password)


@router.patch(
    "/{member_id}",
    summary="Alterar pessoa da equipe",
    description=(
        "Muda nome, perfil ou ativa/desativa. Só os campos enviados mudam.\n\n"
        "- Desativar encerra todas as sessões da pessoa na hora.\n"
        "- `409 cannot_change_self`: ninguém muda o próprio perfil nem desativa a si mesmo "
        "(evita ficar trancado do lado de fora).\n"
        "- `409 last_owner`: precisa sobrar pelo menos um dono ativo.\n"
        "- `404 not_found`: a pessoa não existe neste estabelecimento."
    ),
    response_model=TeamMember,
    responses=error_responses(401, 403, 404, 409, 422),
    openapi_extra=permission_doc(Permission.TEAM_MANAGE),
)
def change_member(
    member_id: uuid.UUID,
    payload: MemberChanges,
    tenant: TenantDep,
    db: DbSession,
    user: TeamManager,
) -> TeamMember:
    member = _get(db, member_id)
    changes_access = (payload.role not in (None, member.role)) or payload.is_active is False
    if member.id == user.id and changes_access:
        raise ApiError(409, "cannot_change_self", "Você não pode mudar o próprio acesso")

    if payload.name is not None:
        member.name = payload.name.strip()
    if payload.role is not None:
        member.role = payload.role
    if payload.is_active is not None:
        member.is_active = payload.is_active
    db.flush()
    if _active_owners(db) == 0:
        raise ApiError(409, "last_owner", "Precisa haver pelo menos um dono ativo")
    if payload.is_active is False:
        revoke_all_sessions(db, member.id)

    changed_fields = sorted(payload.model_dump(exclude_none=True))  # nomes, nunca valores
    log.info(
        "team_member_changed",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        member_id=str(member.id),
        fields=changed_fields,
    )
    return _member(member)


@router.post(
    "/{member_id}/reset-password",
    summary="Gerar nova senha provisória",
    description=(
        "Para quando a pessoa esqueceu a senha e o e-mail não chega. Gera uma senha provisória "
        "nova (devolvida uma única vez), obriga a troca no próximo login e encerra todas as "
        "sessões da pessoa."
    ),
    response_model=MemberWithPassword,
    responses=error_responses(401, 403, 404),
    openapi_extra=permission_doc(Permission.TEAM_MANAGE),
)
def reset_member_password(
    member_id: uuid.UUID, tenant: TenantDep, db: DbSession, user: TeamManager
) -> MemberWithPassword:
    member = _get(db, member_id)
    password = generate_temporary_password()
    member.password_hash = hash_password(password)
    member.must_change_password = True
    revoke_all_sessions(db, member.id)
    log.info(
        "team_member_password_reset",
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        member_id=str(member.id),
    )
    return MemberWithPassword(member=_member(member), temporary_password=password)
