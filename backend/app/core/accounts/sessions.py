import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.accounts.models import RefreshToken


def revoke_all_sessions(db: Session, user_id: uuid.UUID) -> None:
    """Encerra todas as sessões (refresh tokens) da pessoa, em todos os aparelhos."""
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
