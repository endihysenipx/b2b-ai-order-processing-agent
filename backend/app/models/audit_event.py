from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Index, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class AuditEvent(IdMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_client_time", "client_id", "created_at", "id"),
        Index("ix_audit_entity_time", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_order_time", "order_id", "created_at"),
    )

    # Snapshot identifiers deliberately have no cascading foreign keys: record and
    # account deletion must not erase the history of previously committed changes.
    client_id: Mapped[str] = mapped_column(String, nullable=False)
    client_name: Mapped[str] = mapped_column(String(200))
    actor_id: Mapped[str] = mapped_column(String)
    actor_name: Mapped[str] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String)
    entity_label: Mapped[str] = mapped_column(String(200))
    order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String(50))
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    changes: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def prevent_audit_mutation(*_):
    raise ValueError("Change history entries cannot be edited or deleted.")
