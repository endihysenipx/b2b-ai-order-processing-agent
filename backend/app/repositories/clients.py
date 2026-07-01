from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client import Client


def list_clients(db: Session) -> list[Client]:
    return list(db.scalars(select(Client).order_by(Client.client_name)))
