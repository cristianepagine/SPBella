"""Rotas usadas SÓ nos testes para exercitar a sessão do salão por HTTP.

Usam exatamente as mesmas dependências das rotas reais (DbSession / TenantDep).
"""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select, text

from app.core.auth import CurrentUser, OwnerUser, StaffUser
from app.core.errors import ApiError
from app.core.tenancy import DbSession
from app.models.tenant import User

router = APIRouter(prefix="/t/{slug}/_probe")


class UserIn(BaseModel):
    name: str
    email: str


class NameIn(BaseModel):
    name: str


def _out(user: User) -> dict:
    return {"id": str(user.id), "name": user.name, "email": user.email}


@router.post("/users")
def create_user(payload: UserIn, db: DbSession) -> dict:
    user = User(name=payload.name, email=payload.email, password_hash="x", role="professional")
    db.add(user)
    db.flush()
    return _out(user)


@router.get("/users")
def list_users(db: DbSession) -> list[dict]:
    return [_out(u) for u in db.scalars(select(User).order_by(User.email))]


@router.get("/users/{user_id}")
def get_user(user_id: uuid.UUID, db: DbSession) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "not_found")
    return _out(user)


@router.patch("/users/{user_id}")
def rename_user(user_id: uuid.UUID, payload: NameIn, db: DbSession) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "not_found")
    user.name = payload.name
    return _out(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: uuid.UUID, db: DbSession) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "not_found")
    db.delete(user)


@router.get("/whoami")
def whoami(db: DbSession) -> dict:
    row = db.execute(text("SELECT current_user, current_setting('search_path')")).one()
    return {"user": row[0], "search_path": row[1]}


@router.post("/fail")
def create_then_fail(payload: UserIn, db: DbSession) -> dict:
    db.add(User(name=payload.name, email=payload.email, password_hash="x", role="professional"))
    db.flush()
    raise ApiError(409, "forced_failure")


@router.get("/any-user")
def any_user(user: CurrentUser) -> dict:
    return {"role": user.role}


@router.get("/owner-only")
def owner_only(user: OwnerUser) -> dict:
    return {"role": user.role}


@router.get("/staff-only")
def staff_only(user: StaffUser) -> dict:
    return {"role": user.role}
