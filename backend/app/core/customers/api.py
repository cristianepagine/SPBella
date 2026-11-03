"""Clientes (SAL-04): cadastro com consentimento, e auditoria de cada acesso e alteração.

A busca rápida por nome ou telefone com milhares de clientes entra na SAL-07.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.accounts.auth import require_permission
from app.core.accounts.models import User
from app.core.accounts.permissions import Permission, permission_doc
from app.core.audit.service import record
from app.core.customers.models import Consent, Customer
from app.core.customers.phones import InvalidPhoneError, display_phone, normalize_phone
from app.core.customers.search import digits, like_pattern, looks_like_phone, normalize_text
from app.core.infra.errors import ApiError, FieldError, error_responses
from app.core.infra.security import is_valid_email, normalize_email
from app.core.infra.tenancy import DbSession, TenantContext, TenantDep

router = APIRouter(prefix="/t/{slug}/customers", tags=["Clientes"])

CustomerManager = Annotated[User, require_permission(Permission.CUSTOMERS_MANAGE)]
Purpose = Literal["service", "reminders", "marketing"]
PURPOSES_DOC = (
    "`service` = usar os dados para o atendimento (obrigatório); `reminders` = receber "
    "lembretes e confirmações; `marketing` = receber novidades e promoções."
)


# --- esquemas ----------------------------------------------------------------------------


class ConsentOut(BaseModel):
    purpose: Purpose
    granted_at: datetime
    source: Literal["staff", "public_booking"] = Field(
        description="`staff` = registrado pela equipe; `public_booking` = pelo cliente na página."
    )
    policy_version: str = Field(description="Versão da política de privacidade aceita.")


class CustomerSummary(BaseModel):
    id: uuid.UUID
    name: str
    phone: str = Field(description="Formato internacional E.164.", examples=["+5511988887777"])
    phone_display: str = Field(examples=["+55 11 98888-7777"])


class CustomerOut(CustomerSummary):
    email: str | None
    locale: Literal["pt-BR", "es"] | None = Field(
        description="Idioma das mensagens; `null` = idioma padrão do estabelecimento."
    )
    created_at: datetime
    updated_at: datetime
    consents: list[ConsentOut] = Field(description=f"Consentimentos em vigor. {PURPOSES_DOC}")


class CustomerPage(BaseModel):
    items: list[CustomerSummary]
    total: int


class NewCustomer(BaseModel):
    name: str = Field(min_length=1, max_length=120, examples=["Maria Silva"])
    phone: str = Field(
        min_length=1,
        max_length=32,
        description="Como a pessoa digitar: `(11) 98888-7777`, `0981 123456` ou com `+DDI`. "
        "Sem DDI, vale o país do estabelecimento.",
        examples=["(11) 98888-7777"],
    )
    email: str | None = Field(default=None, max_length=254)
    locale: Literal["pt-BR", "es"] | None = None
    consents: list[Purpose] = Field(
        description=f"Com o que o cliente concordou. Precisa incluir `service`. {PURPOSES_DOC}",
        examples=[["service", "reminders"]],
    )


class CustomerChanges(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    email: str | None = Field(default=None, max_length=254, description="`null` apaga o e-mail.")
    locale: Literal["pt-BR", "es"] | None = Field(
        default=None, description="`null` volta ao idioma padrão."
    )


class ConsentChange(BaseModel):
    purpose: Purpose
    granted: bool = Field(description="`true` registra a concordância; `false` a retira.")


# --- utilitários -------------------------------------------------------------------------


def _field_error(field: str, code: str) -> ApiError:
    return ApiError(
        422, "validation_error", "Dados inválidos", fields=[FieldError(field=field, code=code)]
    )


def _phone(raw: str, tenant: TenantContext) -> str:
    try:
        return normalize_phone(raw, tenant.country)
    except InvalidPhoneError:
        raise _field_error("phone", "invalid_phone") from None


def _email(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    email = normalize_email(raw)
    if not is_valid_email(email):
        raise _field_error("email", "invalid_email")
    return email


def _summary(customer: Customer) -> CustomerSummary:
    return CustomerSummary(
        id=customer.id,
        name=customer.name,
        phone=customer.phone_e164,
        phone_display=display_phone(customer.phone_e164),
    )


def _out(customer: Customer) -> CustomerOut:
    return CustomerOut(
        **_summary(customer).model_dump(),
        email=customer.email,
        locale=customer.locale,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        consents=[
            ConsentOut(
                purpose=c.purpose,
                granted_at=c.granted_at,
                source=c.source,
                policy_version=c.policy_version,
            )
            for c in customer.active_consents()
        ],
    )


def _get(db: DbSession, customer_id: uuid.UUID) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise ApiError(404, "not_found", "Cliente não encontrado")
    return customer


# --- rotas -------------------------------------------------------------------------------

DOC = permission_doc(Permission.CUSTOMERS_MANAGE)


@router.get(
    "",
    summary="Listar e buscar clientes",
    description=(
        "Em ordem alfabética, com paginação (`limit` e `offset`).\n\n"
        "**Busca (`q`):**\n"
        "- Só números e sinais (ex.: `98888-77`, `(11) 9888`): busca no **telefone**, em "
        "qualquer parte do número (mínimo 3 dígitos).\n"
        "- Texto: busca no **nome**, sem diferenciar maiúsculas nem acentos (`joao` acha "
        "`João`). Com várias palavras, o nome precisa conter todas (`ana sil` acha "
        "`Ana Paula Silva`).\n"
        "- `total` é o total de resultados da busca."
    ),
    response_model=CustomerPage,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=DOC,
)
def list_customers(
    db: DbSession,
    _user: CustomerManager,
    q: Annotated[
        str | None,
        Query(max_length=100, description="Nome (ou parte) ou telefone (ou parte)."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CustomerPage:
    conditions = []
    term = (q or "").strip()
    if term and looks_like_phone(term):
        conditions.append(Customer.phone_e164.like(like_pattern(digits(term)), escape="\\"))
    elif term:
        for word in normalize_text(term).split(" "):
            conditions.append(Customer.search_name.like(like_pattern(word), escape="\\"))

    total = db.scalar(select(func.count()).select_from(Customer).where(*conditions))
    customers = db.scalars(
        select(Customer).where(*conditions).order_by(Customer.name).limit(limit).offset(offset)
    )
    return CustomerPage(items=[_summary(c) for c in customers], total=total)


@router.post(
    "",
    summary="Cadastrar cliente",
    description=(
        "Cadastra o cliente e registra os consentimentos informados, com a versão atual da "
        "política de privacidade e quem registrou. Fica no log de auditoria.\n\n"
        "- `422` com `fields[0].code`: `invalid_phone`, `invalid_email` ou "
        "`consent_required` (faltou o `service` em `consents`)."
    ),
    status_code=201,
    response_model=CustomerOut,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=DOC,
)
def create_customer(
    payload: NewCustomer, request: Request, tenant: TenantDep, db: DbSession, user: CustomerManager
) -> CustomerOut:
    if "service" not in payload.consents:
        raise _field_error("consents", "consent_required")
    customer = Customer(
        id=uuid.uuid4(),
        name=payload.name.strip(),
        search_name=normalize_text(payload.name),
        phone_e164=_phone(payload.phone, tenant),
        email=_email(payload.email),
        locale=payload.locale,
    )
    if not customer.name:
        raise _field_error("name", "string_too_short")
    db.add(customer)
    policy = request.app.state.settings.privacy_policy_version
    for purpose in sorted(set(payload.consents)):
        db.add(
            Consent(
                customer=customer,
                purpose=purpose,
                policy_version=policy,
                source="staff",
                recorded_by=user.id,
            )
        )
    filled = [f for f in ("name", "phone", "email", "locale") if getattr(payload, f)]
    record(
        db,
        request,
        action="customer.created",
        entity_type="customer",
        entity_id=customer.id,
        actor=user,
        fields=filled,
    )
    record(
        db,
        request,
        action="consent.granted",
        entity_type="customer",
        entity_id=customer.id,
        actor=user,
        fields=payload.consents,
    )
    db.flush()
    db.refresh(customer)
    return _out(customer)


@router.get(
    "/{customer_id}",
    summary="Ver ficha do cliente",
    description="Dados e consentimentos em vigor. Cada consulta fica no log de auditoria "
    "(`customer.viewed`).",
    response_model=CustomerOut,
    responses=error_responses(401, 403, 404),
    openapi_extra=DOC,
)
def get_customer(
    customer_id: uuid.UUID, request: Request, db: DbSession, user: CustomerManager
) -> CustomerOut:
    customer = _get(db, customer_id)
    record(
        db,
        request,
        action="customer.viewed",
        entity_type="customer",
        entity_id=customer.id,
        actor=user,
    )
    return _out(customer)


@router.patch(
    "/{customer_id}",
    summary="Alterar dados do cliente",
    description=(
        "Só os campos enviados mudam. O log de auditoria guarda **quais** campos mudaram "
        "(nunca os valores). Enviar um valor igual ao atual não gera registro.\n\n"
        "- `422` com `fields[0].code`: `invalid_phone` ou `invalid_email`."
    ),
    response_model=CustomerOut,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=DOC,
)
def change_customer(
    customer_id: uuid.UUID,
    payload: CustomerChanges,
    request: Request,
    tenant: TenantDep,
    db: DbSession,
    user: CustomerManager,
) -> CustomerOut:
    customer = _get(db, customer_id)
    sent = payload.model_fields_set
    new_values: dict[str, object] = {}
    if "name" in sent and payload.name is not None:
        if not payload.name.strip():
            raise _field_error("name", "string_too_short")
        new_values["name"] = payload.name.strip()
    if "phone" in sent and payload.phone is not None:
        new_values["phone_e164"] = _phone(payload.phone, tenant)
    if "email" in sent:
        new_values["email"] = _email(payload.email)
    if "locale" in sent:
        new_values["locale"] = payload.locale

    changed = [k for k, v in new_values.items() if getattr(customer, k) != v]
    for key in changed:
        setattr(customer, key, new_values[key])
    if "name" in changed:
        customer.search_name = normalize_text(customer.name)
    if changed:
        customer.updated_at = datetime.now(UTC)
        names = ["phone" if k == "phone_e164" else k for k in changed]
        record(
            db,
            request,
            action="customer.updated",
            entity_type="customer",
            entity_id=customer.id,
            actor=user,
            fields=names,
        )
    db.flush()
    return _out(customer)


@router.post(
    "/{customer_id}/consents",
    summary="Registrar ou retirar consentimento",
    description=(
        f"{PURPOSES_DOC}\n\n"
        "`granted: true` registra a concordância (com a versão atual da política); "
        "`granted: false` a retira, guardando a data. O histórico nunca é apagado. "
        "Repetir o estado atual não muda nada."
    ),
    response_model=CustomerOut,
    responses=error_responses(401, 403, 404, 422),
    openapi_extra=DOC,
)
def change_consent(
    customer_id: uuid.UUID,
    payload: ConsentChange,
    request: Request,
    db: DbSession,
    user: CustomerManager,
) -> CustomerOut:
    customer = _get(db, customer_id)
    active = next((c for c in customer.active_consents() if c.purpose == payload.purpose), None)
    if payload.granted and active is None:
        db.add(
            Consent(
                customer=customer,
                purpose=payload.purpose,
                policy_version=request.app.state.settings.privacy_policy_version,
                source="staff",
                recorded_by=user.id,
            )
        )
        action = "consent.granted"
    elif not payload.granted and active is not None:
        active.revoked_at = datetime.now(UTC)
        action = "consent.revoked"
    else:
        return _out(customer)
    record(
        db,
        request,
        action=action,
        entity_type="customer",
        entity_id=customer.id,
        actor=user,
        fields=[payload.purpose],
    )
    db.flush()
    db.refresh(customer)
    return _out(customer)
