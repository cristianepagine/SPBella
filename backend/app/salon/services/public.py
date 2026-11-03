"""O que o salão acrescenta ao catálogo da página pública: o preço de cada serviço."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.salon.services.models import ServicePrice


def offering_extras(db: Session, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, dict[str, int | str]]:
    prices = db.scalars(select(ServicePrice).where(ServicePrice.offering_id.in_(ids)))
    return {p.offering_id: {"price_minor": p.price_minor} for p in prices}
