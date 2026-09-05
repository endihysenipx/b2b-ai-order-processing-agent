import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import accessible_client_ids, get_current_user, require_admin
from app.db.session import get_db
from app.models.client import Client
from app.models.product import Product
from app.schemas.client import ClientOut
from app.schemas.master_data import CustomerUpdate, ProductInput, ProductOut
from app.services.audit import CUSTOMER_FIELDS, PRODUCT_FIELDS, record_change, snapshot

router = APIRouter(prefix="/clients", tags=["master data"])
logger = logging.getLogger(__name__)


def scoped_client(db, user, client_id):
    allowed = accessible_client_ids(user)
    if allowed is not None and client_id not in allowed:
        raise HTTPException(404, "Client not found")
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(404, "Client not found")
    return client


@router.put("/{client_id}/customer-data", response_model=ClientOut)
def update_customer(client_id: str, payload: CustomerUpdate, db: Session = Depends(get_db), user=Depends(require_admin)):
    client = scoped_client(db, user, client_id)
    db.refresh(client, with_for_update=True)
    before = snapshot(client, CUSTOMER_FIELDS)
    for key, value in payload.model_dump().items():
        setattr(client, key, value)
    record_change(db, user, client, "customer", client, before, snapshot(client, CUSTOMER_FIELDS), "customer_updated")
    db.commit()
    logger.info("Customer data updated actor=%s client=%s", user.id, client_id)
    return client


@router.get("/{client_id}/products", response_model=list[ProductOut])
def list_products(client_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    scoped_client(db, user, client_id)
    return list(db.scalars(select(Product).where(Product.client_id == client_id).order_by(Product.sku)))


def save_product(db, user, client_id, payload, product=None):
    client = scoped_client(db, user, client_id)
    # Serialize catalog writes per client so aliases cannot race with another admin's save.
    db.scalar(select(Client).where(Client.id == client_id).with_for_update())
    if product is not None:
        db.refresh(product)
    before = snapshot(product, PRODUCT_FIELDS) if product is not None else {}
    identifiers = set([payload.sku, *payload.aliases])
    for existing in db.scalars(select(Product).where(Product.client_id == client_id)):
        if product is not None and existing.id == product.id:
            continue
        if identifiers.intersection([existing.sku, *existing.aliases]):
            raise HTTPException(409, "SKU or alias already belongs to another product")
    if product is None:
        product = Product(client_id=client_id)
        db.add(product)
    values = payload.model_dump()
    if values["stock_updated_at"]:
        values["stock_updated_at"] = values["stock_updated_at"].replace(tzinfo=None)
    for key, value in values.items():
        setattr(product, key, value)
    record_change(db, user, client, "product", product, before, snapshot(product, PRODUCT_FIELDS),
                  "product_updated" if before else "product_created")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Product conflicts with an existing record") from exc
    db.refresh(product)
    logger.info("Product data saved actor=%s client=%s product=%s", user.id, client_id, product.id)
    return product


@router.post("/{client_id}/products", response_model=ProductOut, status_code=201)
def create_product(client_id: str, payload: ProductInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    return save_product(db, user, client_id, payload)


@router.put("/{client_id}/products/{product_id}", response_model=ProductOut)
def update_product(client_id: str, product_id: str, payload: ProductInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    scoped_client(db, user, client_id)
    product = db.get(Product, product_id)
    if product is None or product.client_id != client_id:
        raise HTTPException(404, "Product not found")
    return save_product(db, user, client_id, payload, product)
