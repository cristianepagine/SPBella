"""Dados iniciais de todo salão novo (rodam dentro do `tenants create`)."""

from sqlalchemy.orm import Session

from app.core.infra.tenancy import TenantContext


def seed_new_salon(session: Session, tenant: TenantContext) -> None:
    """Serviços de exemplo no idioma e na moeda do salão.

    A tabela de serviços chega no SAL-05; até lá não há o que semear. O gancho já existe para
    que `tenants create` chame este passo na mesma transação que cria o dono.
    """
