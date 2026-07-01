from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin


class GeneratedXML(IdMixin, Base):
    __tablename__ = "generated_xmls"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    xml_type: Mapped[str] = mapped_column(String(50))
    file_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50))
    generated_at: Mapped[datetime] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    order = relationship("Order", back_populates="generated_xmls")
