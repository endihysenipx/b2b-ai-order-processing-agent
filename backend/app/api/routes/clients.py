from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.client import Client
from app.repositories.clients import list_clients
from app.schemas.client import ClientOut

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientOut])
def get_clients(db: Session = Depends(get_db)) -> list[Client]:
    return list_clients(db)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, db: Session = Depends(get_db)) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
