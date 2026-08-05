from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import accessible_client_ids, get_current_user
from app.db.session import get_db
from app.models.client import Client
from app.repositories.clients import list_clients
from app.schemas.client import ClientOut

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientOut])
def get_clients(db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> list[Client]:
    clients = list_clients(db)
    allowed = accessible_client_ids(current_user)
    return clients if allowed is None else [client for client in clients if client.id in allowed]


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> Client:
    allowed = accessible_client_ids(current_user)
    if allowed is not None and client_id not in allowed:
        raise HTTPException(status_code=404, detail="Client not found")
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
